# ADR-007: Third-party modules: packages, scopes, isolation and the developer platform

## Status

Proposed (2026-11-12). Details ADR-006's "Isolation" section and phases 6–7 (#104, #105).
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
- **Marketplace** (milestone 2): publishing adds automated checks and a review; Mizan
  countersigns accepted versions; owners install from listings. Paid modules wait for Paymob (#65).

### D6. Where the developer platform lives

- **The portal** is part of the website app, served at **`dev.allmizan.live`** (ADR-008
  reserved it): a host rule in the website's `vercel.json` sends that host to the portal's
  routes. No new Vercel project, so pushes don't cost more deployments.
- **The developer API** (accounts, keys, packages) is a router in the website API; the extension
  API (`/ext/v1`) is part of the system API, next to the data it serves.
- **The SDK and CLI** (`mizan-sdk` on PyPI, command `mizan`): `mizan login`, `mizan module new`
  (a declarative template), `mizan check` (the same manifest and entity validator the platform
  uses, as a dependency-free package), `mizan package` (zip and sign), later `mizan dev` (a local
  Mizan with the module) and `mizan publish`.
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
