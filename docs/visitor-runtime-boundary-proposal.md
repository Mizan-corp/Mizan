# Visitor runtime boundary, proposed read-only first slice

Status: DESIGN ONLY, 24 November 2026. No public route, publication permission change, migration or visitor command implemented by this document. Existing dynamic publish409 remains in force. Implementation must pass the checks below before that guard changes.

## Current source facts

- SitePage stores separate draft_tree/published_tree and draft/published/archived status. Revisions are immutable snapshots. Site settings are live shared configuration rather than part of the page draft transaction.
- Authenticated site/data preview accepts a supplied tree, requires site.manage, validates provider plans and resolves with the current tenant context. It is not safe to make this endpoint anonymous.
- The data registry is an explicit trusted allowlist. Core profile is separately authored; inventory selections and optional retail price/product media are default off. Section product subsets narrow consent, not grant it.
- Tenant context and PostgreSQL app role/RLS are part of isolation. A public request must bind its independently resolved tenant before any page, settings or provider reads, and clear it on every exit.
- The isolated website adapter currently contains signup/developer routes, not a site-page runtime. A new runtime must not reuse account or developer endpoints as a visitor capability.

Source paths: shared/backend/app/platform/site/{models,router,service}.py, shared/backend/app/platform/site/storefront/{router,registry,card_runtime}.py, shared/backend/app/platform/tenancy/context.py. The isolated deployment adapter was inspected at api/website.py in the deployment package, its canonical repository path must be verified before implementation.

## First slice

Anonymous GET/HEAD of one published native page, in one explicitly activated isolated test site. No anonymous tree submissions, provider query API, module discovery, product search endpoint, shopper account, form submission, cart, tracking or checkout. Do not expose source tree, provider plans, internal IDs, policy selections, edit tokens, revisions, draft titles or debugging output.

The result is rendered HTML only. Product image addresses already intentionally consented to website display may occur in that HTML. No server-side fetching of media, URLs from page content or external templates. No arbitrary plugins or modules loaded from client metadata.

## Tenant and site resolution

An explicit owner-controlled site activation record is required. Existing tenant slug or custom_domain values alone do not activate anonymous data access. Record enabled state and an audience/policy version distinct from Studio preview consent. New activation defaults disabled. Preview consent must not silently become public consent after deployment.

For the isolated path-based test host, use one server-configured allowlisted host and an exact site slug lookup. Reject ambiguous/unknown hosts and slug mismatches. For future custom hosts, use only an already verified host-to-site mapping. Never trust client tenant UUIDs, arbitrary forwarded-host headers, cookies from another workspace, query parameters or guessed subdomains. Use the hosting platform's trusted host normalization and an explicit allowlist. Normalize once, reject malformed/duplicate host values, ports and unsupported encodings.

Resolve activation using the minimum platform lookup, then bind tenant/app role and read only that site's page/settings. Ensure suspended/deactivated workspaces cannot be served. Public serving identity is not an ERP user and has no owner permission fallback.

## Publication and data authorization

Require site enabled, page status published and published_tree present. Render published_tree only, never draft_tree, including on resolution failure. Revalidate all declared languages, sources, bounds and target scopes against the trusted allowlist. Current active modules and website record/field consent must still apply at request time. A published plan cannot freeze old consent forever.

Owner activation must explicitly explain that the selected names, checked prices and checked owned images become visible to any visitor. Separate permission is needed for this public audience. Keep Studio settings notice accurate. Scope the activation so that an owner knows whether later policy edits affect the public site immediately. Do not infer activation from a prior private preview approval.

No static fallback for unavailable dynamic sources. A failure must not reveal template prices, placeholder contact details or stale consented data. Return an agreed generic unavailable/not-found response with no private error reason. Do not silently serve partially resolved pages. Unknown page, draft and archived page should not reveal which hidden page exists.

## Caching and revocation

Begin with Cache-Control: private, no-store and no shared response cache. Confirm CDN/framework do not override it. Revocation, archive, module disable, site disable and tenant suspension must take effect on the next request. Do not claim immediate revocation with a cache that has no tested invalidation path. No edge cache, stale-while-revalidate or browser service worker for these pages in the first slice.

A later cache needs tenant/site/page/language/theme/policy version keys and verified invalidation on every relevant state change, including image provenance and module activation. Never share errors or personalized responses across tenants.

## Response and resource controls

Keep existing native node/size and provider limits; enforce aggregate page limits before reads. Bound database queries and rendering time, rate-limit anonymous requests, allow GET/HEAD only and disallow credential-dependent personalization. No arbitrary language/device strings or paths. Device adaptation should be responsive CSS rather than a cache-key bypass.

Set HTML content type, no-sniff and an appropriate CSP based on inspected renderer output and media sources. Escape page text and validate links/media using existing reviewed rules; do not relax URL or SVG policies. Error responses must not include stack traces, SQL, record identifiers or policy bodies. Operational logs may record request/site outcome, never secrets or source payloads.

## Acceptance gates before enabling

1. Explicit activation authority and original user evidence for the new visitor audience. Default disabled tested through real routes, including an existing tenant with private preview consent.
2. Cross-tenant host/slug/path/header/cookie fuzzing, unknown and suspended site cases, RLS binding and context cleanup under failure/concurrent requests. No unbound ORM reads after site lookup.
3. Draft/private/archive routes return no content. Published page renders only the published tree. Draft edits stay invisible. Removing consent, disabling inventory, archiving or disabling the site affects the next uncached GET.
4. Other-language invalid sources and aggregate overflow fail before provider reads. Missing optional fields hide; source failures do not return partial/static data. No source tree or internal metadata in HTML/errors.
5. Real API/DB rollback tests plus anonymous browser inspection desktop/mobile. Verify headers at the canonical host and inspect actual pixels. No authenticated session may be required for the anonymous acceptance browser.
6. Existing Studio and ERP checks remain healthy. Isolated candidate HTML/assets first, reversible canonical test promotion, immediate checks and rollback on failure. No production changes.

## Later, separate decisions

Shopper identity and own-record ownership are prerequisites for order/invoice or repair tracking. Public tracking codes require a separately reviewed unguessable capability and minimized fields, not ERP IDs. Part requests/contact forms need explicit destination, retention, spam/rate controls and idempotent delivery. Commerce needs pricing/tax/stock/reservation/payment authority and verified cancellation/refund behavior. None belongs in a read-only binding provider.

Complete templates, navigation, catalog browsing/filtering and benchmark visual work can continue independently. A rendered product list does not establish enquiry, repair or commerce parity.
