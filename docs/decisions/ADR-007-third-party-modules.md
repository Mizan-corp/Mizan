# ADR-007: Third-party modules: packages, scopes, isolation and the developer platform

## Status

Accepted; milestone 1 built (2026-11-13, see "Milestone 1 as built"). ADR-010 extends the same
packages to theme packs and whole business activities. Proposed 2026-11-12. Details ADR-006's "Isolation" section and phases 6–7 (#104, #105).
Owner's decisions (2026-11-12): Mizan will move from Vercel to its own cluster of servers
later, so **containers are the long-term sandbox**; the first milestone is **the developer portal,
the docs and private modules**.

## Context

ADR-006 decided that outside developers build modules with the same framework, publish them
to a marketplace or hand owners a private package, that owners approve each module's scopes,
that third-party screens are declarative (no custom JavaScript), and that third-party code runs
isolated with no database credentials. Today:

- every module is code on disk inside the monorepo, mounted at startup; nothing installs from a
  file (uploads were removed on purpose: they ran code in our process);
- modules can only add **fields** to six built-in records (`app/framework/fields.py`); there is
  no workspace-defined record type with its own screens;
- there are no API tokens for outside servers, no scopes and no outgoing webhooks;
- Mizan Cloud runs on Vercel functions, which can't host per-module containers.

## Decision

### D1. Two kinds of third-party module, one package format

1. **Declarative modules** (now): everything a module is, described as data: its record types
   (entities), fields, forms, list and detail screens, menu entries, dashboard widgets,
   permissions, settings, the scopes it needs, and the events it sends to the developer's own
   server. Mizan runs them; no foreign code runs on Mizan's servers. They work in the cloud and
   on site (offline, except webhooks).
2. **Code modules** (with the cluster): the same package plus a server program. It runs in its
   own sandboxed container per module and version (gVisor or Firecracker; no database
   credentials, no access to other processes, outbound network only to an allow-list, CPU,
   memory and time quotas). It talks to Mizan only through the same API and scoped token a
   developer's own server uses (D4), so moving logic from "my server" to "Mizan's sandbox" is a
   deployment choice, not a rewrite.

A **`.mzm` package** is a zip: `manifest.json` (ADR-006 manifest v2 with `kind: "community"`),
`entities/*.json`, `screens/*.json`, `i18n/`, `assets/` (icons, screenshots), later `server/`
(code modules), and `SIGNATURE`: the developer's Ed25519 signature over every file's SHA-256,
plus, once published, Mizan's countersignature. Ids are `<developer>.<module>` so community
modules never collide with official ones or with each other.

### D2. Data: extension records

Entities live in one generic, tenant-scoped table (`ext_records`: workspace, module, entity, id,
data as JSONB, created and updated by and at, soft delete) under row-level security like every
workspace table, counted in the workspace's storage. An entity declares its fields with the
custom-field types (text, number, date, boolean, select) plus `reference` (to another entity of
the module, or to a built-in record such as a customer or product) and `money`. The framework
validates every write against the entity, and indexes searchable fields with expression indexes.
The app renders generic list, detail and form screens from the entity and the module's form
layouts (the same `{"sections": [...]}` shape the screen builder uses), so owners can rearrange
them in the builder too. Uninstalling follows ADR-006 D2 (kept 30 days, then purged).

### D3. Scopes

A module declares the scopes it needs; the owner sees them in plain Arabic and approves them on
install; an update asking for more asks again. Scopes cover:

- its own entities (always granted to itself);
- built-in data, read or write: `products:read`, `customers:read|write`, `sales:read`, `stock:read`, …;
- events it subscribes to: `events:sale.confirmed`, `events:product.updated`, …

Inside the workspace, who may use the module's screens is still decided by **permissions** the
manifest declares and roles hold (ADR-006 D4): scopes limit the module, permissions limit people.

### D4. The extension API and webhooks

- **Installation token**: installing a module that has a server (its own or, later, Mizan's)
  creates a token bound to that workspace and installation, limited to the approved scopes. The
  developer's server calls `/ext/v1/...` (records of its entities, the built-in records its scopes
  allow) with it. Rotated from the owner panel; revoked on uninstall.
