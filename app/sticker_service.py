"""Sticker-set creation through the Bot API (SPEC 4/9).

Pack short names must end with `_by_<bot username>`; the bot can only edit
sets it created itself, which is exactly what "پک‌های من" relies on.
"""
from __future__ import annotations

import random
import string

from aiogram import Bot
from aiogram.types import BufferedInputFile, InputSticker


def make_pack_name(bot_username: str, user_id: int) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"sb{user_id}{suffix}_by_{bot_username}"


def _input(webp: bytes, emoji: str, name: str) -> InputSticker:
    return InputSticker(
        sticker=BufferedInputFile(webp, filename=name),
        format="static",
        emoji_list=[emoji or "🙂"],
    )


async def create_pack(bot: Bot, user_id: int, title: str,
                      stickers: list[tuple[bytes, str]]) -> str:
    """Create a set with all stickers in one call. Returns the pack name."""
    me = await bot.get_me()
    name = make_pack_name(me.username, user_id)
    inputs = [_input(data, emoji, f"s{i}.webp")
              for i, (data, emoji) in enumerate(stickers)]
    await bot.create_new_sticker_set(
        user_id=user_id, name=name, title=title[:64], stickers=inputs
    )
    # Best effort: first sticker as the set thumbnail/cover.
    try:
        await bot.set_sticker_set_thumbnail(
            name=name, user_id=user_id,
            thumbnail=inputs[0].sticker, format="static",
        )
    except Exception:
        pass
    return name


async def add_sticker(bot: Bot, user_id: int, pack_name: str,
                      webp: bytes, emoji: str) -> None:
    await bot.add_sticker_to_set(
        user_id=user_id, name=pack_name,
        sticker=_input(webp, emoji, "add.webp"),
    )
