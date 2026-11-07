# Mizan — Brand Identity & Design System
Source: ChatGPT Main chat (62 messages), Nov 2026 — messages [36–55]
GPT model: gpt-6 / gpt-6-mini

---

## Brand Name
**ميزان (Mizan)** = "balance" or "scale" in Arabic.
Core identity: balance, clarity, and control for a multi-tenant ERP platform.

---

## Brand Direction: Warm Editorial Luxury

Chosen direction (from message [40]): **Warm Editorial Luxury**
> "Burgundy, cream, charcoal, refined typography, premium and sophisticated."

This is NOT:
- A luxury fashion website
- A generic ERP template
- Navy + green fintech dashboard (rejected as "too predictable")

This IS:
- Editorial, premium business platform
- Visual confidence of a luxury brand
- Usability of a modern SaaS product
- An enterprise SaaS brand with personality

### Rejected directions (message [39])
1. **Industrial Precision** — steel, gunmetal, electric blue, high-contrast monochrome
2. **Warm Editorial Luxury** ✓ CHOSEN — burgundy, warm ivory, dark charcoal
3. **Desert Modernism** — sand, olive, warm black
4. **Swiss Minimal** — black, white, cool gray, sharp orange accent

---

## Color System (Warm Editorial Luxury)

### Primary palette
| Role | Color | Notes |
|---|---|---|
| Primary / Oxblood Burgundy | `#651E2C` | Signature brand color and primary actions |
| Deep Merlot | `#35151D` | Dark surfaces, hero areas, and sidebar |
| Background / Warm Ivory | `#F5EBDD` | Main light background; never pure white |
| Charcoal | `#262321` | Primary text and interface elements |
| Muted Rose | `#B86B76` | Secondary accents and highlights |
| Soft Sand | `#E7D6C1` | Secondary surfaces and borders |
| Accent | `#C58A35` | Warm amber for highlights; use sparingly |

The default tenant brand is Oxblood Burgundy. `--brand-hue` remains tenant-assignable;
custom hues must preserve readable contrast and must not recolor status meanings.

### Rules
- Color marks **state and one primary action** per screen — never pure decoration
- All contrast pairs ≥ 4.5:1
- Deep Merlot or Charcoal sidebar rail; never blue
- Warm Ivory is the main light surface; Charcoal is the main text color
- Oxblood Burgundy marks primary actions and selected states; do not use it everywhere
- Never hardcode hex values in components — always use `styles.css` tokens

### Light / Dark token mapping
| Role | Light theme | Dark theme |
|---|---|---|
| Background | Warm Ivory `#F5EBDD` | Deep Merlot `#35151D` |
| Surface | Pure White `#FFFFFF` or Soft Sand `#E7D6C1` | Deep Merlot `#35151D` or Charcoal `#262321` |
| Foreground | Charcoal `#262321` | Warm Ivory `#F5EBDD` |
| Muted text | Muted Text `#77716E` | Warm Ivory with accessible contrast |
| Primary | Oxblood Burgundy `#651E2C` | Muted Rose `#B86B76` or Warm Ivory |
| Sidebar | Deep Merlot `#35151D` | Charcoal `#262321` |
| Success / warning / error / information | `#27835C` / `#C58A35` / `#C14E50` / `#557DA1` | Adjust through semantic tokens for contrast |

Use the semantic CSS tokens in `styles.css`; these values define the brand palette,
not permission to hardcode colors in components.

---

## Typography

### Fonts
| Font | Role |
|---|---|
| **IBM Plex Sans Arabic** | Primary — all Arabic and mixed text |
| **Plex Mono** | Codes, reference numbers, financial IDs |
| **Manrope** | Marketing website headlines (editorial feel) |

> Marketing website: editorial typography (Manrope/custom). ERP dashboard: IBM Plex Sans Arabic almost exclusively. This contrast = premium brand without sacrificing usability.

### Scale
| Size | Use |
|---|---|
| 24px | Page titles, dashboard masthead figures |
| 20px | Section headers |
| 16px | Body, table rows |
| 14px | Secondary text, labels |
| 12px | Minimum — captions, helper text |
| 11px | Sidebar group labels (one exception) |
| Never below 12px |

### Numerals
- Always use `.num` class (tabular, lining, LTR-isolated)
- Always use `ar-EG-u-nu-latn` locale — Western digits, never Arabic-Indic
- Large money figures: `num font-bold tracking-tight`
- Currency suffix: `text-base font-medium text-muted-foreground`

---

## Composition Language: "دفتر اليوم" (The Daily Ledger)

The app composes like a **trading-house daily sheet**, NOT a SaaS admin template.

