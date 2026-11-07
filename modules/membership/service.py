"""Forced channel/group membership configuration."""
from __future__ import annotations

from typing import Any

from core.errors import GameError


class MembershipService:
    def __init__(self, world: Any):
        self.w = world
        self.db = world.db

    async def list_active(self) -> list[dict]:
        return await self.db.fetch("SELECT * FROM force_membership WHERE active=1")

    async def add(self, actor: int, chat_id: str, title: str, link: str) -> str:
        if not self.w.is_owner(actor):
            raise GameError("فقط مالک")
        nid = await self.db.fetchrow("SELECT COALESCE(MAX(id),0)+1 AS id FROM force_membership")
        await self.db.execute(
            "INSERT INTO force_membership (id, chat_id, title, invite_link, active) VALUES ($1,$2,$3,$4,1)",
            (int(nid["id"]), chat_id, title, link),
        )
        return "✅ کانال/گروه اجباری اضافه شد."

    async def clear(self, actor: int) -> str:
        if not self.w.is_owner(actor):
            raise GameError("فقط مالک")
        await self.db.execute("UPDATE force_membership SET active=0")
        return "✅ عضویت اجباری غیرفعال شد."

    async def check_text(self) -> str | None:
        rows = await self.list_active()
        if not rows:
            return None
        lines = ["برای استفاده از ربات ابتدا عضو شوید:"]
        for r in rows:
            lines.append(f"• {r.get('title') or r['chat_id']}: {r.get('invite_link') or ''}")
        return "\n".join(lines)
