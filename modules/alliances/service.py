"""Alliance system for REBIRTH."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.errors import GameError

BASE_COST = 4_000_000
MEMBER_STEP_COST = 800_000
TREASURY_STEP = 50_000_000
TREASURY_STEP_COST = 1_000_000
MAX_CREATE_COST = 7_000_000
MIN_CREATE_COST = 2_000_000


class AllianceService:
    def __init__(self, world: Any):
        self.w = world
        self.db = world.db

    def create_cost(self, member_cap: int, treasury_cap: float) -> int:
        cost = BASE_COST
        cost += max(0, member_cap - 5) * MEMBER_STEP_COST
        cost += max(0, int((treasury_cap - 100_000_000) / TREASURY_STEP)) * TREASURY_STEP_COST
        return int(max(MIN_CREATE_COST, min(MAX_CREATE_COST, cost)))

    async def my_alliance(self, country_code: str) -> dict | None:
        row = await self.db.fetchrow(
            """
            SELECT a.* FROM alliances a
            JOIN alliance_members m ON m.alliance_id=a.id
            WHERE m.country_code=$1 AND COALESCE(a.dissolved,0)=0
            """,
            (country_code,),
        )
        return row

    async def members(self, alliance_id: int) -> list[dict]:
        return await self.db.fetch(
            "SELECT * FROM alliance_members WHERE alliance_id=$1 ORDER BY joined_at",
            (alliance_id,),
        )

    async def create(self, pid: int, name: str, member_cap: int, treasury_cap: float) -> dict:
        code = await self.w.resolve_country(pid)
        if not code:
            raise GameError("ابتدا کشور انتخاب کنید.")
        if await self.my_alliance(code):
            raise GameError("شما هم‌اکنون در یک اتحاد هستید.")
        name = (name or "").strip()[:40]
        if len(name) < 2:
            raise GameError("نام اتحاد کوتاه است.")
        member_cap = max(2, min(20, int(member_cap)))
        treasury_cap = max(50_000_000, float(treasury_cap))
        cost = self.create_cost(member_cap, treasury_cap)
        now = datetime.now(timezone.utc).isoformat()
        async with self.db.transaction() as tx:
            c = await tx.fetchrow(
                "SELECT * FROM countries WHERE country_code=$1 AND owner_player_id=$2",
                (code, pid),
            )
            if not c or float(c["treasury"] or 0) < cost:
                raise GameError(f"موجودی کافی نیست. هزینه: {cost:,}")
            await tx.execute(
                "UPDATE countries SET treasury=$1 WHERE country_code=$2",
                (float(c["treasury"]) - cost, code),
            )
            nid = await tx.fetchrow("SELECT COALESCE(MAX(id),0)+1 AS id FROM alliances")
            aid = int(nid["id"])
            await tx.execute(
                """
                INSERT INTO alliances (id, name, founder_code, owner_code, member_cap, treasury_cap, treasury, created_at, dissolved)
                VALUES ($1,$2,$3,$4,$5,$6,0,$7,0)
                """,
                (aid, name, code, code, member_cap, treasury_cap, now),
            )
            await tx.execute(
                "INSERT INTO alliance_members (alliance_id, country_code, role, joined_at) VALUES ($1,$2,'owner',$3)",
                (aid, code, now),
            )
        await self.w.log_activity("alliance", f"اتحاد «{name}» ساخته شد", code, pid)
        return await self.db.fetchrow("SELECT * FROM alliances WHERE id=$1", (aid,))

    async def join(self, pid: int, alliance_id: int) -> str:
        code = await self.w.resolve_country(pid)
        if not code:
            raise GameError("ابتدا کشور انتخاب کنید.")
        if await self.my_alliance(code):
            raise GameError("قبلاً عضو اتحاد هستید.")
        a = await self.db.fetchrow(
            "SELECT * FROM alliances WHERE id=$1 AND COALESCE(dissolved,0)=0", (alliance_id,)
        )
        if not a:
            raise GameError("اتحاد یافت نشد.")
        mems = await self.members(alliance_id)
        if len(mems) >= int(a["member_cap"]):
            raise GameError("ظرفیت اتحاد پر است.")
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "INSERT INTO alliance_members (alliance_id, country_code, role, joined_at) VALUES ($1,$2,'member',$3)",
            (alliance_id, code, now),
        )
        return f"✅ به اتحاد «{a['name']}» پیوستید."

    async def leave(self, pid: int) -> str:
        code = await self.w.resolve_country(pid)
        if not code:
            raise GameError("کشور ندارید.")
        a = await self.my_alliance(code)
        if not a:
            raise GameError("عضو اتحادی نیستید.")
        if a["owner_code"] == code:
            raise GameError("مالک اتحاد نمی‌تواند خارج شود؛ ابتدا اتحاد را منحل کنید.")
        await self.db.execute(
            "DELETE FROM alliance_members WHERE alliance_id=$1 AND country_code=$2",
            (a["id"], code),
        )
        return "✅ از اتحاد خارج شدید."

    async def dissolve(self, pid: int) -> str:
        code = await self.w.resolve_country(pid)
        a = await self.my_alliance(code)
        if not a or a["owner_code"] != code:
            raise GameError("فقط مالک اتحاد می‌تواند منحل کند.")
        await self.db.execute("UPDATE alliances SET dissolved=1 WHERE id=$1", (a["id"],))
        await self.db.execute("DELETE FROM alliance_members WHERE alliance_id=$1", (a["id"],))
        return "✅ اتحاد منحل شد."

    async def list_open(self) -> list[dict]:
        return await self.db.fetch(
            "SELECT * FROM alliances WHERE COALESCE(dissolved,0)=0 ORDER BY id DESC LIMIT 30"
        )

    async def deposit(self, pid: int, amount: float) -> str:
        code = await self.w.resolve_country(pid)
        a = await self.my_alliance(code)
        if not a:
            raise GameError("عضو اتحاد نیستید.")
        amount = float(amount)
        if amount <= 0:
            raise GameError("مبلغ نامعتبر")
        async with self.db.transaction() as tx:
            c = await tx.fetchrow("SELECT treasury FROM countries WHERE country_code=$1", (code,))
            if float(c["treasury"]) < amount:
                raise GameError("موجودی کافی نیست")
            new_t = float(a["treasury"]) + amount
            if new_t > float(a["treasury_cap"]):
                raise GameError("ظرفیت خزانه اتحاد پر است")
            await tx.execute(
                "UPDATE countries SET treasury=$1 WHERE country_code=$2",
                (float(c["treasury"]) - amount, code),
            )
            await tx.execute("UPDATE alliances SET treasury=$1 WHERE id=$2", (new_t, a["id"]))
        return f"✅ {int(amount):,} به خزانه اتحاد واریز شد."