| Element | What it is | What it is NOT |
|---|---|---|
| Dashboard | Masthead — one dominant tabular figure (مبيعات اليوم at 5xl) + inline SVG sparkline + ruled sections | KPI card grid |
| Tables | Open ledgers — `TableShell` = scroll container only, no border/bg box | Boxed grid with background |
| Stats | Borderless — overline label / 2xl value / hint, rhythm by type | Cards with borders and shadows |
| Status | Small dot + text (`StatusBadge`) | Bold colored chips |
| Money | Large figures `num font-bold tracking-tight`, currency suffix smaller | Colored boxes |
| Cards | Only for genuine containers: POS cart, forms, modals | Every section wrapper |

---

## Marketing Website Design System

### Purpose split
- **Marketing website** (landing, pricing, signup, onboarding): editorial, luxurious, expressive, motion-rich
- **ERP dashboard**: restrained, readable, operationally efficient

### Landing page sections
From the design prompt (message [48]):
1. Hero — dominant headline + product visual + primary CTA
2. Social proof / trust strip
3. Feature showcase — interactive demo panels
4. Industries served — module grid
5. Pricing
6. Documentation portal teaser
7. Blog / content hub
8. Contact / demo request
9. Footer

### Arabic typography rule
> DO NOT use image-generated Arabic text. Always implement Arabic text in actual HTML/CSS with real Arabic fonts. Image generation is for visual composition only (colors, layout, atmosphere).

---

## Motion & Animation System

### Chosen stack: GSAP + Motion (Framer Motion) + Lenis

| Library | Role | Package |
|---|---|---|
| **GSAP** | Complex timelines, scroll triggers, SVG morphing, parallax orchestration | `gsap @gsap/react` |
| **Motion** (Framer Motion) | Per-component micro-interactions, layout transitions, presence animations | `motion` |
| **Lenis** | Smooth scroll normalization — wraps entire app scroll container | `lenis` |
| **Rive** | Interactive animated illustrations (marketing hero only, optional) | |
| **Three.js / R3F** | 3D hero elements (marketing only, optional) | |

```bash
npm install gsap @gsap/react motion lenis
```

### Scroll effects (premium / "$9,000 website" feel)
| Effect | What it does |
|---|---|
| Scroll-triggered reveals | Headlines, images, sections reveal as you scroll |
| Parallax scrolling | Background layers move at different speeds from foreground |
| Horizontal scroll sections | Features or product screens scroll sideways within a pinned vertical section |
| Scroll-pinned storytelling | Section "sticks" while content animates inside |
| Smooth scroll | Lenis replaces browser default — fluid deceleration |
| Counter animations | Numbers count up as they enter the viewport |
| Path drawing | SVG lines draw themselves on scroll |
| Morphing shapes | Organic blob/shape transitions |

### Architecture rules
- GSAP for orchestrated sequences and scroll triggers
- Motion for React component animations
- Lenis wraps the entire app scroll container
- **Never mix GSAP and Motion on the same element**
- `prefers-reduced-motion` must collapse ALL animations to a still version
- Page transitions: 150ms fade/4px-rise keyed by route
- Spring: stiffness 300 / damping 30, stagger 0.04s, reveal ≤ 0.6s
- No inline `style` props in feature code — use `styles.css` classes
- Pause control required for animations > ~5 seconds
- Homepage = most ambitious scrolling experience
- Product/Features = interactive pinned showcases
- Pricing/Contact/Blog/Docs = lighter motion

### Responsibility split
| Tool | Use for |
|---|---|
| GSAP | Hero entrance, scroll-triggered sequences, timeline orchestration, number counters, SVG path drawing |
| Motion | Button hover/tap, card entrance, modal/sheet transitions, navigation bar changes |
| Lenis | All smooth scrolling |

---

## Component System

### Core components (from `frontend/src/components/kit/`)
shadcn/ui v4 on @base-ui/react — 34 components, owned and editable.

### Page primitives (from `frontend/src/components/app/shared.tsx`)
| Component | Purpose |
|---|---|
| `PageHeader` | Every screen — title (2xl semibold) + description + action buttons |
| `StatCard` | Overline label / 2xl value / hint — no border |
| `KpiTile` | Dashboard KPI |
| `ListState` | skeleton → error → empty → content pattern |
| `StatusBadge` | Arabic + API English key badge |
| `TableShell` | Scroll container for all tables |
| `TablePagination` | Pagination row |

### Rules
- `PageHeader` on **every** screen — no exceptions
- `ListState` wraps **every** data list
- Minimum interactive size: **36px** (`h-9`); floor 32px in dense tables
- Icons: **Lucide only** — never emoji — sizes 16/18/20
- Radius: `--radius: 0.625rem` → cards/dialogs `rounded-xl`, controls `rounded-md`
- Shadows: `shadow-xs` resting, `shadow-md` hover, `shadow-lg` overlays only
- RTL first: `dir="rtl"` document, logical properties (`ms-`, `ps-`, `end-`)
