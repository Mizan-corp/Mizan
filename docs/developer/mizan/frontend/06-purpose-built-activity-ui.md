# Mizan — Purpose-Built UI Per Business Activity
Design direction: each module feels like a custom app built for that activity.
Not a generic ERP screen with a different label.

---

## The Principle

A restaurant cashier should feel like they're using a POS built for a restaurant. A gym receptionist should feel like they're using membership software built for a gym. A pharmacist should feel like they're using a pharmacy system.

**This is achieved through module self-configuration, not manual setup.** When a tenant selects their Business Activity, every activated module reads that activity and applies its Activity Profile automatically. The cashier never sees a generic ERP — they see a purpose-built application.

The shared backend and data model are invisible. The UI surface changes completely per activity.

---

## How It Works

Three layers stay the same across all activities:
1. The navigation rail (Mizan brand, always)
2. The data engine (same backend, RLS, tenancy)
3. The design tokens (same colors, typography, spacing)

Everything else adapts:
- Layout (portrait vs landscape, card vs list vs canvas)
- Primary interaction model (tap vs keyboard vs barcode)
- Information density (high for POS, medium for salon, low for field service)
- Dominant metaphor (receipt, calendar, floor plan, ledger, job card)
- Color emphasis (activity-specific accent on primary actions)

---

## Activity UI Profiles

### 1. Retail / متجر تجزئة
**Dominant metaphor:** Checkout counter
**Layout:** Two-pane landscape — product grid left, cart right
**Primary interaction:** Barcode scanner + numpad
**Density:** High — many items visible at once
**Key UI decisions:**
- Product tiles with large touch targets (min 72px)
- Cart as a running receipt (not a table)
- Payment modal with amount-tendered + change display
- Shift status bar always visible (open/closed)
- F2/F3/Esc keyboard shortcuts
- Offline indicator when queue active

### 2. Restaurant / Café — مطعم / كافيه
**Dominant metaphor:** Floor plan + ticket
**Layout:** Table map view → order view (two separate screens)
**Primary interaction:** Tap table → tap items → send to kitchen
**Density:** Medium
**Key UI decisions:**
- Table map (visual floor layout, color = table status: free/occupied/bill-requested)
- Kitchen ticket format: big item names, modifier notes, time since ordered
- KDS (Kitchen Display Screen): dark background, large font, timer per ticket
- Split bill as a first-class action
- Modifier selection as bottom sheet (not dialog)
- "Hold" and "Fire" controls per course

### 3. Pharmacy / صيدلية
**Dominant metaphor:** Dispensing counter
**Layout:** Search-first — large search bar dominates, results below
**Primary interaction:** Search by drug name / barcode / prescription ID
**Density:** Medium-high
**Key UI decisions:**
- Drug result card shows: stock, expiry nearest batch, substitutes
- Expiry warning: color shift (green → amber → red) as expiry approaches
- Prescription view: patient name, doctor, drugs, dispensed vs remaining
- "Substitute" button prominent on out-of-stock drugs
- Controlled drug flag: visually distinct (yellow border, lock icon)
- Receipt includes batch number and expiry date

### 4. School / معهد تعليمي
**Dominant metaphor:** Class register
**Layout:** Student list as primary, schedule as secondary
**Primary interaction:** Select student → record attendance / grade / fee
**Density:** Medium
**Key UI decisions:**
- Attendance: grid view (students as rows, dates as columns, tap to mark)
- Grade entry: spreadsheet-style for bulk entry
- Fee status: colored badge (paid / partial / overdue)
- Student card: photo, guardian contact, balance, upcoming sessions
- Timetable: week view with drag-to-reschedule

### 5. Wholesale / جملة
**Dominant metaphor:** Order book
**Layout:** Customer-first — select customer → create order
**Primary interaction:** Type / search item codes, enter quantities
**Density:** High
**Key UI decisions:**
- Order line: item code, description, qty, unit price tier, line total
- Customer credit status always visible (available credit, overdue)
- Price tier auto-applies based on quantity and customer class
- Bulk order entry: paste from Excel or CSV
- Delivery date picker on every order
- Landed cost allocation modal

### 6. Clinic / عيادة
**Dominant metaphor:** Patient file
**Layout:** Patient card dominant — timeline of visits on the right
**Primary interaction:** Search patient → open encounter
**Density:** Low-medium
**Key UI decisions:**
- Patient banner: name, age, blood type, allergies (always visible)
- Encounter form: chief complaint → vitals → diagnosis → prescription → billing
- Prescription: drug name + dose + frequency + duration — one line per drug
- Appointment calendar: physician columns, time slots as rows
- Insurance status badge on patient banner

### 7. Gym / جيم
**Dominant metaphor:** Membership card + calendar
**Layout:** Member lookup first, then membership status
**Primary interaction:** Scan card / search name → check in / book class
**Density:** Medium
**Key UI decisions:**
- Member card: photo, plan, days remaining, access status (green/red)
- Check-in: one tap → logged (no form)
- Class calendar: week view, capacity indicator per class (10/20)
- Booking: tap class → tap member → confirmed
- Membership expiry alert: banner 7 days before expiry
- Trainer commission: per-session counter visible on trainer profile

