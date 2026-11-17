"""Step-by-step pack wizard (SPEC 4) — static packs in Phase 1.

Every step offers bot suggestions as a multi-option batch with a seen
history (prev/next, position label, seen list, bookmark, hard reject),
plus "✍️ خودم وارد می‌کنم" (manual input) and "⏭ رد کن" (skip).
Steps: topic -> sentence -> image -> style -> emoji -> preview -> loop,
then pack name -> createNewStickerSet -> link.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import aiohttp
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from ..config import config
from ..db import Session, get_setting
from ..image_pipeline import (
    find_font,
    process_image,
    render_style_sheet,
    render_text_sticker,
)
from ..keyboards import preview_kb, seen_list_kb, suggestion_kb
from ..models import Asset, Pack, Sentence, Sticker, User
from ..seed_data import EMOJI_SETS, STYLES, TOPICS
from ..sources import live_search
from ..states import Wizard
from ..sticker_service import add_sticker, create_pack
from ..suggestions import SuggestionSession, make_pool

router = Router()
FONT = find_font(config.fa_font_path)
TMP = Path(os.getenv("SB_TMP", "/tmp/stickerbot"))
TMP.mkdir(parents=True, exist_ok=True)

_STYLE_SHEET: bytes | None = None  # contact sheet is rendered once per process


async def _style_sheet_bytes() -> bytes:
    global _STYLE_SHEET
    if _STYLE_SHEET is None:
        _STYLE_SHEET = await asyncio.to_thread(
            render_style_sheet, "سلام", FONT, STYLES)
    return _STYLE_SHEET

STEP_TITLES = {
    "topic": "۱️⃣ موضوع پک",
    "sentence": "۲️⃣ جمله استیکر",
    "image": "۳️⃣ تصویر استیکر",
    "style": "۴️⃣ سبک و ظاهر",
    "emoji": "۵️⃣ ایموجی استیکر",
    "name": "۶️⃣ اسم پک",
}
BATCH_SIZES = {"topic": 4, "sentence": 5, "image": 6, "style": 6,
               "emoji": 8, "name": 4}


# --------------------------------------------------------------------------
# entry points
# --------------------------------------------------------------------------

async def start_creation(message: Message, state: FSMContext) -> None:
    """Menu entry: quota gate, then pack-type pick (static only, Phase 1)."""
    async with Session() as s:
        user = await s.get(User, message.from_user.id)
        quota = int(await get_setting(s, "quota_packs", "1"))
    if (message.from_user.id not in config.admin_ids and user
            and user.packs_created >= quota):
        from ..texts import DEFAULT_TEXTS
        await message.answer(DEFAULT_TEXTS["quota_full"])
        return
    await state.clear()
    await state.update_data(mode="new", pack_id=None, ready=[],
                            stickers_done=0, topic=None, current={})
    await state.set_state(Wizard.choose_type)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🖼 معمولی (عکس ثابت)",
                               callback_data="wiz:type:static"))
    b.row(InlineKeyboardButton(text="🎬 ویدیویی — به‌زودی 🔜",
                               callback_data="wiz:type:soon"))
    b.row(InlineKeyboardButton(text="✨ متحرک — به‌زودی 🔜",
                               callback_data="wiz:type:soon"))
    await message.answer("چه نوع پکی می‌سازی؟", reply_markup=b.as_markup())


async def start_add_sticker(message: Message, state: FSMContext,
                            pack_id: int) -> None:
    """Add one sticker to an existing pack (same engine, mode='add')."""
    await state.clear()
    await state.update_data(mode="add", pack_id=pack_id, ready=[],
                            stickers_done=0, topic=None, current={})
    await _goto_step(message, state, "sentence")


@router.callback_query(F.data == "wiz:type:soon")
async def type_soon(cb: CallbackQuery) -> None:
    await cb.answer("این نوع در فاز بعد فعال می‌شه 🚀", show_alert=True)


@router.callback_query(F.data == "wiz:type:static")
async def type_static(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await _goto_step(cb.message, state, "topic")


@router.callback_query(F.data == "wiz:img:own")
async def image_own_photo(cb: CallbackQuery, state: FSMContext) -> None:
    """Image step, no ready images: user sends their own photo."""
    await state.update_data(manual_for="image", edit_mode=False)
    await state.set_state(Wizard.manual_input)
    await cb.message.answer("📷 عکست رو بفرست (به‌صورت عکس):")
    await cb.answer()


@router.callback_query(F.data == "wiz:img:text")
async def image_text_only(cb: CallbackQuery, state: FSMContext,
                          bot: Bot) -> None:
    """Image step, no ready images: build a text-only sticker instead."""
    await cb.answer()
    await _apply_skip(cb.message, state, "image", bot)


# --------------------------------------------------------------------------
# step setup: build the suggestion pool, then show the viewer
# --------------------------------------------------------------------------

async def _pool_for(step: str, data: dict) -> list[dict]:
    if step == "topic":
        return [{"id": f"topic:{i}", "label": t, "category": c}
                for i, (t, c) in enumerate(TOPICS)]
    if step == "sentence":
        category = (data.get("topic") or {}).get("category")
        async with Session() as s:
            q = select(Sentence)
            if category:
                q = q.where(Sentence.category == category)
            rows = (await s.execute(q)).scalars().all()
        return [{"id": f"sen:{r.id}", "label": r.text, "emoji": r.emoji}
                for r in rows]
    if step == "image":
        items: list[dict] = []
        async with Session() as s:
            rows = (await s.execute(
                select(Asset).where(Asset.approved.is_(True))
            )).scalars().all()
        for r in rows:
            # Assets without a real file (seed placeholders) are skipped
            # silently: never offered, never mentioned to the user.
            if r.file_id or r.file_url:
                items.append({"id": f"asset:{r.id}", "label": r.title,
                              "file_id": r.file_id, "file_url": r.file_url})
        query = (data.get("current") or {}).get("sentence") or \
            (data.get("topic") or {}).get("label") or "sticker"
        items += [it for it in await live_search(str(query), limit=6)
                  if it.get("file_url")]
        return items
    if step == "style":
        return [{"id": f"style:{k}", "label": t, "key": k} for k, t in STYLES]
    if step == "emoji":
        cur = data.get("current") or {}
        first = cur.get("sentence_emoji")
        pool = [{"id": f"emoji:{i}", "label": e, "emoji": e}
                for i, e in enumerate(EMOJI_SETS)]
        if first:
            pool.insert(0, {"id": "emoji:suggested", "label": first,
                            "emoji": first})
        return pool
    if step == "name":
        topic = (data.get("topic") or {}).get("label") or "پک من"
        names = [topic, f"{topic} 🎨", f"استیکرهای من ✨", f"{topic} | اختصاصی ⭐"]
        return [{"id": f"name:{i}", "label": n} for i, n in enumerate(names)]
    return []


async def _goto_step(message: Message, state: FSMContext, step: str) -> None:
    data = await state.get_data()
    if step == "topic" and data.get("mode") == "add":
        step = "sentence"
    pool = make_pool(await _pool_for(step, data))
    session = SuggestionSession(pool=pool,
                                batch_size=BATCH_SIZES.get(step, 5))
    session.next_batch()
    await state.update_data(step=step, session=session.to_dict())
    state_map = {"topic": Wizard.step_topic, "sentence": Wizard.step_sentence,
                 "image": Wizard.step_image, "style": Wizard.step_style,
                 "emoji": Wizard.step_emoji, "name": Wizard.step_name}
    await state.set_state(state_map[step])
    if step == "style":
        # Styles must be SEEN, not just named: one contact sheet with the
        # sample word rendered in every style (SPEC 4).
        try:
            sheet = await _style_sheet_bytes()
            await message.answer_photo(
                BufferedInputFile(sheet, filename="styles.png"),
                caption="🎨 نمونه همه سبک‌ها با کلمه «سلام» 👆\n"
                        "حالا از پیشنهادهای زیر، سبکت رو انتخاب کن:")
        except Exception:
            pass  # the step itself must go on even if the sheet fails
    await _show_current(message, state)


def _image_empty_kb() -> InlineKeyboardMarkup:
    """Image step when no ready image is available: the two clear paths
    (own photo / text-only sticker) — never an error or a dead end."""
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📷 عکس خودم رو می‌فرستم",
                               callback_data="wiz:img:own"))
    b.row(InlineKeyboardButton(text="🔤 استیکر متنی بساز",
                               callback_data="wiz:img:text"))
    b.row(InlineKeyboardButton(text="🏁 تمام و ساخت پک",
                               callback_data="wiz:finish"))
    b.row(InlineKeyboardButton(text="❌ لغو ساخت", callback_data="wiz:cancel"))
    return b.as_markup()


async def _show_current(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    step = data.get("step", "")
    session = SuggestionSession.from_dict(data.get("session"))
    item = session.current()
    kb = suggestion_kb(step, has_prev=session.cursor > 0,
                       has_next=session.cursor < len(session.seen) - 1,
                       has_more=session.has_more())
    title = STEP_TITLES.get(step, "")
    if item is None:
        if step == "image":
            await message.answer(
                f"{title}\n\n"
                "برای این استیکر، یکی از این دو راه رو انتخاب کن 👇",
                reply_markup=_image_empty_kb())
            return
        await message.answer(
            f"{title}\nپیشنهاد آماده‌ای برای این قدم نیست؛ "
            "می‌تونی خودت وارد کنی یا ردش کنی.", reply_markup=kb)
        return
    pos = session.position_label()
    if step == "image" and (item.get("file_id") or item.get("file_url")):
        # Show the actual image so the user sees it before choosing.
        media = item.get("file_id") or item.get("file_url")
        try:
            await message.answer_photo(
                media, caption=f"{title}\n{item.get('label', '')}\n📍 {pos}",
                reply_markup=kb)
            return
        except Exception:
            pass  # fall through to the text view if the media fails
    await message.answer(f"{title}\n\n{item.get('label', '')}\n\n📍 {pos}",
                         reply_markup=kb)


# --------------------------------------------------------------------------
# suggestion callbacks
# --------------------------------------------------------------------------

@router.callback_query(F.data.startswith("sug:"))
async def suggestion_cb(cb: CallbackQuery, state: FSMContext,
                        bot: Bot) -> None:
    parts = (cb.data or "").split(":")
    action = parts[2] if len(parts) > 2 else ""
    data = await state.get_data()
    step = data.get("step", "")
    session = SuggestionSession.from_dict(data.get("session"))
    note: str | None = None  # single callback answer at the end

    if action == "prev":
        session.go_prev()
    elif action == "next":
        session.go_next()
    elif action == "batch":
        if not session.next_batch():
            await cb.answer("پیشنهاد تازه‌ای نیست؛ از دیده‌شده‌ها انتخاب کن یا خودت وارد کن.")
            return
    elif action == "random":
        session.random_seen_or_batch()
    elif action == "bookmark":
        item = session.current()
        if item:
            on = session.toggle_bookmark(item["id"])
            note = "❤️ نشان شد" if on else "نشان برداشته شد"
    elif action == "reject":
        item = session.current()
        if item:
            session.reject(item["id"])
            if not session.seen:
                session.next_batch()
            note = "🚫 حذف شد و دیگه نشون داده نمی‌شه"
    elif action == "seen":
        await state.update_data(session=session.to_dict())
        if not session.seen:
            await cb.answer("هنوز چیزی دیده نشده")
            return
        lines = [f"{i + 1}. {it.get('label', '')}"
                 for i, it in enumerate(session.seen)]
        await cb.message.answer(
            "📋 دیده‌شده‌ها (رو شماره بزن تا همون انتخاب بشه):\n" +
            "\n".join(lines),
            reply_markup=seen_list_kb(step, len(session.seen)))
        await cb.answer()
        return
    elif action == "back":
        await _show_current(cb.message, state)
        await cb.answer()
        return
    elif action == "seenpick":
        idx = int(parts[3])
        item = session.pick_seen(idx)
        await state.update_data(session=session.to_dict())
        if item:
            await cb.answer(f"✅ پیشنهاد {idx + 1} انتخاب شد")
            await _apply_pick(cb.message, state, step, item, bot)
        return
    elif action == "pick":
        item = session.current()
        await state.update_data(session=session.to_dict())
        if item is None:
            await cb.answer("پیشنهادی برای انتخاب نیست")
            return
        await cb.answer()
        await _apply_pick(cb.message, state, step, item, bot)
        return
    elif action == "edit":
        item = session.current()
        if step not in ("topic", "sentence", "name") or item is None:
            await cb.answer("این قدم ویرایش متنی نداره؛ انتخاب کن یا خودت وارد کن.")
            return
        await state.update_data(manual_for=step, edit_mode=True)
        await state.set_state(Wizard.edit_input)
        await cb.message.answer(
            f"✏️ متن فعلی: {item.get('label', '')}\nنسخه ویرایش‌شده رو بفرست:")
        await cb.answer()
        return
    elif action == "manual":
        prompts = {
            "topic": "✍️ موضوع پکت رو بنویس:",
            "sentence": "✍️ جمله استیکر رو بنویس:",
            "image": "✍️ عکست رو بفرست (به‌صورت عکس):",
            "style": "✍️ از قدم پیشنهاد، سبک رو انتخاب کن یا «رد کن» رو بزن.",
            "emoji": "✍️ ایموجی دلخواهت رو بفرست:",
            "name": "✍️ اسم پک رو بنویس (حداکثر ۶۴ حرف):",
        }
        if step == "style":
            await cb.answer("سبک فقط از فهرست انتخاب می‌شه")
            return
        await state.update_data(manual_for=step, edit_mode=False)
        await state.set_state(Wizard.manual_input)
        await cb.message.answer(prompts.get(step, "✍️ وارد کن:"))
        await cb.answer()
        return
    elif action == "skip":
        await state.update_data(session=session.to_dict())
        await cb.answer()
        await _apply_skip(cb.message, state, step, bot)
        return

    await state.update_data(session=session.to_dict())
    await cb.answer(note)
    await _show_current(cb.message, state)


# --------------------------------------------------------------------------
# applying a pick / skip
# --------------------------------------------------------------------------

async def _apply_pick(message: Message, state: FSMContext, step: str,
                      item: dict, bot: Bot) -> None:
    data = await state.get_data()
    cur = dict(data.get("current") or {})
    if step == "topic":
        await state.update_data(topic={"label": item["label"],
                                       "category": item.get("category")})
        await _goto_step(message, state, "sentence")
    elif step == "sentence":
        cur["sentence"] = item["label"]
        cur["sentence_emoji"] = item.get("emoji")
        await state.update_data(current=cur)
        await _goto_step(message, state, "image")
    elif step == "image":
        cur["image"] = {"kind": "asset" if item.get("file_id") else "url",
                        "file_id": item.get("file_id"),
                        "file_url": item.get("file_url")}
        await state.update_data(current=cur)
        await _goto_step(message, state, "style")
    elif step == "style":
        cur["style"] = item.get("key", "clean")
        await state.update_data(current=cur)
        await _goto_step(message, state, "emoji")
    elif step == "emoji":
        cur["emoji"] = item.get("emoji") or item.get("label") or "🙂"
        await state.update_data(current=cur)
        await _build_preview(message, state, bot)
    elif step == "name":
        await _create_pack_now(message, state, item["label"], bot)


async def _apply_skip(message: Message, state: FSMContext, step: str,
                      bot: Bot) -> None:
    data = await state.get_data()
    cur = dict(data.get("current") or {})
    if step == "topic":
        await state.update_data(topic=None)
        await _goto_step(message, state, "sentence")
    elif step == "sentence":
        cur["sentence"] = None
        await state.update_data(current=cur)
        await _goto_step(message, state, "image")
    elif step == "image":
        cur["image"] = {"kind": "none"}
        await state.update_data(current=cur)
        await _goto_step(message, state, "style")
    elif step == "style":
        cur["style"] = "clean"
        await state.update_data(current=cur)
        await _goto_step(message, state, "emoji")
    elif step == "emoji":
        cur["emoji"] = cur.get("sentence_emoji") or "🙂"
        await state.update_data(current=cur)
        await _build_preview(message, state, bot)
    elif step == "name":
        topic = (data.get("topic") or {}).get("label") or "پک من"
        await _create_pack_now(message, state, topic, bot)


# --------------------------------------------------------------------------
# manual / edited input
# --------------------------------------------------------------------------

@router.message(Wizard.manual_input)
@router.message(Wizard.edit_input)
async def manual_message(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    step = data.get("manual_for", "")
    if step == "image":
        if not message.photo:
            await message.answer("برای این قدم باید عکس بفرستی 📷")
            return
        cur = dict(data.get("current") or {})
        cur["image"] = {"kind": "photo",
                        "file_id": message.photo[-1].file_id}
        await state.update_data(current=cur)
        await _goto_step(message, state, "style")
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("متنی نفرستادی؛ دوباره بفرست ✍️")
        return
    item = {"id": "manual", "label": text[:64] if step == "name" else text}
    if step == "sentence":
        item["emoji"] = None
    if step == "emoji":
        item["emoji"] = text[:8]
    if step == "topic":
        item["category"] = None
    await _apply_pick(message, state, step, item, bot)


@router.message(Wizard.step_image, F.photo)
async def photo_during_image_step(message: Message, state: FSMContext) -> None:
    """Sending a photo directly in the image step counts as manual input."""
    data = await state.get_data()
    cur = dict(data.get("current") or {})
    cur["image"] = {"kind": "photo", "file_id": message.photo[-1].file_id}
    await state.update_data(current=cur)
    await _goto_step(message, state, "style")


# --------------------------------------------------------------------------
# sticker build + preview
# --------------------------------------------------------------------------

async def _download(bot: Bot, file_id: str) -> bytes:
    file = await bot.get_file(file_id)
    buf = await bot.download_file(file.file_path)
    return buf.read()


async def _fetch_url(url: str) -> bytes:
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            return await r.read()


async def _build_preview(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    cur = data.get("current") or {}
    style = cur.get("style", "clean")
    sentence = cur.get("sentence")
    image = cur.get("image") or {"kind": "none"}
    await message.answer("⏳ دارم استیکر رو می‌سازم...")
    try:
        if image.get("kind") in ("photo", "asset") and image.get("file_id"):
            raw = await _download(bot, image["file_id"])
            webp = await asyncio.to_thread(
                process_image, raw, sentence, style,
                config.use_rembg, FONT)
        elif image.get("kind") == "url" and image.get("file_url"):
            raw = await _fetch_url(image["file_url"])
            webp = await asyncio.to_thread(
                process_image, raw, sentence, style,
                config.use_rembg, FONT)
        else:
            webp = await asyncio.to_thread(
                render_text_sticker, sentence or "", style, FONT,
                cur.get("emoji", ""))
    except Exception as exc:  # keep the wizard alive on bad input
        await message.answer(f"❌ ساخت استیکر نشد: {exc}\nدوباره تلاش کن.")
        await _goto_step(message, state, "sentence")
        return

    path = TMP / f"{message.chat.id}_{os.getpid()}_{len(data.get('ready', []))}.webp"
    path.write_bytes(webp)
    await state.update_data(pending_webp=str(path))
    await message.answer_sticker(BufferedInputFile(webp, filename="sticker.webp"))
    await message.answer("این شد استیکرت 👆", reply_markup=preview_kb())


@router.callback_query(F.data == "wiz:redo")
async def redo_sticker(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.update_data(current={}, pending_webp=None)
    await _goto_step(cb.message, state, "sentence")


@router.callback_query(F.data == "wiz:accept")
async def accept_sticker(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    pending = data.get("pending_webp")
    if not pending:
        await cb.answer("استیکری آماده نیست")
        return
    cur = data.get("current") or {}
    ready = list(data.get("ready", []))
    ready.append({"webp_path": pending, "emoji": cur.get("emoji", "🙂"),
                  "text": cur.get("sentence"), "style": cur.get("style")})
    async with Session() as s:
        per_pack = int(await get_setting(s, "quota_stickers_per_pack", "10"))
    if data.get("mode") == "add":
        await _add_ready_to_pack(cb.message, state, bot, ready)
        return
    await state.update_data(ready=ready, current={}, pending_webp=None,
                            stickers_done=len(ready))
    await cb.answer("✅ اضافه شد")
    if len(ready) >= per_pack:
        await cb.message.answer(
            f"به سقف {per_pack} استیکر این پک رسیدی؛ دارم می‌رم برای ساخت پک 🏁")
        await _goto_step(cb.message, state, "name")
    else:
        await cb.message.answer(f"استیکر {len(ready)} آماده‌ست. بعدی رو بساز 👇")
        await _goto_step(cb.message, state, "sentence")


@router.callback_query(F.data == "wiz:finish")
async def finish(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    if data.get("mode") == "add":
        await state.clear()
        await cb.message.answer("✅ کارت با این پک تموم شد.")
        await cb.answer()
        return
    if not data.get("ready"):
        await cb.answer("اول حداقل یه استیکر بساز 🎨", show_alert=True)
        return
    await cb.answer()
    await _goto_step(cb.message, state, "name")


@router.callback_query(F.data == "wiz:cancel")
async def cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.answer()
    await cb.message.answer("❌ ساخت پک لغو شد.")


# --------------------------------------------------------------------------
# pack creation
# --------------------------------------------------------------------------

async def _add_ready_to_pack(message: Message, state: FSMContext, bot: Bot,
                             ready: list[dict]) -> None:
    data = await state.get_data()
    async with Session() as s:
        pack = await s.get(Pack, data.get("pack_id"))
    if pack is None:
        await message.answer("❌ پک پیدا نشد.")
        await state.clear()
        return
    item = ready[-1]
    webp = Path(item["webp_path"]).read_bytes()
    await add_sticker(bot, message.chat.id, pack.name, webp, item["emoji"])
    async with Session() as s:
        s.add(Sticker(pack_id=pack.id, emoji=item["emoji"],
                      text=item.get("text"), style=item.get("style")))
        await s.commit()
    await state.update_data(ready=[], current={}, pending_webp=None)
    await message.answer(f"✅ به پک «{pack.title}» اضافه شد.\n{pack.link}\n"
                         "می‌تونی یکی دیگه بسازی یا از منوی «پک‌های من» برگردی.")
    await _goto_step(message, state, "sentence")


async def _create_pack_now(message: Message, state: FSMContext, title: str,
                           bot: Bot) -> None:
    data = await state.get_data()
    ready = data.get("ready", [])
    if not ready:
        await message.answer("استیکری برای ساخت پک نیست.")
        return
    stickers = [(Path(r["webp_path"]).read_bytes(), r["emoji"]) for r in ready]
    await message.answer("⏳ دارم پک رو تو تلگرام می‌سازم...")
    try:
        name = await create_pack(bot, message.chat.id, title, stickers)
    except Exception as exc:
        await message.answer(f"❌ ساخت پک در تلگرام نشد: {exc}")
        return
    file_ids: list[str | None] = [None] * len(ready)
    try:
        sticker_set = await bot.get_sticker_set(name)
        file_ids = [st.file_id for st in sticker_set.stickers]
    except Exception:
        pass
    async with Session() as s:
        pack = Pack(owner_id=message.chat.id, name=name, title=title[:64],
                    pack_type="static")
        s.add(pack)
        await s.flush()
        for r, fid in zip(ready, file_ids):
            s.add(Sticker(pack_id=pack.id, file_id=fid, emoji=r["emoji"],
                          text=r.get("text"), style=r.get("style")))
        user = await s.get(User, message.chat.id)
        if user:
            user.packs_created += 1
        await s.commit()
        link = pack.link
    for r in ready:
        try:
            Path(r["webp_path"]).unlink(missing_ok=True)
        except Exception:
            pass
    await state.clear()
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🖼 باز کردن پک", url=link))
    await message.answer(
        f"🎉 پکت ساخته شد!\n\n📦 {title}\n🔗 {link}\n\n"
        "لینک رو برای دوستات بفرست تا پک رو اضافه کنن.",
        reply_markup=b.as_markup())
