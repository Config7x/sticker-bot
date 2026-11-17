"""Forced-join / forced-start locks (SPEC 12).

- Channels: membership checked live with getChatMember (the bot must be an
  admin of the channel, otherwise Telegram refuses the check and we treat
  the result as unknown -> the user stays locked with an explanation).
- Other bots: a bot cannot see whether a user started another bot, so the
  verifiable path reads the shared `bot_starts` registry (written by the
  owner's other bots when they are started). Until that integration lands,
  admins can allow trust mode: the user taps "✅ استارت کردم" and we record
  the claim in settings under trust:<user_id>.
"""
from __future__ import annotations

import json

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_setting, set_setting
from .models import BotStart
from sqlalchemy import select

_MEMBER_OK = {
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.RESTRICTED,
}


async def check_bot_started(s: AsyncSession, user_id: int,
                            bot_username: str) -> bool:
    """Verifiable check: True when the shared registry has a start row."""
    row = (await s.execute(
        select(BotStart).where(
            BotStart.user_id == user_id,
            BotStart.bot_username == bot_username.lstrip("@").lower(),
        )
    )).scalars().first()
    return row is not None


async def record_bot_start(s: AsyncSession, user_id: int,
                           bot_username: str) -> None:
    """Called by the owner's other bots (later integration) on /start."""
    if await check_bot_started(s, user_id, bot_username):
        return
    s.add(BotStart(user_id=user_id,
                   bot_username=bot_username.lstrip("@").lower()))
    await s.commit()


async def _json_list(s: AsyncSession, key: str) -> list[str]:
    try:
        value = json.loads(await get_setting(s, key, "[]"))
        return value if isinstance(value, list) else []
    except Exception:
        return []


async def lock_config(s: AsyncSession) -> dict:
    return {
        "channels": await _json_list(s, "lock_channels"),
        "bots": await _json_list(s, "lock_bots"),
        "trust": (await get_setting(s, "lock_bots_trust", "1")) == "1",
    }


async def _trusted_bots(s: AsyncSession, user_id: int) -> list[str]:
    return await _json_list(s, f"trust:{user_id}")


async def mark_trusted(s: AsyncSession, user_id: int, bots: list[str]) -> None:
    current = set(await _trusted_bots(s, user_id))
    current.update(b.lstrip("@").lower() for b in bots)
    await set_setting(s, f"trust:{user_id}", json.dumps(sorted(current)))


async def lock_status(bot: Bot, s: AsyncSession, user_id: int) -> dict:
    """Return missing channels/bots for this user (empty lists = unlocked)."""
    cfg = await lock_config(s)
    missing_channels: list[str] = []
    for ch in cfg["channels"]:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status not in _MEMBER_OK or (
                member.status == ChatMemberStatus.RESTRICTED
                and not getattr(member, "is_member", True)
            ):
                missing_channels.append(ch)
        except Exception:
            # Bot is not admin there / chat unreachable: cannot verify.
            missing_channels.append(ch)

    trusted = set(await _trusted_bots(s, user_id))
    missing_bots: list[str] = []
    for b in cfg["bots"]:
        name = b.lstrip("@")
        if await check_bot_started(s, user_id, name):
            continue
        if cfg["trust"] and name.lower() in trusted:
            continue
        missing_bots.append(name)

    return {
        "channels": missing_channels,
        "bots": missing_bots,
        "trust_allowed": cfg["trust"],
        "locked": bool(missing_channels or missing_bots),
    }
