# Visitor runtime V1 milestone - read-only published-page slice

Status: PREPARATION, 24 November 2026. Builds on docs/visitor-runtime-boundary-proposal.md (DESIGN ONLY), which remains the governing boundary document. Nothing in this milestone is public, deployed, or schema-mutating until the decision gates below are explicitly approved with owner evidence.

## Goal

Close the top missing capability toward the allwirya no-code goal: a published Mizan site page renders for an anonymous visitor as HTML, outside the Studio private preview, on the isolated test site only. Read-only: no forms, cart, search, tracking, shopper identity, checkout, custom domains, or response caching.

## Verified source facts (24 November 2026)

- The isolated canonical host `mizan-studio-feature-test.vercel.app` is already anonymously reachable (unauthenticated GET /api/health returns 200). No platform SSO gate exists on the production domain, so any enabled public route is genuinely public. Today no visitor page route exists.
- The isolated website adapter is `deploy/studio-test/control-plane/website.py`; it mounts only `website_api.routers.signup` and `website_api.routers.developers`. The canonical website package is `website/backend/` (package `website_api`).
- `SitePage` carries `status`, `draft_tree`, `published_tree` (app/platform/site/models.py). Publish is `POST /api/site/pages/{id}/publish` under `site.manage` (app/platform/site/router.py, service.py `publish`).
- The authenticated resolution pipeline (storefront/router.py `preview`) already implements exactly the resolution order V1 needs: `service.check_bound_tree` -> card/repeat/plain resolution via `resolve_cards` / `resolve_composition` / `resolve_tree` -> `render_page`. All provider reads run against current module settings, so consent revalidation at request time is inherent to reuse.
- The Python renderer `app/platform/site/render.py` (`render_page`, `render_document`) refuses trees with unresolved bindings and only emits constrained, escaped theme chrome and allow-listed links.

## Work items

