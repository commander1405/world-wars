"""P2P market listings."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.errors import GameError


class MarketService:
    def __init__(self, world: Any):
        self.w = world
        self.db = world.db

    async def list_active(self, limit: int = 30) -> list[dict]:
        return await self.db.fetch(
            "SELECT * FROM market_listings WHERE active=1 ORDER BY id DESC LIMIT $1", (limit,)
        )

    async def create(self, pid: int, item_code: str, qty: float, unit_price: float) -> dict:
        code = await self.w.resolve_country(pid)
        if not code:
            raise GameError("کشور لازم است.")
        qty = float(qty)
        unit_price = float(unit_price)
        if qty <= 0 or unit_price <= 0:
            raise GameError("مقادیر نامعتبر")
        async with self.db.transaction() as tx:
            inv = await tx.fetchrow(
                "SELECT quantity FROM inventory WHERE country_code=$1 AND item_code=$2",
                (code, item_code),
            )
            if not inv or float(inv["quantity"]) < qty:
                raise GameError("موجودی کافی نیست")
            await tx.execute(
                "UPDATE inventory SET quantity=$1 WHERE country_code=$2 AND item_code=$3",
                (float(inv["quantity"]) - qty, code, item_code),
            )
            nid = await tx.fetchrow("SELECT COALESCE(MAX(id),0)+1 AS id FROM market_listings")
            lid = int(nid["id"])
            now = datetime.now(timezone.utc).isoformat()
            await tx.execute(
                """
                INSERT INTO market_listings (id, seller_code, seller_pid, item_code, quantity, unit_price, active, created_at)
                VALUES ($1,$2,$3,$4,$5,$6,1,$7)
                """,
                (lid, code, pid, item_code, qty, unit_price, now),
            )
        return await self.db.fetchrow("SELECT * FROM market_listings WHERE id=$1", (lid,))

    async def buy(self, pid: int, listing_id: int, qty: float | None = None) -> str:
        buyer = await self.w.resolve_country(pid)
        if not buyer:
            raise GameError("کشور لازم است.")
        async with self.db.transaction() as tx:
            L = await tx.fetchrow("SELECT * FROM market_listings WHERE id=$1", (listing_id,))
            if not L or int(L["active"]) != 1:
                raise GameError("آگهی فعال نیست")
            if int(L["seller_pid"]) == pid:
                raise GameError("خرید آگهی خودتان مجاز نیست")
            take = float(L["quantity"]) if qty is None else min(float(qty), float(L["quantity"]))
            if take <= 0:
                raise GameError("تعداد نامعتبر")
            total = take * float(L["unit_price"])
            bc = await tx.fetchrow("SELECT treasury FROM countries WHERE country_code=$1", (buyer,))
            if float(bc["treasury"]) < total:
                raise GameError("پول کافی نیست")
            await tx.execute(
                "UPDATE countries SET treasury=$1 WHERE country_code=$2",
                (float(bc["treasury"]) - total, buyer),
            )
            sc = await tx.fetchrow("SELECT treasury FROM countries WHERE country_code=$1", (L["seller_code"],))
            await tx.execute(
                "UPDATE countries SET treasury=$1 WHERE country_code=$2",
                (float(sc["treasury"]) + total, L["seller_code"]),
            )
            inv = await tx.fetchrow(
                "SELECT quantity FROM inventory WHERE country_code=$1 AND item_code=$2",
                (buyer, L["item_code"]),
            )
            if inv:
                await tx.execute(
                    "UPDATE inventory SET quantity=$1 WHERE country_code=$2 AND item_code=$3",
                    (float(inv["quantity"]) + take, buyer, L["item_code"]),
                )
            else:
                await tx.execute(
                    "INSERT INTO inventory (country_code, item_code, quantity) VALUES ($1,$2,$3)",
                    (buyer, L["item_code"], take),
                )
            left = float(L["quantity"]) - take
            if left <= 0:
                await tx.execute("UPDATE market_listings SET active=0, quantity=0 WHERE id=$1", (listing_id,))
            else:
                await tx.execute("UPDATE market_listings SET quantity=$1 WHERE id=$2", (left, listing_id))
            now = datetime.now(timezone.utc).isoformat()
            await tx.execute(
                "INSERT INTO market_sales (listing_id, buyer_code, buyer_pid, quantity, total_price, created_at) VALUES ($1,$2,$3,$4,$5,$6)",
                (listing_id, buyer, pid, take, total, now),
            )
        return f"✅ خرید انجام شد. مبلغ: {int(total):,} تومان"

    async def cancel(self, pid: int, listing_id: int) -> str:
        async with self.db.transaction() as tx:
            L = await tx.fetchrow("SELECT * FROM market_listings WHERE id=$1", (listing_id,))
            if not L or int(L["seller_pid"]) != pid or int(L["active"]) != 1:
                raise GameError("آگهی قابل لغو نیست")
            inv = await tx.fetchrow(
                "SELECT quantity FROM inventory WHERE country_code=$1 AND item_code=$2",
                (L["seller_code"], L["item_code"]),
            )
            q = float(L["quantity"])
            if inv:
                await tx.execute(
                    "UPDATE inventory SET quantity=$1 WHERE country_code=$2 AND item_code=$3",
                    (float(inv["quantity"]) + q, L["seller_code"], L["item_code"]),
                )
            else:
                await tx.execute(
                    "INSERT INTO inventory (country_code, item_code, quantity) VALUES ($1,$2,$3)",
                    (L["seller_code"], L["item_code"], q),
                )
            await tx.execute("UPDATE market_listings SET active=0 WHERE id=$1", (listing_id,))
        return "✅ آگهی لغو و موجودی برگشت."
