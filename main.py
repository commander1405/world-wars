"""WORLD WAR REBIRTH entrypoint — same lifecycle as legacy WORLD-WAR (python-bale-bot 2.5.0)."""
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

for name in ("httpx", "httpcore", "asyncio", "aiohttp", "bale.request"):
    logging.getLogger(name).setLevel(logging.WARNING)


def load_settings():
    try:
        import config as cfg
    except ImportError:
        log.error(
            "فایل config.py پیدا نشد.\n"
            "کپی کنید: cp config.example.py config.py\n"
            "سپس BALE_TOKEN و OWNER_ID را در config.py پر کنید."
        )
        sys.exit(1)
    return cfg


async def async_main() -> None:
    settings = load_settings()
    token = (getattr(settings, "BALE_TOKEN", None) or getattr(settings, "BOT_TOKEN", None) or "").strip()
    if not token:
        log.error("BALE_TOKEN در config.py خالی است.")
        sys.exit(1)

    from bale import Bot
    from database import create_database
    from core.world import World
    from handlers.router import register_handlers

    db_path = getattr(settings, "DATABASE_PATH", "db/world_war_rebirth.db")
    log.info("DATABASE=%s", db_path)
    db = await create_database(db_path)
    world = World(db, settings)
    await world.bootstrap()
    log.info(
        "World ready version=%s owner_id=%s",
        getattr(settings, "BOT_VERSION", "2.0.0-rebirth"),
        world.owner_id,
    )

    bot = Bot(token)
    register_handlers(bot, world)

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
                log.exception("background loop")
            await asyncio.sleep(60)

    bg = asyncio.create_task(background(), name="rebirth-background")

    # Exact legacy WORLD-WAR lifecycle for python-bale-bot 2.5.0:
    # async with bot:  -> HTTP start
    # await bot.connect() -> get_me() + updater.start() (polling forever)
    try:
        log.info("Starting bot.connect() REBIRTH %s", getattr(settings, "BOT_VERSION", ""))
        async with bot:
            me = await bot.get_me()
            log.info(
                "Authentication successful bot=@%s id=%s",
                getattr(me, "username", None),
                getattr(me, "user_id", None) or getattr(me, "id", None),
            )
            # connect = get_me + updater.start (blocks on polling)
            await bot.updater.start()
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt")
    except Exception:
        log.exception("Bot connection failed")
        raise
    finally:
        bg.cancel()
        try:
            await bg
        except Exception:
            pass
        try:
            if getattr(bot.updater, "running", False):
                await bot.updater.stop()
        except Exception:
            pass
        await db.close()
        log.info("Shutdown complete")


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        log.info("stop")


if __name__ == "__main__":
    main()
