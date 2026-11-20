# Mizan ERP — Security & Access Standards

## 1. Authorization
Permissions are declared by modules and held by roles; a user acts as one assigned role at a
time, and every route checks a permission (`require_perm`), never a role name. Nobody can grant
a permission their acting role doesn't hold. Positions (job titles) describe people and grant
nothing. Details: [`USER_ROLES_AND_PERMISSIONS.md`](USER_ROLES_AND_PERMISSIONS.md).

## 2. Clinical Isolation
- Medical records are enforced **per patient** on the server, in the clinic module (`/clinic/*`,
  #113): a doctor or nurse reads and writes only the records of patients whose care team they are
  on, unless they hold `clinic:all_patients` or the workspace sets `patient_access` to `all`.
  With `?patient_id` a refused read is a 403; lists return only reachable patients' rows. Writes
  (encounters, prescriptions, lab orders, and changing a patient's allergies, chronic conditions
  or blood group) need the same access.
- Reception and billing never receive clinical fields: the patient list and record are returned
  with allergies, chronic conditions and blood group set to `null` and `clinical_access: false`.
- Pharmacy and lab work queues: non-clinicians holding `clinic:dispense` / `clinic:lab` see every
  prescription / lab order (logged as `queue`).
- **Break-glass**: time-limited (60 minutes), one patient, mandatory reason, audited, notified to
  `clinic:privacy` holders, reviewable and revocable (`clinic_access_grants`).
- Every read that returns clinical data writes one row to `clinic_access_log` (user, patient or
  `NULL` for a list, resource, how access was granted, row count); `clinic:privacy` reads it.
- Not covered: the 24 prototype `/healthcare/*` screens (HLT-01..24) have their own endpoints
  without these checks; they are previews, not the clinic's records.

## 3. Cryptographic & Data Protection Controls
- Passwords hashed with bcrypt (per-password salt).
- Session tokens are JWTs signed with HMAC-SHA256 (`SECRET_KEY`, shared by the four APIs), with
  a token id: signing out revokes it (`revoked_tokens`) and a password change ends every earlier
  session (#77). Tokens carry a scope (workspace, `owner`, `developer`, `print`) and each API
  refuses the others'. A print token opens only documents, and each document still checks its own
  permission and branch (`app/platform/printing`); every text a document prints is HTML-escaped.
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
- Tables without a workspace column of their own (`user_warehouses`) are reached only through a
  row that has one: a user's branches are set only for a user of the bound workspace, to its own
  branches (404 otherwise).

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

## 7. The route security sweep (every route, every run)
`system/backend/tests/test_route_security_sweep.py` checks every route of the system API the same
way, in about a minute (helpers in `tests/route_sweep.py`):

1. **Inventory.** Each route is protected by its dependency tree (an ERP sign-in through
   `get_current_user`, a print token through `get_print_user`, an installed module's installation
   token) or is on the `PUBLIC` allow-list with a reason. A new route that is neither fails the test,
   so no route becomes public by accident.
2. **Anonymous.** Every signed-in route answers 401 without a session.
3. **Permissions.** A user whose role holds no permission calls every signed-in route, with random ids
   and minimal bodies built from the OpenAPI schema. A route with a permission check in its
   dependency tree (`require_perm`, the clinic's guards, `require_superadmin`…) must answer 401/403.
   A route without one must refuse by itself (a 4xx), unless it is on `SIGNED_IN` (open to every
   signed-in user, with a reason: one's own profile, pickers that return names only…) or belongs to an
   activity prototype (`PROTOTYPES`).
4. **No 500.** That user, then the workspace's admin, call every route: nothing answers 500, and no
   general module relies on the database refusing the input (an unknown id, a text too long).
5. **Isolation.** Workspace B is filled (a sale, a customer, a supplier, a product, an expense, an
   employee, a purchase order, ledger entries, and a record through every create route); workspace
   A's admin calls every GET route with B's ids. A record route answers 403/404, and no answer carries
   the id of any of B's rows or B's marker text.

**Adding a route.** Protect it with a dependency: `require_perm("<permission>")` for anything that
changes or reveals data. Only when it is meant for everyone:
- without a session: add `("GET", "/path/{param}")` to `PUBLIC` with the reason and how the route
  protects itself (a signed token, a secret header, a rate limit), and bind no workspace's data;
- for every signed-in user: add it to `SIGNED_IN` with the reason, and return nothing sensitive
  (balances, costs, salaries, phone numbers of customers: only to who holds the permission).
A route that must not be called with generated input goes in `SKIP` with the reason. The lists are
checked too: an entry for a route that no longer exists, or that gained a permission, fails.

**Activities' modules** (gym, hotel, logistics…, outside the production plan for now) answer only
workspaces that use the activity: `require_activity` is added when the module's router is mounted
(`system_api/router.py`) unless all its signed-in routes already check their module. Inside such a
workspace they check no permission yet (their manifests declare none): a known limit.

**Not swept:** static files (`/uploads` holds public images only; private files are served by
routes), the community modules' records (their permission is checked per screen inside the route and
needs an installed package), and the owner, admin and website APIs.
