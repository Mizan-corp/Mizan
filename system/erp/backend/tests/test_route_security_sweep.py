"""The route security sweep (phase D): every route of the system API, checked the same way.

1. Inventory: a route is public by design (PUBLIC, a reason each) or protected by its dependency
   tree: an ERP sign-in (get_current_user), a print token (get_print_user) or an installed module's
   installation token. A new route that is none of these fails here, so no route is public by
   accident.
2. Anonymous: every signed-in route answers 401 without a session.
3. Permissions: a user whose role holds no permission calls every signed-in route (random ids,
   minimal bodies built from the OpenAPI schema). A route with a permission check in its dependency
   tree answers 401/403. A route without one is open to every signed-in user by design (SIGNED_IN, a
   reason each), an activity prototype (PROTOTYPES), or refuses by itself (4xx).
4. No 500: the same user, then the workspace's admin, call every route; nothing answers 500, and
   no answer is the database refusing the input (an unknown id, a text too long) instead of the
   route checking it (activity prototypes excepted: factory.database_refused_input turns those
   into 400/409).
5. Isolation: workspace B is filled (a sale, a customer, a supplier, a product, an expense, an
   employee, a purchase order, ledger entries, and a record through every create route). Workspace
   A's admin calls every GET route with B's ids: a record route answers 403/404, and no answer of A
   carries any id of B's rows or B's marker text.

Adding a route to a list: docs/SECURITY_STANDARDS.md §7.
"""
import asyncio
import os
import re
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from main import app
from app.db.base import AsyncSessionLocal
from app.factory import DB_INPUT_ERRORS
from app.framework.loader import manifest_index, registry
from app.middleware import CSRF_COOKIE, CSRF_HEADER
from app.platform.auth.models.user import User
from app.platform.auth.security import create_access_token, hash_password
from app.platform.permissions.access import set_access
from app.platform.permissions.roles import standard_permissions
from app.platform.tenancy.context import current_tenant_id
from app.platform.tenancy.models import Tenant
from tests.conftest import give_roles
from tests.route_sweep import Builder, classify, has_perm_check, operations

needs_db = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs the database")

# ── The lists ───────────────────────────────────────────────────────────────────────────────────

# Routes anyone may call, without a session. Each says why, and how it protects itself if it does.
PUBLIC = {
    ("GET", "/"): "the API's name and links",
    ("GET", "/health"): "health check (no data)",
    ("POST", "/auth/login"): "signs in (10 a minute per address)",
    ("POST", "/auth/logout"): "ends the session the request carries, if any",
    ("POST", "/account/login"): "the owner's sign-in (rate limited)",
    ("POST", "/account/password/forgot"): "owner password reset: sends a code, same answer whether the account exists",
    ("POST", "/account/password/reset"): "owner password reset with the emailed code (rate limited, 5 tries)",
    ("GET", "/settings/manifest.json"): "the PWA manifest: Mizan's own branding, no workspace",
    ("POST", "/platform/verify-license"): "checks a licence key's signature offline; reads nothing",
    ("POST", "/platform/migrate-schema"): "platform staff or the deployment's secret, checked inside",
    ("GET", "/tenants/resolve/{slug_or_domain}"): "sign-in page bootstrap: a workspace's name, modules and colours by slug",
    ("GET", "/updater/{target}/{current_version}"): "desktop updater: the latest public release",
    ("GET", "/updater/download/{filename:path}"): "desktop updater: a public release file",
    ("GET", "/billing/plans"): "the public price list",
    ("POST", "/modules/automation/cron/{job_name}"): "the scheduler: CRON_SECRET in a header, checked inside",
    ("GET", "/themes/assets/files/{theme_id}/{path:path}"): "a theme pack's fonts and images (no data)",
    ("GET", "/themes/assets/{tenant_id}/{theme_id}/{path:path}"): "an uploaded theme's fonts and images (no data)",
    ("GET", "/themes/assets/fonts/{family_id}/{path:path}"): "a registry font family's file: family and path both validated against the font registry (no data)",
    ("GET", "/uploads/{path:path}"): "workspace upload readback: ERP session + owning module's permission checked inside; anonymous only for the current sign-in branding, one generic 404 otherwise",
    ("GET", "/clinic/media/{token}"): "one clinic file by a signed, expiring link (the token is checked inside)",
}

