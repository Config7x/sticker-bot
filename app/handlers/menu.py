"""Main menu routing, /start, lock screen callbacks, and simple sections
(idea bank, trends placeholder, search, support) — SPEC 3."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import or_, select

from ..config import config
from ..db import Session, get_text
from ..keyboards import (
    BTN_ADMIN, BTN_BUILD, BTN_EDIT, BTN_HELP, BTN_IDEA, BTN_MY, BTN_NEW,
    BTN_POPULAR, BTN_QUOTA, BTN_SEARCH, BTN_SUPPORT, BTN_TREND,
    lock_kb, main_menu,
)
from ..locks import lock_status, mark_trusted
from ..models import Asset, Pack, Sentence
from ..seed_data import CATEGORY_TITLES
from . import admin as admin_h
from . import buildforme, mypacks, wizard

router = Router()


class Search(StatesGroup):
    waiting = State()


class Support(StatesGroup):
    waiting = State()


def _is_admin(uid: int) -> bool:
    return uid in config.admin_ids


async def _send_welcome(message: Message) -> None:
    async with Session() as s:
        text = await get_text(s, "welcome")
    await message.answer(text, reply_markup=main_menu(_is_admin(message.from_user.id)))


async def _send_lock_screen(message: Message, bot: Bot) -> bool:
    """Show the lock screen when locked. Returns True when locked."""
    async with Session() as s:
        status = await lock_status(bot, s, message.from_user.id)
        text = await get_text(s, "lock")
    if not status["locked"]:
        return False
    await message.answer(
        text, reply_markup=lock_kb(status["channels"], status["bots"],
                                   status["trust_allowed"]))
    return True


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    if not _is_admin(message.from_user.id):
        if await _send_lock_screen(message, bot):
            return
    await _send_welcome(message)


# --- lock callbacks -----------------------------------------------------------

@router.callback_query(F.data == "lock:recheck")
async def lock_recheck(cb, bot: Bot) -> None:
    async with Session() as s:
        status = await lock_status(bot, s, cb.from_user.id)
    if status["locked"]:
        await cb.answer("🔒 هنوز کامل نشده", show_alert=True)
        return
    await cb.answer("✅ باز شد!")
    if cb.message:
        await cb.message.answer("✅ همه قفل‌ها کامل شد. خوش اومدی!",
                                reply_markup=main_menu(_is_admin(cb.from_user.id)))


@router.callback_query(F.data == "lock:trust")
async def lock_trust(cb, bot: Bot) -> None:
    """Trust-mode confirm for forced-start bots (SPEC 12.2, mode 2)."""
    async with Session() as s:
        status = await lock_status(bot, s, cb.from_user.id)
        if status["bots"]:
            await mark_trusted(s, cb.from_user.id, status["bots"])
    await cb.answer("✅ ثبت شد؛ «بررسی مجدد» رو بزن")


# --- main menu buttons ----------------------------------------------------------

@router.message(F.text == BTN_NEW)
async def btn_new(message: Message, state: FSMContext) -> None:
    await wizard.start_creation(message, state)


@router.message(F.text == BTN_BUILD)
async def btn_build(message: Message, state: FSMContext) -> None:
    await buildforme.start_build_for_me(message, state)


@router.message(F.text == BTN_MY)
@router.message(F.text == BTN_EDIT)
async def btn_my(message: Message) -> None:
    await mypacks.show_my_packs(message)


@router.message(F.text == BTN_QUOTA)
async def btn_quota(message: Message) -> None:
    await mypacks.show_quota(message)


@router.message(F.text == BTN_POPULAR)
async def btn_popular(message: Message) -> None:
    await mypacks.show_popular(message)


@router.message(F.text == BTN_ADMIN)
async def btn_admin(message: Message) -> None:
    await admin_h.show_admin(message)


@router.message(F.text == BTN_HELP)
async def btn_help(message: Message) -> None:
    async with Session() as s:
        text = await get_text(s, "help")
    await message.answer(text)


# --- idea bank ------------------------------------------------------------------

@router.message(F.text == BTN_IDEA)
async def btn_idea(message: Message) -> None:
    b = InlineKeyboardBuilder()
    for key, title in CATEGORY_TITLES.items():
        b.row(InlineKeyboardButton(text=title, callback_data=f"idea:cat:{key}"))
    b.adjust(2)
    await message.answer("💡 یه دسته انتخاب کن تا جمله‌های آماده‌ش رو ببینی:",
                         reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("idea:cat:"))
async def idea_cat(cb) -> None:
    category = (cb.data or "").split(":")[-1]
    async with Session() as s:
        rows = (await s.execute(
            select(Sentence).where(Sentence.category == category).limit(10)
        )).scalars().all()
    title = CATEGORY_TITLES.get(category, category)
    lines = [f"💡 {title}:\n"] + [f"• {r.text}" for r in rows]
    lines.append("\nاین جمله‌ها موقع ساخت پک هم بهت پیشنهاد داده می‌شن 🎨")
    await cb.answer()
    await cb.message.answer("\n".join(lines))


# --- trends (Phase 2 collector feeds this; seed view for now) -------------------

@router.message(F.text == BTN_TREND)
async def btn_trend(message: Message) -> None:
    async with Session() as s:
        rows = (await s.execute(
            select(Asset).where(Asset.approved.is_(True))
            .order_by(Asset.trend_score.desc()).limit(6)
        )).scalars().all()
    lines = ["🔥 ترندهای این ماه\n"]
    if rows:
        lines += [f"• {r.title} ({r.category})" for r in rows]
    lines.append("\nجمع‌آورنده ترند فارسی و صف تأیید ادمین در فاز ۲ کامل می‌شه؛ "
                 "فعلاً این‌ها قالب‌های پایه دیتابیسن.")
    await message.answer("\n".join(lines))


# --- search ---------------------------------------------------------------------

@router.message(F.text == BTN_SEARCH)
async def btn_search(message: Message, state: FSMContext) -> None:
    await state.set_state(Search.waiting)
    await message.answer("🔍 اسم پک یا کلمه‌ای از قالب‌ها رو بنویس:")


@router.message(Search.waiting)
async def search_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    q = (message.text or "").strip()
    async with Session() as s:
        packs = (await s.execute(
            select(Pack).where(Pack.title.contains(q)).limit(8)
        )).scalars().all()
        assets = (await s.execute(
            select(Asset).where(or_(Asset.title.contains(q),
                                    Asset.tags.contains(q))).limit(8)
        )).scalars().all()
    lines = [f"🔍 نتیجه جستجو برای «{q}»:\n"]
    if packs:
        lines.append("📦 پک‌ها:")
        lines += [f"• {p.title}\n{p.link}" for p in packs]
    if assets:
        lines.append("🎨 قالب‌ها:")
        lines += [f"• {a.title}" for a in assets]
    if not packs and not assets:
        lines.append("چیزی پیدا نشد 😅")
    await message.answer("\n".join(lines))


# --- support ----------------------------------------------------------------------

@router.message(F.text == BTN_SUPPORT)
async def btn_support(message: Message, state: FSMContext) -> None:
    await state.set_state(Support.waiting)
    await message.answer("📞 پیامت رو بنویس؛ برای پشتیبانی ارسال می‌شه:")


@router.message(Support.waiting)
async def support_text(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    sent = 0
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"📞 پیام پشتیبانی از {message.from_user.id} "
                f"(@{message.from_user.username or '-'}):\n\n{message.text}")
            sent += 1
        except Exception:
            pass
    await message.answer("✅ پیامت ارسال شد." if sent else
                         "پشتیبانی فعلاً در دسترس نیست؛ بعداً تلاش کن.")
