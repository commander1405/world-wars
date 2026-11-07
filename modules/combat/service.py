"""Combat / attack system for REBIRTH — abstract strategy mechanics."""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from core.errors import GameError
from modules.shop.catalog import CATALOG


class CombatService:
    def __init__(self, world: Any):
        self.w = world
        self.db = world.db
        self._cat = {c["item_code"]: c for c in CATALOG}

    async def _cd_ok(self, code: str) -> None:
        row = await self.db.fetchrow("SELECT until_ts FROM attack_cooldowns WHERE country_code=$1", (code,))
        if not row:
            return
        try:
            until = datetime.fromisoformat(row["until_ts"].replace("Z", "+00:00"))
            if datetime.now(timezone.utc) < until:
                sec = int((until - datetime.now(timezone.utc)).total_seconds())
                raise GameError(f"خسته شدی… {sec} ثانیه صبر کن.")
        except GameError:
            raise
        except Exception:
            pass

    async def _set_cd(self, code: str, sec: int) -> None:
        until = (datetime.now(timezone.utc) + timedelta(seconds=sec)).isoformat()
        if await self.db.fetchrow("SELECT 1 AS x FROM attack_cooldowns WHERE country_code=$1", (code,)):
            await self.db.execute(
                "UPDATE attack_cooldowns SET until_ts=$1 WHERE country_code=$2", (until, code)
            )
        else:
            await self.db.execute(
                "INSERT INTO attack_cooldowns (country_code, until_ts) VALUES ($1,$2)", (code, until)
            )

    def _force_power(self, inv: list[dict], kind: str) -> tuple[float, list[str]]:
        power = 0.0
        used = []
        for r in inv:
            meta = self._cat.get(r["item_code"]) or {}
            cat = meta.get("category") or ""
            if kind == "ground" and cat not in ("ground", "defense"):
                if cat not in ("missile",):
                    continue
            if kind == "air" and cat not in ("air", "missile", "drone"):
                continue
            if kind == "sea" and cat != "sea":
                continue
            qty = float(r["quantity"] or 0)
            if qty <= 0:
                continue
            dmg = float(meta.get("damage") or meta.get("power_score") or 1)
            take = min(qty, 5.0)
            power += dmg * take
            used.append((r["item_code"], take, meta.get("name_fa", r["item_code"])))
        return power, used

    async def attack(self, pid: int, target: str, intensity: float = 1.0) -> str:
        if not await self.w.war_enabled() and not self.w.is_owner(pid):
            raise GameError("وضعیت جنگ در جهان بسته است.")
        attacker = await self.w.resolve_country(pid)
        if not attacker:
            raise GameError("کشور ندارید.")
        if attacker == target:
            raise GameError("به خودتان حمله نمی‌کنید.")
        target = target.upper()
        # legendary sleep / immunity checks could go here
        await self._cd_ok(attacker)
        def_c = await self.w.get_country(target)
        if not def_c or not def_c.get("owner_player_id") or int(def_c.get("is_destroyed") or 0):
            raise GameError("هدف معتبر نیست.")
        inv = await self.w.inventory(attacker)
        power, used = self._force_power(inv, "ground")
        if power <= 0:
            raise GameError("نیروی قابل اعزام ندارید.")
        intensity = max(0.1, min(1.0, float(intensity)))
        power *= intensity

        def_inv = await self.w.inventory(target)
        def_power = 0.0
        def_systems = []
        for r in def_inv:
            meta = self._cat.get(r["item_code"]) or {}
            if meta.get("category") != "defense":
                continue
            q = float(r["quantity"] or 0)
            if q <= 0:
                continue
            def_power += float(meta.get("defense") or meta.get("power_score") or 1) * min(q, 10)
            def_systems.append(meta.get("name_fa", r["item_code"]))

        # coverage soft cap
        coverage = min(0.75, def_power / (def_power + power + 1) * 0.9)
        raw = power * random.uniform(0.85, 1.15)
        intercepted = raw * coverage
        final_dmg = max(1.0, (raw - intercepted) * (1.0 - coverage * 0.3))
        if int(def_c.get("double_hp") or 0):
            final_dmg *= 0.5

        async with self.db.transaction() as tx:
            # consume attacker units
            for item_code, take, _name in used:
                row = await tx.fetchrow(
                    "SELECT quantity FROM inventory WHERE country_code=$1 AND item_code=$2",
                    (attacker, item_code),
                )
                if not row or float(row["quantity"]) < take * intensity:
                    raise GameError("موجودی نیرو در لحظه حمله کافی نبود.")
                left = float(row["quantity"]) - take * intensity
                await tx.execute(
                    "UPDATE inventory SET quantity=$1 WHERE country_code=$2 AND item_code=$3",
                    (left, attacker, item_code),
                )
            # defense wear
            for r in def_inv:
                meta = self._cat.get(r["item_code"]) or {}
                if meta.get("category") != "defense":
                    continue
                # random wear 1 hit counter
                pass
            live = await tx.fetchrow("SELECT hp, treasury, double_hp FROM countries WHERE country_code=$1", (target,))
            hp = float(live["hp"])
            new_hp = max(0.0, hp - final_dmg)
            loot = 0.0
            if final_dmg > 5:
                loot = min(float(live["treasury"]) * 0.05 * (final_dmg / 100), float(live["treasury"]) * 0.2)
                loot = min(loot, 50_000_000)
            await tx.execute(
                "UPDATE countries SET hp=$1, treasury=$2 WHERE country_code=$3",
                (new_hp, float(live["treasury"]) - loot, target),
            )
            if loot > 0:
                at = await tx.fetchrow("SELECT treasury FROM countries WHERE country_code=$1", (attacker,))
                await tx.execute(
                    "UPDATE countries SET treasury=$1 WHERE country_code=$2",
                    (float(at["treasury"]) + loot, attacker),
                )
            destroyed = new_hp <= 0
            if destroyed:
                await tx.execute(
                    "UPDATE countries SET owner_player_id=NULL, is_destroyed=1, treasury=0 WHERE country_code=$1",
                    (target,),
                )
            now = datetime.now(timezone.utc).isoformat()
            await tx.execute(
                "INSERT INTO wars (attacker, defender, status, created_at, report) VALUES ($1,$2,$3,$4,$5)",
                (attacker, target, "done", now, f"dmg={final_dmg:.1f}"),
            )

        sec = int(getattr(self.w.settings, "ATTACK_COOLDOWN_SEC", 120))
        await self._set_cd(attacker, sec)

        a_name = await self.w.country_label(attacker)
        d_name = await self.w.country_label(target)
        used_txt = "\n".join(f"{n}: −{take * intensity:.1f}" for _, take, n in used) or "—"
        def_txt = "، ".join(def_systems) if def_systems else "بدون پدافند فعال"
        report = (
            f"⚔️ گزارش درگیری\n\n"
            f"مهاجم: {a_name}\n"
            f"مدافع: {d_name}\n"
            f"شدت: {int(intensity*100)}٪\n"
            f"خسارت نهایی: {final_dmg:.1f}\n"
            f"رهگیری پدافند: {intercepted:.1f} (پوشش {int(coverage*100)}٪)\n"
            f"پدافند: {def_txt}\n"
            f"سلامت فعلی مدافع: {max(0, int(new_hp))}\n"
            f"غنیمت نقدی: {int(loot):,}\n"
            f"📦 مصرف مهاجم:\n{used_txt}"
        )
        if destroyed:
            report += f"\n💥 {d_name} نابود شد."
        await self.w.log_activity("attack", report[:400], attacker, pid)
        return report
