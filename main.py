"""WORLD WAR REBIRTH entrypoint — correct python-bale-bot 2.x lifecycle."""
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

for name in ("httpx", "httpcore", "asyncio", "aiohttp"):
    logging.getLogger(name).setLevel(logging.WARNING)


def load_settings():
    try:
        import config as cfg
    except ImportError:
        log.error("config.py missing — copy from config.example.py")
        sys.exit(1)
    return cfg


async def async_main() -> None:
    settings = load_settings()
    token = (getattr(settings, "BALE_TOKEN", None) or "").strip()
    if not token:
        log.error("BALE_TOKEN empty in config.py")
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
    log.info("World ready version=%s owner_id=%s", getattr(settings, "BOT_VERSION", ""), world.owner_id)

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

    bg_task = asyncio.create_task(background(), name="rebirth-background")

    # Official lifecycle (python-bale-bot 2.x):
    # async with bot -> HTTP start
    # get_me -> auth
    # updater.setup + fetcher + start_polling -> receive updates
    # Handlers must be MessageHandler / BaseHandler — NOT listen("message")
    try:
        log.info("Connection starting (HTTP + getMe + polling)…")
        async with bot:
            me = await bot.get_me()
            uname = getattr(me, "username", None)
            uid = getattr(me, "user_id", None) or getattr(me, "id", None)
            log.info("Authentication successful bot=@%s id=%s", uname, uid)

            await bot.updater.setup()
            # Start queue consumer that process_update -> handlers
            asyncio.create_task(bot._updater_fetcher_wrapper(), name="Bot:updater_fetcher")
            log.info("Update receiver started")

            await bot.updater.start_polling()
            log.info("Polling worker running — bot is live. Send /start in private chat.")

            # start_polling returns after scheduling worker; keep process alive
            stop = asyncio.Event()
            try:
                await stop.wait()
            except asyncio.CancelledError:
                raise
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt — shutting down")
    except Exception:
        log.exception("Bot connection / polling failed")
        raise
    finally:
        bg_task.cancel()
        try:
            await bg_task
        except Exception:
            pass
        try:
            if bot.updater and getattr(bot.updater, "_running", False):
                await bot.updater.stop()
        except Exception:
            log.exception("updater stop")
        await db.close()
        log.info("Shutdown complete")


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        log.info("stop")


if __name__ == "__main__":
    main()
