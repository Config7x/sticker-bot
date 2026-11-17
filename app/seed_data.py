"""Seed data: Persian sentence bank, topics, styles, emoji sets, assets.

Sentences are grouped by the categories required by the SPEC (section 5).
Assets are placeholder records only: file_id / file_url stay empty until
real template files are added from the admin panel or the trend pipeline
(Phase 2). The image step gracefully skips assets without a file.
"""
from __future__ import annotations

# category -> list of (text, suggested emoji)
# Rebuilt 2026-11-17 from REAL usage research in the owner's own Telegram
# (his installed packs + busy groups): people actually send SHORT, slangy
# reaction captions — sarcasm and poker-face included — not polite
# textbook sentences. Texts carry NO emoji chars (the emoji lives in the
# emoji field; drawing emoji glyphs inside the text breaks rendering).
SENTENCE_BANK: dict[str, list[tuple[str, str]]] = {
    "greetings": [
        ("سلااام", "👋"), ("سلام علیکم", "🤝"), ("درود", "✨"),
        ("صبح بخیر", "☀️"), ("شب بخیر", "🌙"), ("چه خبرا؟", "👀"),
        ("خوبی؟", "🙂"), ("کجایی؟", "👀"), ("دلم برات تنگ شده", "🥹"),
        ("خوش اومدی", "🎉"),
    ],
    "farewell": [
        ("خداحافظ", "👋"), ("فعلاً", "✌️"), ("میرم دیگه", "🏃"),
        ("شب خوش", "🌙"), ("می‌بینمت", "😉"), ("تا فردا", "👋"),
        ("برو به سلامت", "🚶"),
    ],
    "thanks": [
        ("مرسی", "🙏"), ("دمت گرم", "🔥"), ("لطف کردی", "🌹"),
        ("نوکرم", "😎"), ("دستت طلا", "✨"), ("ممنونم", "🙏"),
        ("قربونت", "😘"), ("زنده باشی", "❤️"),
    ],
    "apology": [
        ("ببخشید", "🙏"), ("شرمنده", "🥺"), ("غلط کردم", "😅"),
        ("ببخش دیر شد", "⏰"), ("اشتباه از من بود", "😔"), ("جبران می‌کنم", "🤝"),
    ],
    "laughter": [
        ("مردم از خنده", "🤣"), ("ترکیدم", "🤣"), ("پاره شدم", "😂"),
        ("نمیتونم", "😭"), ("وای مردم", "🤣"), ("خخخخ", "😆"),
        ("این چی بود", "😂"), ("مُردم", "😭"),
    ],
    "sarcasm": [
        ("ممنون که اطلاع دادید", "😐"), ("واقعاً؟", "🤨"), ("آهان", "😐"),
        ("باشه حاجی", "😒"), ("چه جالب", "😐"), ("به من چه", "🤷"),
        ("نکنمت", "😬"), ("هی روزگار", "😮‍💨"), ("چشم", "🙄"),
        ("حتماً حتماً", "🙄"), ("شوخی بود", "😅"), ("برو بیرون بیا", "🚪"),
    ],
    "agree": [
        ("دقیقاً", "👌"), ("موافقم", "🤝"), ("آره والا", "👍"),
        ("همینه", "💯"), ("صد درصد", "💯"), ("قبول", "✅"),
        ("چشم", "✅"), ("اوکیه", "👌"), ("حرفت حقه", "🤝"),
    ],
    "disagree": [
        ("نه داداش", "❌"), ("اصلاً", "🚫"), ("ول کن", "😤"),
        ("بیخیال", "🙄"), ("نمیشه", "❌"), ("اشتباه می‌کنی", "🤨"),
        ("برو بابا", "😒"), ("عمراً", "🚫"),
    ],
    "shock": [
        ("چی بود؟", "😳"), ("جدی؟", "😮"), ("پشمام", "🤯"),
        ("عه؟", "😲"), ("باورم نمیشه", "😱"), ("چی شد؟", "👀"),
        ("وااای", "😱"), ("مگه داریم؟", "🤯"),
    ],
    "sad": [
        ("خسته‌م", "😩"), ("دیگه نمی‌کشم", "🫠"), ("حالم بده", "🥴"),
        ("دلم گرفته", "🥺"), ("خوابم میاد", "😴"), ("ولم کن", "😔"),
        ("ای خدا", "😮‍💨"), ("مردم از خستگی", "🫠"),
    ],
    "love": [
        ("قربونت", "😘"), ("عشقمی", "😍"), ("جونمی", "❤️"),
        ("دلم برات تنگ شده", "🥹"), ("بغل", "🤗"), ("عزیز دلی", "💖"),
        ("دوستت دارم", "❤️"),
    ],
    "group": [
        ("پینش کن", "📌"), ("ادمین کجایی؟", "📣"), ("پاپ‌کورن آوردم", "🍿"),
        ("من هیچی نمیگم", "🤐"), ("ادامه بدین", "👀"), ("چه خبره اینجا", "👀"),
        ("یکی خلاصه کنه", "📝"),
    ],
    "sales": [
        ("برای خرید پیام بده", "🛒"), ("تست رایگان داریم", "🎁"),
        ("پشتیبانی ۲۴ ساعته", "🛎"), ("کیفیت تضمینی", "💯"),
        ("همین حالا سفارش بده", "⚡"),
    ],
    "gaming": [
        ("GG", "🎮"), ("بردیم", "🏆"), ("باختیم", "😭"),
        ("یه دست دیگه", "🔁"), ("نوب", "😂"), ("لگه", "🐌"),
        ("حمله کنین", "⚔️"),
    ],
    "congrats": [
        ("تبریک", "🎉"), ("آفرین", "👏"), ("دمت گرم", "🔥"),
        ("ترکوندی", "💪"), ("همینه که هست", "😎"),
    ],
}

