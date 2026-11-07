"""WORLD WAR REBIRTH entrypoint — Termux / local."""
from __future__ import annotations

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("rebirth")

for name in ("httpx", "httpcore", "asyncio", "bale", "aiohttp"):
    logging.getLogger(name).setLevel(logging.WARNING)


def load_settings():
    try:
        import config as cfg
    except ImportError:
        log.error("فایل config.py پیدا نشد. از config.example.py کپی کنید.")
        sys.exit(1)
    return cfg


async def async_main():
    settings = load_settings()
    token = (getattr(settings, "BALE_TOKEN", None) or "").strip()
    if not token:
        log.error("BALE_TOKEN خالی است. آن را در config.py قرار دهید.")
        sys.exit(1)

    from database import create_database
    from core.world import World
    from handlers.router import register_handlers
    from bale import Bot

    db_path = getattr(settings, "DATABASE_PATH", "db/world_war_rebirth.db")
    log.info("DATABASE=%s", db_path)
    db = await create_database(db_path)
    world = World(db, settings)
    await world.bootstrap()

    bot = Bot(token)
    register_handlers(bot, world)

    async def daily_loop():
        from datetime import datetime
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(getattr(settings, "TIMEZONE", "Asia/Tehran"))
        while True:
            try:
                now = datetime.now(tz)
                today = now.date().isoformat()
                meta = await world.db.fetchrow("SELECT last_daily_date FROM world_meta WHERE id=1")
                last = (meta or {}).get("last_daily_date")
                if last != today and now.hour == 0:
                    n = await world.daily_payout_all()
                    await world.db.execute(
                        "UPDATE world_meta SET last_daily_date=$1 WHERE id=1", (today,)
                    )
                    if n:
                        log.info("daily payout n=%s", n)
                elif last != today and now.hour > 0:
                    n = await world.daily_payout_all()
                    await world.db.execute(
                        "UPDATE world_meta SET last_daily_date=$1 WHERE id=1", (today,)
                    )
                    if n:
                        log.info("daily catch-up n=%s", n)
            except Exception:
                log.exception("daily_loop")
            await asyncio.sleep(60)

    asyncio.create_task(daily_loop())
    log.info("Starting bot.connect() REBIRTH %s", getattr(settings, "BOT_VERSION", ""))
    async with bot:
        await bot.connect()


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
