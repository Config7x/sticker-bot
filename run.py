#!/usr/bin/env python3
"""Run the sticker-maker bot:  python3 run.py   (reads .env)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.main import run  # noqa: E402

if __name__ == "__main__":
    asyncio.run(run())
