<div dir="rtl">

# whycached

**دیپلوی کردی ولی هنوز نسخه‌ی قدیمی رو می‌بینی؟** `whycached URL` پیدا می‌کنه **کدوم لایه‌ی کش** داره نسخه‌ی قدیمی رو بهت می‌ده: CDN جلوی سرورت، کش HTTP مرورگر خودت، یک service worker، یا اسم فایلی که هیچ‌وقت عوض نمی‌شه. با آزمایش اثبات می‌کنه (جوابِ یک درخواست عادی رو با جواب واقعیِ origin مقایسه می‌کنه) و بعد دقیقاً همون کاری که برای اون لایه لازمه (purge، هارد‌ریلود، حذف service worker) رو چاپ می‌کنه.

[English](README.md) | فارسی

</div>

```text
$ whycached https://shop.example.com/ --expect "v2"
HTTP 200 · 56 bytes · layers: Cloudflare

STALE (1)

✗ shared · a shared cache (Cloudflare) is serving an older copy than the origin
    why:    the normal response differs from the cache-busted one
            'v2' is MISSING in the normal response and present in the fresh one
            Age: 4120 = the copy you got is 68m 40s old
    fix:    Dashboard > Caching > Configuration > Purge Cache > Custom Purge > the URL
```

<div dir="rtl">

(خروجی کوتاه‌شده است؛ خروجی واقعیِ دموی آفلاین در [docs/demo.txt](docs/demo.txt) و یک اجرا روی یک سایت واقعی (GitHub Pages) در [docs/real-github-pages.txt](docs/real-github-pages.txt) هست.)

## چرا؟

«فیکس رو پوش کردم ولی هیچی عوض نشد» تقریباً هیچ‌وقت مشکل کد نیست. بین کامیت تو و پیکسلی که می‌بینی چهار پنج تا کش هست؛ هرکدوم قانون خودش و راه پاک کردن خودش رو داره و علامتشون یکیه. آدم‌ها (و ایجنت‌های هوش مصنوعی) حدس می‌زنن: دوباره دیپلوی، دوباره تغییر کد، هارد‌ریلود، صبر. `whycached` حدس رو با یک آزمایش عوض می‌کنه: همون URL به چهار شکل مختلف گرفته می‌شه و بایت‌به‌بایت مقایسه می‌شه.

ابزارهای موجود هدرها رو آفلاین توضیح می‌دن یا سیاست کش رو شبیه‌سازی می‌کنن. `whycached` زنده‌ست: به همون URL که می‌بینی وصل می‌شه و می‌گه **کدوم لایه** مقصره (در [NOVELTY.md](NOVELTY.md) نوشتم چی جستجو شده و چی وجود داره).

## نصب

پایتون ۳٫۹ به بالا، بدون وابستگی. روی لینوکس تست شده؛ فقط از کتابخانه‌ی استاندارد استفاده می‌کنه پس روی macOS و ویندوز هم باید کار کنه ولی هنوز تست نشده.

</div>

```sh
pipx install git+https://github.com/mrzroot/whycached      # هنوز روی PyPI منتشر نشده
uvx --from git+https://github.com/mrzroot/whycached whycached --demo
pip install -e .                                           # از یک کلون محلی
```

<div dir="rtl">

## استفاده

</div>

```sh
whycached https://example.com/page                 # تشخیص برای یک URL
whycached https://example.com/ --expect "v2.4.1"   # متنی که باید در نسخه‌ی جدید باشه؛ حدس رو تبدیل به اثبات می‌کنه
whycached URL -H "Authorization: Bearer ..."       # هدر اضافه
whycached URL --no-assets                          # CSS/JS لینک‌شده رو نگیر
whycached URL -v                                   # همه‌ی probeها
whycached URL --json                               # خروجی ماشینی
whycached --demo                                   # آفلاین: یک سرور محلی که مثل ۳ دیپلوی خراب رفتار می‌کنه
```

<div dir="rtl">

**کد خروج:** `0` چیزی پیدا نشد · `1` چیزی STALE یا LIKELY بود · `2` دریافت ممکن نشد.

## چه کار می‌کنه

