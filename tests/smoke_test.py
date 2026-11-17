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


def test_image_pipeline() -> None:
    from PIL import Image, ImageDraw

    from app.image_pipeline import find_font, process_image, render_text_sticker

    font = find_font("")
    check("font: a Noto Arabic font is found", font is not None, str(font))

    img = Image.new("RGBA", (800, 600), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([200, 100, 600, 500], fill=(220, 40, 40, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()

    out = process_image(raw, text="سلام دنیا", style="clean",
                        use_rembg=False, font_path=font)
    check("pipeline: output is WebP", out[:4] == b"RIFF" and out[8:12] == b"WEBP")
    check("pipeline: output <= 512 KB", len(out) <= 512 * 1024, f"{len(out)} B")
    decoded = Image.open(io.BytesIO(out))
    check("pipeline: long side <= 512", max(decoded.size) <= 512, str(decoded.size))

    out2 = process_image(raw, text=None, style="neon",
                         use_rembg=False, font_path=font)
    decoded2 = Image.open(io.BytesIO(out2))
    check("pipeline: no-text variant ok, long side == 512",
          out2[:4] == b"RIFF" and max(decoded2.size) == 512, str(decoded2.size))

    out3 = render_text_sticker("مرسی!", "clean", font, "🙏")
    decoded3 = Image.open(io.BytesIO(out3))
    check("pipeline: text-only sticker ok",
          out3[:4] == b"RIFF" and len(out3) <= 512 * 1024
          and max(decoded3.size) <= 512, str(decoded3.size))


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
