# Mizan ERP — Security & Access Standards

## 1. Authorization
Permissions are declared by modules and held by roles; a user acts as one assigned role at a
time, and every route checks a permission (`require_perm`), never a role name. Nobody can grant
a permission their acting role doesn't hold. Positions (job titles) describe people and grant
nothing. Details: [`USER_ROLES_AND_PERMISSIONS.md`](USER_ROLES_AND_PERMISSIONS.md).

## 2. Clinical Isolation
- Medical records (EMR, diagnoses, prescriptions) are behind clinical permissions held only by
  clinical roles (`doctor`, `nurse`, `lab_tech`, `pharmacist`); administrative and reception roles
  don't hold them.
- An emergency **break-glass** override (time-limited, notified, audited) is designed but not
  built; its unenforced endpoints were removed (#94 follow-up).

## 3. Cryptographic & Data Protection Controls
- Passwords hashed with bcrypt (per-password salt).
- Session tokens are JWTs signed with HMAC-SHA256 (`SECRET_KEY`, shared by the four APIs), with
  a token id: signing out revokes it (`revoked_tokens`) and a password change ends every earlier
  session (#77). Tokens carry a scope (workspace, `owner`, `developer`, `print`) and each API
  refuses the others'.
- Machine tokens (installation tokens `mzx_`, CLI tokens `mzd_`) are random, shown once, and
  stored only as SHA-256.
- Owners' email codes (#71, #72) are 6 random digits stored only as an HMAC (`SECRET_KEY`),
  valid 15 minutes, single use, locked after 5 wrong tries, limited to one a minute and three an
  hour per owner; reset codes go only to a verified address, and "forgot password" answers the
  same whether the account exists or not.
- Sensitive patient identifiers (Egyptian National ID, Passport) masked in non-clinical views (e.g., `2980101****512`).

## 3a. Workspace isolation
- Every workspace table is `TenantScoped` and has row-level security; while a workspace is bound,
  queries run as the `mizan_app` role, which can't bypass RLS (see `DATABASE_DESIGN.md`).
- Cross-workspace reads (scheduler, token lookups) switch the bypass on for one transaction and
  off before binding a workspace. Tests check that two workspaces with the same module or theme
  never see each other's records.

## 4. Owner Accounts & Payments (ADR-004)
- Owner tokens carry `scope: owner`: the ERP refuses them, and the owner API refuses ERP tokens.
- Paymob callbacks are verified with HMAC-SHA512 over Paymob's field list before anything is
  activated, and recorded once per Paymob transaction id (idempotent). Plans change only through
  `activate_invoice`, never from inside a workspace.

## 5. On-Site Installs & Licences (ADR-005)
- **Platform signing key.** Licences, release offers (`MZR1`) and developer certificates (`MZD1`)
  are signed with Ed25519 (`LICENSE_SIGNING_KEY`, set only on the owner, admin and website APIs in
  production). It is the platform's most sensitive secret: leaked, anyone can mint licences and
  certify developer keys; lost, every install needs an update with a new public key. Keep an
  offline copy. The production public key is built into the app (`app.platform.licensing.keys`);
  outside production a development key derived from `SECRET_KEY` is used, which production
  installs never accept.
- **Offline enforcement.** An expired or revoked licence makes the install read-only (sign-in and
  licence endpoints still work). A copied key can't be prevented offline; installs are visible
  to the admin panel once they check in, and a licence is bound to one computer (#92).
- **Database.** The bundled PostgreSQL listens on `127.0.0.1` only, with SCRAM passwords
  generated per install; it is never exposed to the network.
- **Network.** Single device listens on `127.0.0.1` only. LAN serves HTTPS with a certificate
  authority generated per install (server certificates ≤ 397 days, renewed automatically);
  on Windows the firewall rule admits the local subnet only.
- **Files.** `config.json` (database password, secret key) is readable by the service account
  only. On Windows, setup grants explicit access to the data folder (installing account and
  SYSTEM) and read/execute on the PostgreSQL programs, because PostgreSQL drops administrator
  rights when it starts.
- **Data stays on site.** Check-ins send the installation id, host name, OS, version and last
  backup time, never business data. Cloud backup will be opt-in and encrypted (#117).

## 6. The Developer Platform (ADR-007, ADR-010)
- **Nothing outside runs inside Mizan.** Community modules, theme packs and activity packages are
  declarative (JSON and assets); developers' logic runs on their own servers. Code modules wait
  for isolated containers.
- **Packages are signed.** A `.mzm` carries the developer's Ed25519 signature over every file's
  hash and Mizan's certificate for that key; installs verify both offline, refuse any changed file,
  and refuse a module id outside the key's team. Cloud installs also refuse keys revoked in the
  portal. Package size ≤ 4 MB; only known file types and paths (no `..`, no absolute paths).
- **Owners approve access.** A module's scopes are shown in plain Arabic before install (new ones
  marked on updates); nothing installs without approving all of them. Its own records need no
  scope; everything else (customers, sales, stock…) is by scope, read-only unless a `:write`
  scope says otherwise.
- **Installation tokens** reach one workspace and its approved scopes only (`/ext/v1`, 240/min);
  issuing a new one or uninstalling ends the old one at once.
- **Webhooks** go only to public HTTPS hosts (private, loopback and link-local addresses are
  refused, against SSRF), signed with the installation's secret and a timestamp (replays older
  than five minutes are to be rejected by the receiver; `mizan_sdk.verify_webhook` does).
- **Themes can't inject code or break layouts**: only known tokens, strict colour, font and length
  formats, readable contrast; values are checked again in the browser before becoming CSS. A
  theme reaches no data.
- **Developer accounts** are separate from owner accounts; team owners manage members and revoke
  keys; CLI tokens can be revoked one by one; a password change ends every portal session.
