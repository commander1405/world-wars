# WORLD WAR REBIRTH

نسل جدید بازی استراتژیک/اقتصادی چندنفره روی بله.

**شاخه توسعه:** `rebirth-v2`  
**دیتابیس:** کاملاً مستقل — `world_war_rebirth.db` (دیتابیس قدیمی دست نخورده می‌ماند)

## نصب Termux

```bash
cd /storage/emulated/0/worldwarbot
git clone https://github.com/commander1405/world-wars.git
cd world-wars
git checkout rebirth-v2
pip install -r requirements.txt
cp config.example.py config.py
# توکن را در config.py بگذارید
mkdir -p /storage/emulated/0/worldwarbot/db
python main.py
```

## معماری

- `core/` — World، Nav، خطاها
- `database/` — SQLite async + schema
- `handlers/` — پیام و Callback
- `keyboards/` — منوی دسته‌بندی‌شده
- `modules/shop` — کاتالوگ کامل نظامی/اقتصادی
- `tools/migrate_from_legacy.py` — انتقال از دیتابیس قدیمی

## منوی اصلی (کم‌دکمه)

کشور من · اقتصاد · ساخت‌وساز · ارتش · روابط · بازار · آیتم‌ها · رتبه · اخبار · تنظیمات · حمایت · انتخاب کشور · مدیریت (مالک)

تمام قابلیت‌ها در زیرمنوها هستند.

## تست

```bash
python -m unittest tests.test_rebirth_core -v
```
