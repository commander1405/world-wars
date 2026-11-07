"""Peace treaty system."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.errors import GameError


class PeaceService:
    def __init__(self, world: Any):
        self.w = world
        self.db = world.db

    async def propose(self, pid: int, other: str) -> str:
        code = await self.w.resolve_country(pid)
        if not code:
            raise GameError("کشور لازم است")
        other = other.upper()
        if other == code:
            raise GameError("نامعتبر")
        exists = await self.db.fetchrow(
            """
            SELECT id FROM peace_treaties
            WHERE active=1 AND ((country_a=$1 AND country_b=$2) OR (country_a=$2 AND country_b=$1))
            """,
            (code, other),
        )
        if exists:
            raise GameError("پیمان فعال وجود دارد")
        nid = await self.db.fetchrow("SELECT COALESCE(MAX(id),0)+1 AS id FROM peace_treaties")
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "INSERT INTO peace_treaties (id, country_a, country_b, active, created_at) VALUES ($1,$2,$3,1,$4)",
            (int(nid["id"]), code, other, now),
        )
        await self.w.log_activity("peace", f"پیمان صلح {code}-{other}", code, pid)
        return "✅ پیمان صلح ثبت شد."

    async def list_for(self, code: str) -> list[dict]:
        return await self.db.fetch(
            """
            SELECT * FROM peace_treaties
            WHERE active=1 AND (country_a=$1 OR country_b=$1)
            """,
            (code,),
        )

    async def break_peace(self, pid: int, treaty_id: int) -> str:
        code = await self.w.resolve_country(pid)
        t = await self.db.fetchrow("SELECT * FROM peace_treaties WHERE id=$1", (treaty_id,))
        if not t or code not in (t["country_a"], t["country_b"]):
            raise GameError("مجاز نیستید")
        await self.db.execute("UPDATE peace_treaties SET active=0 WHERE id=$1", (treaty_id,))
        return "⚠ پیمان صلح نقض شد."