- **Webhooks**: events the module subscribed to are POSTed to its URL, signed (HMAC-SHA256 with
  the installation's secret, timestamped against replay), retried with backoff for a day, and
  logged for the owner and the developer. On site they queue until the install is online.

### D5. Developers, signing and installing privately

- **Developer accounts** (separate from owner accounts; one person can have both) with teams.
  A developer registers an Ed25519 public key in the portal; Mizan certifies it (signs it with
  the platform key under its own prefix), so an install can verify a package offline: the
  developer's signature → the certified key → Mizan's public key that every install already has.
- **Private install**: the owner uploads a `.mzm` (owner panel, or the app's module centre),
  Mizan verifies it, shows its scopes, and installs it into that workspace only. Packages from an
  unknown or revoked developer key are refused.
- **Marketplace** (milestone 2, built for free modules and themes, below): publishing adds
  automated checks and a review; Mizan countersigns accepted versions; owners install from
  listings. Paid modules wait for Paymob (#65).

### D6. Where the developer platform lives

- **The portal** is part of the website app, served at **`dev.allmizan.live`** (ADR-008
  reserved it): a host rule (then the website's `vercel.json`, now `deploy/server/nginx.conf`, ADR-011) sends that host to the portal's
  routes. No new Vercel project, so pushes don't cost more deployments.
- **The developer API** (accounts, keys, packages) is a router in the website API; the extension
  API (`/ext/v1`) is part of the system API, next to the data it serves.
- **The SDK and CLI** (`mizan-sdk` on PyPI, command `mizan`): `mizan login`, `mizan module new`
  (a declarative template), `mizan check` (the same manifest and entity validator the platform
  uses, as a dependency-free package), `mizan package` (zip and sign), `mizan publish` (send to
  the marketplace), later `mizan dev` (a local Mizan with the module).
- **Docs** at `dev.allmizan.live/docs`: getting started, the package and manifest reference,
  entities and screens, scopes, the extension API (generated from its OpenAPI), webhooks, the CLI,
  signing and private installs. The old, inaccurate developer articles on the website are
  replaced.

## Milestone 1 (this ADR): portal, docs, private declarative modules

1. Pure validator for manifests and entities (shared by the platform and the CLI); `.mzm` format,
   signing and verification.
2. Extension records: `ext_records`, entity validation, generic list/detail/form screens.
3. Installing from a file: verification, scope approval, install and uninstall.
4. Scopes, installation tokens and the `/ext/v1` API.
5. Webhooks: delivery, signing, retries, logs.
6. The SDK and CLI.
7. The portal: developer accounts, teams, signing keys, CLI tokens; the docs.

## Milestone 1 as built (2026-11-13)

- **Platform** (`app/platform/community/`, always on): `community_modules`, `ext_records`,
  `community_webhook_deliveries` (v69–v71, RLS). The standard admin holds every permission the
  workspace's community modules declare; custom roles can be granted them. Install, update and
  uninstall need `community.manage`. Screens at `/x/<module>/<entity>` in the app, menu group
  "وحدات إضافية".
- **Extension API** (`ext_api.py`): `/ext/v1` with an `mzx_` installation token (only its SHA-256
  stored), 240 requests a minute; the module's records plus customers, suppliers, products,
  stock, sales, employees and branches by scope. CSRF-exempt (bearer only).
- **Webhooks** (`events.py`): recorded in the transaction that made the change, sent after the
  commit, retried 1m/5m/30m/2h/6h/12h by the hourly `community_webhooks` job, HTTPS to public
  hosts only, `Mizan-Signature: sha256=` HMAC over `"<timestamp>.<body>"`.
- **Developer portal** (`app/platform/developers/`, v72; router `website_api/routers/developers.py`):
  developer accounts (email login, separate from owners), teams (the handle is the module
  namespace; some handles are reserved), members (owner/member; added by the email of an
  existing developer), signing keys certified with `MZD1` (`key_id` = `<handle>-<8 hex>`,
  up to 10 active per team; owners revoke), CLI tokens (`mzd_`, hashed). Portal sessions are
  JWTs with scope `developer`; the CLI token reaches the same endpoints.
- **Revocation**: installs in the cloud refuse packages signed with a revoked key (the system API
  reads `developer_keys`). On-site installs verify offline and can't see revocations yet; they
  will when they sync with the cloud.
- **Signing key**: the website API certifies keys, so it needs `LICENSE_SIGNING_KEY` like the
  owner API (outside production both derive a development key from `SECRET_KEY`).
- **Frontend**: the website app serves the developer platform at the root of `dev.*` hosts and
  under `/dev` elsewhere (`features/developers/paths.ts`): home, sign-in, the portal (teams,
  keys, CLI tokens, account) and the docs (`devDocs.ts`, rendered by the docs components). The
  old developer articles in the general docs were removed; the docs home links to the new ones.
- **Language**: the developer platform is English by default (developers anywhere), Arabic on
  request: its own preference (`mizan.dev_locale`), so the website keeps its Arabic default. The
  docs exist in both (`devDocs.en.ts`, `devDocs.ts`); the developer API answers in English unless
  asked `Accept-Language: ar` (the CLI prints its messages). Modules' own labels stay Arabic: the
  app is Arabic.
- **SDK** (`sdk/python`): `mizan login|whoami|logout`, `module new`, `check` (a byte copy of the
  platform validator, kept identical by a test), `keys new [--team]` (registers the key and saves
  its certificate when signed in), `package`. Until it is on PyPI, deploy builds the wheel into
  the website's `public/sdk/` and the docs install it from `dev.allmizan.live/sdk/`.
- **Not yet**: developer email verification and password reset (with the mail work), the
  marketplace and paid modules (milestone 2), code modules (the cluster), installs from the owner
  panel (the app's module centre does it today).

## Milestone 2 as built (2026-11-13, #105): the marketplace, free listings

- **Scope**: developers' modules (`kind: community`) and theme packs. Free only; paid listings,
  revenue share and payouts wait for Paymob (#65); developer activity packages wait for #107's
  second part (running a developer's activity in a workspace).
- **Tables** (v75, platform, no RLS): `marketplace_versions` (every package version sent: the
  `.mzm` bytes, SHA-256, manifest, team, status `in_review|approved|rejected|withdrawn`, the
  reviewer's note, and Mizan's countersignature once approved; unique `(item_id, version)`) and
  `marketplace_items` (one row per listing: current version, `listed|delisted` with a reason,
  install count). Logic in `app/platform/marketplace/listings.py`.
- **Submitting** (website API `POST /developers/teams/{handle}/packages`, the `.mzm` as the body
  or a multipart `file`): the same checks as an install from file (signature, certificate, key not
  revoked, the team's namespace, the validator), then: modules and themes only, a version is sent
  once, and it must be newer than the listed one. `GET` lists the team's listings and versions;
  `DELETE …/{item}/{version}` withdraws one in review. The portal's team page has a
  "Marketplace" panel; `mizan publish [folder|file.mzm]` packages and sends.
- **Review** (admin API `/admoon/marketplace`, page "Marketplace", and a "Needs you" row per
  submission): the reviewer sees what it adds, its scopes (new ones against the listed version
  marked), where it sends webhooks, its permissions, a theme's colours and fonts, its files and
  manifest. **Approving** countersigns it with the platform key under prefix `MZP1` (item,
  version, package SHA-256, kind) and makes it the listing's current version; **rejecting** needs a
  note the developer sees. A listing can be **delisted** with a reason (hidden from the store; the
  workspaces that have it keep it) and relisted.
- **The store** (system API `/modules/store`, section «المتجر» in the module centre, for users with
  `community.manage` or `themes.manage`): browse and search listings, filtered by kind, with
  "installed" and "update available". Opening one re-verifies the stored package (developer
  signature and certificate, key not revoked since, and the countersignature over exactly these
  bytes) and shows the same review as an install from file; installing goes through the same
  install code as a file. The install count is a platform row, written after unbinding the
  workspace (#112).
- **Not yet**: automated checks beyond the validator (e.g. webhook host reachability), developer
  analytics, on-site servers installing from the cloud store, paid listings.

## Consequences

- Nothing a third party writes runs inside Mizan's processes until the cluster brings sandboxes;
  developers who need logic run it on their own servers meanwhile.
- One generic record table keeps schema changes away from installs (no DDL per module), at the
  cost of JSONB queries; expression indexes cover searchable fields.
- The API and webhooks become a public contract: versioned (`/ext/v1`), documented, and changed
  only with deprecation.

## Open questions

- Revenue share, payout schedule and developer verification for paid modules (milestone 2).
- Rate limits per installation token, and webhook volume limits per plan.