# Signed-in routes without a permission, on purpose: every signed-in user may call them.
SIGNED_IN = {
    ("GET", "/auth/me"): "one's own profile",
    ("POST", "/auth/print-token"): "a print token opens documents only, each with its own permission check",
    ("GET", "/auth/roles"): "the names of the standard roles",
    ("GET", "/community/menu"): "the installed modules' screens this user may open",
    ("GET", "/customers"): "picker fields only (id, name, phone) unless customers/sales/pos/finance/reports",
    ("GET", "/financial-categories"): "category names for the expense and receipt pickers",
    ("GET", "/integrations/whatsapp/status"): "whether WhatsApp is set up and message counts (no contents)",
    ("GET", "/modules"): "the workspace's active modules (the menu)",
    ("GET", "/modules/categories"): "the module centre's categories",
    ("GET", "/modules/automation/jobs"): "job names and this workspace's last run",
    ("GET", "/modules/automation/logs"): "this workspace's job runs (RLS hides the platform's)",
    ("GET", "/notifications"): "one's own notifications",
    ("POST", "/notifications/read-all"): "one's own notifications",
    ("POST", "/notifications/register"): "one's own device for push notifications",
    ("POST", "/notifications/unregister"): "one's own device for push notifications",
    ("POST", "/notifications/generate-system-alerts"): "the notification centre's scan (low stock, trial end)",
    ("GET", "/platform/me/tenant"): "the workspace's name, plan and colours",
    ("GET", "/safes"): "picker fields only; balances and stopped safes to finance/reports",
    ("GET", "/wallets"): "picker fields only; balances and stopped wallets to finance/reports",
    ("GET", "/settings"): "the store's profile (name, address, currency); modules' settings left out",
    ("GET", "/settings/product-options"): "the product form's option lists",
    ("GET", "/settings/screens"): "the acting role's menu and home screen",
    ("GET", "/settings/vat"): "whether prices include VAT (every sale screen needs it)",
    ("GET", "/settings/workspace-profile"): "the activity's terms, variants and custom fields",
    ("GET", "/stock/warehouses"): "the branch picker; stopped branches to settings only",
    ("GET", "/themes/current"): "the workspace's theme",
    ("GET", "/themes/palettes"): "the static design palette registry (ids, swatches, licences; no workspace data) for the studio's recolor pickers",
    ("GET", "/users/managers"): "names for the approver picker",
    ("GET", "/users/staff"): "names for the handover and assignment pickers",
    ("GET", "/users/me/settings"): "one's own preferences",
    ("PUT", "/users/me/settings"): "one's own preferences",
}

# Activities' modules (out of scope of the production plan: PRODUCTION_READINESS.md). They need a
# sign-in and the activity switched on in the workspace (require_activity / require_module), but
# check no permission: their manifests declare none. Known limit, reported.
PROTOTYPES = {
    "agency", "agriculture", "banking", "banquet_events", "billing_folio", "construction", "ecommerce",
    "energy", "events", "field_service", "food_manufacturing", "government", "gym", "hospitality",
    "hotel_pms", "housekeeping", "insurance", "kitchen_display", "law", "logistics", "manufacturing",
    "night_audit", "oil_gas", "pharma_manufacturing", "printing", "real_estate", "restaurant", "salon",
    "school", "services", "travel", "wholesale", "wms",
}

# Not called by the sweep at all.
SKIP = {
    ("PUT", "/auth/me/password"): "would end the sweep's sessions (tested in test_auth_hardening)",
}

# Not called with generated bodies by workspace B's create pass (they act outside the workspace's
# records: sessions, owners, platform jobs, payments, package installs).
B_POST_SKIP = ("/auth/", "/account/", "/platform/", "/billing/", "/modules/store", "/community/",
               "/modules/automation/")

# Path parameters ending in _id that name something shared by every workspace, not a record.
NOT_RECORDS = {"module_id", "job_name", "theme_id"}

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
TIMEOUT = 20


def _module_of() -> dict[tuple[str, str], str]:
    out = {}
    for module_id, router in registry.get_routers().items():
        for r in router.routes:
            for m in getattr(r, "methods", ()):
                out[(m, r.path)] = module_id
    return out


MODULE_OF = _module_of()


def _key(method: str, route) -> tuple[str, str]:
    return (method, route.path)


NET = {message for _, message in DB_INPUT_ERRORS.values()}


def _failed(r, method: str, route) -> str | None:
    """Why an answer counts as a server error: a 500 or no answer, or (outside the prototypes) a
    refusal that came from the database rather than the route (factory.database_refused_input)."""
    if r is None:
        return "timeout"
    if r.status_code == 500:
        return "500"
    if r.status_code in (400, 409) and MODULE_OF.get(_key(method, route)) not in PROTOTYPES:
        try:
            detail = r.json().get("detail")
        except ValueError:
            detail = None
        if detail in NET:
            return f"{r.status_code} from the database, not the route ({detail})"
    return None


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test")


