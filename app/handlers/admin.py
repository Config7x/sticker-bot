"""Owner/admin panel inside the bot (SPEC 12). Buttons only.

Covers: stats, user list/search + ban, lock management (channels, bots,
trust toggle), quota settings, editable texts, broadcast with confirm.
"""
from __future__ import annotations

import json
from datetime import datetime, time

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from ..config import config
from ..db import Session, get_setting, set_setting
from ..locks import lock_config
from ..models import Pack, Sticker, User
from ..states import Admin
from ..texts import DEFAULT_TEXTS

router = Router()

TEXT_KEYS = {"welcome": "👋 متن خوشامد", "lock": "🔒 متن قفل",
             "help": "❓ متن راهنما", "quota_full": "⭐ متن اتمام سهمیه"}


def _is_admin(user_id: int) -> bool:
    return user_id in config.admin_ids


def admin_kb() -> object:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📊 آمار", callback_data="adm:stats"))
    b.row(InlineKeyboardButton(text="👥 کاربرها", callback_data="adm:users"))
    b.row(InlineKeyboardButton(text="🔒 قفل‌ها و جوین اجباری",
                               callback_data="adm:locks"))
    b.row(InlineKeyboardButton(text="⭐ سهمیه‌ها", callback_data="adm:quota"))
    b.row(InlineKeyboardButton(text="✏️ متن‌های ربات", callback_data="adm:texts"))
    b.row(InlineKeyboardButton(text="📣 پیام همگانی", callback_data="adm:bc"))
    return b.as_markup()


