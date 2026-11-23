"""Social images (1200x630 PNG per page type and language) and the PNG icons, in the brand style.

Run when the copy or the brand changes, then commit public/og/ and public/icons/:
    python3 scripts/og-images.py          (needs Python Playwright with Chromium, and Pillow)
Development tool only: the production image never runs it.
"""
import base64
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "src" / "assets" / "fonts"
OG = ROOT / "public" / "og"
ICONS = ROOT / "public" / "icons"
MARK = (ROOT / "public" / "icon.svg").read_text()

# (title, subtitle) per page type; keep them true (see src/seo/pages.ts).
COPY = {
    "home": {
        "ar": ("أدر أعمالك بتوازن", "الحسابات والمخازن والمبيعات والكاشير في نظام واحد"),
        "en": ("Run your business in balance", "Accounting, inventory, sales and POS in one system"),
    },
    "product": {
        "ar": ("منصة واحدة متصلة", "فاتورة الكاشير تخصم المخزون وتُرحّل القيد تلقائيًا"),
        "en": ("One connected platform", "A sale updates stock and posts the journal entry"),
    },
    "features": {
        "ar": ("مميزات ميزان", "محاسبة، نقاط بيع، مخازن، مشتريات، موارد بشرية"),
        "en": ("Mizan features", "Accounting, POS, inventory, purchasing, HR"),
    },
    "industries": {
        "ar": ("ميزان لكل نشاط", "تجزئة، مطاعم، صيدليات، عيادات، مواد بناء وخدمات"),
        "en": ("Built for your trade", "Retail, restaurants, pharmacies, clinics and more"),
    },
    "pricing": {
        "ar": ("أسعار واضحة بالجنيه المصري", "تجربة مجانية 14 يومًا بدون وسيلة دفع"),
        "en": ("Clear prices in Egyptian pounds", "A free 14-day trial, no payment details"),
    },
    "about": {
        "ar": ("عن ميزان", "منصة مصرية لإدارة الأعمال من السويس"),
        "en": ("About Mizan", "An Egyptian business platform from Suez"),
    },
    "contact": {
        "ar": ("تواصل معنا", "واتساب وهاتف: +20 106 779 0350"),
        "en": ("Contact us", "WhatsApp and phone: +20 106 779 0350"),
    },
    "demo": {
        "ar": ("جرّب شاشات ميزان", "لوحة التحكم والمبيعات والمخزون"),
        "en": ("Try Mizan's screens", "The dashboard, sales and stock"),
    },
    "blog": {
        "ar": ("مدونة ميزان", "مقالات عن الأنظمة والكاشير والمحاسبة"),
        "en": ("The Mizan blog", "On systems, point of sale and accounting"),
    },
    "docs": {
        "ar": ("دليل استخدام ميزان", "خطوة بخطوة، من إنشاء الحساب إلى النسخ الاحتياطي"),
        "en": ("Mizan documentation", "Step by step, from signup to backups"),
    },
    "legal": {
        "ar": ("الشروط والسياسات", "الاستخدام والخصوصية والاسترداد"),
        "en": ("Terms and policies", "Terms, privacy and refunds"),
    },
}

def font(name: str) -> str:
    # Inlined: a page opened with set_content can't read file:// fonts.
    return "data:font/woff2;base64," + base64.b64encode((FONTS / name).read_bytes()).decode()


FONT_FACES = f"""
@font-face {{ font-family: Naskh; src: url("{font('noto-naskh-arabic-400-arabic.woff2')}"); font-weight: 400 700; }}
@font-face {{ font-family: Plex; src: url("{font('ibm-plex-sans-arabic-500-arabic.woff2')}"); font-weight: 500; }}
@font-face {{ font-family: Cormorant; src: url("{font('cormorant-garamond-400-latin.woff2')}"); font-weight: 400 700; }}
@font-face {{ font-family: Manrope; src: url("{font('manrope-400-700-latin.woff2')}"); font-weight: 400 700; }}
"""


