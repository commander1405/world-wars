"""WORLD WAR REBIRTH game world facade."""
from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.errors import GameError
from core.nav import Nav
from modules.shop.catalog import CATALOG, CAT_FA, items_in_category

log = logging.getLogger(__name__)
SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "countries" / "seed_ng.json"
UN_CODE = "UN"


class World:
    def __init__(self, db, settings: Any):
        self.db = db
        self.settings = settings
        self.owner_id = int(getattr(settings, "OWNER_ID", 0) or 0)
        self.group_id = getattr(settings, "MAIN_GROUP", None)
        self.nav = Nav(db)
        self._cat = {c["item_code"]: c for c in CATALOG}

    def is_owner(self, pid: int) -> bool:
        return bool(self.owner_id and int(pid) == int(self.owner_id))

    async def bootstrap(self) -> None:
        from database.schema import apply_schema
        await apply_schema(self.db)
        now = datetime.now(timezone.utc).isoformat()
        meta = await self.db.fetchrow("SELECT * FROM world_meta WHERE id=1")
        if not meta:
            await self.db.execute(
                """
                INSERT INTO world_meta (id, started_at, war_enabled, nuclear_enabled, main_group_id, reset_count, bot_version)
                VALUES (1,$1,1,0,$2,0,$3)
                """,
                (now, self.group_id, getattr(self.settings, "BOT_VERSION", "2.0.0")),
            )
        await self._seed_catalog()
        await self._seed_countries()
        await self.ensure_un()
        await self._seed_settings()
        log.info("WORLD WAR REBIRTH ready owner_id=%s", self.owner_id)

    async def _seed_catalog(self) -> None:
        for c in CATALOG:
            exists = await self.db.fetchrow(
                "SELECT item_code FROM shop_catalog WHERE item_code=$1", (c["item_code"],)
            )
            vals = (
                c["item_code"], c.get("category"), c.get("name_fa"), c.get("description_fa"),
                float(c.get("unit_price") or 0), int(c.get("max_per_order") or 10),
                float(c.get("power_score") or 0), float(c.get("damage") or 0),
                float(c.get("defense") or 0), float(c.get("accuracy") or 0),
                int(c.get("technology_level") or 1), c.get("consumption_type") or "sortie",
                float(c.get("daily_income") or 0), float(c.get("maintenance") or 0),
                int(c.get("is_building") or 0),
            )
            if not exists:
                await self.db.execute(
                    """
                    INSERT INTO shop_catalog (
                        item_code, category, name_fa, description_fa, unit_price, max_per_order,
                        power_score, damage, defense, accuracy, technology_level, consumption_type,
                        daily_income, maintenance, is_building
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
                    """,
                    vals,
                )
            self._cat[c["item_code"]] = c

    async def _seed_countries(self) -> None:
        data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        for c in data:
            exists = await self.db.fetchrow(
                "SELECT country_code FROM countries WHERE country_code=$1", (c["code"],)
            )
            if exists:
                continue
            et = str(c.get("entity_type") or "country")
            npt = 0 if et == "group" else int(c.get("npt", 1))
            await self.db.execute(
                """
                INSERT INTO countries (
                    country_code, name_fa, name_en, flag, capital_fa, leader_fa, leader_title_fa,
                    currency_code, currency_name_fa, npt_member, owner_player_id, treasury,
                    hp, max_hp, is_destroyed, entity_type
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,NULL,0,1000,1000,0,$11)
                """,
                (
                    c["code"], c["name_fa"], c["name_en"], c["flag"], c["capital_fa"],
                    c["leader_fa"], c["leader_title_fa"], c["currency_code"], c["currency_name_fa"],
                    npt, et,
                ),
            )

    async def ensure_un(self) -> None:
        if not self.owner_id:
            return
        row = await self.db.fetchrow("SELECT * FROM countries WHERE country_code=$1", (UN_CODE,))
        now = datetime.now(timezone.utc).isoformat()
        if not row:
            await self.db.execute(
                """
                INSERT INTO countries (
                    country_code, name_fa, name_en, flag, capital_fa, leader_fa, leader_title_fa,
                    currency_code, currency_name_fa, npt_member, owner_player_id, treasury,
                    hp, max_hp, is_destroyed, claimed_at, entity_type
                ) VALUES ($1,'سازمان ملل','United Nations','🇺🇳','نیویورک','—','دبیرکل','USD','دلار',0,$2,200000000,1000,1000,0,$3,'country')
                """,
                (UN_CODE, self.owner_id, now),
            )
        else:
            await self.db.execute(
                "UPDATE countries SET owner_player_id=$1, is_destroyed=0 WHERE country_code=$2",
                (self.owner_id, UN_CODE),
            )
        p = await self.db.fetchrow("SELECT * FROM players WHERE player_id=$1", (self.owner_id,))
        if not p:
            await self.db.execute(
                "INSERT INTO players (player_id, username, display_name, country_code, created_at, last_seen_at) VALUES ($1,'owner','مالک',$2,$3,$4)",
                (self.owner_id, UN_CODE, now, now),
            )
        else:
            await self.db.execute(
                "UPDATE players SET country_code=$1 WHERE player_id=$2",
                (UN_CODE, self.owner_id),
            )

    async def _seed_settings(self) -> None:
        defaults = {
            "start_message": "به WORLD WAR REBIRTH خوش آمدید.\nکشور انتخاب کنید و رهبری را آغاز کنید.",
            "about_message": "WORLD WAR REBIRTH — نسل جدید بازی کشور‌داری چندنفره.",
            "donation_card": "—",
            "donation_card_name": "—",
            "donation_intro": "می‌توانید از توسعه بازی حمایت کنید. کاملاً اختیاری است.",
            "donation_instructions": "مبلغ را به کارت واریز کنید و درخواست ثبت کنید.",
            "donations_total": "0",
        }
        for k, v in defaults.items():
            if not await self.db.fetchrow("SELECT key FROM bot_settings WHERE key=$1", (k,)):
                await self.db.execute(
                    "INSERT INTO bot_settings (key, value) VALUES ($1,$2)", (k, v)
                )

    async def get_setting(self, key: str, default: str = "") -> str:
        row = await self.db.fetchrow("SELECT value FROM bot_settings WHERE key=$1", (key,))
        return (row["value"] if row else default) or default

    async def set_setting(self, key: str, value: str) -> None:
        if await self.db.fetchrow("SELECT key FROM bot_settings WHERE key=$1", (key,)):
            await self.db.execute("UPDATE bot_settings SET value=$1 WHERE key=$2", (value, key))
        else:
            await self.db.execute("INSERT INTO bot_settings (key, value) VALUES ($1,$2)", (key, value))

    async def touch_player(self, pid: int, username=None, display=None) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        row = await self.db.fetchrow("SELECT * FROM players WHERE player_id=$1", (pid,))
        if row:
            await self.db.execute(
                "UPDATE players SET username=COALESCE($1,username), display_name=COALESCE($2,display_name), last_seen_at=$3 WHERE player_id=$4",
                (username, display, now, pid),
            )
        else:
            await self.db.execute(
                "INSERT INTO players (player_id, username, display_name, created_at, last_seen_at) VALUES ($1,$2,$3,$4,$5)",
                (pid, username, display, now, now),
            )
        return await self.db.fetchrow("SELECT * FROM players WHERE player_id=$1", (pid,))

    async def resolve_country(self, pid: int) -> str | None:
        if self.is_owner(pid):
            return UN_CODE
        row = await self.db.fetchrow(
            "SELECT country_code FROM countries WHERE owner_player_id=$1 AND COALESCE(is_destroyed,0)=0",
            (pid,),
        )
        if row:
            return row["country_code"]
        return None

    def starting_capital(self, code: str) -> float:
        data = {c["code"]: c for c in json.loads(SEED_PATH.read_text(encoding="utf-8"))}
        mult = float(data.get(code, {}).get("capital_mult", 0.8))
        lo = float(getattr(self.settings, "STARTING_CAPITAL_MIN", 50_000_000))
        hi = float(getattr(self.settings, "STARTING_CAPITAL_MAX", 100_000_000))
        return round(random.uniform(lo, hi) * mult, 2)

    async def claim(self, pid: int, code: str) -> dict:
        code = code.upper()
        if code == UN_CODE:
            raise GameError("سازمان ملل فقط برای مالک است.")
        await self.touch_player(pid)
        if await self.resolve_country(pid):
            raise GameError("شما هم‌اکنون یک کشور دارید.")
        capital = self.starting_capital(code)
        now = datetime.now(timezone.utc).isoformat()
        async with self.db.transaction() as tx:
            c = await tx.fetchrow("SELECT * FROM countries WHERE country_code=$1", (code,))
            if not c or int(c.get("is_destroyed") or 0):
                raise GameError("کشور معتبر نیست.")
            if c.get("owner_player_id"):
                raise GameError("این کشور دارای بازیکن است.")
            await tx.execute(
                "UPDATE countries SET owner_player_id=$1, treasury=$2, claimed_at=$3, hp=1000, is_destroyed=0 WHERE country_code=$4 AND owner_player_id IS NULL",
                (pid, capital, now, code),
            )
            check = await tx.fetchrow("SELECT owner_player_id FROM countries WHERE country_code=$1", (code,))
            if not check or int(check["owner_player_id"]) != pid:
                raise GameError("کشور لحظه‌ای گرفته شد.")
            await tx.execute(
                "UPDATE players SET country_code=$1 WHERE player_id=$2", (code, pid)
            )
        return await self.db.fetchrow("SELECT * FROM countries WHERE country_code=$1", (code,))

    async def country_label(self, code: str) -> str:
        r = await self.db.fetchrow("SELECT flag, name_fa FROM countries WHERE country_code=$1", (code,))
        if not r:
            return code
        return f"{r.get('flag') or ''} {r['name_fa']}".strip()

    async def list_free_countries(self) -> list[dict]:
        return await self.db.fetch(
            """
            SELECT * FROM countries
            WHERE owner_player_id IS NULL AND COALESCE(is_destroyed,0)=0 AND country_code<>$1
            ORDER BY entity_type, name_fa
            """,
            (UN_CODE,),
        )

    async def get_country(self, code: str) -> dict | None:
        return await self.db.fetchrow("SELECT * FROM countries WHERE country_code=$1", (code,))

    async def inventory(self, code: str) -> list[dict]:
        return await self.db.fetch(
            "SELECT * FROM inventory WHERE country_code=$1 AND quantity>0 ORDER BY item_code",
            (code,),
        )

    async def add_item(self, code: str, item: str, qty: float, tx=None) -> None:
        db = tx or self.db
        row = await db.fetchrow(
            "SELECT quantity FROM inventory WHERE country_code=$1 AND item_code=$2", (code, item)
        )
        if row:
            await db.execute(
                "UPDATE inventory SET quantity=$1 WHERE country_code=$2 AND item_code=$3",
                (float(row["quantity"]) + qty, code, item),
            )
        else:
            await db.execute(
                "INSERT INTO inventory (country_code, item_code, quantity) VALUES ($1,$2,$3)",
                (code, item, qty),
            )

    async def buy_item(self, pid: int, item: str, qty: float) -> str:
        code = await self.resolve_country(pid)
        if not code:
            raise GameError("ابتدا کشور انتخاب کنید.")
        meta = self._cat.get(item)
        if not meta:
            raise GameError("آیتم نامعتبر.")
        qty = float(qty)
        if qty <= 0 or qty > float(meta.get("max_per_order") or 50):
            raise GameError("تعداد نامعتبر.")
        price = float(meta["unit_price"]) * qty
        async with self.db.transaction() as tx:
            c = await tx.fetchrow("SELECT * FROM countries WHERE country_code=$1 AND owner_player_id=$2", (code, pid))
            if not c:
                raise GameError("کشور یافت نشد.")
            treas = float(c["treasury"] or 0)
            if treas < price:
                raise GameError("موجودی کافی نیست.")
            await tx.execute(
                "UPDATE countries SET treasury=$1 WHERE country_code=$2",
                (treas - price, code),
            )
            inv = await tx.fetchrow(
                "SELECT quantity FROM inventory WHERE country_code=$1 AND item_code=$2", (code, item)
            )
            if inv:
                await tx.execute(
                    "UPDATE inventory SET quantity=$1 WHERE country_code=$2 AND item_code=$3",
                    (float(inv["quantity"]) + qty, code, item),
                )
            else:
                await tx.execute(
                    "INSERT INTO inventory (country_code, item_code, quantity) VALUES ($1,$2,$3)",
                    (code, item, qty),
                )
        return f"✅ خرید {meta.get('name_fa')} × {int(qty)}\nمبلغ: {int(price):,} تومان"

    async def daily_payout_all(self, *, force: bool = False) -> int:
        from zoneinfo import ZoneInfo
        TEHRAN = ZoneInfo(getattr(self.settings, "TIMEZONE", "Asia/Tehran"))
        today = datetime.now(TEHRAN).date().isoformat()
        base = float(getattr(self.settings, "BASE_DAILY_INCOME", 20_000_000))
        countries = await self.db.fetch(
            "SELECT * FROM countries WHERE owner_player_id IS NOT NULL AND COALESCE(is_destroyed,0)=0 AND country_code<>$1",
            (UN_CODE,),
        )
        n = 0
        for c in countries:
            code = c["country_code"]
            if not force:
                if await self.db.fetchrow(
                    "SELECT 1 AS x FROM daily_payouts WHERE country_code=$1 AND payout_date=$2",
                    (code, today),
                ):
                    continue
            amount = base + float(c.get("daily_income") or 0)
            amount = max(0.0, amount)
            async with self.db.transaction() as tx:
                live = await tx.fetchrow(
                    "SELECT treasury, owner_player_id FROM countries WHERE country_code=$1", (code,)
                )
                if not live or live.get("owner_player_id") is None:
                    continue
                await tx.execute(
                    "UPDATE countries SET treasury=$1 WHERE country_code=$2",
                    (float(live["treasury"] or 0) + amount, code),
                )
                if not force:
                    try:
                        await tx.execute(
                            "INSERT INTO daily_payouts (country_code, payout_date, amount) VALUES ($1,$2,$3)",
                            (code, today, amount),
                        )
                    except Exception:
                        continue
            n += 1
        return n

    async def war_enabled(self) -> bool:
        m = await self.db.fetchrow("SELECT war_enabled FROM world_meta WHERE id=1")
        return bool(m and int(m.get("war_enabled") or 0))

    async def set_war(self, enabled: bool) -> None:
        await self.db.execute(
            "UPDATE world_meta SET war_enabled=$1 WHERE id=1", (1 if enabled else 0,)
        )

    async def log_activity(self, kind: str, message: str, country: str | None = None, pid: int | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "INSERT INTO activity_log (kind, message, country_code, player_id, created_at) VALUES ($1,$2,$3,$4,$5)",
            (kind, message[:500], country, pid, now),
        )
