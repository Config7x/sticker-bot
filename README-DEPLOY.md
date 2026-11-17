# راهنمای نصب ربات استیکرساز — فاز ۱ (MVP)

ربات عمومی ساخت پک استیکر تلگرام (معمولی/ثابت) با موتور قدم‌به‌قدم،
پیشنهادهای چندگزینه‌ای با تاریخچه، پنل مدیریت و قفل جوین اجباری.

## نیازمندی‌ها

- اوبونتو با Python 3.12 یا بالاتر
- PostgreSQL (برای توسعه، SQLite پیش‌فرض هم کار می‌کند)
- فونت فارسی برای متن روی استیکر: `fonts-noto-core` (شامل Noto Sans Arabic)
- FFmpeg در فاز ۱ لازم نیست (فاز ۲ ویدیویی)

## نصب روی سرور (AWS میلاد: 13.61.173.127)

```bash
sudo apt update && sudo apt install -y python3-venv fonts-noto-core postgresql
sudo mkdir -p /opt/stickerbot && sudo chown ubuntu:ubuntu /opt/stickerbot
# کد پروژه را در /opt/stickerbot بگذارید (git clone یا کپی)
cd /opt/stickerbot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
nano .env   # BOT_TOKEN و ADMIN_IDS و DATABASE_URL را پر کنید
```

ساخت دیتابیس پستگرس:

```bash
sudo -u postgres psql -c "CREATE USER stickerbot WITH PASSWORD 'پسورد';"
sudo -u postgres psql -c "CREATE DATABASE stickerbot OWNER stickerbot;"
```

و در `.env`:

```
DATABASE_URL=postgresql+asyncpg://stickerbot:پسورد@127.0.0.1:5432/stickerbot
```

## اجرا

تست دستی:

```bash
cd /opt/stickerbot && .venv/bin/python run.py
```

اجرا به‌صورت سرویس دائمی:

```bash
sudo cp stickerbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stickerbot
journalctl -u stickerbot -f
```

## قبل از اولین اجرا

1. ربات را در BotFather بسازید و توکن را فقط در `.env` بگذارید.
   اسم کاربری ربات مهم است: اسم همه پک‌ها به `_by_<آیدی ربات>` ختم می‌شود.
2. آیدی عددی خودتان را در `ADMIN_IDS` بگذارید (مالک از قفل و سهمیه معاف است).
3. برای هر کانال جوین اجباری، ربات را در آن کانال **ادمین** کنید
   (وگرنه تلگرام اجازه چک عضویت نمی‌دهد) و بعد کانال را از داخل
   پنل مدیریت ربات (دکمه «🛠 پنل مدیریت» ← «🔒 قفل‌ها») اضافه کنید.
4. حذف پس‌زمینه (اختیاری): در `.env` مقدار `USE_REMBG=1` و نصب پکیج
   `rembg`؛ بدون آن هم ربات کامل کار می‌کند.

## متغیرهای محیطی

| متغیر | توضیح |
|---|---|
| `BOT_TOKEN` | توکن BotFather (اجباری) |
| `ADMIN_IDS` | آیدی عددی مالک/ادمین‌ها، جداشده با کاما |
| `DATABASE_URL` | آدرس دیتابیس؛ پیش‌فرض فایل SQLite |
| `FA_FONT_PATH` | مسیر فونت Noto Arabic (خالی = تشخیص خودکار) |
| `USE_REMBG` | فعال‌کردن حذف پس‌زمینه با rembg (`1`) |
| `TENOR_API_KEY` / `GIPHY_API_KEY` | جستجوی زنده استیکر در قدم تصویر (اختیاری) |

## تست دود (بدون توکن)

```bash
.venv/bin/python tests/smoke_test.py
```

پایپ‌لاین تصویر و منطق دسته/تاریخچه پیشنهادها و ساخت دیتابیس را
بدون اتصال به تلگرام بررسی می‌کند.
