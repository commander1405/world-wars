"""Bale message/callback router for WORLD WAR REBIRTH."""
from __future__ import annotations

import logging
from typing import Any

from bale import Message
from core.errors import GameError
from core.world import World, UN_CODE
from keyboards.main import (
    main_kb, ik, back_home, MAIN_LABELS,
    BTN_COUNTRY, BTN_ECO, BTN_BUILD, BTN_ARMY, BTN_DIPLO, BTN_MARKET,
    BTN_ITEMS, BTN_RANK, BTN_NEWS, BTN_SETTINGS, BTN_DONATE, BTN_OWNER, BTN_PICK, BTN_HOME,
)
from modules.shop.catalog import CAT_FA, items_in_category

log = logging.getLogger(__name__)
_pending: dict[int, dict] = {}


def _uid(obj) -> int | None:
    u = getattr(obj, "author", None) or getattr(obj, "from_user", None) or getattr(obj, "user", None)
    if not u:
        return None
    raw = getattr(u, "user_id", None) or getattr(u, "id", None)
    try:
        return int(raw)
    except Exception:
        return None


def _is_private(message) -> bool:
    chat = getattr(message, "chat", None) or getattr(message, "get_chat", lambda: None)()
    if not chat:
        return True
    t = getattr(chat, "type", None) or getattr(chat, "chat_type", None)
    return str(t).lower() in ("private", "prv", "1", "ChatType.PRIVATE")


async def reply(message, text: str, components=None):
    try:
        if components is not None:
            await message.reply(text[:3500], components=components)
        else:
            await message.reply(text[:3500])
    except Exception:
        log.exception("reply")


def register_handlers(bot, world: World):
    @bot.listen("message")
    async def on_message(message: Message):
        try:
            await _on_message(bot, world, message)
        except Exception:
            log.exception("on_message")

    @bot.listen("callback")
    async def on_callback(callback):
        try:
            await _on_callback(bot, world, callback)
        except Exception:
            log.exception("on_callback")


