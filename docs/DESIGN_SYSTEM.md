# Mizan ERP — Design System & Visual Canon

## 1. Color Palette Tokens
| Token | Hex Value | Semantic Purpose |
|---|---|---|
| `brand-deep` | `#0A2540` | Deep Midnight Blue / Primary executive branding |
| `brand-primary`| `#1E3A8A` | Classic Corporate Blue / Primary buttons & active tabs |
| `brand-accent` | `#0D9488` | Clinical Teal / Status indicators & highlights |
| `surface-bg` | `#F8FAFC` | Light Cool Slate / Application background |
| `surface-card` | `#FFFFFF` | Crisp White / Elevated cards & tables |
| `text-primary` | `#0F172A` | Slate 900 / High-contrast page titles & table data |
| `text-muted` | `#64748B` | Slate 500 / Subtitles, labels & helper metadata |
| `border-subtle`| `#E2E8F0` | Slate 200 / Standard card borders & dividers |
| `state-success`| `#10B981` | Emerald / Confirmed, active, paid, healthy |
| `state-warning`| `#F59E0B` | Amber / Pending, waiting queue, expiring soon |
| `state-error` | `#EF4444` | Red / Critical, cancelled, overdue, code blue |

## 2. Typography
- **Primary Font Family:** Inter / IBM Plex Sans Arabic / system-ui.
- **Figures & Quantities:** Fixed-width font (`font-mono` / tabular numbers) for prices, percentages, dates, and medical identifiers.
- **Hierarchy:**
  - Page Titles: `text-xl sm:text-2xl font-bold tracking-tight text-[#0F172A]`
  - Section Headings: `text-base sm:text-lg font-bold text-[#0F172A]`
  - Body & Table Text: `text-xs sm:text-sm text-[#334155]`
  - Metadata & Badges: `text-[10px] sm:text-xs font-semibold`

## 3. Iconography
- Exclusively use `lucide-react`.
- Never use emojis as functional application icons.
- Standard sizes: `14px` (`size-3.5`), `16px` (`size-4`), `20px` (`size-5`).
