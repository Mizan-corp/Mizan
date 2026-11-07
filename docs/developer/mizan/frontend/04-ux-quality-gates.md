# Mizan — UI/UX Quality Gates & What AI Forgets
Source: ChatGPT Main chat, messages [60–61], Nov 2026
GPT model: gpt-6

---

## The Core Problem with AI-Assisted UI/UX

> "AI can make a SaaS look polished in a screenshot but feel frustrating during actual work."

For Mizan, the challenge is bigger than making the interface beautiful. An ERP is used **for hours every day**, often for repetitive, high-volume tasks. The UI must be:
- Visually premium (brand identity)
- Operationally efficient (speed + accuracy)
- Arabic-first and RTL-correct
- Accessible under real-world conditions (low light, gloves, rushed)

---

## 10 UI/UX Dimensions Most AI Misses

### 1. UX Consistency Across Modules
**What AI does wrong:** Builds each module with slightly different patterns — one uses a Sheet, another uses a Dialog, another uses a full page. One uses toast errors, another uses inline validation.

**What Mizan requires:**
- Same component for same concept everywhere
- `PageHeader` on every screen — no exceptions
- `ListState` (skeleton → error → empty → content) wrapping every data list
- `StatusBadge` for every status display
- Errors always via sonner toast + inline validation — never bare alerts
- Sheet for side panels, Dialog for confirmations, never improvise

### 2. Information Architecture and Navigation
**What AI does wrong:** Groups navigation by data model (Customers, Products, Invoices) instead of user workflow (نقطة البيع، المبيعات، المخزون، الموردين).

**What Mizan requires:**
- Navigation grouped by user workflow, not data model
- Permission-gated nav items — hide what the user can't access
- Trial banner visible but never blocking
- Branch/warehouse selector in topbar
- Ctrl+K global search palette
- Active shift badge in topbar

### 3. Workflow Design — Not Just Screen Design
**What AI does wrong:** Designs screens without mapping to actual user jobs. Creates CRUD forms instead of workflow screens.

**What Mizan requires:**
- Every screen maps to a specific user job
- POS flow: Cashier must complete a sale in under 30 seconds
- Invoice flow: From draft → confirm is one clear action
- Shift flow: Open shift → sell → close shift → Z-report
- Payroll flow: Draft → review → approve → pay — distinct states with clear actions
- Never design a screen without first defining its user job

### 4. Dense Data Interfaces
**What AI does wrong:** Adds padding, makes everything spacious. Results in tables that require scrolling to see 5 rows.

**What Mizan requires:**
- Tables must be scannable at a glance
- Secondary columns `hidden sm:table-cell` — only primary columns on mobile
- Fixed-width `.num` columns for money — never variable-width financial data
- `gap-3` in dense lists, `gap-4` inside cards, `gap-6` on page rhythm
- POS: large touch targets (h-14 / 56px primary buttons) while maximizing product visibility

### 5. Forms and Data Entry
**What AI does wrong:** Validates on blur (annoying). Shows generic error messages. Uses placeholder text instead of labels.

**What Mizan requires:**
- Labels always visible, never placeholder-only
- Validate on submit, not on blur
- Arabic error messages — specific, actionable
- Disabled fields show WHY they're disabled
- Form submit: disable the button while loading, show spinner, re-enable on error
- After `POST /platform/signup`: fetch `/auth/me` before `setUser`

### 6. Feedback and System States
**What AI does wrong:** Leaves users wondering if their action worked. No loading states. No empty states. Generic error messages.

**What Mizan requires:**
- Every async action shows loading state (skeleton or spinner)
- Success: sonner toast `position="top-center" dir="rtl"`
- Error: sonner toast + specific Arabic message + retry action
- Network failure message: `«تعذر الاتصال بالخادم — تحقق من اتصال الإنترنت»`
- Never leave the user on a blank screen
- Empty states have one primary CTA (not just "No data")
- Filtered-empty has a "reset filters" action; first-use-empty has a "create" action

### 7. Destructive and Irreversible Actions
**What AI does wrong:** No confirmation. Or confirmation that says "Are you sure?" without explaining what gets deleted.

**What Mizan requires:**
- Confirm dialog for every: cancel invoice, delete product, wipe demo data, approve payroll
- Show exactly what will happen: "This will cancel invoice #INV-001043 and restore 5 units to stock"
- Clearly state if it cannot be undone
- Never auto-dismiss a confirm dialog
- Invoice, payment, stock movement records: soft-delete only — never hard delete

### 8. Accessibility and Localization
**What AI does wrong:** RTL layout breaks (icons flip wrong direction, numbers read right-to-left). Touch targets too small.

