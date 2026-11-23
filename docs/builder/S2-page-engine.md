# S2: the page engine lands

## Status

Proposed 2026-11-23. Working note for ADR-015 step S2, not yet accepted architecture.
The contract lives in [page-engine.md](page-engine.md); this note records what of it is code.

## What landed (branch `feat/s2-page-engine`)

| Piece | File | Notes |
|---|---|---|
| Block registry v0 + page-tree validator | `shared/backend/app/framework/manifest.py` (appended section) | `PAGE_BLOCKS` is data, versioned per block; `page_problems()` returns what is wrong, manifest-style |
| The SDK copy | `sdk/python/mizan_sdk/manifest.py` | Byte for byte the same file; a drift test keeps them identical (ADR-016 D4) |
| Server renderer | `shared/backend/app/platform/site/render.py` | Platform side only; stdlib-only like the validator |
| Platform tests | `system/backend/tests/test_site_pages.py` | 20 tests, no database needed |
| SDK tests | `sdk/python/tests/test_pagetree.py` | 2 tests: the validator ships and a minimal page round-trips |

## Validator coverage

- Root must be a `section`; levels `section → columns → column → blocks`, with `canvas` as the
  one free-positioning section child allowed per page.
- Node ids (`n_…`) are well-formed and unique across the page; unknown block types fail.
- Settings are per device (`desktop`, `tablet`, `mobile`); only schema-declared keys, typed
  values (`bool`, spacing tokens, choices, 1–6 counts).
- Content is per language; only the block's declared fields, in the site's languages when given.
- `button` hrefs are http(s), `mailto:`, `tel:`, site paths or anchors. `video_embed` frames only
  the allow-listed hosts (`PAGE_EMBED_HOSTS`, ADR-015 D2). Size limits: 500 nodes, 12 deep.

## Renderer coverage

- Every string is escaped; `text` and `html` blocks pass an allow-list sanitizer (formatting
  tags survive; scripts, styles, event handlers, `javascript:` URLs and foreign iframes do not).
  The `html` block adds structural tags (`div`, `img`, tables, `h2–h4`) and still no iframes.
- `video_embed` renders an `<iframe>` only for allow-listed hosts.
- Per-device visibility applies at render; the published tree renders identically on every pass
  (no mutation of the input tree).
- `render_document()` emits the SEO head: per-language title and description, canonical,
  hreflang alternates, Open Graph, `dir="rtl"` for RTL languages, and the theme's colors as CSS
  variables (only values that parse as colors are emitted).

## Not in this slice (per the ADR-015 roadmap)

- Storage (`site_pages`, `site_page_revisions`), the REST API and publish/rollback flows: S2's
  next slice, together with RLS tests.
- Theme HTML templates in sandboxed Jinja2 (ADR-015 D6): arrive with site themes at S5; v0 blocks
  render from platform templates only.
- The site runtime script, edge caching and purge hooks: with the site service.
- The studio (the builder web interface, ADR-016 D3): S3, on top of this engine.

## Verification

Run on a monorepo mirror with the changed files overlaid:

- `system/backend/tests/test_site_pages.py`: 20 passed.
- `sdk/python/tests/test_pagetree.py`: 2 passed.
- `ruff check --select E9,F63,F7,F82,F821,F601,F401,F841` (the CI selection): clean on every
  touched file.
- Existing validator behaviour unchanged: the change to `manifest.py` is additive (module
  docstring plus an appended section); the full backend suites need the CI runners and were not
  run here.

A rendered demo (Arabic RTL and English, desktop and mobile, using Mizan's own theme) is
attached to the branch discussion as `demo-*.html`.
