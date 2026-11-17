"""Outer middlewares: user upsert + lock gate for messages and callbacks."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from .config import config
from .db import Session, get_text
from .keyboards import lock_kb
from .locks import lock_status
from .models import User


async def upsert_user(from_user) -> None:
    async with Session() as s:
        user = await s.get(User, from_user.id)
        if user is None:
            s.add(User(id=from_user.id, username=from_user.username,
                       first_name=from_user.first_name,
                       last_seen_at=datetime.utcnow()))
        else:
            user.username = from_user.username
            user.first_name = from_user.first_name
            user.last_seen_at = datetime.utcnow()
        await s.commit()


async def is_banned(user_id: int) -> bool:
    async with Session() as s:
        user = await s.get(User, user_id)
        return bool(user and user.is_banned)


class UserMiddleware(BaseMiddleware):
    """Register the user and silently drop banned users."""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        from_user = getattr(event, "from_user", None)
        if from_user is not None and not from_user.is_bot:
            await upsert_user(from_user)
            if await is_banned(from_user.id):
                return None
        return await handler(event, data)


class LockMiddleware(BaseMiddleware):
    """Block locked users with the lock screen (SPEC 12).

    Exempt: admins/owner, /start, and the lock:* callbacks themselves.
    """

    async def __call__(self, handler, event: TelegramObject, data: dict):
        from_user = getattr(event, "from_user", None)
        if from_user is None or from_user.is_bot:
            return await handler(event, data)
        if from_user.id in config.admin_ids:
            return await handler(event, data)
        if isinstance(event, CallbackQuery) and (event.data or "").startswith("lock:"):
            return await handler(event, data)
        if isinstance(event, Message) and (event.text or "").startswith("/start"):
            return await handler(event, data)

        bot = data["bot"]
        async with Session() as s:
            status = await lock_status(bot, s, from_user.id)
            if not status["locked"]:
                return await handler(event, data)
            text = await get_text(s, "lock")

        kb = lock_kb(status["channels"], status["bots"], status["trust_allowed"])
        if isinstance(event, Message):
            await event.answer(text, reply_markup=kb)
        elif isinstance(event, CallbackQuery):
            await event.answer("🔒 اول قفل‌ها رو کامل کن.", show_alert=True)
            if event.message:
                await event.message.answer(text, reply_markup=kb)
        return None