0. **Server gate (config).** `PUBLIC_SITE_HOST` env setting (empty default = route disabled server-side). The route answers only when the request Host exactly equals the configured registered domain AND a matching activation row exists: client headers can never widen the audience, and activation rows on other deployments stay inert. Set as a non-secret env var on the isolated test project only.
1. **Activation record (additive migration, needs D2).** New table `site_activation`: tenant_id (FK), host (exact, lowercase), slug (exact), page_path (exact), enabled boolean NOT NULL DEFAULT false, allow_connected_data boolean NOT NULL DEFAULT false, theme jsonb (synthetic-scope chrome, served INSTEAD of shared site_settings), audience_policy_version text, activated_by user id, timestamps. One row per exact (host, slug, page_path) triple, so an unrelated published page in the same site can never be served without its own row. No activation means no anonymous data access; existing tenant slugs/domains alone never activate. `allow_connected_data=false` refuses any tree with data-binding/provider nodes (`bindings`/`card`/`repeat` anywhere), refuses absolute destinations outside the activation host (mailto/tel refused outright), and never reads the tenant's shared site_settings (business profile fields cannot leak through chrome): this is the enforceable synthetic-content boundary, in code, not policy. The private-preview consent (`inventory_website_cards_v0`) is never consulted on the public route and does not authorize public-audience data; public connected data requires its own explicit later approval and a new consent version.
2. **Public router `website/backend/website_api/routers/public_pages.py`.** GET/HEAD only. Path: `/site/{slug}/{page_path}` on hosts with a matching activation row; activation rows are the host allowlist (attacker-supplied Host can only match a row registered for that exact host; X-Forwarded-Host is never read). Resolution order: normalize host once (reject malformed/duplicate/port-bearing hosts) -> exact (host, slug, page_path) activation lookup with enabled=true under a request-local bypass that is cleared before any tenant-scoped read -> bind tenant context + app role -> load page by (tenant, path) requiring status=published and published_tree present -> refuse card/repeat trees unless allow_connected_data -> run the shared resolution pipeline on published_tree with an anonymous SourceContext -> `render_document` with the site's current settings as theme -> HTML response. Any failure: one generic 404/503 with no private reason, no partial render, no static fallback. Audit: the isolated website app mounts only signup (/plans, /signup), developers (all data routes bearer-protected), and public_pages; no other anonymous path serves site pages or product data.
3. **Response controls.** `Cache-Control: private, no-store`; `X-Content-Type-Options: nosniff`; HTML content type; CSP derived from inspected renderer output (theme inline style block + consented image origins only). Anonymous rate limit per IP+site. Aggregate page bounds checked before provider reads (existing manifest limits). GET/HEAD only; no personalization.
4. **Tests** (mapped to the proposal's six acceptance gates):
   - G1: default-disabled activation returns 404 through real routes, including a tenant that has Studio preview consent (preview consent never implies public consent).
   - G2: cross-tenant host/slug/path/header/cookie fuzz; unknown and suspended sites; tenant context cleared on failure and concurrency; no unbound ORM reads after site lookup; RLS/bypass cleanup verified on the REAL pooled isolated test DB (two interleaved activation rows) before the synthetic page is enabled; spoofed registered Host through a different ingress rejected by the server-config gate.
   - G3: draft and archived pages return 404 identical to unknown pages (no existence oracle); published page renders published_tree only; edits to draft_tree stay invisible; consent removal, module disable, archive, and site disable change the next uncached GET.
   - G4: invalid language and aggregate overflow rejected before provider reads; missing optional fields hide; source failure returns the generic unavailable, never partial/static data; HTML and errors contain no source tree, internal IDs, edit tokens, revisions, or policy bodies.
   - G5: API/DB rollback tests plus anonymous desktop/mobile browser inspection with pixel checks at the canonical host.
   - G6: existing Studio and ERP suites stay green; isolated candidate first, reversible canonical promotion, immediate checks and rollback on failure.
5. **Docs**: update this file and technical-business-composition.md at each gate.

## Decision gates

- D1 - public audience (APPROVED 24 Nov 16:02, direct reply to the 15:57 scoped question): anonymously accessible page on the isolated test host with SYNTHETIC content only, no actual Mizan business data, no login. This approval does NOT cover public connected products, real catalog data, or unrelated published pages; those remain distinct later decisions. No inference from private preview approvals.
- D2 - schema (GROUNDED, not a separate user question): the additive `site_activation` migration on the isolated test DB sits inside the established test-deployment authority. Originals: 24 Nov 10:36 "approve what you see fit, keep in mind we run a full business" (wamid.HBgMMjAxNTU4Njk1MjAyFQIAEhggQUM3MDlFNkE1MUU0RThENDVCNjE1MEQzNzVENjFFQTgA), 24 Nov 12:24 "ok, continue work in Mizan" (wamid.HBgMMjAxNTU4Njk1MjAyFQIAEhggQUMwNUI1RTlGN0UxQzY5RTFEOEM3M0JBRTkzOEQ5NzcA), 23 Nov 22:10 "publish and bring the link and continue" (wamid.HBgMMjAxNTU4Njk1MjAyFQIAEhggQUM0MUZEMUJEN0VBN0UxMTg4NUI2RjFFMEIxRkJFRjAA). Standing constraints ban destructive migrations and production mutation; an additive, default-disabled, reversible table on the isolated environment is neither. Parent confirmed 24 Nov 15:57: ground this in original constraints rather than a new blanket rule.
- D3 - URL shape (CHOSEN, routine engineering): `https://mizan-studio-feature-test.vercel.app/site/{slug}/{page_path}`; `{slug}` is the activation record's exact site slug, `{page_path}` the published page path. Chosen within the isolated route; not a user-facing decision.

V1 is one milestone toward the public visitor site capability (assessment item C1), not its closure: navigation across public pages, catalog browsing, forms and tracking remain later slices.

Later, separately approved: contact/part-request forms, repair/order tracking (unguessable capability, minimized fields), shopper identity, commerce, custom hosts, and any shared cache (requires per-tenant/site/page/language/theme/policy keys plus tested invalidation).

## Non-goals for V1

No anonymous tree submissions, provider query API, module discovery, product search, shopper accounts, form submission, cart, tracking, checkout, edge/shared caching, service workers, or client-selected plugins. No changes to the authenticated Studio data endpoints' permission requirements.

## Rollout sequence

1. Branch preparation: migration + router + tests + docs, all local/candidate verified with activation default-disabled (route present, closed).
2. Candidate deploy on the isolated project; G1-G2, G4-G6 verified while disabled.
3. Only after D1-D4: enable activation for the isolated fixture site, run G3 and G5 anonymously, revoke-and-retry drill.
4. Reversible canonical test promotion, immediate checks, rollback path armed. No production-business deployment at any step.
