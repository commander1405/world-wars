"""Legendary items — permanent player ownership."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.errors import GameError

DEFAULTS = [
    {"item_code": "leg_samovar", "name_fa": "سماور", "description_fa": "افزایش درآمد موقت", "price": 25_000_000, "uses_per_unit": 20, "effect_type": "income_boost", "duration_sec": 3600},
    {"item_code": "leg_anime_girl", "name_fa": "دختر انیمه‌ای", "description_fa": "مصونیت موقت حمله", "price": 40_000_000, "uses_per_unit": 20, "effect_type": "attack_immunity", "duration_sec": 1800},
    {"item_code": "leg_pillow", "name_fa": "بالش انیمه‌ای", "description_fa": "فلج خواب هدف", "price": 35_000_000, "uses_per_unit": 20, "effect_type": "sleep", "duration_sec": 900},
    {"item_code": "leg_card", "name_fa": "کارت پایان خدمت", "description_fa": "کاهش هزینه نظامی", "price": 20_000_000, "uses_per_unit": 20, "effect_type": "discount", "duration_sec": 3600},
    {"item_code": "leg_femboy", "name_fa": "فمبوی", "description_fa": "ممنوعیت اتم موقت", "price": 50_000_000, "uses_per_unit": 20, "effect_type": "nuke_ban", "duration_sec": 3600},
]


class LegendaryService:
    def __init__(self, world: Any):
        self.w = world
        self.db = world.db

    async def ensure(self) -> None:
        for d in DEFAULTS:
            if not await self.db.fetchrow("SELECT item_code FROM legendary_defs WHERE item_code=$1", (d["item_code"],)):
                await self.db.execute(
                    """
                    INSERT INTO legendary_defs (item_code, name_fa, description_fa, price, uses_per_unit, effect_type, duration_sec, active)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,1)
                    """,
                    (d["item_code"], d["name_fa"], d["description_fa"], d["price"], d["uses_per_unit"], d["effect_type"], d["duration_sec"]),
                )

    async def catalog(self) -> list[dict]:
        return await self.db.fetch("SELECT * FROM legendary_defs WHERE active=1 ORDER BY name_fa")

    async def buy(self, pid: int, item_code: str) -> str:
        d = await self.db.fetchrow("SELECT * FROM legendary_defs WHERE item_code=$1 AND active=1", (item_code,))
        if not d:
            raise GameError("آیتم نامعتبر")
        price = float(d["price"])
        code = await self.w.resolve_country(pid)
        if not code:
            raise GameError("کشور لازم است")
        async with self.db.transaction() as tx:
            c = await tx.fetchrow("SELECT treasury FROM countries WHERE country_code=$1 AND owner_player_id=$2", (code, pid))
            if not c or float(c["treasury"]) < price:
                raise GameError("پول کافی نیست")
            await tx.execute(
                "UPDATE countries SET treasury=$1 WHERE country_code=$2",
                (float(c["treasury"]) - price, code),
            )
            nid = await tx.fetchrow("SELECT COALESCE(MAX(id),0)+1 AS id FROM player_legendary")
            now = datetime.now(timezone.utc).isoformat()
            await tx.execute(
                "INSERT INTO player_legendary (id, player_id, item_code, uses_left, acquired_at) VALUES ($1,$2,$3,$4,$5)",
                (int(nid["id"]), pid, item_code, int(d["uses_per_unit"]), now),
            )
        return f"✅ {d['name_fa']} خریداری شد ({d['uses_per_unit']} استفاده)."

    async def inventory(self, pid: int) -> list[dict]:
        return await self.db.fetch(
            "SELECT * FROM player_legendary WHERE player_id=$1 AND uses_left>0 ORDER BY id",
            (pid,),
        )
