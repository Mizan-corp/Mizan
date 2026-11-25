# Studio search and form blocks - safe design research (G1/G6)

Status: DESIGN RESEARCH ONLY. No block types, renderer support, visitor-side
JavaScript, endpoints, or authority changes are shipped or proposed as shipped.
Every point that needs owner or platform approval is listed explicitly under
"Unresolved consent/action points" and nothing in that list has been implemented.

## Context and constraints

- Gaps G1 (no search element) and G6 (no input/form element) from
  `docs/studio-allwirya-recreation-gaps.md` block a faithful no-code allwirya
  clone: allwirya's header search is central and its contact/newsletter forms
  are visible on the page.
- Current block surface: the native registry (`nativeTree.ts` settings/fields,
  `PAGE_BLOCKS` in `app/framework/manifest.py`), validation
  (`check_tree`/`page_problems`), the server renderer (`render.py
  _render_node`), and its React mirror (`treerender.tsx`). A new block type
  must land in all four plus editor support, or the renderers diverge.
- The visitor renderer today emits static escaped HTML with ZERO JavaScript;
  `sanitize_html` drops script content by design. Buttons are links only.
- Dynamic content (bindings/repeat/card) requires authorized provider
  resolution before rendering (`render.py` unresolved guard), and the
  synthetic boundary keeps `site_activation.allow_connected_data=false`.
- Product-card precedent: connected sections are consent-gated and hide
  themselves when nothing is consented; placeholder copy must never read as a
  real capability (owner's stated rule).

## Search (G1)

Option A - "search this page" client filter. Filters blocks of the current
page as the visitor types. Honest, no data leaves the browser, no endpoint.
BLOCKER: requires visitor-side JavaScript, which the visitor renderer does
not ship at all today (point 1 below). Without JS this option cannot exist.

Option B - site search via plain GET form. An HTML `<form method="GET">` with
one input is pure markup: it fits the zero-JS escaped renderer as-is. It needs
a same-origin search endpoint over the site's own published static content
(read-only, no module data). In synthetic scope there is no public site, so
the endpoint's availability is itself a scope decision (point 3). Server work:
bounded query over published page text, rate-limited, no per-visitor state.

Option C - store/product search over the module catalog. This is what
allwirya's header search actually is. It requires connected data: flipping
`allow_connected_data`, provider resolution, and the consent flow. Parked
until the owner approves that boundary (point 2).

Placement: header search (a `theme.header.search` chrome flag) versus a
regular page block is a product decision; chrome placement touches the shared
settings contract, block placement stays inside the page tree (point 6).

## Form (G6)

Option A - mailto compose form. `<form action="mailto:OWNER" method="GET">`
opens the visitor's own mail client. Pure markup, zero JS, nothing stored or
transmitted by Mizan. Honest labeling ("opens your mail app"). Needs the
owner's verified destination address (point 4). Weak mobile UX when no mail
client is configured; acceptable as an honest v0.

Option B - server-stored submissions. Real contact/newsletter capture. Needs
submission storage, retention policy, visitor privacy notice text, spam/rate
controls, and an owner-visible inbox. Every one of those is an approval point
(point 5), not an implementation detail.

Option C - webhook to an external service. External submission to a third
party; needs explicit owner authority and a URL allowlist. Parked (point 5).

## Unresolved consent/action points (exact)

1. Visitor-side JavaScript in rendered pages: any interactive block (live
   search filtering, client validation, dynamic show/hide) introduces the
   first JS into the visitor renderer. Platform-level decision; currently
   none exists and sanitization strips scripts.
2. Connected-data boundary: catalog-backed search requires flipping
   `site_activation.allow_connected_data` and provider resolution. Owner
   approval required; nothing may query module data before then.
3. Public search endpoint in synthetic scope: even a read-only GET search over
   the site's own pages needs a decision that such an endpoint may exist and
   be reachable in the synthetic deployment.
4. Form destination ownership: any mailto or inbox destination address must
   come from the owner and be verified as theirs before a form block can be
   configured with it.
5. Submission handling: storage, retention, privacy notice, and anti-spam for
   server-side forms; destination allowlist for webhooks. Owner approval
   required for each.
6. Placement decision: search in shared header chrome versus a page block.

## What does NOT need new authority (preparable now)

- Registry/validation/editor shape for a GET-form search block and a mailto
  form block, kept unlisted from the Insert panel until enabled.
- Renderer markup and mirrored React components for both, inert without a
  configured destination/endpoint, with tests.
- This preparation is still implementation work and waits for the parent's
  go; LIVE enabling of either block waits for the numbered points it depends
  on (search: 1 or 3, and 2 for catalog scope; form: 4, and 5 for anything
  beyond mailto).

## Recommendation

Smallest honest v0: the mailto contact form block (pure markup, no JS, no
storage) once point 4 is satisfied, and defer all search variants until the
platform decides visitor-side JS (point 1) or approves the endpoint (point 3).
Do not ship a decorative search box: a search input that searches nothing real
is exactly the fictional-capability pattern the owner banned.
