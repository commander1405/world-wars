import asyncio
import os
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class S:
    OWNER_ID = 1967315238
    MAIN_GROUP = None
    BOT_VERSION = "test"
    TIMEZONE = "Asia/Tehran"
    BASE_DAILY_INCOME = 20_000_000
    STARTING_CAPITAL_MIN = 50_000_000
    STARTING_CAPITAL_MAX = 70_000_000
    ATTACK_COOLDOWN_SEC = 1


class TestSystems(unittest.TestCase):
    def test_alliance_market_combat(self):
        async def run():
            from database import create_database
            from core.world import World
            from core.errors import GameError

            fd, path = tempfile.mkstemp(suffix=".db")
            os.close(fd)
            db = await create_database(path)
            w = World(db, S())
            await w.bootstrap()
            free = await w.list_free_countries()
            c1, c2 = free[0]["country_code"], free[1]["country_code"]
            await w.claim(10, c1)
            await w.claim(20, c2)
            # give infantry
            await w.add_item(c1, "g_inf", 20)
            await w.add_item(c2, "g_inf", 5)
            a = await w.alliances.create(10, "TestAlly", 5, 200_000_000)
            self.assertTrue(a["id"])
            await w.alliances.join(20, a["id"])
            # market
            await w.add_item(c1, "g_inf", 10)
            L = await w.market.create(10, "g_inf", 2, 1000)
            # boost buyer money
            await db.execute("UPDATE countries SET treasury=treasury+100000 WHERE country_code=$1", (c2,))
            msg = await w.market.buy(20, L["id"])
            self.assertIn("خرید", msg)
            # war on
            await w.set_war(True)
            await w.add_item(c1, "g_inf", 30)
            report = await w.combat.attack(10, c2, 0.5)
            self.assertIn("گزارش", report)
            await db.close()
            os.unlink(path)

        asyncio.run(run())

    def test_legendary_referral(self):
        async def run():
            from database import create_database
            from core.world import World

            fd, path = tempfile.mkstemp(suffix=".db")
            os.close(fd)
            db = await create_database(path)
            w = World(db, S())
            await w.bootstrap()
            free = await w.list_free_countries()
            await w.claim(30, free[0]["country_code"])
            await db.execute("UPDATE countries SET treasury=100000000 WHERE owner_player_id=30")
            await w.legendary.ensure()
            cat = await w.legendary.catalog()
            self.assertTrue(cat)
            await w.legendary.buy(30, cat[0]["item_code"])
            inv = await w.legendary.inventory(30)
            self.assertTrue(inv)
            code = await w.referral.get_or_create_code(30)
            await w.claim(31, free[1]["country_code"])
            await w.referral.apply(31, code)
            await db.close()
            os.unlink(path)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
