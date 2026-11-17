"""Default Persian UI texts. Welcome / lock / help texts are editable from
the admin panel (stored in the settings table, keys text_*)."""
from __future__ import annotations

DEFAULT_TEXTS: dict[str, str] = {
    "welcome": (
        "سلام! 👋 به ربات استیکرساز خوش اومدی.\n\n"
        "اینجا می‌تونی بدون بلد بودن فتوشاپ، پک استیکر اختصاصی خودت رو بسازی؛ "
        "تو هر مرحله ربات بهت پیشنهاد می‌ده و هرجا خواستی خودت وارد می‌کنی. 🎨"
    ),
    "lock": (
        "🔒 برای استفاده از ربات، اول این موارد رو کامل کن:\n"
        "بعد از انجام هرکدوم، دکمه «✅ بررسی مجدد» رو بزن."
    ),
    "help": (
        "❓ راهنما\n\n"
        "🎨 ساخت پک جدید: قدم‌به‌قدم، با پیشنهاد ربات یا ورودی خودت.\n"
        "✨ بساز برام: فقط موضوع رو بگو، ربات پیش‌نویس کامل پک رو می‌سازه.\n"
        "🖼 پک‌های من: پک‌هایی که ساختی و افزودن استیکر به اون‌ها.\n\n"
        "هر پک فقط یک نوع می‌تونه باشه (معمولی/ویدیویی/متحرک). "
        "در این نسخه فقط پک معمولی فعال است؛ ویدیویی و متحرک به‌زودی. 🚀"
    ),
    "quota_full": (
        "⭐ سهمیه رایگان تو تموم شده.\n"
        "برای ساخت پک بیشتر، منتظر فعال شدن اشتراک باش یا با پشتیبانی در تماس باش."
    ),
}

DEFAULT_SETTINGS: dict[str, str] = {
    # free quota (SPEC 11/14): 1 pack, up to 10 stickers
    "quota_packs": "1",
    "quota_stickers_per_pack": "10",
    # locks: JSON lists, managed from the admin panel
    "lock_channels": "[]",   # ["@CONFIG7X", ...]
    "lock_bots": "[]",       # ["somebot", ...] usernames without @
    "lock_bots_trust": "1",  # 1 = trust-mode button allowed, 0 = registry only
}