async def _call(c: AsyncClient, method: str, req: dict, headers: dict | None = None):
    kw = {"params": req["params"], "headers": headers or {}}
    if req["json"] is not None and not req["multipart"]:
        kw["json"] = req["json"]
    try:
        return await asyncio.wait_for(c.request(method, req["url"], **kw), TIMEOUT)
    except TimeoutError:
        return None
    finally:
        current_tenant_id.set(None)


# ── 1. inventory (no database) ─────────────────────────────────────────────────────────────────

def test_every_route_is_public_by_design_or_needs_a_sign_in():
    unprotected = []
    for method, route in operations(app):
        if classify(route) == "none" and _key(method, route) not in PUBLIC:
            unprotected.append(f"{method} {route.path}")
    assert not unprotected, (
        "Routes reachable without a sign-in, a print token or an installation token, and not on the "
        "PUBLIC allow-list (docs/SECURITY_STANDARDS.md §7):\n" + "\n".join(unprotected))


def test_the_lists_name_existing_routes_only():
    ops = {_key(m, r): r for m, r in operations(app)}
    stale = [f"PUBLIC {k}" for k in PUBLIC if k not in ops or classify(ops[k]) != "none"]
    stale += [f"SIGNED_IN {k}" for k in SIGNED_IN if k not in ops or classify(ops[k]) != "signed_in"
              or has_perm_check(ops[k])]
    stale += [f"SKIP {k}" for k in SKIP if k not in ops]
    stale += [f"PROTOTYPES {m}" for m in PROTOTYPES if m not in registry.get_routers()]
    assert not stale, "Entries to remove or fix:\n" + "\n".join(stale)


def test_every_activity_prototype_checks_the_activity():
    """The activities' modules answer only workspaces that use the activity (they answered every
    signed-in user of every workspace)."""
    ungated = []
    for method, route in operations(app):
        module = MODULE_OF.get(_key(method, route))
        if module in PROTOTYPES and classify(route) == "signed_in":
            names = {getattr(d.call, "__qualname__", "") for d in route.dependant.dependencies}
            if not any(n.startswith(("require_activity.", "require_module.")) for n in names):
                ungated.append(f"{method} {route.path}")
    assert not ungated, "\n".join(ungated)


# ── workspaces ─────────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


def _token(user: User) -> dict:
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": str(user.id), "role": user.role, "username": user.username, "tid": str(user.tenant_id)})}


async def _user(tid, role: str, permissions: list[str] | None = None) -> dict:
    """A user of the workspace: a standard role, or (with `permissions`) a role of exactly those."""
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        u = User(id=uuid.uuid4(), tenant_id=tid, username=f"{role}_{uuid.uuid4().hex[:10]}", full_name=role, role=role,
                 password_hash=hash_password("Pass12345!"), is_active=True, is_manager=role == "admin",
                 permissions=standard_permissions(role) if permissions is None else permissions)
        s.add(u)
        if permissions is None:
            await give_roles(s)
        else:
            await s.flush()
            await s.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            await set_access(s, u, role, permissions)
        await s.commit()
    current_tenant_id.set(None)
    return _token(u)


async def _all_modules_on(tid, name: str | None = None) -> None:
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        t = await s.get(Tenant, tid)
        t.active_modules = sorted(manifest_index())
        if name:
            t.name = name
        await s.commit()


async def _workspace() -> uuid.UUID:
    tid = uuid.uuid4()
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        s.add(Tenant(id=tid, name=f"Sweep {tid.hex[:6]}", slug=f"sweep-{tid.hex[:10]}", status="active"))
        await s.commit()
    await _all_modules_on(tid)
    return tid


def _report(title: str, rows: list[str]) -> str:
    return f"{title} ({len(rows)}):\n" + "\n".join(rows)


# ── 2-4. sign-in, permissions, no 500 ─────────────────────────────────────────────────────────

@needs_db
async def test_signed_in_routes_refuse_anonymous_callers():
    builder = Builder(app.openapi())
    wrong = []
    async with _client() as c:
        c.cookies.set(CSRF_COOKIE, "sweep")  # past the CSRF check, to reach the route's own
        for method, route in operations(app):
            if classify(route) != "signed_in":
                continue
            r = await _call(c, method, builder.build(method, route), {CSRF_HEADER: "sweep"})
            if r is None or r.status_code != 401:
                wrong.append(f"{method} {route.path} → {r.status_code if r else 'timeout'}")
    assert not wrong, _report("Signed-in routes that did not answer 401 without a session", wrong)


