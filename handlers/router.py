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
    BTN_ITEMS, BTN_RANK, BTN_NEWS, BTN_SETTINGS, BTN_DONATE, BTN_OWNER, BTN_PICK, BTN_HOME, BTN_REF,
)
from modules.shop.catalog import CAT_FA, items_in_category

log = logging.getLogger(__name__)
_pending: dict[int, dict] = {}
_busy: set[int] = set()


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
    chat = getattr(message, "chat", None)
    if not chat:
        return True
    t = str(getattr(chat, "type", None) or getattr(chat, "chat_type", None) or "").lower()
    return t in ("private", "prv", "1", "chattype.private") or "private" in t


async def reply(message, text: str, components=None):
    try:
        if components is not None:
            await message.reply(str(text)[:3500], components=components)
        else:
            await message.reply(str(text)[:3500])
    except Exception:
        log.exception("reply failed")


def register_handlers(bot, world: World):
    @bot.listen("message")
    async def on_message(message: Message):
        try:
            pid = _uid(message)
            log.info("message received pid=%s private=%s", pid, _is_private(message))
            await _on_message(bot, world, message)
        except Exception:
            log.exception("on_message")

    @bot.listen("callback")
    async def on_callback(callback):
        try:
            pid = _uid(callback)
            data = getattr(callback, "data", None) or ""
            log.info("callback received pid=%s data=%s", pid, str(data)[:40])
            await _on_callback(bot, world, callback)
        except Exception:
            log.exception("on_callback")

    log.info("handlers registered (message + callback)")


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

    if not private:
        if text in ("/start", "شروع"):
            await reply(message, "برای بازی به پیوی ربات مراجعه کنید.")
        return

    # Forced membership notice (soft — API membership check needs bot admin)
    if text in ("/start", "شروع") and not owner:
        notice = await world.membership.check_text()
        if notice:
            # still allow play; owner configures channels
            pass

    if pid in _pending:
        st = _pending[pid]
        kind = st.get("kind")
        if text in ("لغو", "انصراف", "/cancel"):
            _pending.pop(pid, None)
            await reply(message, "لغو شد.", main_kb(owner))
            return
        try:
            if kind == "donation_amount":
                amount = float(text.replace(",", "").replace(" ", "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")))
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
                            f"💎 حمایت #{did}\n{dname or uname or pid}\n{int(amount):,}",
                            components=ik([[("✅", f"don:ok:{did}"), ("❌", f"don:no:{did}")]]),
                        )
                    except Exception:
                        pass
                return
            if kind == "buy_qty":
                qty = float(text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")))
                msg = await world.buy_item(pid, st["item"], qty)
                _pending.pop(pid, None)
                await reply(message, msg, main_kb(owner))
                return
            if kind == "ally_name":
                _pending[pid] = {"kind": "ally_caps", "name": text.strip()[:40]}
                await reply(message, "ظرفیت اعضا را بنویس (۲ تا ۲۰). مثال: 5")
                return
            if kind == "ally_caps":
                cap = int(float(text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))))
                _pending[pid] = {"kind": "ally_treasury", "name": st["name"], "cap": cap}
                await reply(message, "ظرفیت خزانه (تومان) را بنویس. مثال: 200000000")
                return
            if kind == "ally_treasury":
                treas = float(text.replace(",", "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")))
                a = await world.alliances.create(pid, st["name"], st["cap"], treas)
                _pending.pop(pid, None)
                cost = world.alliances.create_cost(st["cap"], treas)
                await reply(message, f"✅ اتحاد «{a['name']}» ساخته شد.\nهزینه ساخت حدود {cost:,}", main_kb(owner))
                return
            if kind == "ally_deposit":
                amount = float(text.replace(",", "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")))
                msg = await world.alliances.deposit(pid, amount)
                _pending.pop(pid, None)
                await reply(message, msg, main_kb(owner))
                return
            if kind == "ref_code":
                msg = await world.referral.apply(pid, text)
                _pending.pop(pid, None)
                await reply(message, msg, main_kb(owner))
                return
            if kind == "mkt_price":
                price = float(text.replace(",", "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")))
                L = await world.market.create(pid, st["item"], st["qty"], price)
                _pending.pop(pid, None)
                await reply(message, f"✅ آگهی #{L['id']} ثبت شد.", main_kb(owner))
                return
            if kind == "mkt_qty":
                qty = float(text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")))
                _pending[pid] = {"kind": "mkt_price", "item": st["item"], "qty": qty}
                await reply(message, "قیمت هر واحد (تومان) را بنویس:")
                return
            if kind == "peace_target":
                code = text.strip().upper()
                msg = await world.peace.propose(pid, code)
                _pending.pop(pid, None)
                await reply(message, msg, main_kb(owner))
                return
        except GameError as e:
            await reply(message, f"❌ {e}")
            return
        except Exception as e:
            log.exception("pending")
            await reply(message, f"❌ {e}")
            return

    if text in ("/start", "شروع", "منو", "menu", BTN_HOME):
        await world.nav.clear(pid)
        start = await world.get_setting("start_message")
        code = await world.resolve_country(pid)
        extra = f"\nکشور شما: {await world.country_label(code)}" if code else "\nهنوز کشور ندارید — از «انتخاب کشور» استفاده کنید."
        await reply(message, f"🎮 {getattr(world.settings,'BOT_NAME','WORLD WAR REBIRTH')}\n\n{start}{extra}", main_kb(owner))
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
        await reply(message, "🗺 کشور یا گروهک آزاد:", ik(rows))
        return

    if text == BTN_COUNTRY:
        await world.nav.push(pid, "country")
        code = await world.resolve_country(pid)
        if not code:
            await reply(message, "ابتدا کشور انتخاب کنید.", ik([[(BTN_PICK, "nav:pick")], back_home()]))
            return
        c = await world.get_country(code)
        body = (
            f"🌍 {await world.country_label(code)}\n"
            f"━━━━━━━━━━━━━━\n"
            f"💰 خزانه: {int(float(c['treasury'])):,} تومان\n"
            f"❤️ سلامت: {int(float(c['hp']))}/{int(float(c['max_hp']))}"
            f"{' ×۲' if int(c.get('double_hp') or 0) else ''}\n"
            f"☢ NPT: {'عضو' if int(c.get('npt_member') or 0) else 'غیرعضو'}\n"
            f"🏷 نوع: {'گروهک' if c.get('entity_type')=='group' else 'کشور'}"
        )
        await reply(message, body, ik([
            [("📦 انبار", "inv:show"), ("🏭 کارگاه", "ws:home")],
            [("📊 آمار بیشتر", "country:stats")],
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
        base = int(getattr(world.settings, "BASE_DAILY_INCOME", 20_000_000))
        await reply(
            message,
            f"💰 اقتصاد و دارایی\nخزانه: {int(float(c['treasury'])):,} تومان\n"
            f"درآمد پایه روزانه: {base:,}\nدرآمد ساختمان‌ها: {int(float(c.get('daily_income') or 0)):,}",
            ik([[("📜 تاریخچه فعالیت", "eco:log")], back_home()]),
        )
        return

    if text == BTN_MARKET:
        await world.nav.push(pid, "shop")
        await reply(message, "🛒 بازار و فروشگاه", ik([
            [("🛍 فروشگاه رسمی", "shop:cats")],
            [("🌐 بازار آزاد (P2P)", "mkt:list")],
            [("➕ ثبت آگهی", "mkt:sell")],
            back_home(),
        ]))
        return

    if text == BTN_ARMY:
        await world.nav.push(pid, "army")
        war = await world.war_enabled()
        await reply(
            message,
            f"⚔️ ارتش و امنیت\nوضعیت جنگ جهان: {'🟢 باز' if war else '🔴 بسته'}",
            ik([
                [("🎯 لیست اهداف", "atk:list")],
                [("🛡 نیروهای من", "army:forces")],
                [("📜 تاریخچه جنگ", "atk:hist")],
                back_home(),
            ]),
        )
        return

    if text == BTN_DIPLO:
        await world.nav.push(pid, "diplo")
        await reply(message, "🤝 روابط و اتحادها", ik([
            [("اتحاد من", "ally:mine"), ("فهرست اتحادها", "ally:list")],
            [("➕ ساخت اتحاد", "ally:create")],
            [("🕊 پیمان صلح", "peace:menu")],
            back_home(),
        ]))
        return

    if text == BTN_BUILD:
        await world.nav.push(pid, "build")
        await reply(message, "🏗 ساخت‌وساز", ik([
            [("⛏ معادن", "shop:cat:mine"), ("🏭 زیرساخت", "shop:cat:infra")],
            [("🏭 کارگاه پژوهش", "ws:home")],
            back_home(),
        ]))
        return

    if text == BTN_ITEMS:
        await world.nav.push(pid, "items")
        await reply(message, "🎒 آیتم‌ها و تجهیزات", ik([
            [("📦 انبار نظامی", "inv:show")],
            [("✨ آیتم‌های لجندری", "leg:shop")],
            [("📋 لجندری‌های من", "leg:mine")],
            back_home(),
        ]))
        return

    if text == BTN_RANK:
        rows = await world.db.fetch(
            "SELECT name_fa, treasury, flag FROM countries WHERE owner_player_id IS NOT NULL AND country_code<>'UN' ORDER BY treasury DESC LIMIT 15"
        )
        lines = ["🏆 ثروتمندترین کشورها:"] + [
            f"{i}. {r.get('flag','')} {r['name_fa']}: {int(float(r['treasury'])):,}" for i, r in enumerate(rows, 1)
        ]
        await reply(message, "\n".join(lines) if rows else "داده‌ای نیست.", main_kb(owner))
        return

    if text == BTN_NEWS:
        logs = await world.db.fetch("SELECT message FROM activity_log ORDER BY id DESC LIMIT 12")
        lines = ["📜 آخرین رویدادها:"] + [f"• {r['message'][:120]}" for r in logs]
        await reply(message, "\n".join(lines) if logs else "خبری نیست.", main_kb(owner))
        return

    if text == BTN_SETTINGS:
        about = await world.get_setting("about_message")
        await reply(message, f"⚙️ تنظیمات و راهنما\n\n{about}", ik([
            [("📖 راهنما", "guide:home")],
            back_home(),
        ]))
        return

    if text == BTN_REF:
        code = await world.referral.get_or_create_code(pid)
        await reply(
            message,
            f"🎁 سیستم دعوت\nکد شما: `{code}`\n\nدعوت‌شونده ۲ میلیون و شما ۱۵ میلیون (در صورت داشتن کشور) دریافت می‌کنید.",
            ik([[("وارد کردن کد دعوت", "ref:enter")], back_home()]),
        )
        return

    if text == BTN_DONATE:
        await world.nav.push(pid, "donate")
        card = await world.get_setting("donation_card")
        name = await world.get_setting("donation_card_name")
        intro = await world.get_setting("donation_intro")
        total = await world.get_setting("donations_total", "0")
        await reply(
            message,
            f"💎 حمایت مالی\n\n{intro}\n\n💳 `{card}`\n👤 {name}\n📊 مجموع تأییدشده: {total}",
            ik([[("✅ ثبت درخواست", "donate:new")], back_home()]),
        )
        return

    if text == BTN_OWNER and owner:
        await world.nav.push(pid, "owner")
        await reply(message, "👑 پنل مدیریت", ik([
            [("👥 بازیکنان", "own:players"), ("🌍 جهان", "own:world")],
            [("🟢 جنگ باز", "own:war:1"), ("🔴 جنگ بسته", "own:war:0")],
            [("💰 درآمد روزانه", "own:daily")],
            [("💎 حمایت‌ها", "own:donate")],
            [("⚙️ عضویت اجباری", "own:force")],
            back_home(),
        ]))
        return

    if text not in MAIN_LABELS:
        await reply(message, "از دکمه‌های منو استفاده کنید.", main_kb(owner))


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
    if pid in _busy:
        return
    data = str(getattr(callback, "data", None) or getattr(callback, "callback_data", None) or "")
    owner = world.is_owner(pid)
    msg = getattr(callback, "message", None)

    async def out(text, components=None):
        try:
            if msg:
                await msg.reply(str(text)[:3500], components=components)
                return
        except Exception:
            pass
        try:
            chat = getattr(msg, "chat", None) if msg else None
            cid = getattr(chat, "id", None) or getattr(chat, "chat_id", None)
            if cid:
                await bot.send_message(cid, str(text)[:3500], components=components)
        except Exception:
            log.exception("out")

    _busy.add(pid)
    try:
        if data == "nav:home":
            await world.nav.clear(pid)
            await out("🏠 منوی اصلی", main_kb(owner))
            return
        if data == "nav:back":
            await world.nav.pop(pid)
            await out("بازگشت — بخش را از منوی اصلی دوباره باز کنید.", main_kb(owner))
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
                await out(f"✅ {c['name_fa']} انتخاب شد.\nسرمایه: {int(float(c['treasury'])):,} تومان", main_kb(owner))
            except GameError as e:
                await out(f"❌ {e}")
            return

        if data == "shop:cats":
            rows, pair = [], []
            for cat, name in CAT_FA.items():
                pair.append((f"{name}", f"shop:cat:{cat}"))
                if len(pair) == 2:
                    rows.append(pair); pair = []
            if pair:
                rows.append(pair)
            rows.append(back_home())
            await out("دسته‌بندی فروشگاه:", ik(rows))
            return

        if data.startswith("shop:cat:"):
            cat = data.split(":")[-1]
            items = items_in_category(cat)
            rows = [[(f"{it['name_fa']} — {int(it['unit_price']):,}", f"buy:{it['item_code']}")] for it in items[:25]]
            rows.append(back_home())
            await out(f"{CAT_FA.get(cat, cat)}:", ik(rows))
            return

        if data.startswith("buy:"):
            item = data.split(":", 1)[1]
            meta = world._cat.get(item)
            if not meta:
                await out("نامعتبر"); return
            _pending[pid] = {"kind": "buy_qty", "item": item}
            await out(f"خرید {meta.get('name_fa')}\nقیمت واحد: {int(meta['unit_price']):,}\nتعداد را بنویسید:")
            return

        if data in ("inv:show", "army:forces"):
            code = await world.resolve_country(pid)
            inv = await world.inventory(code) if code else []
            lines = []
            for r in inv[:40]:
                meta = world._cat.get(r["item_code"], {})
                lines.append(f"• {meta.get('name_fa', r['item_code'])}: {int(float(r['quantity']))}")
            await out("\n".join(lines) if lines else "انبار خالی است.", ik([back_home()]))
            return

        if data == "atk:list":
            if not await world.war_enabled() and not owner:
                await out("⚠️ جنگ جهان بسته است."); return
            code = await world.resolve_country(pid)
            targets = await world.db.fetch(
                "SELECT country_code, name_fa, flag FROM countries WHERE owner_player_id IS NOT NULL AND country_code NOT IN ($1,'UN') AND COALESCE(is_destroyed,0)=0 LIMIT 30",
                (code or "",),
            )
            rows = [[(f"{t.get('flag','')} {t['name_fa']}", f"atk:go:{t['country_code']}")] for t in targets]
            rows.append(back_home())
            await out("هدف حمله:", ik(rows) if targets else ik([back_home()]))
            return

        if data.startswith("atk:go:"):
            target = data.split(":")[-1]
            try:
                report = await world.combat.attack(pid, target, 1.0)
                await out(report, ik([back_home()]))
            except GameError as e:
                await out(f"❌ {e}")
            return

        if data == "atk:hist":
            rows = await world.db.fetch("SELECT * FROM wars ORDER BY id DESC LIMIT 10")
            lines = [f"• {r['attacker']} → {r['defender']}: {r.get('report')}" for r in rows]
            await out("\n".join(lines) if lines else "تاریخچه‌ای نیست.", ik([back_home()]))
            return

        if data == "ally:create":
            _pending[pid] = {"kind": "ally_name"}
            await out("نام اتحاد را بنویسید:")
            return
        if data == "ally:mine":
            code = await world.resolve_country(pid)
            a = await world.alliances.my_alliance(code) if code else None
            if not a:
                await out("عضو اتحادی نیستید.", ik([[("➕ ساخت", "ally:create")], back_home()])); return
            mems = await world.alliances.members(a["id"])
            await out(
                f"🤝 {a['name']}\nخزانه: {int(float(a['treasury'])):,}/{int(float(a['treasury_cap'])):,}\nاعضا: {len(mems)}/{a['member_cap']}",
                ik([
                    [("💵 واریز به خزانه", "ally:deposit"), ("🚪 خروج", "ally:leave")],
                    [("🗑 انحلال (مالک)", "ally:dissolve")],
                    back_home(),
                ]),
            )
            return
        if data == "ally:list":
            rows = await world.alliances.list_open()
            kb = [[(f"{r['name']} ({r['id']})", f"ally:join:{r['id']}")] for r in rows[:20]]
            kb.append(back_home())
            await out("اتحادهای فعال — برای عضویت لمس کنید:", ik(kb))
            return
        if data.startswith("ally:join:"):
            try:
                msg = await world.alliances.join(pid, int(data.split(":")[-1]))
                await out(msg)
            except GameError as e:
                await out(f"❌ {e}")
            return
        if data == "ally:leave":
            try:
                await out(await world.alliances.leave(pid))
            except GameError as e:
                await out(f"❌ {e}")
            return
        if data == "ally:dissolve":
            try:
                await out(await world.alliances.dissolve(pid))
            except GameError as e:
                await out(f"❌ {e}")
            return
        if data == "ally:deposit":
            _pending[pid] = {"kind": "ally_deposit"}
            await out("مبلغ واریز به خزانه اتحاد را بنویسید:")
            return

        if data == "peace:menu":
            await out("🕊 پیمان صلح", ik([
                [("ثبت پیمان (کد کشور)", "peace:new")],
                [("پیمان‌های من", "peace:list")],
                back_home(),
            ]))
            return
        if data == "peace:new":
            _pending[pid] = {"kind": "peace_target"}
            await out("کد کشور طرف مقابل را بنویس (مثل IR):")
            return
        if data == "peace:list":
            code = await world.resolve_country(pid)
            rows = await world.peace.list_for(code) if code else []
            lines = [f"#{r['id']}: {r['country_a']} ↔ {r['country_b']}" for r in rows]
            await out("\n".join(lines) if lines else "پیمانی نیست.", ik([back_home()]))
            return

        if data == "mkt:list":
            rows = await world.market.list_active()
            kb = []
            for r in rows[:20]:
                meta = world._cat.get(r["item_code"], {})
                kb.append([(f"#{r['id']} {meta.get('name_fa', r['item_code'])} ×{int(float(r['quantity']))} @ {int(float(r['unit_price'])):,}", f"mkt:buy:{r['id']}")])
            kb.append(back_home())
            await out("بازار آزاد:", ik(kb) if rows else ik([back_home()]))
            return
        if data.startswith("mkt:buy:"):
            try:
                await out(await world.market.buy(pid, int(data.split(":")[-1])))
            except GameError as e:
                await out(f"❌ {e}")
            return
        if data == "mkt:sell":
            code = await world.resolve_country(pid)
            inv = await world.inventory(code) if code else []
            kb = [[(world._cat.get(r["item_code"], {}).get("name_fa", r["item_code"]), f"mkt:sellitem:{r['item_code']}")] for r in inv[:20]]
            kb.append(back_home())
            await out("کدام آیتم را بفروشیم؟", ik(kb) if inv else ik([back_home()]))
            return
        if data.startswith("mkt:sellitem:"):
            item = data.split(":")[-1]
            _pending[pid] = {"kind": "mkt_qty", "item": item}
            await out("تعداد برای فروش را بنویسید:")
            return

        if data == "leg:shop":
            await world.legendary.ensure()
            rows = await world.legendary.catalog()
            kb = [[(f"{r['name_fa']} — {int(float(r['price'])):,}", f"leg:buy:{r['item_code']}")] for r in rows]
            kb.append(back_home())
            await out("✨ فروشگاه لجندری:", ik(kb))
            return
        if data.startswith("leg:buy:"):
            try:
                await out(await world.legendary.buy(pid, data.split(":")[-1]))
            except GameError as e:
                await out(f"❌ {e}")
            return
        if data == "leg:mine":
            inv = await world.legendary.inventory(pid)
            lines = [f"• {r['item_code']}: {r['uses_left']} استفاده" for r in inv]
            await out("\n".join(lines) if lines else "لجندری ندارید.", ik([back_home()]))
            return

        if data == "ws:home":
            code = await world.resolve_country(pid)
            if not code:
                await out("کشور لازم است"); return
            st = await world.workshop.status(code)
            await out(
                f"🏭 کارگاه\nسطح: {st['level']}\nفناوری: {st['tech_level']}\nاورانیوم بازی: {st['uranium']}",
                ik([
                    [("🔬 پژوهش فناوری", "ws:tech"), ("⛏ تولید منبع", "ws:uranium")],
                    back_home(),
                ]),
            )
            return
        if data == "ws:tech":
            try:
                await out(await world.workshop.start_research(pid, "tech"))
            except GameError as e:
                await out(f"❌ {e}")
            return
        if data == "ws:uranium":
            try:
                await out(await world.workshop.start_research(pid, "uranium"))
            except GameError as e:
                await out(f"❌ {e}")
            return

        if data == "donate:new":
            _pending[pid] = {"kind": "donation_amount"}
            await out("مبلغ حمایت (تومان) را بنویسید:")
            return
        if data.startswith("don:ok:") or data.startswith("don:no:"):
            if not owner:
                await out("فقط مالک"); return
            did = int(data.split(":")[-1])
            ok = data.startswith("don:ok:")
            row = await world.db.fetchrow("SELECT * FROM donations WHERE id=$1", (did,))
            if not row or row["status"] != "pending":
                await out("قبلاً بررسی شده"); return
            from datetime import datetime, timezone
            status = "approved" if ok else "rejected"
            await world.db.execute(
                "UPDATE donations SET status=$1, reviewed_at=$2, reviewed_by=$3 WHERE id=$4 AND status='pending'",
                (status, datetime.now(timezone.utc).isoformat(), pid, did),
            )
            if ok:
                total = float(await world.get_setting("donations_total", "0") or 0) + float(row["amount"])
                await world.set_setting("donations_total", str(int(total)))
            await out(f"{'تأیید' if ok else 'رد'} شد #{did}")
            return

        if data == "ref:enter":
            _pending[pid] = {"kind": "ref_code"}
            await out("کد دعوت را بنویسید:")
            return

        if data == "guide:home":
            await out(
                "📖 راهنما\n۱) کشور انتخاب کنید\n۲) از فروشگاه نیرو بخرید\n۳) اقتصاد و اتحاد بسازید\n۴) در صورت باز بودن جنگ، حمله کنید",
                ik([back_home()]),
            )
            return

        if data.startswith("own:") and owner:
            if data == "own:daily":
                n = await world.daily_payout_all(force=True)
                await out(f"پرداخت روزانه: {n} کشور")
                return
            if data == "own:war:1":
                await world.set_war(True); await out("جنگ باز شد"); return
            if data == "own:war:0":
                await world.set_war(False); await out("جنگ بسته شد"); return
            if data == "own:world":
                m = await world.db.fetchrow("SELECT * FROM world_meta WHERE id=1")
                pc = await world.db.fetchrow("SELECT COUNT(*) AS c FROM players")
                cc = await world.db.fetchrow("SELECT COUNT(*) AS c FROM countries WHERE owner_player_id IS NOT NULL")
                await out(f"نسخه REBIRTH\nجنگ={m.get('war_enabled')}\nبازیکن={pc['c']}\nکشور دارای رهبر={cc['c']}")
                return
            if data == "own:players":
                rows = await world.db.fetch("SELECT player_id, username, display_name, country_code FROM players ORDER BY last_seen_at DESC LIMIT 25")
                lines = [f"{r['player_id']} | {r.get('display_name') or r.get('username')} | {r.get('country_code')}" for r in rows]
                await out("\n".join(lines) or "خالی")
                return
            if data == "own:donate":
                rows = await world.db.fetch("SELECT * FROM donations WHERE status='pending' ORDER BY id DESC LIMIT 15")
                if not rows:
                    await out("موردی نیست"); return
                kb, lines = [], []
                for r in rows:
                    lines.append(f"#{r['id']} {int(float(r['amount'])):,}")
                    kb.append([("✅", f"don:ok:{r['id']}"), ("❌", f"don:no:{r['id']}")])
                await out("\n".join(lines), ik(kb))
                return
            if data == "own:force":
                rows = await world.membership.list_active()
                await out("عضویت اجباری:\n" + ("\n".join(f"{r['title']}: {r['invite_link']}" for r in rows) or "خالی"), ik([
                    [("🗑 پاک‌سازی", "own:forceclear")], back_home()
                ]))
                return
            if data == "own:forceclear":
                await out(await world.membership.clear(pid)); return

        await out("دکمه نامعتبر یا منقضی.")
    finally:
        _busy.discard(pid)
