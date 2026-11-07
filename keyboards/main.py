"""Main and category keyboards — sparse main menu, full features in submenus."""
from __future__ import annotations

from bale import MenuKeyboardMarkup, MenuKeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

BTN_COUNTRY = "🌍 کشور من"
BTN_ECO = "💰 اقتصاد و دارایی"
BTN_BUILD = "🏗 ساخت‌وساز"
BTN_ARMY = "⚔️ ارتش و امنیت"
BTN_DIPLO = "🤝 روابط و اتحادها"
BTN_MARKET = "🛒 بازار و فروشگاه"
BTN_ITEMS = "🎒 آیتم‌ها و تجهیزات"
BTN_RANK = "🏆 رتبه‌بندی و آمار"
BTN_NEWS = "📜 اخبار و رویدادها"
BTN_SETTINGS = "⚙️ تنظیمات و راهنما"
BTN_DONATE = "💎 حمایت مالی"
BTN_OWNER = "👑 مدیریت"
BTN_PICK = "🗺 انتخاب کشور"
BTN_HOME = "🏠 خانه"
BTN_REF = "🎁 دعوت دوستان"

MAIN_LABELS = {
    BTN_COUNTRY, BTN_ECO, BTN_BUILD, BTN_ARMY, BTN_DIPLO, BTN_MARKET,
    BTN_ITEMS, BTN_RANK, BTN_NEWS, BTN_SETTINGS, BTN_DONATE, BTN_OWNER, BTN_PICK, BTN_HOME, BTN_REF,
    "/start", "شروع", "منو", "menu",
}


def main_kb(is_owner: bool = False) -> MenuKeyboardMarkup:
    kb = MenuKeyboardMarkup()
    rows = [
        [BTN_COUNTRY, BTN_ECO],
        [BTN_BUILD, BTN_ARMY],
        [BTN_DIPLO, BTN_MARKET],
        [BTN_ITEMS, BTN_RANK],
        [BTN_NEWS, BTN_SETTINGS],
        [BTN_DONATE, BTN_REF],
        [BTN_PICK],
    ]
    if is_owner:
        rows.append([BTN_OWNER])
    for i, row in enumerate(rows, 1):
        for t in row:
            kb.add(MenuKeyboardButton(t), row=i)
    return kb


def ik(rows: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    for ri, row in enumerate(rows, 1):
        for label, data in row:
            if label:
                kb.add(InlineKeyboardButton(str(label)[:64], callback_data=str(data)[:64]), row=ri)
    return kb


def back_home(back_cb: str = "nav:back"):
    return [("🔙 بازگشت", back_cb), ("🏠 خانه", "nav:home")]
