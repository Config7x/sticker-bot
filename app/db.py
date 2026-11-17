"""Async engine/session, schema creation and first-run seeding."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import config
from .models import Asset, Base, Sentence, Setting
from .seed_data import SEED_ASSETS, SENTENCE_BANK
from .texts import DEFAULT_SETTINGS, DEFAULT_TEXTS

engine = create_async_engine(config.database_url, pool_pre_ping=True)
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with Session() as s:
        await seed_defaults(s)


async def seed_defaults(s: AsyncSession) -> None:
    """Insert default settings/texts, the sentence bank and seed assets once."""
    for key, value in {**DEFAULT_SETTINGS, **{f"text_{k}": v for k, v in DEFAULT_TEXTS.items()}}.items():
        exists = await s.get(Setting, key)
        if exists is None:
            s.add(Setting(key=key, value=value))

    count = len((await s.execute(select(Sentence.id))).scalars().all())
    if count == 0:
        for category, items in SENTENCE_BANK.items():
            for text, emoji in items:
                s.add(Sentence(category=category, text=text, emoji=emoji))

    count = len((await s.execute(select(Asset.id))).scalars().all())
    if count == 0:
        for item in SEED_ASSETS:
            s.add(Asset(**item))
    await s.commit()


# --- small settings helpers -------------------------------------------------

async def get_setting(s: AsyncSession, key: str, default: str = "") -> str:
    row = await s.get(Setting, key)
    return row.value if row is not None else default


async def set_setting(s: AsyncSession, key: str, value: str) -> None:
    row = await s.get(Setting, key)
    if row is None:
        s.add(Setting(key=key, value=value))
    else:
        row.value = value
    await s.commit()


async def get_text(s: AsyncSession, name: str) -> str:
    return await get_setting(s, f"text_{name}", DEFAULT_TEXTS.get(name, ""))
