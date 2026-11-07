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

## رفع مشکل «گیر کردن روی bot.connect»

در python-bale-bot نسخه ۲.x:

- متد `bot.connect()` برای دریافت پیام کافی/صحیح نیست.
- `@bot.listen("message")` رویداد پیام را ثبت نمی‌کند؛ باید از `MessageHandler` استفاده شود.
- چرخه صحیح: `async with bot` → `get_me()` → `updater.setup()` → fetcher → `start_polling()`.

بعد از آپدیت باید این لاگ‌ها را ببینید:

```
Authentication successful bot=@...
Update receiver started
Polling worker running — bot is live
```

سپس در **پیوی** ربات `/start` بزنید.

## کتابخانه Bale (ثابت)

نسخهٔ الزامی: **python-bale-bot==2.5.0** (همان پروژهٔ WORLD-WAR قدیمی)

رویدادها:
- `@bot.listen("on_ready")`
- `@bot.listen("on_message")`
- `@bot.listen("on_callback")`

چرخه اجرا:
```python
async with bot:
    await bot.get_me()
    await bot.updater.start()  # polling
```

**از `bale.handlers` استفاده نکنید** — در 2.5.0 وجود ندارد.

## نصب Termux

```bash
cd /storage/emulated/0/worldwarbot/world-wars
git checkout rebirth-v2
git pull
pip install -r requirements.txt
# config.py را بسازید یا از قبل داشته باشید
python main.py
```
