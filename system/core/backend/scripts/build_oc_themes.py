#!/usr/bin/env python3
"""Generate Mizan theme packs from Open Color (MIT) shades + bundled OFL fonts.

Every palette here is an ORIGINAL combination designed for Mizan from the
MIT-licensed Open Color catalog (scripts/open-color/); nothing is copied from a
third-party palette collection. Each theme bundles its real font files (SIL OFL
1.1, license text included in assets/) so the preview and the applied workspace
render the same face. Run from the repo root:

    python3 system/core/backend/scripts/build_oc_themes.py

Regenerating overwrites app/themes/<id>/ for the ids in SPECS only.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.framework.manifest import theme_problems  # noqa: E402

OC = json.loads((ROOT / "scripts/open-color/open-color.json").read_text())
FONTS_STAGE = Path("/downloads/branding-fonts")
THEMES = ROOT / "app/themes"

# Font bundles: file name (as shipped in assets/) -> (family, weight, source file).
FONT_FILES = {
    "cairo.ttf": ("Cairo", "200 900", "Cairo[slnt,wght].ttf", "cairo-OFL.txt"),
    "tajawal-400.ttf": ("Tajawal", "400", "Tajawal-Regular.ttf", "tajawal-OFL.txt"),
    "tajawal-700.ttf": ("Tajawal", "700", "Tajawal-Bold.ttf", "tajawal-OFL.txt"),
    "almarai-400.ttf": ("Almarai", "400", "Almarai-Regular.ttf", "almarai-OFL.txt"),
    "almarai-700.ttf": ("Almarai", "700", "Almarai-Bold.ttf", "almarai-OFL.txt"),
}
FAMILY_LICENSE = {"Cairo": "cairo-OFL.txt", "Tajawal": "tajawal-OFL.txt", "Almarai": "almarai-OFL.txt"}

# Original palette designs. shades: Open Color family + indices for
# (bg, primary, secondary, accent, sidebar). Fonts: (body, display).
SPECS = [
    {"id": "ruby",    "oc": "red",    "name": "ياقوتي",   "name_en": "Ruby",    "fonts": ("Tajawal", "Cairo"),  "hue": 0,
     "desc": "أحمر ياقوتي دافئ على ورق فاتح. تركيبة أصلية من ألوان Open Color (MIT)."},
    {"id": "rose",    "oc": "pink",   "name": "وردي",    "name_en": "Rose",    "fonts": ("Almarai", "Cairo"),  "hue": 340,
     "desc": "وردي ناعم وهوية مضيئة. تركيبة أصلية من ألوان Open Color (MIT)."},
    {"id": "grape",   "oc": "grape",  "name": "عنبي",    "name_en": "Grape",   "fonts": ("Tajawal", "Tajawal"),"hue": 290,
     "desc": "عنبي عميق وهادئ. تركيبة أصلية من ألوان Open Color (MIT)."},
    {"id": "violet",  "oc": "violet", "name": "بنفسجي",  "name_en": "Violet",  "fonts": ("Cairo", "Cairo"),    "hue": 275,
     "desc": "بنفسجي واثق مع تباين واضح. تركيبة أصلية من ألوان Open Color (MIT)."},
    {"id": "indigo",  "oc": "indigo", "name": "نيلي",    "name_en": "Indigo",  "fonts": ("Almarai", "Tajawal"),"hue": 255,
     "desc": "نيلي رسمي مناسب للشركات. تركيبة أصلية من ألوان Open Color (MIT)."},
    {"id": "ocean",   "oc": "blue",   "name": "محيطي",   "name_en": "Ocean",   "fonts": ("Tajawal", "Cairo"),  "hue": 215,
     "desc": "أزرق محيطي نظيف. تركيبة أصلية من ألوان Open Color (MIT)."},
    {"id": "cyan",    "oc": "cyan",   "name": "سماوي",   "name_en": "Cyan",    "fonts": ("Almarai", "Almarai"),"hue": 190,
     "desc": "سماوي منعش وخفيف. تركيبة أصلية من ألوان Open Color (MIT)."},
    {"id": "teal",    "oc": "teal",   "name": "فيروزي",  "name_en": "Teal",    "fonts": ("Cairo", "Tajawal"),  "hue": 170,
     "desc": "فيروزي متزن للخدمات الصحية والمهنية. تركيبة أصلية من ألوان Open Color (MIT)."},
    {"id": "olive",   "oc": "green",  "name": "زيتوني",  "name_en": "Olive",   "fonts": ("Tajawal", "Almarai"),"hue": 145,
     "desc": "أخضر زيتوني طبيعي. تركيبة أصلية من ألوان Open Color (MIT)."},
    {"id": "lime",    "oc": "lime",   "name": "ليموني",  "name_en": "Lime",    "fonts": ("Almarai", "Cairo"),  "hue": 95,
     "desc": "ليموني حيوي بروح شابة. تركيبة أصلية من ألوان Open Color (MIT)."},
    {"id": "honey",   "oc": "yellow", "name": "عسلي",    "name_en": "Honey",   "fonts": ("Tajawal", "Tajawal"),"hue": 50,
     "desc": "عسلي دافئ للمطاعم والحلويات. تركيبة أصلية من ألوان Open Color (MIT)."},
    {"id": "tangerine","oc": "orange", "name": "ماندرين", "name_en": "Mandarin",   "fonts": ("Cairo", "Almarai"),  "hue": 25,
     "desc": "برتقالي ماندين جريء. تركيبة أصلية من ألوان Open Color (MIT)."},
]

GRAY = OC["gray"]  # neutral scale shared by every palette

def _lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    def ch(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def ratio(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def pick_primary(oc: list[str]) -> tuple[str, str]:
    for idx in (5, 6, 7, 8, 9):
        if ratio("#FFFFFF", oc[idx]) >= 3.5:
            return oc[idx], "#FFFFFF"
    # light family (yellow/lime): use a mid shade with dark text instead
    for idx in (6, 7, 8, 9, 5):
        if ratio(GRAY[9], oc[idx]) >= 3.5:
            return oc[idx], GRAY[9]
    return oc[9], "#FFFFFF"


def _mix(a: str, b: str, t: float) -> str:
    ha, hb = a.lstrip("#"), b.lstrip("#")
    ch = [round(int(ha[i:i + 2], 16) * (1 - t) + int(hb[i:i + 2], 16) * t) for i in (0, 2, 4)]
    return "#" + "".join(f"{c:02X}" for c in ch)


def pick_sidebar(oc: list[str]) -> tuple[str, str]:
    """Darkest family shade, deepened toward black until white text passes 4.6."""
    bg = oc[9]
    for step in range(0, 9):
        candidate = _mix(bg, "#000000", step * 0.08)
        if ratio("#FFFFFF", candidate) >= 4.6:
            fg = oc[0] if ratio(oc[0], candidate) >= 4.6 else "#FFFFFF"
            return candidate, fg
    return _mix(bg, "#000000", 0.64), "#FFFFFF"




def pick_fg(bg: str, preferred: list[str], threshold: float = 3.2) -> str:
    for cand in preferred:
        if ratio(cand, bg) >= threshold:
            return cand
    return GRAY[9]

def light(oc: list[str]) -> dict:
    return {
        "background": oc[0], "foreground": GRAY[9],
        "card": "#FFFFFF", "card-foreground": GRAY[9],
        "popover": "#FFFFFF", "popover-foreground": GRAY[9],
        "primary": pick_primary(oc)[0], "primary-foreground": pick_primary(oc)[1],
        "secondary": oc[1], "secondary-foreground": pick_fg(oc[1], [oc[8], oc[9], GRAY[9]]),
        "muted": GRAY[1], "muted-foreground": GRAY[7],
        "accent": oc[2], "accent-foreground": pick_fg(oc[2], [oc[9], oc[8], GRAY[9]]),
        "destructive": OC["red"][7], "destructive-foreground": "#FFFFFF",
        "success": OC["green"][7], "success-foreground": "#FFFFFF",
        "warning": OC["yellow"][7], "warning-foreground": GRAY[9],
        "border": oc[2], "input": oc[2], "ring": pick_primary(oc)[0],
        "chart-1": pick_primary(oc)[0], "chart-2": oc[5], "chart-3": OC["teal"][6],
        "chart-4": OC["orange"][6], "chart-5": GRAY[6],
        "sidebar": pick_sidebar(oc)[0], "sidebar-foreground": pick_sidebar(oc)[1],
        "sidebar-primary": oc[6], "sidebar-primary-foreground": "#FFFFFF",
        "sidebar-accent": oc[8], "sidebar-accent-foreground": oc[0],
        "sidebar-border": oc[8], "sidebar-ring": oc[6],
    }


def dark(oc: list[str]) -> dict:
    return {
        "background": GRAY[9], "foreground": GRAY[0],
        "card": GRAY[8], "card-foreground": GRAY[0],
        "popover": GRAY[8], "popover-foreground": GRAY[0],
        "primary": oc[4], "primary-foreground": GRAY[9],
        "secondary": GRAY[7], "secondary-foreground": oc[0],
        "muted": GRAY[8], "muted-foreground": GRAY[5],
        "accent": GRAY[7], "accent-foreground": oc[1],
        "destructive": OC["red"][5], "destructive-foreground": GRAY[0],
        "success": OC["green"][5], "success-foreground": GRAY[0],
        "warning": OC["yellow"][4], "warning-foreground": GRAY[9],
        "border": "rgba(255, 255, 255, 0.12)", "input": "rgba(255, 255, 255, 0.16)", "ring": oc[4],
        "chart-1": oc[4], "chart-2": oc[6], "chart-3": OC["teal"][4],
        "chart-4": OC["orange"][4], "chart-5": GRAY[5],
        "sidebar": GRAY[9], "sidebar-foreground": GRAY[0],
        "sidebar-primary": oc[4], "sidebar-primary-foreground": GRAY[9],
        "sidebar-accent": GRAY[8], "sidebar-accent-foreground": GRAY[0],
        "sidebar-border": GRAY[8], "sidebar-ring": oc[4],
    }


FAMILY_REF = {"Cairo": "cairo", "Tajawal": "tajawal", "Almarai": "almarai",
              "Manrope": "manrope", "Cormorant Garamond": "cormorant-garamond"}
PALETTES = THEMES / "_palettes"


def build(spec: dict) -> None:
    oc = OC[spec["oc"]]
    body, display = spec["fonts"]
    refs, seen = [], set()
    for fam in (body, display):
        if fam not in seen:
            seen.add(fam)
            refs.append({"ref": FAMILY_REF[fam]})
    colors = {"light": light(oc), "dark": dark(oc)}
    theme = {
        "id": spec["id"], "name": spec["name"], "name_en": spec["name_en"], "version": "1.0.0",
        "kind": "theme", "description": spec["desc"],
        "palette": spec["id"],
        "fonts": {"body": body, "display": display, "files": refs},
        "radius": "0.625rem", "shadows": "soft", "motion": "full",
        "preview": {"source": "open-color-mit", "designed_for": "mizan"},
    }
    palette = {
        "id": spec["id"],
        "source": "Original Mizan combination designed from Open Color (MIT) shades",
        "license": "MIT (Open Color), original composition",
        "colors": colors,
    }
    # validate the expanded form consumers see (registry refs resolved)
    from app.platform.themes.service import _expand_font_refs

    expanded = {**_expand_font_refs(theme), "colors": colors}
    expanded.pop("palette", None)
    problems = theme_problems(expanded)
    if problems:
        raise SystemExit(f"{spec['id']}: theme_problems: {problems}")
    tdir = THEMES / spec["id"]
    if tdir.exists():
        shutil.rmtree(tdir)
    tdir.mkdir(parents=True)
    (tdir / "theme.json").write_text(json.dumps(theme, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PALETTES.mkdir(exist_ok=True)
    (PALETTES / f"{spec['id']}.json").write_text(json.dumps(palette, ensure_ascii=False, indent=2) + "\n",
                                                 encoding="utf-8")
    print(f"built {spec['id']}: palette + {len(refs)} font refs, contrast-clean")


def main() -> None:
    for spec in SPECS:
        build(spec)
    print(f"{len(SPECS)} themes generated")


if __name__ == "__main__":
    main()