@needs_db
async def test_permission_sweep_and_no_500():
    """A user whose role holds no permission, in a workspace with every module on: permission-checked
    routes answer 401/403; the others are listed (SIGNED_IN, PROTOTYPES) or refuse by themselves.
    Then the admin calls everything too: nothing answers 500."""
    tid = await _workspace()
    nobody = await _user(tid, "cashier", [])
    admin = await _user(tid, "admin")
    builder = Builder(app.openapi())
    open_by_design, refused, errors = [], [], []
    swept = special = 0
    async with _client() as c:
        for method, route in operations(app):
            key = _key(method, route)
            if classify(route) != "signed_in":
                continue
            if key in SKIP:
                special += 1
                continue
            swept += 1
            r = await _call(c, method, builder.build(method, route), nobody)
            status = r.status_code if r else "timeout"
            if why := _failed(r, method, route):
                errors.append(f"no permission: {method} {route.path} → {why}")
            elif has_perm_check(route):
                if status not in (401, 403):
                    refused.append(f"{method} {route.path} → {status} (expected 401/403)")
            elif key in SIGNED_IN or MODULE_OF.get(key) in PROTOTYPES:
                open_by_design.append(key)
            elif status < 400:
                refused.append(f"{method} {route.path} → {status}: answered a user without permissions, "
                               "and has no permission check (add one, or list it in SIGNED_IN with a reason)")
        for method, route in operations(app):
            if classify(route) != "signed_in" or _key(method, route) in SKIP or route.path == "/auth/logout":
                continue
            r = await _call(c, method, builder.build(method, route), admin)
            if why := _failed(r, method, route):
                errors.append(f"admin: {method} {route.path} → {why}")
    print(f"\npermission sweep: {swept} signed-in operations swept, {special} special-cased, "
          f"{len(open_by_design)} open by design or prototypes")
    assert not refused, _report("Routes that let a user without permissions through", refused)
    assert not errors, _report("Server errors (500) or timeouts", errors)


@needs_db
async def test_an_activity_prototype_answers_only_workspaces_that_use_the_activity():
    tid = uuid.uuid4()
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        s.add(Tenant(id=tid, name=f"Retail {tid.hex[:6]}", slug=f"retail-{tid.hex[:10]}", status="active",
                     active_modules=["core", "pos", "inventory", "finance"]))
        await s.commit()
    admin = await _user(tid, "admin")
    async with _client() as c:
        for path in ("/gym/summary", "/hospitality/summary", "/hospitality/pms/rooms", "/wms/summary"):
            r = await c.get(path, headers=admin)
            assert r.status_code == 403 and "غير مفعلة" in r.json()["detail"], (path, r.text)
        await _set_modules(tid, ["core", "pos", "finance", "hospitality"])
        # The hotel's sub-modules open with its main module.
        assert (await c.get("/hospitality/pms/rooms", headers=admin)).status_code == 200
        assert (await c.get("/gym/summary", headers=admin)).status_code == 403


async def _set_modules(tid, modules: list[str]) -> None:
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        (await s.get(Tenant, tid)).active_modules = modules
        await s.commit()


# ── 5. workspace isolation ─────────────────────────────────────────────────────────────────────

async def _rows_of(tid) -> set[str]:
    """The ids of every row of the workspace, in every table with a tenant_id and an id."""
    ids: set[str] = set()
    async with AsyncSessionLocal() as s:
        await s.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        tables = (await s.execute(text("""
            SELECT c.table_name FROM information_schema.columns c
            JOIN information_schema.columns i ON i.table_schema = c.table_schema AND i.table_name = c.table_name
                 AND i.column_name = 'id'
            JOIN information_schema.tables t ON t.table_schema = c.table_schema AND t.table_name = c.table_name
                 AND t.table_type = 'BASE TABLE'
            WHERE c.table_schema = 'public' AND c.column_name = 'tenant_id'"""))).scalars().all()
        for table in tables:
            ids.update((await s.execute(text(f'SELECT id::text FROM "{table}" WHERE tenant_id = :t'),
                                        {"t": tid})).scalars().all())
    return ids


async def _first_ids(tid, tables: tuple[str, ...]) -> list[str]:
    out = []
    async with AsyncSessionLocal() as s:
        await s.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        for table in tables:
            v = await s.scalar(text(f"SELECT id::text FROM {table} WHERE tenant_id = :t ORDER BY id LIMIT 1"), {"t": tid})
            if v:
                out.append(v)
    return out