async def show_admin(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ این بخش فقط برای مالک و ادمین‌هاست.")
        return
    await message.answer("🛠 پنل مدیریت ربات:", reply_markup=admin_kb())


@router.callback_query(F.data == "adm:home")
async def adm_home(cb, state: FSMContext) -> None:
    await state.clear()
    await cb.answer()
    await cb.message.answer("🛠 پنل مدیریت ربات:", reply_markup=admin_kb())


# --- stats ------------------------------------------------------------------

@router.callback_query(F.data == "adm:stats")
async def adm_stats(cb) -> None:
    async with Session() as s:
        users = (await s.execute(select(func.count(User.id)))).scalar_one()
        packs = (await s.execute(select(func.count(Pack.id)))).scalar_one()
        stickers = (await s.execute(select(func.count(Sticker.id)))).scalar_one()
        today = (await s.execute(
            select(func.count(User.id)).where(
                User.created_at >= datetime.combine(datetime.utcnow().date(),
                                                    time.min))
        )).scalar_one()
    await cb.answer()
    await cb.message.answer(
        f"📊 آمار ربات\n\n👥 کل کاربرها: {users} (امروز: {today})\n"
        f"📦 کل پک‌ها: {packs}\n🎨 کل استیکرها: {stickers}")


# --- users ------------------------------------------------------------------

@router.callback_query(F.data == "adm:users")
async def adm_users(cb) -> None:
    async with Session() as s:
        users = (await s.execute(
            select(User).order_by(User.created_at.desc()).limit(10)
        )).scalars().all()
    lines = ["👥 آخرین کاربرها:\n"]
    for u in users:
        lines.append(f"• {u.id} @{u.username or '-'} — {u.first_name or ''} "
                     f"(پک: {u.packs_created}){' 🚫' if u.is_banned else ''}")
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔍 جستجوی کاربر", callback_data="adm:usearch"))
    b.row(InlineKeyboardButton(text="🔙 پنل", callback_data="adm:home"))
    await cb.answer()
    await cb.message.answer("\n".join(lines) or "کاربری نیست.",
                            reply_markup=b.as_markup())


@router.callback_query(F.data == "adm:usearch")
async def adm_usearch(cb, state: FSMContext) -> None:
    await state.set_state(Admin.search_user)
    await cb.answer()
    await cb.message.answer("آیدی عددی یا یوزرنیم کاربر رو بفرست:")


@router.message(Admin.search_user)
async def adm_usearch_text(message: Message, state: FSMContext) -> None:
    q = (message.text or "").strip().lstrip("@")
    async with Session() as s:
        if q.isdigit():
            user = await s.get(User, int(q))
        else:
            user = (await s.execute(
                select(User).where(User.username == q))).scalars().first()
    await state.clear()
    if user is None:
        await message.answer("کاربری پیدا نشد.")
        return
    b = InlineKeyboardBuilder()
    if user.is_banned:
        b.row(InlineKeyboardButton(text="✅ آن‌بن", callback_data=f"adm:unban:{user.id}"))
    else:
        b.row(InlineKeyboardButton(text="🚫 بن کردن", callback_data=f"adm:ban:{user.id}"))
    await message.answer(
        f"👤 {user.id} @{user.username or '-'}\nاسم: {user.first_name or '-'}\n"
        f"پک ساخته: {user.packs_created}\nوضعیت: {'🚫 بن' if user.is_banned else 'فعال'}",
        reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("adm:ban:"))
@router.callback_query(F.data.startswith("adm:unban:"))
async def adm_ban(cb) -> None:
    uid = int((cb.data or "").split(":")[-1])
    ban = (cb.data or "").startswith("adm:ban:")
    async with Session() as s:
        user = await s.get(User, uid)
        if user:
            user.is_banned = ban
            await s.commit()
    await cb.answer("🚫 بن شد" if ban else "✅ آن‌بن شد")


# --- locks ------------------------------------------------------------------

async def _locks_text(s) -> str:
    cfg = await lock_config(s)
    ch = "\n".join(f"  • {c}" for c in cfg["channels"]) or "  (هیچ‌کدام)"
    bt = "\n".join(f"  • @{b}" for b in cfg["bots"]) or "  (هیچ‌کدام)"
    return (f"🔒 قفل‌های فعال\n\n📣 کانال‌های جوین اجباری:\n{ch}\n\n"
            f"🤖 ربات‌های استارت اجباری:\n{bt}\n\n"
            f"حالت اعتمادی استارت: {'✅ روشن' if cfg['trust'] else '❌ خاموش'}\n"
            "نکته: برای چک عضویت کانال، ربات باید ادمین اون کانال باشه.")


def _locks_kb(cfg: dict) -> object:
    b = InlineKeyboardBuilder()
    for i, c in enumerate(cfg["channels"]):
        b.row(InlineKeyboardButton(text=f"❌ حذف کانال {c}",
                                   callback_data=f"adm:lock:delch:{i}"))
    for i, bt in enumerate(cfg["bots"]):
        b.row(InlineKeyboardButton(text=f"❌ حذف ربات @{bt}",
                                   callback_data=f"adm:lock:delbot:{i}"))
    b.row(InlineKeyboardButton(text="➕ افزودن کانال", callback_data="adm:lock:addch"))
    b.row(InlineKeyboardButton(text="➕ افزودن ربات", callback_data="adm:lock:addbot"))
    b.row(InlineKeyboardButton(
        text="🔁 حالت اعتمادی: " + ("خاموش کن" if cfg["trust"] else "روشن کن"),
        callback_data="adm:lock:trust"))
    b.row(InlineKeyboardButton(text="🔙 پنل", callback_data="adm:home"))
    return b.as_markup()


@router.callback_query(F.data == "adm:locks")
async def adm_locks(cb) -> None:
    async with Session() as s:
        cfg = await lock_config(s)
        text = await _locks_text(s)
    await cb.answer()
    await cb.message.answer(text, reply_markup=_locks_kb(cfg))


async def _edit_list(s, key: str, fn) -> None:
    raw = await get_setting(s, key, "[]")
    items = json.loads(raw) if raw else []
    fn(items)
    await set_setting(s, key, json.dumps(items))


@router.callback_query(F.data.startswith("adm:lock:delch:"))
@router.callback_query(F.data.startswith("adm:lock:delbot:"))
async def adm_lock_del(cb) -> None:
    parts = (cb.data or "").split(":")
    idx = int(parts[-1])
    key = "lock_channels" if parts[2] == "delch" else "lock_bots"
    async with Session() as s:
        def drop(items):
            if 0 <= idx < len(items):
                items.pop(idx)
        await _edit_list(s, key, drop)
        cfg = await lock_config(s)
        text = await _locks_text(s)
    await cb.answer("حذف شد")
    await cb.message.answer(text, reply_markup=_locks_kb(cfg))


@router.callback_query(F.data == "adm:lock:addch")
async def adm_lock_addch(cb, state: FSMContext) -> None:
    await state.set_state(Admin.add_channel)
    await cb.answer()
    await cb.message.answer("آیدی کانال رو بفرست (مثل @CONFIG7X یا -100...):")


@router.callback_query(F.data == "adm:lock:addbot")
async def adm_lock_addbot(cb, state: FSMContext) -> None:
    await state.set_state(Admin.add_bot)
    await cb.answer()
    await cb.message.answer("یوزرنیم ربات رو بفرست (بدون @ هم قبوله):")


@router.message(Admin.add_channel)
async def adm_add_channel_text(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    async with Session() as s:
        await _edit_list(s, "lock_channels", lambda items: items.append(value))
    await state.clear()
    await message.answer(f"✅ کانال {value} به جوین اجباری اضافه شد.")


@router.message(Admin.add_bot)
async def adm_add_bot_text(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip().lstrip("@").lower()
    async with Session() as s:
        await _edit_list(s, "lock_bots", lambda items: items.append(value))
    await state.clear()
    await message.answer(f"✅ ربات @{value} به استارت اجباری اضافه شد.")


@router.callback_query(F.data == "adm:lock:trust")
async def adm_lock_trust(cb) -> None:
    async with Session() as s:
        cur = await get_setting(s, "lock_bots_trust", "1")
        await set_setting(s, "lock_bots_trust", "0" if cur == "1" else "1")
        cfg = await lock_config(s)
        text = await _locks_text(s)
    await cb.answer("تغییر کرد")
    await cb.message.answer(text, reply_markup=_locks_kb(cfg))


# --- quota ------------------------------------------------------------------

@router.callback_query(F.data == "adm:quota")
async def adm_quota(cb) -> None:
    async with Session() as s:
        packs = await get_setting(s, "quota_packs", "1")
        stickers = await get_setting(s, "quota_stickers_per_pack", "10")
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✏️ تعداد پک رایگان", callback_data="adm:quota:packs"))
    b.row(InlineKeyboardButton(text="✏️ استیکر هر پک", callback_data="adm:quota:stickers"))
    b.row(InlineKeyboardButton(text="🔙 پنل", callback_data="adm:home"))
    await cb.answer()
    await cb.message.answer(
        f"⭐ سهمیه رایگان فعلی:\n📦 پک: {packs}\n🎨 استیکر در هر پک: {stickers}",
        reply_markup=b.as_markup())


@router.callback_query(F.data == "adm:quota:packs")
async def adm_quota_packs(cb, state: FSMContext) -> None:
    await state.set_state(Admin.set_quota_packs)
    await cb.answer()
    await cb.message.answer("عدد جدید تعداد پک رایگان رو بفرست:")


@router.callback_query(F.data == "adm:quota:stickers")
async def adm_quota_stickers(cb, state: FSMContext) -> None:
    await state.set_state(Admin.set_quota_stickers)
    await cb.answer()
    await cb.message.answer("عدد جدید سقف استیکر هر پک رو بفرست:")


@router.message(Admin.set_quota_packs)
@router.message(Admin.set_quota_stickers)
async def adm_quota_text(message: Message, state: FSMContext) -> None:
    cur = await state.get_state()
    value = (message.text or "").strip()
    if not value.isdigit():
        await message.answer("فقط عدد بفرست 🔢")
        return
    key = "quota_packs" if cur == Admin.set_quota_packs else "quota_stickers_per_pack"
    async with Session() as s:
        await set_setting(s, key, value)
    await state.clear()
    await message.answer(f"✅ سهمیه به {value} تغییر کرد.")


# --- texts ------------------------------------------------------------------

@router.callback_query(F.data == "adm:texts")
async def adm_texts(cb) -> None:
    b = InlineKeyboardBuilder()
    for key, title in TEXT_KEYS.items():
        b.row(InlineKeyboardButton(text=title, callback_data=f"adm:text:{key}"))
    b.row(InlineKeyboardButton(text="🔙 پنل", callback_data="adm:home"))
    await cb.answer()
    await cb.message.answer("کدوم متن رو ویرایش می‌کنی؟", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("adm:text:"))
async def adm_text_pick(cb, state: FSMContext) -> None:
    key = (cb.data or "").split(":")[-1]
    if key not in DEFAULT_TEXTS:
        await cb.answer("متن نامعتبر")
        return
    await state.update_data(text_key=key)
    await state.set_state(Admin.edit_text)
    async with Session() as s:
        cur = await get_setting(s, f"text_{key}", DEFAULT_TEXTS[key])
    await cb.answer()
    await cb.message.answer(f"متن فعلی:\n\n{cur}\n\nمتن جدید رو بفرست:")


@router.message(Admin.edit_text)
async def adm_text_save(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    key = data.get("text_key", "welcome")
    async with Session() as s:
        await set_setting(s, f"text_{key}", message.text or "")
    await state.clear()
    await message.answer("✅ متن ذخیره شد.")


# --- broadcast ----------------------------------------------------------------

@router.callback_query(F.data == "adm:bc")
async def adm_bc(cb, state: FSMContext) -> None:
    await state.set_state(Admin.broadcast_text)
    await cb.answer()
    await cb.message.answer("📣 متن پیام همگانی رو بفرست (اول پیش‌نمایش می‌بینی):")


@router.message(Admin.broadcast_text)
async def adm_bc_text(message: Message, state: FSMContext) -> None:
    await state.update_data(bc_text=message.text or "")
    await state.set_state(Admin.broadcast_confirm)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🚀 ارسال به همه", callback_data="adm:bc:yes"))
    b.row(InlineKeyboardButton(text="❌ لغو", callback_data="adm:bc:no"))
    await message.answer(f"پیش‌نمایش پیام:\n\n{message.text}\n\nارسال بشه؟",
                         reply_markup=b.as_markup())


@router.callback_query(F.data == "adm:bc:no")
async def adm_bc_no(cb, state: FSMContext) -> None:
    await state.clear()
    await cb.answer()
    await cb.message.answer("❌ پیام همگانی لغو شد.")


@router.callback_query(F.data == "adm:bc:yes")
async def adm_bc_yes(cb, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    text = data.get("bc_text", "")
    await state.clear()
    async with Session() as s:
        ids = (await s.execute(select(User.id))).scalars().all()
    ok = fail = 0
    for uid in ids:
        try:
            await bot.send_message(uid, text)
            ok += 1
        except Exception:
            fail += 1
    await cb.answer()
    await cb.message.answer(f"📣 ارسال تموم شد.\n✅ موفق: {ok}\n❌ ناموفق: {fail}")