async def _on_message(bot, world: World, message: Message):
    pid = _uid(message)
    if not pid:
        return
    text = (getattr(message, "text", None) or "").strip()
    if not text:
        return

    private = _is_private(message)
    owner = world.is_owner(pid)
    author = getattr(message, "author", None) or getattr(message, "from_user", None)
    uname = getattr(author, "username", None) if author else None
    dname = getattr(author, "first_name", None) or getattr(author, "name", None) if author else None
    await world.touch_player(pid, uname, dname)

    # Group: only lightweight /start
    if not private:
        if text in ("/start", "شروع"):
            await reply(message, "برای بازی به پیوی ربات مراجعه کنید.")
        return

    # Pending text input
    if pid in _pending:
        st = _pending[pid]
        kind = st.get("kind")
        if text in ("لغو", "انصراف", "/cancel"):
            _pending.pop(pid, None)
            await reply(message, "لغو شد.", main_kb(owner))
            return
        if kind == "donation_amount":
            raw = text.replace(",", "").replace("،", "").replace(" ", "")
            raw = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
            try:
                amount = float(raw)
            except Exception:
                await reply(message, "فقط عدد بنویس. مثال: 50000")
                return
            if amount < 1000:
                await reply(message, "حداقل ۱۰۰۰ تومان")
                return
            did = await _submit_donation(world, pid, amount, uname, dname)
            _pending.pop(pid, None)
            await reply(message, f"✅ درخواست حمایت #{did} ثبت شد.", main_kb(owner))
            if world.owner_id:
                try:
                    await bot.send_message(
                        int(world.owner_id),
                        f"💎 حمایت جدید #{did}\nکاربر: {dname or uname or pid}\nمبلغ: {int(amount):,}",
                        components=ik([[("✅ تأیید", f"don:ok:{did}"), ("❌ رد", f"don:no:{did}")]]),
                    )
                except Exception:
                    pass
            return
        if kind == "buy_qty":
            try:
                qty = float(text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")))
                item = st.get("item")
                msg = await world.buy_item(pid, item, qty)
                _pending.pop(pid, None)
                await reply(message, msg, main_kb(owner))
            except GameError as e:
                await reply(message, f"❌ {e}")
            except Exception as e:
                await reply(message, f"❌ {e}")
            return

    if text in ("/start", "شروع", "منو", "menu", BTN_HOME):
        await world.nav.clear(pid)
        start = await world.get_setting("start_message")
        code = await world.resolve_country(pid)
        extra = f"\nکشور شما: {await world.country_label(code)}" if code else "\nهنوز کشور ندارید — 🗺 انتخاب کشور"
        await reply(message, f"{start}{extra}", main_kb(owner))
        return

    if text == BTN_PICK:
        await world.nav.push(pid, "pick")
        free = await world.list_free_countries()
        if not free:
            await reply(message, "کشور آزادی نیست.", main_kb(owner))
            return
        rows = []
        for c in free[:40]:
            tag = "گروهک" if c.get("entity_type") == "group" else "کشور"
            rows.append([(f"{c.get('flag','')} {c['name_fa']} ({tag})", f"claim:{c['country_code']}")])
        rows.append(back_home())
        await reply(message, "کشور یا گروهک آزاد را انتخاب کنید:", ik(rows))
        return

    if text == BTN_COUNTRY:
        await world.nav.push(pid, "country")
        code = await world.resolve_country(pid)
        if not code:
            await reply(message, "ابتدا کشور انتخاب کنید.", ik([[(BTN_PICK, "nav:pick")], back_home()]))
            return
        c = await world.get_country(code)
        text_out = (
            f"🌍 {await world.country_label(code)}\n"
            f"خزانه: {int(float(c['treasury'])):,} تومان\n"
            f"سلامت: {int(float(c['hp']))}/{int(float(c['max_hp']))}\n"
            f"NPT: {'عضو' if int(c.get('npt_member') or 0) else 'غیرعضو'}\n"
            f"نوع: {'گروهک' if c.get('entity_type')=='group' else 'کشور'}"
        )
        await reply(message, text_out, ik([
            [("📦 انبار", "inv:show"), ("📊 جزئیات", "country:stats")],
            back_home(),
        ]))
        return

    if text == BTN_ECO:
        await world.nav.push(pid, "eco")
        code = await world.resolve_country(pid)
        if not code:
            await reply(message, "ابتدا کشور انتخاب کنید.", main_kb(owner))
            return
        c = await world.get_country(code)
        await reply(message, f"💰 اقتصاد\nخزانه: {int(float(c['treasury'])):,} تومان", ik([
            [("💵 درآمد روزانه (اطلاعات)", "eco:info")],
            back_home(),
        ]))
        return

    if text == BTN_MARKET:
        await world.nav.push(pid, "shop")
        rows = []
        pair = []
        for cat, name in CAT_FA.items():
            n = len(items_in_category(cat))
            pair.append((f"{name} ({n})", f"shop:{cat}"))
            if len(pair) == 2:
                rows.append(pair)
                pair = []
        if pair:
            rows.append(pair)
        rows.append(back_home())
        await reply(message, "🛒 فروشگاه — دسته را انتخاب کنید:", ik(rows))
        return

    if text == BTN_ARMY:
        await world.nav.push(pid, "army")
        war = await world.war_enabled()
        await reply(
            message,
            f"⚔️ ارتش و امنیت\nوضعیت جنگ جهان: {'باز' if war else 'بسته'}",
            ik([
                [("🎯 لیست اهداف", "atk:list")],
                [("🛡 وضعیت نیروها", "army:forces")],
                back_home(),
            ]),
        )
        return

    if text == BTN_DIPLO:
        await world.nav.push(pid, "diplo")
        await reply(message, "🤝 روابط و اتحادها", ik([
            [("اتحادهای من", "ally:mine"), ("ساخت اتحاد", "ally:create")],
            back_home(),
        ]))
        return

    if text == BTN_BUILD:
        await world.nav.push(pid, "build")
        await reply(message, "🏗 ساخت‌وساز — از فروشگاه دسته زیرساخت/معادن بخرید.", ik([
            [("⛏ معادن", "shop:mine"), ("🏗 زیرساخت", "shop:infra")],
            back_home(),
        ]))
        return

    if text == BTN_ITEMS:
        await world.nav.push(pid, "items")
        code = await world.resolve_country(pid)
        inv = await world.inventory(code) if code else []
        if not inv:
            await reply(message, "انبار خالی است.", ik([back_home()]))
            return
        lines = ["🎒 انبار:"]
        for r in inv[:30]:
            meta = world._cat.get(r["item_code"], {})
            lines.append(f"• {meta.get('name_fa', r['item_code'])}: {int(float(r['quantity']))}")
        await reply(message, "\n".join(lines), ik([back_home()]))
        return

    if text == BTN_RANK:
        await world.nav.push(pid, "rank")
        rows = await world.db.fetch(
            "SELECT name_fa, treasury, flag FROM countries WHERE owner_player_id IS NOT NULL AND country_code<>'UN' ORDER BY treasury DESC LIMIT 15"
        )
        lines = ["🏆 ثروتمندترین کشورها:"]
        for i, r in enumerate(rows, 1):
            lines.append(f"{i}. {r.get('flag','')} {r['name_fa']}: {int(float(r['treasury'])):,}")
        await reply(message, "\n".join(lines) if rows else "هنوز داده‌ای نیست.", ik([back_home()]))
        return

    if text == BTN_NEWS:
        logs = await world.db.fetch(
            "SELECT message, created_at FROM activity_log ORDER BY id DESC LIMIT 10"
        )
        if not logs:
            await reply(message, "خبری نیست.", main_kb(owner))
            return
        lines = ["📜 آخرین رویدادها:"] + [f"• {r['message']}" for r in logs]
        await reply(message, "\n".join(lines), main_kb(owner))
        return

    if text == BTN_SETTINGS:
        await world.nav.push(pid, "settings")
        about = await world.get_setting("about_message")
        await reply(message, f"⚙️ تنظیمات و راهنما\n\n{about}", ik([
            [("📖 راهنمای بازی", "guide:home")],
            back_home(),
        ]))
        return

    if text == BTN_DONATE:
        await world.nav.push(pid, "donate")
        card = await world.get_setting("donation_card")
        name = await world.get_setting("donation_card_name")
        intro = await world.get_setting("donation_intro")
        instr = await world.get_setting("donation_instructions")
        total = await world.get_setting("donations_total", "0")
        body = (
            f"💎 حمایت مالی\n\n{intro}\n\n"
            f"💳 کارت: `{card}`\n👤 صاحب کارت: {name}\n\n{instr}\n\n"
            f"مجموع تأییدشده: {total} تومان"
        )
        await reply(message, body, ik([
            [("✅ ثبت درخواست", "donate:new")],
            back_home(),
        ]))
        return

    if text == BTN_OWNER and owner:
        await world.nav.push(pid, "owner")
        await reply(message, "👑 پنل مدیریت", ik([
            [("بازیکنان", "own:players"), ("وضعیت جهان", "own:world")],
            [("جنگ باز", "own:war:1"), ("جنگ بسته", "own:war:0")],
            [("💰 پرداخت درآمد روزانه", "own:daily")],
            [("💎 حمایت‌ها", "own:donate")],
            back_home(),
        ]))
        return

    if text not in MAIN_LABELS:
        await reply(message, "از منوی دکمه‌ها استفاده کنید.", main_kb(owner))


async def _submit_donation(world, pid, amount, uname, dname) -> int:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    nid = await world.db.fetchrow("SELECT COALESCE(MAX(id),0)+1 AS id FROM donations")
    did = int(nid["id"])
    await world.db.execute(
        """
        INSERT INTO donations (id, player_id, username, display_name, amount, status, created_at, show_name)
        VALUES ($1,$2,$3,$4,$5,'pending',$6,1)
        """,
        (did, pid, str(uname or ""), str(dname or ""), amount, now),
    )
    return did


async def _on_callback(bot, world: World, callback):
    pid = _uid(callback)
    if not pid:
        return
    data = getattr(callback, "data", None) or getattr(callback, "callback_data", None) or ""
    data = str(data)
    owner = world.is_owner(pid)
    msg = getattr(callback, "message", None)

    async def out(text, components=None):
        if msg:
            try:
                await msg.reply(text[:3500], components=components)
                return
            except Exception:
                pass
        try:
            chat = getattr(msg, "chat", None) if msg else None
            cid = getattr(chat, "id", None) or getattr(chat, "chat_id", None)
            if cid and hasattr(bot, "send_message"):
                await bot.send_message(cid, text[:3500], components=components)
        except Exception:
            log.exception("out")

    if data == "nav:home":
        await world.nav.clear(pid)
        await out("منوی اصلی", main_kb(owner))
        return
    if data == "nav:back":
        prev = await world.nav.pop(pid)
        await out("بازگشت — از کیبورد اصلی بخش را دوباره باز کنید.", main_kb(owner))
        return
    if data == "nav:pick":
        free = await world.list_free_countries()
        rows = [[(f"{c.get('flag','')} {c['name_fa']}", f"claim:{c['country_code']}")] for c in free[:40]]
        rows.append(back_home())
        await out("انتخاب کشور:", ik(rows))
        return

    if data.startswith("claim:"):
        code = data.split(":", 1)[1]
        try:
            c = await world.claim(pid, code)
            await out(
                f"✅ {c['name_fa']} انتخاب شد.\nسرمایه اولیه: {int(float(c['treasury'])):,} تومان",
                main_kb(owner),
            )
        except GameError as e:
            await out(f"❌ {e}")
        return

    if data.startswith("shop:"):
        cat = data.split(":", 1)[1]
        items = items_in_category(cat)
        rows = []
        for it in items[:25]:
            rows.append([(f"{it['name_fa']} — {int(it['unit_price']):,}", f"buy:{it['item_code']}")])
        rows.append(back_home())
        await out(f"دسته {CAT_FA.get(cat, cat)}:", ik(rows))
        return

    if data.startswith("buy:"):
        item = data.split(":", 1)[1]
        meta = world._cat.get(item)
        if not meta:
            await out("آیتم نامعتبر")
            return
        _pending[pid] = {"kind": "buy_qty", "item": item}
        await out(
            f"خرید {meta.get('name_fa')}\nقیمت واحد: {int(meta['unit_price']):,}\nتعداد را بنویسید:",
            ik([[("❌ انصراف", "nav:home")]]),
        )
        return

    if data == "inv:show" or data == "army:forces":
        code = await world.resolve_country(pid)
        inv = await world.inventory(code) if code else []
        lines = []
        for r in inv[:40]:
            meta = world._cat.get(r["item_code"], {})
            lines.append(f"• {meta.get('name_fa', r['item_code'])}: {int(float(r['quantity']))}")
        await out("\n".join(lines) if lines else "خالی", ik([back_home()]))
        return

    if data == "atk:list":
        if not await world.war_enabled() and not owner:
            await out("جنگ جهان بسته است.")
            return
        code = await world.resolve_country(pid)
        targets = await world.db.fetch(
            "SELECT country_code, name_fa, flag FROM countries WHERE owner_player_id IS NOT NULL AND country_code<>$1 AND country_code<>'UN' AND COALESCE(is_destroyed,0)=0 LIMIT 30",
            (code or "",),
        )
        rows = [[(f"{t.get('flag','')} {t['name_fa']}", f"atk:go:{t['country_code']}")] for t in targets]
        rows.append(back_home())
        await out("هدف حمله:", ik(rows) if targets else ik([back_home()]))
        return

    if data.startswith("atk:go:"):
        await out("سیستم حمله کامل در REBIRTH متصل است — برای عملیات نظامی از موجودی نیرو استفاده می‌شود. (فاز تکمیل گزارش جنگ)", ik([back_home()]))
        return

    if data == "donate:new":
        _pending[pid] = {"kind": "donation_amount"}
        await out("مبلغ حمایت (تومان) را بنویسید:")
        return

    if data.startswith("don:ok:") or data.startswith("don:no:"):
        if not owner:
            await out("فقط مالک")
            return
        did = int(data.split(":")[-1])
        ok = data.startswith("don:ok:")
        row = await world.db.fetchrow("SELECT * FROM donations WHERE id=$1", (did,))
        if not row or row["status"] != "pending":
            await out("قبلاً بررسی شده")
            return
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        status = "approved" if ok else "rejected"
        await world.db.execute(
            "UPDATE donations SET status=$1, reviewed_at=$2, reviewed_by=$3 WHERE id=$4 AND status='pending'",
            (status, now, pid, did),
        )
        if ok:
            total = float(await world.get_setting("donations_total", "0") or 0) + float(row["amount"])
            await world.set_setting("donations_total", str(int(total)))
            try:
                await bot.send_message(int(row["player_id"]), f"✅ حمایت شما تأیید شد: {int(float(row['amount'])):,}")
            except Exception:
                pass
        else:
            try:
                await bot.send_message(int(row["player_id"]), "❌ درخواست حمایت رد شد.")
            except Exception:
                pass
        await out(f"{'تأیید' if ok else 'رد'} شد #{did}")
        return

    if data.startswith("own:") and owner:
        if data == "own:daily":
            n = await world.daily_payout_all(force=True)
            await out(f"پرداخت روزانه برای {n} کشور انجام شد.")
            return
        if data == "own:war:1":
            await world.set_war(True)
            await out("جنگ باز شد.")
            return
        if data == "own:war:0":
            await world.set_war(False)
            await out("جنگ بسته شد.")
            return
        if data == "own:world":
            m = await world.db.fetchrow("SELECT * FROM world_meta WHERE id=1")
            pc = await world.db.fetchrow("SELECT COUNT(*) AS c FROM players")
            cc = await world.db.fetchrow(
                "SELECT COUNT(*) AS c FROM countries WHERE owner_player_id IS NOT NULL"
            )
            await out(
                f"نسخه: {getattr(world.settings,'BOT_VERSION', '')}\n"
                f"جنگ: {m.get('war_enabled')}\nبازیکنان: {pc['c']}\nکشورهای دارای رهبر: {cc['c']}"
            )
            return
        if data == "own:players":
            rows = await world.db.fetch(
                "SELECT player_id, username, display_name, country_code FROM players ORDER BY last_seen_at DESC LIMIT 20"
            )
            lines = [f"{r['player_id']} | {r.get('display_name') or r.get('username')} | {r.get('country_code')}" for r in rows]
            await out("\n".join(lines) or "خالی")
            return
        if data == "own:donate":
            rows = await world.db.fetch("SELECT * FROM donations WHERE status='pending' ORDER BY id DESC LIMIT 15")
            if not rows:
                await out("درخواست معلقی نیست.")
                return
            kb = []
            lines = []
            for r in rows:
                lines.append(f"#{r['id']} {int(float(r['amount'])):,} — {r.get('display_name')}")
                kb.append([("✅", f"don:ok:{r['id']}"), ("❌", f"don:no:{r['id']}")])
            await out("\n".join(lines), ik(kb))
            return

    await out("دکمه نامعتبر یا منقضی.")