**What Mizan requires:**
- `dir="rtl"` on the document root
- Logical CSS properties: `ms-`, `ps-`, `end-` (never `margin-left`, `padding-left`, `right:`)
- All user-facing text in Arabic
- Minimum interactive size: 36px (`h-9`); absolute floor 32px in dense tables
- Focus ring visible: `focus-visible:ring-[3px] ring-ring/30`
- No global outline removal
- All icons: Lucide — stroke 1.25 for large decorative glyphs
- `.num` class on every figure: LTR-isolated, tabular lining

### 9. Performance as a UX Requirement
**What AI does wrong:** Doesn't think about loading time. Fetches all data at once. No optimistic updates.

**What Mizan requires:**
- Skeleton screens, not spinners — shaped like the actual content
- TanStack Query for server state — automatic cache, background refresh
- Optimistic updates in POS flow (add item immediately, reconcile with server)
- Offline queue for POS sales (IndexedDB, `lib/offline.ts`)
- PWA service worker: network-first navigations, never caches `/api/`
- No N+1 queries — use `selectinload` or `joinedload`

### 10. Visual Hierarchy and Brand Discipline
**What AI does wrong:** Introduces new colors, shadows, and border styles not in the design system. Makes every section a card. Uses charts for everything.

**What Mizan requires:**
- All colors from `styles.css` tokens — never hardcoded hex
- All spacing from Tailwind scale
- No new border or shadow values outside design system
- Chart 1–5 colors: brand / gold / teal / magenta / sky
- Cards only for genuine containers: POS cart, forms, modals
- Dashboard: masthead, not card grid
- Every section carries a heading — never orphan content

---

## UI/UX Quality Gate Checklist

### Design system
- [ ] All colors from `styles.css` tokens — none hardcoded
- [ ] All spacing from Tailwind scale
- [ ] All icons Lucide, sizes 16/18/20, never emoji
- [ ] Typography: IBM Plex Sans Arabic, scale 24/20/16/14/12px
- [ ] `.num` class on every financial figure
- [ ] `--brand-hue` CSS variable used for tenant customization (not hardcoded color)

### Workflow and usability
- [ ] `PageHeader` on every screen (no exceptions)
- [ ] `ListState` wraps every data list (skeleton → error → empty → content)
- [ ] One dominant action per state (including filtered-empty vs first-use-empty)
- [ ] Empty state has a meaningful CTA (not just "No data")
- [ ] Destructive actions have a confirm step explaining what happens

### Tables and forms
- [ ] Secondary columns `hidden sm:table-cell`
- [ ] Financial columns fixed-width with `.num`
- [ ] Form validation shows Arabic error messages
- [ ] Submit button disabled while loading

### Accessibility and localization
- [ ] `dir="rtl"` on document
- [ ] All interactive elements ≥ 36px touch target
- [ ] Focus ring visible on all interactive elements
- [ ] All user-facing text in Arabic
- [ ] No `margin-left`/`padding-left`/`right:` — use logical properties

### Performance
- [ ] No N+1 queries in new endpoints
- [ ] Skeleton screens for all async data (not spinners)
- [ ] Optimistic updates in POS flow
- [ ] PWA service worker in place (network-first, never caches /api/)

### Before completion
- [ ] `npm test` passes (9 unit tests)
- [ ] `npx tsc -b --noEmit` passes
- [ ] `npm run build` passes
- [ ] e2e suite if touching auth, sales, stock, or payroll

---

## The Most Important Review Question

When an AI finishes a screen, don't ask only:
> "Does this look professional?"

Ask:
> **"Can a real employee complete the actual task quickly, confidently, and without making a costly mistake?"**

That is the difference between a beautiful SaaS UI and a good ERP product.

---

## Specific Mizan UX Patterns

### POS (نقطة البيع)
- Barcode scanner always listening (`useBarcodeScanner`)
- F2/F3/Esc keyboard shortcuts for POS actions
- F1–F10 velocity shortcuts modal
- Offline queue in IndexedDB (`lib/offline.ts`)
- Replay queue with conflict classification on reconnect
- Fixed bottom bar for mobile primary action (safe-area padded)
- Cashier must complete a sale in under 30 seconds

### Dashboard
- One dominant tabular figure at 5xl (مبيعات اليوم)
- Inline SVG sparkline next to the figure
- Ruled sections with overline labels
- NO PageHeader on dashboard (exception to the rule)
- NO KPI card grid

### Navigation
- Navy brand rail (deep, constant in both themes)
- Grouped nav from `lib/nav.ts`, permission-gated
- Branch selector (from `/stock/warehouses`)
- Live shift badge
- Ctrl+K search palette
- Theme toggle
- User menu
- Trial banner (not blocking)
- Sidebar upsell card (for plan upgrade)
