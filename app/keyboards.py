"""Keyboards. Main menu is a reply keyboard (buttons only, no commands);
wizard/admin use inline keyboards. All labels carry emojis (SPEC 3/12)."""
from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

BTN_NEW = "🎨 ساخت پک جدید"
BTN_BUILD = "✨ بساز برام"
BTN_IDEA = "💡 ایده بده"
BTN_TREND = "🔥 ترندهای این ماه"
BTN_MY = "🖼 پک‌های من"
BTN_EDIT = "✏️ ویرایش پک"
BTN_POPULAR = "🏆 پک‌های محبوب"
BTN_SEARCH = "🔍 جستجوی پک و قالب"
BTN_QUOTA = "⭐ اشتراک و سهمیه من"
BTN_HELP = "❓ راهنما"
BTN_SUPPORT = "📞 پشتیبانی"
BTN_ADMIN = "🛠 پنل مدیریت"


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    for label in (BTN_NEW, BTN_BUILD, BTN_IDEA, BTN_TREND, BTN_MY, BTN_EDIT,
                  BTN_POPULAR, BTN_SEARCH, BTN_QUOTA, BTN_HELP, BTN_SUPPORT):
        b.add(KeyboardButton(text=label))
    if is_admin:
        b.add(KeyboardButton(text=BTN_ADMIN))
    b.adjust(2)
    return b.as_markup(resize_keyboard=True)


def lock_kb(channels: list[str], bots: list[str],
            trust_allowed: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for ch in channels:
        name = ch.lstrip("@")
        b.row(InlineKeyboardButton(text=f"📣 عضویت در @{name}",
                                   url=f"https://t.me/{name}"))
    for bot_name in bots:
        b.row(InlineKeyboardButton(text=f"🤖 استارت @{bot_name}",
                                   url=f"https://t.me/{bot_name}"))
    if bots and trust_allowed:
        b.row(InlineKeyboardButton(text="✅ استارت کردم (تأیید دستی)",
                                   callback_data="lock:trust"))
    b.row(InlineKeyboardButton(text="✅ بررسی مجدد", callback_data="lock:recheck"))
    return b.as_markup()


def suggestion_kb(step: str, has_prev: bool, has_next: bool,
                  has_more: bool) -> InlineKeyboardMarkup:
    """Controls under the single-item suggestion viewer (SPEC 4)."""
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✅ انتخاب", callback_data=f"sug:{step}:pick"))
    nav = []
    if has_prev:
        nav.append(InlineKeyboardButton(text="⏮ قبلی", callback_data=f"sug:{step}:prev"))
    if has_next:
        nav.append(InlineKeyboardButton(text="⏭ بعدی", callback_data=f"sug:{step}:next"))
    nav.append(InlineKeyboardButton(text="📋 دیده‌شده‌ها", callback_data=f"sug:{step}:seen"))
    b.row(*nav)
    b.row(
        InlineKeyboardButton(text="❤️ نشان‌کردن", callback_data=f"sug:{step}:bookmark"),
        InlineKeyboardButton(text="🚫 این نه", callback_data=f"sug:{step}:reject"),
        InlineKeyboardButton(text="🎲 شانسی", callback_data=f"sug:{step}:random"),
    )
    row = []
    if has_more:
        row.append(InlineKeyboardButton(text="🔄 دسته بعدی", callback_data=f"sug:{step}:batch"))
    row.append(InlineKeyboardButton(text="✏️ انتخاب + ویرایش", callback_data=f"sug:{step}:edit"))
    b.row(*row)
    b.row(
        InlineKeyboardButton(text="✍️ خودم وارد می‌کنم", callback_data=f"sug:{step}:manual"),
        InlineKeyboardButton(text="⏭ رد کن", callback_data=f"sug:{step}:skip"),
    )
    b.row(InlineKeyboardButton(text="🏁 تمام و ساخت پک", callback_data="wiz:finish"))
    b.row(InlineKeyboardButton(text="❌ لغو ساخت", callback_data="wiz:cancel"))
    return b.as_markup()


def seen_list_kb(step: str, count: int) -> InlineKeyboardMarkup:
    """Direct-pick buttons for the seen-history list (pick e.g. #2 of 5)."""
    b = InlineKeyboardBuilder()
    row: list[InlineKeyboardButton] = []
    for i in range(count):
        row.append(InlineKeyboardButton(text=f"✅ {i + 1}",
                                        callback_data=f"sug:{step}:seenpick:{i}"))
        if len(row) == 5:
            b.row(*row)
            row = []
    if row:
        b.row(*row)
    b.row(InlineKeyboardButton(text="🔙 برگشت", callback_data=f"sug:{step}:back"))
    return b.as_markup()


def preview_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✅ افزودن و استیکر بعدی",
                               callback_data="wiz:accept"))
    b.row(InlineKeyboardButton(text="🔄 ساخت دوباره این استیکر",
                               callback_data="wiz:redo"))
    b.row(InlineKeyboardButton(text="🏁 تمام و ساخت پک", callback_data="wiz:finish"))
    b.row(InlineKeyboardButton(text="❌ لغو ساخت", callback_data="wiz:cancel"))
    return b.as_markup()