CATEGORY_TITLES: dict[str, str] = {
    "greetings": "👋 سلام و احوال‌پرسی",
    "farewell": "🌙 خداحافظی",
    "thanks": "🙏 تشکر",
    "apology": "🥺 عذرخواهی",
    "laughter": "😂 خنده",
    "sarcasm": "😐 طعنه و پوکرفیس",
    "agree": "👍 تأیید و موافقت",
    "disagree": "👎 مخالفت و کل‌کل",
    "shock": "😱 تعجب و شوک",
    "sad": "🥺 غم و خستگی",
    "group": "👥 جواب‌های گروه",
    "sales": "🛒 فروش و کانال",
    "love": "❤️ عاشقانه",
    "gaming": "🎮 گیم",
    "congrats": "🎉 تبریک و تشویق",
}

# Pack topics suggested in step 1 (also used by "بساز برام").
TOPICS: list[tuple[str, str]] = [  # (title, sentence category)
    ("ری‌اکشن‌های روزمره 😐", "sarcasm"),
    ("خنده و فان 😂", "laughter"),
    ("جواب‌های آماده گروه 👥", "group"),
    ("تأیید و مخالفت 👍👎", "agree"),
    ("تعجب و شوک 😱", "shock"),
    ("سلام و خداحافظی 👋", "greetings"),
    ("تشکر و محبت ❤️", "thanks"),
    ("غم و خستگی 🥺", "sad"),
    ("عاشقانه 💖", "love"),
    ("فروش و کانال من 🛒", "sales"),
    ("گیم و بازی 🎮", "gaming"),
]

STYLES: list[tuple[str, str]] = [  # (key, title)
    ("clean", "✨ تمیز و ساده"),
    ("bold", "💪 درشت و پررنگ"),
    ("bubble", "💬 حبابی"),
    ("shadow", "🌑 سایه‌دار"),
    ("neon", "🌈 نئونی"),
    ("minimal", "⚪ مینیمال"),
]

EMOJI_SETS: list[str] = [
    "😂", "😍", "👍", "❤️", "🔥", "😎", "🤝", "🙏",
    "😭", "🤣", "👀", "💯", "🎉", "😅", "🤔", "✌️",
]

# Real character assets (18): two mascot sets (cat + frog, 9 expressions
# each), generated for this bot, sliced into single characters and shipped
# in the public repo under assets/. file_url points at the repo raw file,
# so the wizard can preview (send_photo by URL) and process (fetch) them.
_RAW = "https://raw.githubusercontent.com/Config7x/sticker-bot/main/assets/"


def _asset(name: str, title: str, category: str, tags: str) -> dict:
    return {"title": title, "kind": "image", "file_url": _RAW + name,
            "tags": tags, "category": category, "style": "clean",
            "source": "seed"}


SEED_ASSETS: list[dict] = [
    _asset("cat_wave.png", "گربه — سلام", "greetings", "گربه,سلام,cat,wave"),
    _asset("cat_laugh.png", "گربه — خنده", "laughter", "گربه,خنده,cat,laugh"),
    _asset("cat_cry.png", "گربه — گریه", "sad", "گربه,گریه,غم,cat,cry"),
    _asset("cat_angry.png", "گربه — عصبانی", "disagree", "گربه,عصبانیت,cat,angry"),
    _asset("cat_shock.png", "گربه — شوکه", "shock", "گربه,تعجب,cat,shock"),
    _asset("cat_love.png", "گربه — عاشق", "love", "گربه,عشق,قلب,cat,love"),
    _asset("cat_sleepy.png", "گربه — خواب‌آلود", "sad", "گربه,خواب,خستگی,cat,sleepy"),
    _asset("cat_cool.png", "گربه — خفن", "agree", "گربه,عینک,خفن,cat,cool"),
    _asset("cat_thumbsup.png", "گربه — لایک", "agree", "گربه,لایک,تأیید,cat,thumbsup"),
    _asset("frog_wave.png", "قورباغه — سلام", "greetings", "قورباغه,سلام,frog,wave"),
    _asset("frog_laugh.png", "قورباغه — خنده", "laughter", "قورباغه,خنده,frog,laugh"),
    _asset("frog_eyeroll.png", "قورباغه — پوکرفیس", "sarcasm", "قورباغه,طعنه,پوکرفیس,frog,eyeroll"),
    _asset("frog_popcorn.png", "قورباغه — پاپ‌کورن", "group", "قورباغه,پاپکورن,تماشا,frog,popcorn"),
    _asset("frog_sleep.png", "قورباغه — خواب", "sad", "قورباغه,خواب,frog,sleep"),
    _asset("frog_cheer.png", "قورباغه — جشن", "congrats", "قورباغه,جشن,تبریک,frog,cheer"),
    _asset("frog_think.png", "قورباغه — فکر", "sarcasm", "قورباغه,فکر,شک,frog,think"),
    _asset("frog_thumbsup.png", "قورباغه — لایک", "thanks", "قورباغه,لایک,تشکر,frog,thumbsup"),
    _asset("frog_heart.png", "قورباغه — قلب", "love", "قورباغه,قلب,عشق,frog,heart"),
]
