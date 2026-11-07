"""Referral codes and rewards."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from core.errors import GameError

INVITEE_REWARD = 2_000_000
INVITER_REWARD = 15_000_000


class ReferralService:
    def __init__(self, world: Any):
        self.w = world
        self.db = world.db

    async def get_or_create_code(self, pid: int) -> str:
        row = await self.db.fetchrow("SELECT code FROM referral_codes WHERE player_id=$1", (pid,))
        if row:
            return row["code"]
        code = secrets.token_hex(3).upper()
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "INSERT INTO referral_codes (player_id, code, created_at) VALUES ($1,$2,$3)",
            (pid, code, now),
        )
        return code

    async def apply(self, invitee: int, code: str) -> str:
        code = (code or "").strip().upper()
        if not code:
            raise GameError("کد خالی است")
        if await self.db.fetchrow("SELECT invitee_id FROM referrals WHERE invitee_id=$1", (invitee,)):
            raise GameError("قبلاً دعوت ثبت شده")
        inv = await self.db.fetchrow("SELECT player_id FROM referral_codes WHERE code=$1", (code,))
        if not inv:
            raise GameError("کد نامعتبر")
        inviter = int(inv["player_id"])
        if inviter == invitee:
            raise GameError("خوددعوتی مجاز نیست")
        now = datetime.now(timezone.utc).isoformat()
        # pay to countries if exist
        async with self.db.transaction() as tx:
            await tx.execute(
                "INSERT INTO referrals (invitee_id, inviter_id, code, paid, created_at) VALUES ($1,$2,$3,1,$4)",
                (invitee, inviter, code, now),
            )
            for pid, amount in ((invitee, INVITEE_REWARD), (inviter, INVITER_REWARD)):
                c = await tx.fetchrow(
                    "SELECT country_code, treasury FROM countries WHERE owner_player_id=$1 AND COALESCE(is_destroyed,0)=0",
                    (pid,),
                )
                if c:
                    await tx.execute(
                        "UPDATE countries SET treasury=$1 WHERE country_code=$2",
                        (float(c["treasury"]) + amount, c["country_code"]),
                    )
        return f"✅ دعوت ثبت شد. پاداش دعوت‌شونده {INVITEE_REWARD:,} — دعوت‌کننده {INVITER_REWARD:,}"
