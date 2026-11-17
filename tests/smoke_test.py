#!/usr/bin/env python3
"""Smoke test — no Telegram token needed.

Covers: package imports, suggestion batching/history logic, the image
pipeline on a generated test image, DB init + seeding, and the
forced-start registry logic. Run:  python3 tests/smoke_test.py
"""
from __future__ import annotations

import asyncio
import io
import os
import sys
import tempfile
from pathlib import Path

# Env must be set before importing app modules (config reads env at import).
_TMP = Path(tempfile.mkdtemp(prefix="sb-smoke-"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP}/smoke.db"
os.environ.setdefault("BOT_TOKEN", "0:dummy-for-smoke-test")
os.environ.setdefault("ADMIN_IDS", "111")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FAILURES: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(("PASS " if cond else "FAIL ") + name + (f" — {extra}" if extra else ""))
    if not cond:
        FAILURES.append(name)


def test_imports() -> None:
    import importlib

    for mod in ("app.config", "app.models", "app.db", "app.texts",
                "app.seed_data", "app.suggestions", "app.image_pipeline",
                "app.keyboards", "app.states", "app.locks", "app.middlewares",
                "app.sources", "app.sticker_service", "app.handlers.menu",
                "app.handlers.wizard", "app.handlers.buildforme",
                "app.handlers.mypacks", "app.handlers.admin", "app.main"):
        importlib.import_module(mod)
    check("imports: all app modules import cleanly", True)


def test_suggestions() -> None:
    from app.suggestions import SuggestionSession

    pool = [{"id": i, "label": f"گزینه {i}"} for i in range(12)]
    s = SuggestionSession(pool=list(pool), batch_size=5)

    b1 = s.next_batch()
    check("batching: first batch has 5 items", len(b1) == 5)
    b2 = s.next_batch()
    ids = [it["id"] for it in s.seen]
    check("batching: second batch adds 5 new, no repeats",
          len(b2) == 5 and len(set(ids)) == 10)

    # History: walk to the 5th seen item, then pick the 2nd one directly.
    s.cursor = 4
    check("history: position label is '5 of 10'",
          s.position_label() == "پیشنهاد 5 از 10", s.position_label())
    second = s.pick_seen(1)
    check("history: pick_seen(1) returns the 2nd seen item",
          second is not None and second["id"] == ids[1])

    # Prev/next navigation stays inside the seen history.
    s.go_prev()
    check("history: go_prev moves to 1st item", s.current()["id"] == ids[0])
    s.go_next()
    check("history: go_next returns to 2nd item", s.current()["id"] == ids[1])

    # Hard reject removes the item and it never comes back in later batches.
    rejected_id = ids[1]
    s.reject(rejected_id)
    check("reject: item removed from seen",
          all(it["id"] != rejected_id for it in s.seen))
    b3 = s.next_batch()
    check("reject: later batch skips the rejected item",
          all(it["id"] != rejected_id for it in b3) and len(b3) == 2)
    check("batching: pool exhausted -> has_more() is False", not s.has_more())

    # Bookmark toggling.
    cur = s.current()
    check("bookmark: toggle on/off",
          s.toggle_bookmark(cur["id"]) is True
          and s.toggle_bookmark(cur["id"]) is False)

    # FSM round-trip.
    s2 = SuggestionSession.from_dict(s.to_dict())
    check("fsm: to_dict/from_dict round-trip keeps seen+rejected",
          [it["id"] for it in s2.seen] == [it["id"] for it in s.seen]
          and s2.rejected == s.rejected)


def _dims(data: bytes) -> tuple[int, int]:
    from PIL import Image

    return Image.open(io.BytesIO(data)).size


def _sticker_geometry_ok(data: bytes) -> bool:
    """Telegram static-sticker rule: one side EXACTLY 512, other <= 512,
    WebP, <= 512 KB. (Regression guard for STICKER_PNG_DIMENSIONS.)"""
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return False
    if len(data) > 512 * 1024:
        return False
    w, h = _dims(data)
    return max(w, h) == 512 and min(w, h) <= 512


def test_image_pipeline() -> None:
    from PIL import Image, ImageDraw

    from app.image_pipeline import (
        find_font,
        normalize_512,
        process_image,
        render_style_sheet,
        render_text_sticker,
    )
    from app.seed_data import STYLES

    font = find_font("")
    check("font: a Noto Arabic font is found", font is not None, str(font))

    # normalize_512 on raw geometry edge cases.
    for size, want in (((100, 50), (512, 256)), ((2000, 1000), (512, 256)),
                       ((511, 300), (512, 301)), ((10, 10), (512, 512)),
                       ((300, 511), (301, 512)), ((512, 512), (512, 512))):
        got = normalize_512(Image.new("RGBA", size, (10, 20, 30, 255))).size
        check(f"normalize_512: {size} -> {want}", got == want, str(got))

    img = Image.new("RGBA", (800, 600), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([200, 100, 600, 500], fill=(220, 40, 40, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()

    # Photo pipeline, with and without text, several styles: the long
    # side must be EXACTLY 512 (not just <= 512) or Telegram rejects it.
    for style in ("clean", "neon", "bubble", "minimal"):
        out = process_image(raw, text="سلام دنیا", style=style,
                            use_rembg=False, font_path=font)
        check(f"pipeline: photo+text [{style}] exact-512 geometry",
              _sticker_geometry_ok(out), str(_dims(out)))
    for style in ("clean", "bold"):
        out = process_image(raw, text=None, style=style,
                            use_rembg=False, font_path=font)
        check(f"pipeline: photo only [{style}] exact-512 geometry",
              _sticker_geometry_ok(out), str(_dims(out)))

    # A small photo must be scaled UP so one side is exactly 512.
    small = Image.new("RGBA", (120, 90), (0, 0, 0, 0))
    ImageDraw.Draw(small).ellipse([10, 10, 110, 80], fill=(40, 180, 60, 255))
    sbuf = io.BytesIO()
    small.save(sbuf, format="PNG")
    out_small = process_image(sbuf.getvalue(), text=None, style="clean",
                              use_rembg=False, font_path=font)
    check("pipeline: small photo upscaled to exact-512 geometry",
          _sticker_geometry_ok(out_small), str(_dims(out_small)))

    # Text-only stickers (the «بساز برام» path): several texts x all
    # styles — this is the exact output that failed live with
    # STICKER_PNG_DIMENSIONS before the normalization fix.
    texts = [("سلام", "👋"), ("مرسی! خیلی ممنون از لطفت", "🙏"),
             ("😂😂😂", "😂"), ("یه جمله نسبتاً طولانی برای تست کوچیک شدن فونت و جا شدن توی قاب", "✨")]
    for text, emoji in texts:
        for key, _title in STYLES:
            out = render_text_sticker(text, key, font, emoji)
            check(f"text sticker: exact-512 [{key}] «{text[:12]}»",
                  _sticker_geometry_ok(out), str(_dims(out)))

    # Style contact sheet renders and is a real image.
    sheet = render_style_sheet("سلام", font, STYLES)
    simg = Image.open(io.BytesIO(sheet))
    check("style sheet: PNG with all styles in a grid",
          sheet[:8] == b"\x89PNG\r\n\x1a\n" and simg.width >= 1000
          and simg.height >= 700, str(simg.size))


async def test_db_and_locks() -> None:
    from sqlalchemy import func, select

    from app.db import Session, get_setting, init_db
    from app.locks import check_bot_started, record_bot_start
    from app.models import Asset, Sentence

    await init_db()
    async with Session() as s:
        n_sent = (await s.execute(select(func.count(Sentence.id)))).scalar_one()
        n_assets = (await s.execute(select(func.count(Asset.id)))).scalar_one()
        quota = await get_setting(s, "quota_packs", "")
    check("db: sentence bank seeded (>80)", n_sent > 80, str(n_sent))
    check("db: seed assets inserted (6)", n_assets == 6, str(n_assets))
    check("db: default quota_packs == '1'", quota == "1", quota)

    async with Session() as s:
        before = await check_bot_started(s, 424242, "somebot")
        await record_bot_start(s, 424242, "SomeBot")
        after = await check_bot_started(s, 424242, "somebot")
    check("locks: bot_starts registry round-trip", before is False and after is True)


def main() -> int:
    test_imports()
    test_suggestions()
    test_image_pipeline()
    asyncio.run(test_db_and_locks())
    if FAILURES:
        print(f"\nSMOKE FAILED: {len(FAILURES)} check(s): {FAILURES}")
        return 1
    print("\nSMOKE OK — all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
