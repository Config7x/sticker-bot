"""Entry point: build the dispatcher and start long polling."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from .config import config
from .db import init_db
from .handlers import admin, buildforme, menu, mypacks, wizard
from .middlewares import LockMiddleware, UserMiddleware


async def run() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    await init_db()
    bot = Bot(token=config.require_token())
    dp = Dispatcher(storage=MemoryStorage())

    user_mw, lock_mw = UserMiddleware(), LockMiddleware()
    for target in (dp.message, dp.callback_query):
        target.outer_middleware(user_mw)
        target.outer_middleware(lock_mw)

    # State-filtered routers first, generic menu last.
    dp.include_routers(admin.router, wizard.router, buildforme.router,
                       mypacks.router, menu.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
