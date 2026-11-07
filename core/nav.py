"""Central navigation stack: back returns to previous menu, home clears stack."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


class Nav:
    def __init__(self, db):
        self.db = db

    async def get_stack(self, pid: int) -> list[dict]:
        row = await self.db.fetchrow("SELECT stack_json FROM nav_state WHERE player_id=$1", (pid,))
        if not row or not row.get("stack_json"):
            return []
        try:
            return json.loads(row["stack_json"])
        except Exception:
            return []

    async def set_stack(self, pid: int, stack: list[dict]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        raw = json.dumps(stack, ensure_ascii=False)
        exists = await self.db.fetchrow("SELECT player_id FROM nav_state WHERE player_id=$1", (pid,))
        if exists:
            await self.db.execute(
                "UPDATE nav_state SET stack_json=$1, updated_at=$2 WHERE player_id=$3",
                (raw, now, pid),
            )
        else:
            await self.db.execute(
                "INSERT INTO nav_state (player_id, stack_json, updated_at) VALUES ($1,$2,$3)",
                (pid, raw, now),
            )

    async def push(self, pid: int, screen: str, data: dict | None = None) -> None:
        stack = await self.get_stack(pid)
        stack.append({"screen": screen, "data": data or {}})
        if len(stack) > 20:
            stack = stack[-20:]
        await self.set_stack(pid, stack)

    async def pop(self, pid: int) -> dict | None:
        stack = await self.get_stack(pid)
        if not stack:
            return None
        stack.pop()
        await self.set_stack(pid, stack)
        return stack[-1] if stack else None

    async def current(self, pid: int) -> dict | None:
        stack = await self.get_stack(pid)
        return stack[-1] if stack else None

    async def clear(self, pid: int) -> None:
        await self.set_stack(pid, [])
