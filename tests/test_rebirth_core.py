import asyncio
import os
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class FakeSettings:
    OWNER_ID = 1967315238
    MAIN_GROUP = None
    BOT_VERSION = "test"
    TIMEZONE = "Asia/Tehran"
    BASE_DAILY_INCOME = 20_000_000
    STARTING_CAPITAL_MIN = 50_000_000
    STARTING_CAPITAL_MAX = 70_000_000


class TestRebirth(unittest.TestCase):
    def test_claim_and_buy(self):
        async def run():
            from database import create_database
            from core.world import World
            from core.errors import GameError

            fd, path = tempfile.mkstemp(suffix=".db")
            os.close(fd)
            try:
                db = await create_database(path)
                w = World(db, FakeSettings())
                await w.bootstrap()
                free = await w.list_free_countries()
                self.assertTrue(len(free) > 0)
                code = free[0]["country_code"]
                c = await w.claim(111, code)
                self.assertEqual(int(c["owner_player_id"]), 111)
                self.assertGreater(float(c["treasury"]), 0)
                # buy infantry if exists
                from modules.shop.catalog import CATALOG
                item = CATALOG[0]["item_code"]
                msg = await w.buy_item(111, item, 1)
                self.assertIn("خرید", msg)
                with self.assertRaises(GameError):
                    await w.claim(111, free[1]["country_code"])
                await db.close()
            finally:
                try:
                    os.unlink(path)
                except Exception:
                    pass

        asyncio.run(run())

    def test_schema_independent(self):
        async def run():
            from database import create_database
            from core.world import World
            fd, path = tempfile.mkstemp(suffix=".db")
            os.close(fd)
            db = await create_database(path)
            w = World(db, FakeSettings())
            await w.bootstrap()
            # empty player money not from legacy
            n = await db.fetchrow("SELECT COUNT(*) AS c FROM players WHERE player_id<>1967315238")
            self.assertEqual(int(n["c"]), 0)
            await db.close()
            os.unlink(path)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