async def _filled_workspace(marker: str) -> dict:
    """A workspace with books (tests.test_accounting_reports._books: sales, a return, a customer and
    their receipt, a product, an approved expense, the opening and manual entries), every module on,
    an admin, and through the API a supplier, a purchase order and an employee."""
    from tests.test_accounting_reports import _books

    env = await _books()
    tid = env["tenant_id"]
    await _all_modules_on(tid, name=f"Workspace {marker}")
    admin = await _user(tid, "admin")
    async with _client() as c:
        supplier = (await c.post("/suppliers", headers=admin, json={"name": f"{marker} supplier", "phone": "01012345678"}))
        assert supplier.status_code in (200, 201), supplier.text
        supplier = supplier.json()
        po = await c.post("/purchases", headers=admin, json={
            "supplier_id": supplier["id"], "warehouse_id": str(env["warehouse_id"]),
            "items": [{"product_id": str(env["product_id"]), "qty": 2, "unit_cost": "60"}]})
        assert po.status_code in (200, 201), po.text
        emp = await c.post("/hr/employees", headers=admin, json={
            "emp_code": marker[:12].upper(), "name": f"{marker} employee", "position": "x", "monthly_salary": "5000",
            "hire_date": "2024-01-01", "is_active": True})
        assert emp.status_code in (200, 201), emp.text
    pool = [str(env[k]) for k in ("sale1", "customer_id", "product_id", "warehouse_id", "shift_id", "safe_id",
                                  "wallet_id", "cashier_id")]
    pool += [supplier["id"], po.json()["id"], emp.json()["id"]]
    pool += await _first_ids(tid, ("acc_entries", "acc_lines", "acc_accounts", "expenses", "financial_categories",
                                   "categories", "subcategories", "customer_payments", "sale_items",
                                   "purchase_order_items", "stock_movements", "drawer_transactions"))
    return {"tid": tid, "admin": admin, "marker": marker, "pool": pool}


@needs_db
async def test_workspace_isolation_sweep():
    b = await _filled_workspace("isob" + uuid.uuid4().hex[:8])
    a = await _filled_workspace("isoa" + uuid.uuid4().hex[:8])
    spec = app.openapi()
    b_builder, a_builder = Builder(spec, marker=b["marker"]), Builder(spec, marker=a["marker"])
    created: dict[str, list[str]] = {}
    errors, leaks, found = [], [], []
    async with _client() as c:
        # B makes one record through every create route (marker text in every string field).
        for method, route in operations(app):
            if (method != "POST" or classify(route) != "signed_in" or "{" in route.path
                    or route.path.startswith(B_POST_SKIP) or _key(method, route) in SKIP):
                continue
            req = b_builder.build(method, route)
            if req["multipart"]:
                continue
            r = await _call(c, method, req, b["admin"])
            if why := _failed(r, method, route):
                errors.append(f"B: POST {route.path} → {why}")
            elif r.status_code < 300:
                body = r.json() if r.headers.get("content-type", "").startswith("application/json") else None
                if isinstance(body, dict) and UUID_RE.fullmatch(str(body.get("id", ""))):
                    created.setdefault(route.path.split("/")[1], []).append(str(body["id"]))
        b_ids = await _rows_of(b["tid"]) | {str(b["tid"])} | {i for ids in created.values() for i in ids}

        # A's admin reads everything, with B's ids where a route takes a record id.
        reads = 0
        for method, route in operations(app):
            if method != "GET" or classify(route) != "signed_in" or _key(method, route) in SKIP:
                continue
            params = re.findall(r"{(\w+)(?::\w+)?}", route.path)
            id_params = [p for p in params if (p == "id" or p.endswith("_id")) and p not in NOT_RECORDS]
            candidates = [None] if not id_params else b["pool"] + created.get(route.path.split("/")[1], [])[:10]
            for cand in candidates:
                req = a_builder.build(method, route, {p: cand for p in id_params} if cand else None)
                r = await _call(c, method, req, a["admin"])
                reads += 1
                if why := _failed(r, method, route):
                    errors.append(f"A: GET {req['url']} → {why}")
                    continue
                seen = (set(UUID_RE.findall(r.text)) & b_ids) - {cand}
                if seen or b["marker"] in r.text:
                    leaks.append(f"GET {route.path} with {cand} → {r.status_code} carries B's {sorted(seen)[:3] or b['marker']}")
                elif cand and r.status_code < 300:
                    found.append(f"GET {route.path} with B's {cand} → {r.status_code} (expected 403/404)")
    print(f"\nisolation sweep: {reads} reads by A, {len(b_ids)} ids of B, {sum(map(len, created.values()))} "
          "records made by B through create routes")
    assert not leaks, _report("Answers to workspace A carrying workspace B's data", leaks)
    assert not found, _report("Record routes answering another workspace's id", found)
    assert not errors, _report("Server errors (500) or timeouts", errors)