### 8. Salon / صالون
**Dominant metaphor:** Appointment book
**Layout:** Calendar as primary (time slots = rows, staff = columns)
**Primary interaction:** Tap slot → assign client + service
**Density:** Medium
**Key UI decisions:**
- Appointment block: client name, service, duration, staff color-coded
- Walk-in: tap "+" on current time slot
- Service checkout: services + products used → total → payment
- Commission tally visible on staff row
- No-show: red slot, fee auto-added to client account
- Client card: treatment history, product preferences, loyalty balance

### 9. Hotel / فندق
**Dominant metaphor:** Room map
**Layout:** Floor plan / grid of rooms → reservation panel
**Primary interaction:** Click room → view/change reservation
**Density:** Medium
**Key UI decisions:**
- Room grid: color = status (available/occupied/dirty/maintenance)
- Reservation card: guest name, check-in/out dates, nights, total
- Check-in: one-step with ID scan option
- Guest folio: running charges (room + restaurant + extras)
- Night audit: one button, auto-closes day
- Housekeeping view: simplified room status, no financial data

### 10. Field Service / صيانة
**Dominant metaphor:** Job card
**Layout:** Job list → job detail (technician's view)
**Primary interaction:** Open job → update status → add parts → close
**Density:** Medium
**Key UI decisions:**
- Job card: customer, equipment, problem description, status pipeline
- Status pipeline: New → Assigned → En Route → On Site → Done
- Parts used: barcode scan from van stock
- Time tracker: start/pause/stop buttons, auto-calculates billable hours
- Customer signature: touchscreen sign-off at close
- Photo attachment: camera button on job card

### 11. Construction / مقاولات
**Dominant metaphor:** Project board + site sheet
**Layout:** Projects list → project detail (phases, costs, timeline)
**Primary interaction:** Select project → drill into phase → approve cost
**Density:** Medium-high
**Key UI decisions:**
- Project dashboard: budget vs actual bar, % complete, cash flow trend
- WBS tree: expand/collapse phases and tasks
- Cost entry: category + amount + subcontractor + receipt attachment
- Progress billing: milestone → invoice generation
- Site daily report: manpower count + activities + issues + photo
- Variation order: change request → approval chain → cost update

### 12. Manufacturing / تصنيع
**Dominant metaphor:** Production board
**Layout:** Work orders as kanban (queued / in progress / done)
**Primary interaction:** Open work order → record output → consume materials
**Density:** High
**Key UI decisions:**
- Work order card: BOM item, quantity, work center, due date, status
- Material consumption: barcode scan or manual entry, lot tracking
- Quality hold: red status card, blocks dispatch
- OEE indicator per machine (green > 85%, amber > 65%, red below)
- Scrap entry: quantity + reason code → auto-adjusts BOM yield
- Production costing: real vs standard cost comparison

### 13. Real Estate / عقارات
**Dominant metaphor:** Property register
**Layout:** Property hierarchy (building → unit) → lease panel
**Primary interaction:** Select unit → view tenant / create lease
**Density:** Medium
**Key UI decisions:**
- Unit grid: color = occupancy status
- Lease card: tenant, start/end, monthly rent, next due date
- Rent collection: one-click "collect" → payment recorded
- Maintenance request: tenant submits → manager assigns → technician closes
- Rent escalation: scheduled alert + auto-calculate new amount

### 14. Travel Agency / سياحة
**Dominant metaphor:** Booking file
**Layout:** Booking list → booking detail (itinerary)
**Primary interaction:** Create booking → add services → generate invoice
**Density:** Medium
**Key UI decisions:**
- Itinerary builder: drag-and-drop timeline (flight → hotel → tour)
- Margin display: selling price - cost = margin % always visible
- Passenger manifest: list view with passport details
- Commission tracker: per supplier, per booking
- Invoice: multi-service layout, each service on its own line

---

## What Never Changes (Shared Chrome)

| Element | Always the same |
|---|---|
| Navigation rail | Navy, permission-gated, Mizan brand |
| Top bar | Branch selector, shift badge, Ctrl+K, theme toggle, user menu |
| Toast notifications | sonner, `position="top-center"`, `dir="rtl"` |
| Typography | IBM Plex Sans Arabic, same scale |
| `.num` class | On every financial figure, everywhere |
| Error messages | Arabic, specific, actionable |
| Loading states | Skeletons shaped like content |
| Destructive confirm | Always a dialog, always explains what happens |

---

## Implementation Rules for Agents

When building a module screen:

1. **Identify the activity type** — what business is this for?
2. **Find its metaphor** — what physical object does this replace? (receipt, appointment book, job card, floor plan)
3. **Set the layout** — does the user start from a list, a map, a calendar, or a search?
4. **Set the primary interaction** — tap, scan, type, drag?
5. **Set the density** — how much data needs to be visible at once?
6. **Build from the metaphor up** — not from a generic table down

Never start by placing a `PageHeader` + `TableShell` + filter bar. That is the generic ERP approach. Start from: "what does a [pharmacist / gym receptionist / hotel front desk] actually reach for first?"

---

## Agent Prompt for Purpose-Built Screens

> Before building a screen for [activity]:
> 1. What is the dominant metaphor for this activity? (receipt / calendar / floor plan / job card / ledger)
> 2. What does the user need to see FIRST when they open this screen?
> 3. What is the single most common action they take? Make that action 1 tap or 1 keystroke.
> 4. What information must always be visible (never hidden in a tab or modal)?
> 5. What would embarrass a professional in this field if the UI got wrong?
> Build from those 5 answers. The ERP data model is invisible.
