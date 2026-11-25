# Studio Gap Register (feat/studio-render-parity)

Durable register of every capability gap discovered while rebuilding a real
site (Wirya) through the Studio UI only. Each gap is a missing Studio
capability, not a site-specific shortcut. Items move to **Done** only when the
capability is editable through the Studio UI, verified live, and covered by
tests. This file is the acceptance checklist; nothing here may be silently
dropped or marked done by narration alone.

Conventions: "per-device" means the responsive authoring model (switch
desktop/tablet/mobile in the editor, edit each view manually, unset values
inherit from desktop).

## Done this branch (verified live, tests green)

| Area | Capability | Commits |
|---|---|---|
| Header composition | Row align (start/center/end/between/around/evenly) + precise gap slider 0-64px via `--row-gap` | e04f228 |
| Header per-device | Tablet/mobile overrides for density, hide search, hide bar, with desktop inheritance; visitor media classes `mz-t-*` (769-1024px) / `mz-m-*` (<=768px); mobile hide-bar also drops bar links from the menu sheet | 90be7e2, 6ecefe2 |
| Base CSS | Responsive columns media block kept last in `_BASE_CSS` (test pin) | 7f7cd91 |
| Search (data) | Public page `?q=` filters repeat items by case-insensitive substring on rendered display text; blank keeps all | 7e06431 |
| Search (wiring) | Header search form targets a UI-editable `search_target` header setting; the GET form submits `q` to that page. Verified by real typing + submit in the browser: header on wirya-home -> products-cd-e2e?q=... -> filtered items | pre-existing + 7e06431 |
| Search (empty state) | Zero-match query renders a localized (en/ar) "no results for q" text node instead of pruning the section; query-less pages keep the old prune behavior | 8083e86 |

## Open gaps

### Header / theme composition
1. **Per-device alignment, reorder, and gap.** `header.tablet` / `header.mobile`
   currently expose only `density`, `hide_search`, `hide_bar`. Row align,
   element order, and precise gap must also be settable per device.
2. **Arbitrary header sizing and colors.** Height, padding, background, text
   and accent colors beyond the fixed presets are not editable in the UI.
3. **Search scope is display-field-only.** `?q=` matches only the repeated
   heading/display field. Full searchable data scope (descriptions, SKUs,
   other typed fields) is not yet searchable; widening needs a consent and
   exposure review before more provider data is matchable.

### Catalog / navigation
4. **Category destinations.** Menu/bar items need link destinations that
   resolve to filtered collection pages (category landing), not only static
   URLs.
5. **Locale switch.** Site content is Arabic while the Studio UI is English;
   a visitor-facing locale switch and per-locale content editing are not
   available.

### Assets
6. **Original source-asset workflow.** Site authoring must use the original
   Wirya source assets through the UI (upload/media library), never
   hand-authored HTML/CSS/SVG or DB/API seeding. The hosted test host also
   refuses uploads (no blob storage) — that limitation must stay visible.

### Module capabilities (unimplemented module surface)
7. **Cookies consent.** Module capability must be real consent behavior, not
   decorative UI.
8. **Notifications UI blocks.** Real notification surface per the module
   semantics.
9. **Mobile app bottom panel.** Per `app-shell.tsx` source semantics.

### Verification / environment
10. **Desktop/LAN verification** is parked by user decision (workspace-scoped
    branding only).
11. **Screenshot capture hang** recurs intermittently in the CDP harness;
    unresolved flake, worked around with fresh-target captures.
12. **Combined pytest runs** of the whole backend test directory show
    cross-file isolation failures (9) unrelated to individual files; run
    affected files individually for signal.

## Out of scope by user ruling
- Salon adapter: stays an honestly labeled placeholder. No salon adapter.
- Hosted test deploy (mizan-studio-feature-test.vercel.app): link sharing
  deferred by user until asked. Deploy is 2+ commits behind HEAD; re-verify
  before any share.
