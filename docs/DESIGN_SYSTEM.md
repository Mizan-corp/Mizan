# Mizan ERP — Design System & Visual Canon

The look is **warm editorial**: a merchant's ledger, not a generic admin template. Brand
background, voice and the full identity: [`developer/mizan/frontend/08-brand-identity-full.md`](developer/mizan/frontend/08-brand-identity-full.md).
Screen-level rules: [`UI_UX_GUIDELINES.md`](UI_UX_GUIDELINES.md) and [`ui-ux-kit/`](ui-ux-kit/).

## 1. Tokens, never colours

Screens never write a colour. They use the **design tokens**, the CSS variables in
`system/core/frontend/src/styles.css`, through Tailwind (`bg-background`, `text-foreground`,
`bg-card`, `border-border`, `bg-primary text-primary-foreground`, `text-muted-foreground`,
`bg-sidebar`…). A workspace's theme sets the tokens, so every screen follows it (section 2).

| Token | Purpose | Mizan theme, light | dark |
|---|---|---|---|
| `background` / `foreground` | Page and its text | `#FAF6F0` / `#262321` | `#270F16` / `#FAF6F0` |
| `card` / `card-foreground` | Cards, tables, dialogs (`popover` too) | `#FFFFFF` / `#262321` | `#35151D` / `#FAF6F0` |
| `primary` / `primary-foreground` | The one main action, active states, brand | `#651E2C` (oxblood) / `#FAF6F0` | `#D4626E` / `#270F16` |
| `secondary`, `muted`, `accent` (+ `-foreground`) | Quiet surfaces, hovers, selected rows | `#E7D6C1`, `#EFE4D6`, `#EFE4D6` | `#481D26`, `#3D161F`, `#4D1B26` |
| `muted-foreground` | Labels, help, metadata | `#77716E` | `#BCA39B` |
| `destructive`, `success`, `warning` | Status: refused/overdue, done/paid, waiting/expiring | `#C14E50`, `#27835C`, `#C58A35` | `#E05A68`, `#34A876`, `#E0A346` |
| `border`, `input`, `ring` | Lines, fields, focus ring | `#E6DCD2`, `#E6DCD2`, `#651E2C` | translucent, `#D4626E` |
| `sidebar`, `sidebar-foreground`, `sidebar-primary`, `sidebar-accent`, `sidebar-border`, `sidebar-ring` | The side rail | `#35151D` (deep merlot) … | `#1F0A11` … |
| `chart-1` … `chart-5` | Charts, in order | `#651E2C`, `#B86B76`, … | |

- Status colours keep their meaning in every theme: a theme may tint them, never swap them.
- Status is a dot and a word, never colour alone.

## 2. Themes (ADR-010 D3)

A workspace has **one theme pack**, chosen by its admin (module centre → المظاهر, permission
`themes.manage`), seen by everyone in it, its login page and its printed invoices included. A
theme sets the tokens for light and dark, the fonts, the corner radius, the shadows and the
motion. Users choose only what is theirs, on their device: dark mode, layout and density.

- **Where themes come from**: Mizan's six (`system/core/backend/app/themes/`: mizan, slate, cobalt,
  emerald, amber, monokai, the default being *mizan*), the activity's
  (`activities/<activity>/themes/`), and signed theme packages from developers.
- **Checked before use** (`theme_problems` in `app/framework/manifest.py`): known tokens only,
  `#hex` / `rgb()` / `oklch()` values, and readable contrast (4.5 for text on background, card
  and sidebar; 3 for the other pairs). A new theme must pass the same checks.
- **Applied by** `system/core/frontend/src/lib/theme.ts`: the tokens become variables on
  `html[data-theme="workspace"]` (and `html.dark[…]`), with `@font-face`, `--radius`, the
  shadow preset and `data-motion`.

## 3. Typography

- **Interface:** IBM Plex Sans Arabic for Arabic, Manrope for Latin (`--font-sans`, which a
  theme's `fonts.body` replaces).
- **Display headings** (`.font-display`): Noto Naskh Arabic in Arabic, Cormorant Garamond in
  English (a theme's `fonts.display` replaces them).
- **Numbers:** always Western digits (`ar-EG-u-nu-latn`), tabular and isolated from the Arabic
  text around them (`.num`); codes and ids in `.code` / `font-mono` (IBM Plex Mono).
- **Hierarchy:** page title `text-xl sm:text-2xl font-bold text-foreground`; section
  `text-base sm:text-lg font-bold`; body and tables `text-sm`; metadata `text-xs text-muted-foreground`.
- Mixed scripts: an English id, email or code inside Arabic text sits in its own
  `dir="ltr"` isolated span (`inline-block` or `<bdi>`), so punctuation stays in place.

## 4. Shape, depth, density and motion

- **Radius:** one base, `--radius` (Mizan: 0.875rem); `rounded-sm…4xl` scale from it.
- **Shadows:** presets `flat`, `soft` (default), `raised`, chosen by the theme; content is
  separated by lines and space before shadows.
- **Density:** `compact` (default, for all-day work) or `comfortable` (`data-density`); a theme
  may suggest one, the user's choice wins.
- **Motion:** short and purposeful; `data-motion="reduced"` or `"none"` from the theme, and the
  system's *reduce motion* setting, always honoured.

## 5. Iconography

- Exclusively `lucide-react`; a theme or module names icons by their lucide name
  (`CalendarCheck`).
- Never use emojis as functional application icons.
- Standard sizes: `14px` (`size-3.5`), `16px` (`size-4`), `20px` (`size-5`); arrows and chevrons
  that point "forward" flip in RTL (`rtl:-scale-x-100`).

## 6. Where each look applies

| Surface | Look |
|---|---|
| The ERP (`system/`) | The workspace's theme |
| The owner panel, the admin panel | Mizan's own tokens (the admin panel is English, LTR) |
| The website and the developer platform | The warm editorial brand palette directly (`#651E2C`, `#FAF6F0`, `#E7D6C1`…); the developer platform is English (LTR) by default with Arabic on request |
