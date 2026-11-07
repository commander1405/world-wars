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
        log.error("config.py missing — copy config.example.py")
        sys.exit(1)
    return cfg


async def async_main():
    settings = load_settings()
    token = (getattr(settings, "BALE_TOKEN", None) or "").strip()
    if not token:
        log.error("BALE_TOKEN empty — set it in config.py (never commit the token)")
        sys.exit(1)

    from database import create_database
    from core.world import World
    from handlers.router import register_handlers
    from bale import Bot

    db_path = getattr(settings, "DATABASE_PATH", "db/world_war_rebirth.db")
    log.info("Connection starting… DATABASE=%s", db_path)
    db = await create_database(db_path)
    world = World(db, settings)
    await world.bootstrap()
    log.info("World bootstrap complete version=%s", getattr(settings, "BOT_VERSION", ""))

    bot = Bot(token)
    register_handlers(bot, world)
    log.info("Handlers registered — authentication via Bot() constructed")

    async def background():
        from datetime import datetime
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(getattr(settings, "TIMEZONE", "Asia/Tehran"))
        while True:
            try:
                now = datetime.now(tz)
                today = now.date().isoformat()
                meta = await world.db.fetchrow("SELECT last_daily_date FROM world_meta WHERE id=1")
                last = (meta or {}).get("last_daily_date")
                if last != today:
                    n = await world.daily_payout_all()
                    await world.db.execute(
                        "UPDATE world_meta SET last_daily_date=$1 WHERE id=1", (today,)
                    )
                    if n:
                        log.info("Daily payout countries=%s", n)
                try:
                    await world.workshop.tick_jobs()
                except Exception:
                    log.exception("workshop tick")
            except Exception:
                log.exception("background")
            await asyncio.sleep(60)

    asyncio.create_task(background())
    log.info("Starting bot.connect() / update receiver…")
    try:
        async with bot:
            log.info("Bot context entered — polling updates")
            await bot.connect()
    except Exception:
        log.exception("bot connection failed")
        raise
    finally:
        await db.close()
        log.info("Database closed")


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