def og_html(lang: str, title: str, subtitle: str) -> str:
    ar = lang == "ar"
    return f"""<!doctype html><html lang="{lang}" dir="{'rtl' if ar else 'ltr'}"><head><meta charset="utf-8"><style>
{FONT_FACES}
html,body {{ margin:0; width:1200px; height:630px; overflow:hidden; }}
body {{ background:#35151D; color:#FAF6F0; position:relative; overflow:hidden;
  font-family:{'Plex, Manrope' if ar else 'Manrope'}, sans-serif; }}
.arc {{ position:absolute; border:1.5px solid rgba(250,246,240,.08); border-radius:50%; }}
.wrap {{ position:absolute; inset:72px 84px; display:flex; flex-direction:column; justify-content:space-between; }}
.brand {{ display:flex; align-items:center; gap:18px; }}
.tile {{ width:76px; height:76px; border-radius:20px; background:#FAF6F0; display:grid; place-items:center; }}
.tile svg {{ width:54px; height:46px; }}
.name {{ font-family:{'Naskh, Cormorant' if ar else 'Cormorant'}, serif; font-size:44px; font-weight:{700 if ar else 600}; }}
h1 {{ margin:0; font-family:{'Naskh, Cormorant' if ar else 'Cormorant'}, serif; font-weight:{600 if ar else 500};
  font-size:{76 if ar else 84}px; line-height:1.2; max-width:960px; }}
.sub {{ margin-top:22px; font-size:32px; color:#E7D6C1; font-weight:500; max-width:960px; line-height:1.45; }}
.foot {{ display:flex; justify-content:space-between; align-items:center; font-size:26px; color:#E7D6C1; }}
.dot {{ display:inline-block; width:12px; height:12px; border-radius:50%; background:#D4626E; margin-inline-end:12px; }}
.url {{ font-family:Manrope, sans-serif; letter-spacing:.5px; direction:ltr; }}
</style></head><body>
<div class="arc" style="width:900px;height:900px;{'left' if ar else 'right'}:-380px;top:-300px"></div>
<div class="arc" style="width:640px;height:640px;{'left' if ar else 'right'}:-250px;top:-170px"></div>
<div class="arc" style="width:380px;height:380px;{'left' if ar else 'right'}:-120px;top:-40px"></div>
<div class="wrap">
  <div class="brand"><div class="tile">{MARK}</div><div class="name">{'ميزان ERP' if ar else 'Mizan ERP'}</div></div>
  <div><h1>{title}</h1><div class="sub">{subtitle}</div></div>
  <div class="foot"><span><span class="dot"></span>{'منصة مصرية لإدارة الأعمال' if ar else 'Business management, made in Egypt'}</span><span class="url">allmizan.live</span></div>
</div></body></html>"""


def icon_html(size: int, pad: float, radius: int) -> str:
    inner = int(size * (1 - 2 * pad))
    return f"""<!doctype html><html><head><style>html,body{{margin:0;width:{size}px;height:{size}px;}}
body{{background:#FAF6F0;display:grid;place-items:center;border-radius:{radius}px;}}
svg{{width:{inner}px;height:{int(inner * 40 / 48)}px;}}</style></head><body>{MARK}</body></html>"""


def main() -> None:
    OG.mkdir(parents=True, exist_ok=True)
    ICONS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 630})
        for key, langs in COPY.items():
            for lang, (title, subtitle) in langs.items():
                page.set_content(og_html(lang, title, subtitle), wait_until="load")
                page.evaluate("document.fonts.ready")
                out = OG / f"{key}-{lang}.png"
                page.screenshot(path=str(out), omit_background=False)
                Image.open(out).convert("RGB").save(out, optimize=True)
        # Icons: apple-touch (180, full bleed: iOS rounds it), any (192/512), maskable (512, 20% safe zone), logo.
        for name, size, pad in [("apple-touch-icon", 180, 0.14), ("icon-192", 192, 0.12), ("icon-512", 512, 0.12),
                                ("maskable-512", 512, 0.24), ("logo-512", 512, 0.12), ("favicon-32", 32, 0.06)]:
            page.set_viewport_size({"width": size, "height": size})
            page.set_content(icon_html(size, pad, 0), wait_until="load")
            out = ICONS / f"{name}.png"
            page.screenshot(path=str(out))
            Image.open(out).convert("RGB").save(out, optimize=True)
        browser.close()
    Image.open(ICONS / "favicon-32.png").save(ROOT / "public" / "favicon.ico", sizes=[(32, 32)])
    (ICONS / "favicon-32.png").unlink()
    print(f"{len(list(OG.glob('*.png')))} social images, icons in {ICONS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
