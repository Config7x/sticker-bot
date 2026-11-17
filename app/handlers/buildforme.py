"""✨ «بساز برام» — simple Phase 1 version (SPEC 4/14).

User picks or writes a topic -> the bot drafts a pack from the sentence
bank (+ a rotating style per sticker, text stickers) -> preview lists the
draft with a per-sticker "replace sentence" button -> publish creates the
pack through the Bot API and delivers the link.
"""
from __future__ import annotations

import asyncio

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from ..config import config
from ..db import Session
from ..image_pipeline import find_font, render_text_sticker
from ..keyboards import main_menu
from ..models import Pack, Sentence, Sticker, User
from ..seed_data import STYLES, TOPICS
from ..states import BuildForMe
from ..sticker_service import create_pack

router = Router()
FONT = find_font(config.fa_font_path)
DRAFT_SIZE = 5


async def start_build_for_me(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(BuildForMe.ask_topic)
    b = InlineKeyboardBuilder()
    for title, category in TOPICS:
        b.row(InlineKeyboardButton(text=title,
                                   callback_data=f"bf:topic:{category}"))
    await message.answer("✨ موضوع پکت رو انتخاب کن، یا خودت بنویس:",
                         reply_markup=b.as_markup())


async def _sentences_for(category: str | None,
                         topic_text: str = "") -> list[dict]:
    async with Session() as s:
        q = select(Sentence)
        if category:
            q = q.where(Sentence.category == category)
        rows = (await s.execute(q)).scalars().all()
        if not rows and topic_text:
            rows = (await s.execute(
                select(Sentence).where(Sentence.text.contains(topic_text))
            )).scalars().all()
        if not rows:
            rows = (await s.execute(select(Sentence))).scalars().all()
    return [{"text": r.text, "emoji": r.emoji} for r in rows]


async def _make_draft(message: Message, state: FSMContext, label: str,
                      category: str | None) -> None:
    pool = await _sentences_for(category, label)
    if not pool:
        await message.answer("بانک جمله خالیه؛ اول از پنل ادمین جمله اضافه کن.")
        return
    style_keys = [k for k, _ in STYLES]
    draft = []
    for i in range(min(DRAFT_SIZE, len(pool))):
        item = pool[i]
        draft.append({"sentence": item["text"], "emoji": item["emoji"],
                      "style": style_keys[i % len(style_keys)],
                      "pool_idx": i})
    await state.update_data(bf_topic=label, bf_category=category,
                            bf_pool=pool, bf_draft=draft)
    await state.set_state(BuildForMe.preview)
    await _show_preview(message, state)


async def _show_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    draft = data.get("bf_draft", [])
    lines = [f"✨ پیش‌نویس پک «{data.get('bf_topic', '')}»:\n"]
    for i, d in enumerate(draft):
        lines.append(f"{i + 1}. {d['sentence']}  ({d['emoji']})")
    lines.append("\nرو «🔄» هر استیکر بزنی، جمله‌ش عوض می‌شه.")
    b = InlineKeyboardBuilder()
    row = []
    for i in range(len(draft)):
        row.append(InlineKeyboardButton(text=f"🔄 {i + 1}",
                                        callback_data=f"bf:replace:{i}"))
        if len(row) == 5:
            b.row(*row)
            row = []
    if row:
        b.row(*row)
    b.row(InlineKeyboardButton(text="🚀 انتشار پک", callback_data="bf:publish"))
    b.row(InlineKeyboardButton(text="❌ لغو", callback_data="bf:cancel"))
    await message.answer("\n".join(lines), reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("bf:topic:"))
async def bf_topic(cb, state: FSMContext) -> None:
    category = (cb.data or "").split(":")[-1]
    label = next((t for t, c in TOPICS if c == category), "پک من")
    await cb.answer()
    await _make_draft(cb.message, state, label, category)


@router.message(BuildForMe.ask_topic)
async def bf_topic_text(message: Message, state: FSMContext) -> None:
    await _make_draft(message, state, (message.text or "پک من")[:40], None)


@router.callback_query(F.data.startswith("bf:replace:"))
async def bf_replace(cb, state: FSMContext) -> None:
    idx = int((cb.data or "").split(":")[-1])
    data = await state.get_data()
    draft = list(data.get("bf_draft", []))
    pool = data.get("bf_pool", [])
    if not pool or idx >= len(draft):
        await cb.answer("چیزی برای تعویض نیست")
        return
    nxt = (draft[idx].get("pool_idx", idx) + 1) % len(pool)
    draft[idx] = {**draft[idx], "sentence": pool[nxt]["text"],
                  "emoji": pool[nxt]["emoji"], "pool_idx": nxt}
    await state.update_data(bf_draft=draft)
    await cb.answer("🔄 عوض شد")
    await _show_preview(cb.message, state)


@router.callback_query(F.data == "bf:cancel")
async def bf_cancel(cb, state: FSMContext) -> None:
    await state.clear()
    await cb.answer()
    await cb.message.answer("❌ لغو شد.")


@router.callback_query(F.data == "bf:publish")
async def bf_publish(cb, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    draft = data.get("bf_draft", [])
    if not draft:
        await cb.answer("پیش‌نویسی نیست")
        return
    await cb.answer()
    await cb.message.answer("⏳ دارم پک رو می‌سازم...")
    stickers: list[tuple[bytes, str]] = []
    for d in draft:
        webp = await asyncio.to_thread(
            render_text_sticker, d["sentence"], d.get("style", "clean"),
            FONT, d.get("emoji", ""))
        stickers.append((webp, d.get("emoji", "🙂")))
    title = (data.get("bf_topic") or "پک من")[:64]
    try:
        name = await create_pack(bot, cb.from_user.id, title, stickers)
    except Exception as exc:
        await cb.message.answer(f"❌ ساخت پک در تلگرام نشد: {exc}")
        return
    async with Session() as s:
        pack = Pack(owner_id=cb.from_user.id, name=name, title=title,
                    pack_type="static")
        s.add(pack)
        await s.flush()
        for d in draft:
            s.add(Sticker(pack_id=pack.id, emoji=d.get("emoji", "🙂"),
                          text=d.get("sentence"), style=d.get("style")))
        user = await s.get(User, cb.from_user.id)
        if user:
            user.packs_created += 1
        await s.commit()
        link = pack.link
    await state.clear()
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🖼 باز کردن پک", url=link))
    await cb.message.answer(f"🎉 پکت ساخته شد!\n🔗 {link}",
                            reply_markup=b.as_markup())
