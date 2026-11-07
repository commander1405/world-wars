"""Async SQLite adapter for WORLD WAR REBIRTH (stdlib sqlite3 + asyncio)."""
from __future__ import annotations

import asyncio
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)
_PARAM = re.compile(r"\$\d+")


def _convert(sql: str) -> str:
    return _PARAM.sub("?", sql)


class _Tx:
    def __init__(self, db: "Database"):
        self.db = db

    async def execute(self, sql: str, params: tuple | list = ()):
        return await self.db.execute(sql, params, _commit=False)

    async def fetchrow(self, sql: str, params: tuple | list = ()):
        return await self.db.fetchrow(sql, params)

    async def fetch(self, sql: str, params: tuple | list = ()):
        return await self.db.fetch(sql, params)


class _TxCtx:
    def __init__(self, db: "Database"):
        self.db = db
        self._tx = _Tx(db)

    async def __aenter__(self):
        await self.db.execute("BEGIN", _commit=False)
        return self._tx

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type:
            await self.db.execute("ROLLBACK", _commit=False)
        else:
            await self.db.execute("COMMIT", _commit=False)
        return False


class Database:
    def __init__(self, path: str):
        self.path = path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)

        def _open():
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                conn.execute("PRAGMA journal_mode=WAL")
            except Exception:
                pass
            conn.commit()
            return conn

        self._conn = await asyncio.to_thread(_open)
        log.info("SQLite ready at %s", self.path)

    async def close(self) -> None:
        if self._conn:
            await asyncio.to_thread(self._conn.close)
            self._conn = None

    def transaction(self) -> _TxCtx:
        return _TxCtx(self)

    async def execute(self, sql: str, params: tuple | list = (), _commit: bool = True) -> None:
        assert self._conn
        q = _convert(sql)

        def _run():
            self._conn.execute(q, tuple(params))
            if _commit and not q.strip().upper().startswith(("BEGIN", "COMMIT", "ROLLBACK")):
                self._conn.commit()

        async with self._lock:
            await asyncio.to_thread(_run)

    async def fetchrow(self, sql: str, params: tuple | list = ()) -> Optional[dict]:
        assert self._conn
        q = _convert(sql)

        def _run():
            cur = self._conn.execute(q, tuple(params))
            row = cur.fetchone()
            return dict(row) if row else None

        async with self._lock:
            return await asyncio.to_thread(_run)

    async def fetch(self, sql: str, params: tuple | list = ()) -> list[dict]:
        assert self._conn
        q = _convert(sql)

        def _run():
            cur = self._conn.execute(q, tuple(params))
            return [dict(r) for r in cur.fetchall()]

        async with self._lock:
            return await asyncio.to_thread(_run)


async def create_database(path: str) -> Database:
    db = Database(path)
    await db.connect()
    return db
