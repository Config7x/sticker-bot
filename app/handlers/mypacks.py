"""🖼 پک‌های من + ⭐ سهمیه (SPEC 9/11)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from ..config import config
from ..db import Session, get_setting
from ..models import Pack, Sticker, User
from . import wizard

router = Router()


async def _user_packs(user_id: int) -> list[tuple[Pack, int]]:
    async with Session() as s:
        packs = (await s.execute(
            select(Pack).where(Pack.owner_id == user_id)
            .order_by(Pack.created_at.desc())
        )).scalars().all()
        out = []
        for p in packs:
            count = (await s.execute(
                select(func.count(Sticker.id)).where(Sticker.pack_id == p.id)
            )).scalar_one()
            out.append((p, count))
        return out


async def show_my_packs(message: Message) -> None:
    packs = await _user_packs(message.from_user.id)
    if not packs:
        await message.answer("هنوز پکی نساختی. از «🎨 ساخت پک جدید» شروع کن.")
        return
    b = InlineKeyboardBuilder()
    lines = ["🖼 پک‌های تو:\n"]
    for p, count in packs:
        lines.append(f"📦 {p.title} — {count} استیکر\n{p.link}")
        b.row(InlineKeyboardButton(text=f"➕ افزودن استیکر به «{p.title[:20]}»",
                                   callback_data=f"mypack:add:{p.id}"))
    await message.answer("\n".join(lines), reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("mypack:add:"))
async def add_to_pack(cb, state: FSMContext) -> None:
    pack_id = int((cb.data or "").split(":")[-1])
    await cb.answer()
    await wizard.start_add_sticker(cb.message, state, pack_id)


async def show_quota(message: Message) -> None:
    async with Session() as s:
        user = await s.get(User, message.from_user.id)
        quota_packs = await get_setting(s, "quota_packs", "1")
        quota_stickers = await get_setting(s, "quota_stickers_per_pack", "10")
    made = user.packs_created if user else 0
    if message.from_user.id in config.admin_ids:
        await message.answer("⭐ تو مالک رباتی؛ سهمیه برات نامحدوده. 👑")
        return
    await message.answer(
        f"⭐ اشتراک و سهمیه تو\n\n"
        f"📦 پک ساخته‌شده: {made} از {quota_packs} (رایگان)\n"
        f"🎨 سقف استیکر هر پک: {quota_stickers}\n\n"
        "اشتراک پولی به‌زودی فعال می‌شه. 🚀")


async def show_popular(message: Message) -> None:
    async with Session() as s:
        packs = (await s.execute(
            select(Pack).where(Pack.is_public.is_(True))
            .order_by(Pack.created_at.desc()).limit(10)
        )).scalars().all()
    if not packs:
        await message.answer("هنوز پک عمومی‌ای نیست؛ اولین نفر باش! 🎨")
        return
    lines = ["🏆 پک‌های تازه و محبوب:\n"]
    for p in packs:
        lines.append(f"📦 {p.title}\n{p.link}")
    await message.answer("\n".join(lines))
