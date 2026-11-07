"""Abstract nuclear workshop / research progression (game fiction)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.errors import GameError


class WorkshopService:
    def __init__(self, world: Any):
        self.w = world
        self.db = world.db

    async def status(self, code: str) -> dict:
        row = await self.db.fetchrow("SELECT * FROM workshop WHERE country_code=$1", (code,))
        if not row:
            await self.db.execute(
                "INSERT INTO workshop (country_code, level, uranium, tech_level) VALUES ($1,1,0,0)",
                (code,),
            )
            row = await self.db.fetchrow("SELECT * FROM workshop WHERE country_code=$1", (code,))
        return row

    async def start_research(self, pid: int, job_type: str = "tech") -> str:
        code = await self.w.resolve_country(pid)
        if not code:
            raise GameError("کشور لازم است")
        cost = 5_000_000 if job_type == "tech" else 8_000_000
        st = await self.status(code)
        async with self.db.transaction() as tx:
            c = await tx.fetchrow("SELECT treasury FROM countries WHERE country_code=$1", (code,))
            if float(c["treasury"]) < cost:
                raise GameError("پول کافی نیست")
            await tx.execute(
                "UPDATE countries SET treasury=$1 WHERE country_code=$2",
                (float(c["treasury"]) - cost, code),
            )
            nid = await tx.fetchrow("SELECT COALESCE(MAX(id),0)+1 AS id FROM workshop_jobs")
            now = datetime.now(timezone.utc)
            fin = now + timedelta(hours=2)
            await tx.execute(
                """
                INSERT INTO workshop_jobs (id, country_code, job_type, progress, target, cost_paid, started_at, finishes_at, completed)
                VALUES ($1,$2,$3,0,100,$4,$5,$6,0)
                """,
                (int(nid["id"]), code, job_type, cost, now.isoformat(), fin.isoformat()),
            )
        return f"✅ پژوهش «{job_type}» شروع شد. هزینه {cost:,} تومان — حدود ۲ ساعت."

    async def tick_jobs(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        rows = await self.db.fetch(
            "SELECT * FROM workshop_jobs WHERE completed=0 AND finishes_at<=$1", (now,)
        )
        n = 0
        for j in rows:
            await self.db.execute("UPDATE workshop_jobs SET completed=1, progress=100 WHERE id=$1", (j["id"],))
            if j["job_type"] == "tech":
                await self.db.execute(
                    "UPDATE workshop SET tech_level=tech_level+1 WHERE country_code=$1",
                    (j["country_code"],),
                )
            elif j["job_type"] == "uranium":
                await self.db.execute(
                    "UPDATE workshop SET uranium=uranium+10 WHERE country_code=$1",
                    (j["country_code"],),
                )
            n += 1
        return n
