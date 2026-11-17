"""Database tables (SQLAlchemy 2.0 async style).

users / packs / stickers   — product data
settings                   — key/value: locks, texts, quota (admin editable)
assets                     — suggestion database (templates / characters)
sentences                  — seeded Persian sentence bank
bot_starts                 — shared registry used by the forced-start lock:
                             other bots of the owner insert (user_id, bot)
                             rows here when a user starts them (later
                             integration; the lock check reads this table).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram id
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    packs_created: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)

    packs: Mapped[list["Pack"]] = relationship(back_populates="owner")


class Pack(Base):
    __tablename__ = "packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))          # short name (_by_bot)
    title: Mapped[str] = mapped_column(String(64))
    pack_type: Mapped[str] = mapped_column(String(16), default="static")
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    owner: Mapped[User] = relationship(back_populates="packs")
    stickers: Mapped[list["Sticker"]] = relationship(back_populates="pack")

    @property
    def link(self) -> str:
        return f"https://t.me/addstickers/{self.name}"


class Sticker(Base):
    __tablename__ = "stickers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pack_id: Mapped[int] = mapped_column(ForeignKey("packs.id"), index=True)
    file_id: Mapped[str | None] = mapped_column(String(256))
    emoji: Mapped[str] = mapped_column(String(32), default="🙂")
    text: Mapped[str | None] = mapped_column(Text)
    style: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    pack: Mapped[Pack] = relationship(back_populates="stickers")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class Asset(Base):
    """One suggestion-database item (template / character / reaction face)."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(16), default="image")  # image/gif/video
    file_id: Mapped[str | None] = mapped_column(String(256))        # Telegram file_id
    file_url: Mapped[str | None] = mapped_column(Text)              # or external URL
    tags: Mapped[str] = mapped_column(Text, default="")             # comma separated FA/EN
    category: Mapped[str] = mapped_column(String(64), default="general")
    style: Mapped[str] = mapped_column(String(64), default="")
    source: Mapped[str] = mapped_column(String(64), default="seed")
    trend_score: Mapped[float] = mapped_column(Float, default=0.0)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Sentence(Base):
    __tablename__ = "sentences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    text: Mapped[str] = mapped_column(Text)
    emoji: Mapped[str] = mapped_column(String(32), default="🙂")


class BotStart(Base):
    """Central start registry for the forced-start lock (see SPEC 12.2)."""

    __tablename__ = "bot_starts"
    __table_args__ = (UniqueConstraint("user_id", "bot_username"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    bot_username: Mapped[str] = mapped_column(String(64))  # without @
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