فقط درخواست `GET` می‌فرسته (هیچ‌وقت purge نمی‌کنه و چیزی رو تغییر نمی‌ده):

- **درخواست عادی (دو بار)**: هدرها، `Age`، `X-Cache` / `CF-Cache-Status` / `x-vercel-cache` و تغییر hit/miss بین دو بار.
- **همون URL با `?_whycached=<nonce>`**: نسخه‌ای که تقریباً هیچ‌وقت توی کش مشترک نیست؛ نزدیک به چیزی که origin الان می‌ده.
- **درخواست با `Cache-Control: no-cache`**: یک کش درست‌رفتار رو مجبور به revalidate می‌کنه.
- **درخواست شرطی** (`If-None-Match` / `If-Modified-Since`): آیا origin `304` می‌ده.

بعد برای هر لایه نتیجه می‌گیره:

- **کش مشترک (CDN / پراکسی)، اثبات‌شده.** اگه جواب عادی با جواب cache-bust یا no-cache فرق داشته باشه، یا `--expect` در جواب عادی نباشه ولی در جواب تازه باشه → `STALE`، با اسم لایه، سنِ نسخه (`Age`)، مدت تازگی و دستور purge مخصوص همون سرویس. شناخته‌شده‌ها: Cloudflare، Fastly، GitHub Pages، Vercel، CloudFront، Netlify، Akamai، Azure Front Door، Varnish، کش nginx/پراکسی، `Cache-Status` (RFC 9211) و `Age` ساده.
- **مرورگر خودت.** تازگیِ کش خصوصی رو حساب می‌کنه (از جمله حدس ۱۰٪ وقتی فقط `Last-Modified` هست) و می‌گه مرورگر تا کی قانوناً می‌تونه بدون پرسیدن از سرور از نسخه‌ی خودش استفاده کنه، با راه هارد‌ریلود.
- **Service worker.** `serviceWorker.register(...)` رو توی HTML پیدا می‌کنه (یا اسم‌های مرسوم مثل `sw.js`) و خودِ worker رو می‌خونه: Cache API / Workbox / cache-first، `skipWaiting`، اسم کش‌ها، و باگ کلاسیکِ سرو شدن خودِ فایل worker با `max-age` بلند.
- **فایل‌های استاتیک.** CSS/JS هم‌مبدأ که یک روز یا بیشتر کش می‌شن ولی اسمشون هش یا نسخه نداره.
- **مشکل کش نیست.** اگه `--expect` در هیچ پاسخی نباشه همین رو می‌گه: دیپلوی تموم نشده یا محیط اشتباهه.

سطح‌ها: `STALE` = با شواهد اثبات شده، `LIKELY` = دلیل قانونی که مرورگرت نسخه‌ی قدیمی نشون بده، `NOTE` = خوبه بدونی، `OK`.

## محدودیت‌ها (لطفاً بخون)

- داخل مرورگر تو رو نمی‌بینه. یافته‌های مرورگر و service worker **دلیل‌هایی‌اند که ممکنه رخ بدن**، نه اثبات اینکه همین تب کهنه‌ست. هارد‌ریلود یا پنجره‌ی خصوصی تکلیف رو روشن می‌کنه.
- تضمینی نیست درخواست cache-bust به origin برسه؛ بعضی CDNها query string رو در کلید کش نادیده می‌گیرن (روی GitHub Pages هم همین‌طوره). `no-cache` و `--expect` دو راستی‌آزمایی مستقل‌اند.
- کش‌های هر منطقه/کاربر/دستگاه (POPهای CDN، `Vary`، کوکی) ممکنه با چیزی که این ماشین می‌بینه فرق کنن.
- امضای هدرها بر اساس رفتار عمومی سرویس‌ها تا اکتبر ۲۰۲۶ هست و ممکنه تغییر کنه.

## توسعه

</div>

```sh
pip install -e ".[test]" && pytest     # ۳۱ تست، فقط سرور محلی، بدون اینترنت
```

<div dir="rtl">

لایسنس MIT · ساخته‌ی [محمدرضا زارع (mrzroot)](https://github.com/mrzroot) · صفحه‌ی معرفی: https://mrzroot.github.io/whycached/

</div>
