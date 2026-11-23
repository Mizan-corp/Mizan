import os
import sys

sys.path.insert(0, os.environ.get("STUDIO_BACKEND_ROOT", "/tmp/pgtest"))  # dir containing app/ (shared/backend in the repo)
os.environ["DATABASE_URL"] = "postgresql://postgres@/postgres?host=" + os.environ.get("STUDIO_PGDATA", "/tmp/pgdata2")

import pgserver  # noqa: E402

srv = pgserver.get_server(os.environ.get("STUDIO_PGDATA", "/tmp/pgdata2"))
print("server:", srv.get_uri())

import psycopg2  # noqa: E402

from app.db.migrations import FOUNDATION_SQL, MIGRATIONS, APP_ROLE_GRANTS, split_statements  # noqa: E402

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()
cur.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='mizan_app') "
            "THEN CREATE ROLE mizan_app NOBYPASSRLS LOGIN; END IF; END $$")
cur.execute("GRANT mizan_app TO postgres")
for stmt in split_statements(FOUNDATION_SQL):
    cur.execute(stmt)
for key in ("v108_site_pages", "v109_site_settings"):
    for stmt in split_statements(dict(MIGRATIONS)[key]):
        cur.execute(stmt)
for stmt in split_statements(APP_ROLE_GRANTS):
    cur.execute(stmt)
# harness-only: the real owner_accounts table lives outside this subset of the schema
cur.execute("CREATE TABLE IF NOT EXISTS owner_accounts (id uuid PRIMARY KEY DEFAULT gen_random_uuid())")
cur.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS owner_account_id uuid REFERENCES owner_accounts(id) ON DELETE SET NULL")
# harness-only: columns later migrations add to tenants in the full schema
cur.execute("""ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS paid_until timestamptz,
    ADD COLUMN IF NOT EXISTS slug varchar(64),
    ADD COLUMN IF NOT EXISTS custom_domain varchar(128),
    ADD COLUMN IF NOT EXISTS status varchar(32) NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS deployment_mode varchar(32) NOT NULL DEFAULT 'cloud_saas',
    ADD COLUMN IF NOT EXISTS business_type varchar(80) NOT NULL DEFAULT 'retail',
    ADD COLUMN IF NOT EXISTS tech_stack jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS active_modules jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS limits jsonb NOT NULL DEFAULT '{}'::jsonb""")
cur.execute("SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname LIKE 'site_page%'")
print("RLS flags:", cur.fetchall())
conn.close()

import asyncio  # noqa: E402
import uuid  # noqa: E402

from fastapi import HTTPException  # noqa: E402

from app.db.base import AsyncSessionLocal, Base  # noqa: E402

# harness-only metadata stub so Tenant's owner_account_id FK resolves
import sqlalchemy as _sa  # noqa: E402
from sqlalchemy.dialects.postgresql import UUID as _UUID  # noqa: E402

if "owner_accounts" not in Base.metadata.tables:
    _sa.Table("owner_accounts", Base.metadata, _sa.Column("id", _UUID(as_uuid=True), primary_key=True))

from app.platform.site import service  # noqa: E402
from app.platform.tenancy.context import bind_tenant, install_tenancy_events, unbind_tenant  # noqa: E402

install_tenancy_events()  # what factory.create_app does: GUC + stamping + read scoping listeners
from app.platform.tenancy.models import Tenant  # noqa: E402


def tree(text="مرحبا"):
    return {
        "id": "n_root", "type": "section",
        "settings": {"desktop": {"padding": "l", "max_width": "wide"}, "mobile": {"padding": "m"}},
        "content": {},
        "children": [{
            "id": "n_rw01", "type": "columns",
            "settings": {"desktop": {"columns": 1, "gap": "l"}, "mobile": {"stack": True}},
            "content": {},
            "children": [{
                "id": "n_cl01", "type": "column", "settings": {}, "content": {},
                "children": [
                    {"id": "n_hd01", "type": "heading", "settings": {"desktop": {"level": 1}},
                     "content": {"ar": {"text": text}, "en": {"text": "Hello"}}},
                    {"id": "n_tx01", "type": "text", "settings": {},
                     "content": {"ar": {"html": "<p>أهلاً</p>"}, "en": {"html": "<p>Hello</p>"}}},
                ],
            }],
        }],
    }


async def main():
    # ── lifecycle ──────────────────────────────────────────────────────────
    tid = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(Tenant(id=tid, name=f"site-{tid.hex[:8]}", sector="retail", scale="small"))
        await db.commit()
        await bind_tenant(db, tid)
        page = await service.create_page(db, slug="home", titles={"ar": "الرئيسية", "en": "Home"})
        assert page.status == "draft" and page.draft_tree is None, page.status
        print("1. create_page: draft, no trees  OK")

        await service.save_draft(db, page.id, tree=tree())
        page = await service.get_page(db, page.id)
        assert page.draft_tree is not None and page.published_tree is None and page.status == "draft"
        print("2. save_draft: draft only, nothing published  OK")

        await service.publish(db, page.id, None)
        page = await service.get_page(db, page.id)
        assert page.published_tree == page.draft_tree and page.status == "published"
        revs = await service.list_revisions(db, page.id)
        assert [r.number for r in revs] == [1] and revs[0].tree == page.published_tree
        print("3. publish: published tree + immutable revision 1  OK")

        await service.save_draft(db, page.id, tree=tree("أهلاً"))
        await service.publish(db, page.id, None)
        revs = await service.list_revisions(db, page.id)
        assert [r.number for r in revs] == [2, 1]
        print("4. second publish: revisions [2, 1]  OK")

        await service.rollback(db, page.id, revs[1].id)
        page = await service.get_page(db, page.id)
        draft_txt = page.draft_tree["children"][0]["children"][0]["children"][0]["content"]["ar"]["text"]
        live_txt = page.published_tree["children"][0]["children"][0]["children"][0]["content"]["ar"]["text"]
        assert draft_txt == "مرحبا" and live_txt == "أهلاً", (draft_txt, live_txt)
        print("5. rollback: draft rewound, published untouched  OK")

        await service.archive(db, page.id)
        try:
            await service.save_draft(db, page.id, tree=tree())
            raise AssertionError("archived page accepted a draft")
        except HTTPException as e:
            assert e.status_code == 409
        await service.reopen(db, page.id)
        assert (await service.get_page(db, page.id)).status == "published"
        print("6. archive blocks drafts; reopen restores  OK")

        try:
            await service.create_page(db, slug="home", titles={"ar": "أخرى"})
            raise AssertionError("duplicate slug accepted")
        except HTTPException as e:
            assert e.status_code == 409, e.status_code
        print("7. duplicate slug rejected with 409  OK")
        await db.rollback()
        await unbind_tenant(db)

    # ── tenant isolation through RLS + ORM scoping ─────────────────────────
    one, two = uuid.uuid4(), uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add_all([Tenant(id=one, name=f"site-{one.hex[:8]}", sector="retail", scale="small"),
                    Tenant(id=two, name=f"site-{two.hex[:8]}", sector="retail", scale="small")])
        await db.commit()
        await bind_tenant(db, one)
        page = await service.create_page(db, slug="home", titles={"ar": "الرئيسية"})
        assert (await db.execute(__import__("sqlalchemy").text("select current_setting('app.tenant_id', true)"))).scalar() == str(one)
        print("8. GUC app.tenant_id bound for tenant one  OK")
        await unbind_tenant(db)
        await bind_tenant(db, two)
        assert await service.list_pages(db) == []
        other = await service.create_page(db, slug="home", titles={"ar": "الرئيسية"})
        assert other.id != page.id
        db.expunge_all()  # drop the identity map so the read below actually hits the database
        try:
            await service.get_page(db, page.id)
            raise AssertionError("cross-tenant get_page succeeded")
        except HTTPException as e:
            assert e.status_code == 404
        print("9. tenant two: no pages visible, same slug free, cross-tenant read is 404  OK")
        await db.rollback()
        await unbind_tenant(db)

    # raw SQL as mizan_app (RLS, not just ORM scoping)
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text
        await db.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(two)})
        conn = await db.connection()
        from app.platform.tenancy.context import restrict_to_app_role
        await conn.run_sync(restrict_to_app_role)
        role = (await db.execute(text("select current_role"))).scalar()
        rows = (await db.execute(text("SELECT count(*) FROM site_pages"))).scalar()
        assert role == "mizan_app", role
        assert rows == 1, rows  # only tenant two's own page
        await db.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(one)})
        rows = (await db.execute(text("SELECT count(*) FROM site_pages"))).scalar()
        assert rows == 1, rows
        print("10. raw SQL as mizan_app under RLS sees only the bound tenant's rows  OK")
        await db.rollback()
        await unbind_tenant(db)

    # 12-14. site settings: validation, upsert roundtrip, tenant isolation under RLS
    async with AsyncSessionLocal() as db:
        await bind_tenant(db, one)
        bad = {"colors": {"light": {"background": "red"}}, "evil": True}
        try:
            await service.put_settings(db, value=bad)
            raise SystemExit("settings accepted unknown key")
        except HTTPException:
            await db.rollback()
        theme = {"colors": {"light": {"background": "#f3f5f2", "primary": "#c3ed8d"}},
                 "typography": {"family": "serif"}, "shape": {"radius": 4},
                 "header": {"brand": "Northline", "links": [{"label": "Collections", "href": "#c"}], "actions": []},
                 "footer": {"lines": ["Northline"], "links": []}}
        saved = await service.put_settings(db, value=theme)
        assert saved["typography"]["family"] == "serif" and saved["shape"]["radius"] == 4
        print("12. settings validation rejects bad input, accepts a full theme  OK")
        again = await service.get_settings(db)
        assert again == saved, (again, saved)
        assert (await db.execute(__import__("sqlalchemy").text("SELECT count(*) FROM site_settings"))).scalar() == 1
        print("13. settings upsert roundtrip keeps a single row  OK")
        await db.rollback()
        await unbind_tenant(db)

    async with AsyncSessionLocal() as db:
        await bind_tenant(db, two)
        other = await service.get_settings(db)
        assert other == {}, other
        print("14. settings are tenant-isolated under RLS  OK")
        await db.rollback()
        await unbind_tenant(db)

    # 15. A single tenant setting is consumed by distinct persisted page trees.
    async with AsyncSessionLocal() as db:
        from app.platform.site.render import render_document
        await bind_tenant(db, one)
        first = await service.get_page(db, page.id)
        second = await service.create_page(db, slug="about", titles={"en": "About"}, tree=tree("About content"))
        await service.save_draft(db, first.id, tree=tree("Home content"), titles={"en": "Home"})
        shared = {"header": {"brand": "Shared brand", "links": [{"label": "About", "href": "/about"}]},
                  "footer": {"lines": ["Shared footer"], "links": [{"label": "Returns", "href": "/returns"}]}}
        await service.put_settings(db, value=shared)
        await db.commit()
        db.expunge_all()
        await bind_tenant(db, one)
        first = await service.get_page(db, page.id)
        second = await service.get_page(db, second.id)
        stored = await service.get_settings(db)
        home_html = render_document(first.draft_tree, {"titles": first.titles}, stored, "ar", "desktop")
        about_html = render_document(second.draft_tree, {"titles": second.titles}, stored, "ar", "desktop")
        for html in (home_html, about_html):
            assert "Shared brand" in html and "Shared footer" in html and 'href="/returns"' in html
        assert "Home content" in home_html and "About content" in about_html
        assert "About content" not in home_html and "Home content" not in about_html
        print("15. two persisted pages render shared header/footer links with distinct content  OK")
        await db.rollback()
        await unbind_tenant(db)

    # 16. Native JSON edit roundtrip: preserve IDs, alternate language, markup and settings.
    async with AsyncSessionLocal() as db:
        import copy
        await bind_tenant(db, one)
        original = tree("Native original")
        heading = original["children"][0]["children"][0]["children"][0]
        heading["content"]["en"]["text"] = "Original English"
        original["children"][0]["children"][0]["children"][1]["content"]["ar"]["html"] = "<p><strong>Keep rich markup</strong></p>"
        alternate = copy.deepcopy(original)
        alternate["id"] = "n_alternateroot"
        alternate["settings"]["desktop"]["padding"] = "s"
        alternate["children"][0]["settings"]["desktop"]["gap"] = "s"
        for number, source in enumerate((original, alternate)):
            created = await service.create_page(db, slug=f"native-{number}", titles={"en": "Page title", "ar": "عنوان"}, tree=source)
            page_id = created.id
            expected = copy.deepcopy(source)
            expected["children"][0]["children"][0]["children"][0]["content"]["en"]["text"] = "Native changed field"
            await service.save_draft(db, page_id, tree=expected)
            db.expunge_all()
            reloaded = await service.get_page(db, page_id)
            assert reloaded.draft_tree == expected
            assert reloaded.titles == {"en": "Page title", "ar": "عنوان"}
        print("16. two native tree JSON draft save/reloads preserve all fields and titles  OK")
        await db.rollback()
        await unbind_tenant(db)

    # Two genuinely independent sessions race on the same loaded token.
    async with AsyncSessionLocal() as db:
        await bind_tenant(db, one)
        race = await service.create_page(db, slug="race-" + uuid.uuid4().hex[:6], titles={"en": "Race"}, tree=tree())
        race_id, token = race.id, service.page_token(race)
    async def attempt(label):
        async with AsyncSessionLocal() as db:
            await bind_tenant(db, one)
            await service.get_page(db, race_id)  # deliberately stale identity-map entry
            await asyncio.sleep(0.01)
            try:
                result = await service.save_draft(db, race_id, tree=tree(label), expected_token=token)
                return ("saved", service.page_token(result))
            except HTTPException as exc:
                assert exc.status_code == 409
                return ("conflict", None)
    results = await asyncio.gather(attempt("Session A"), attempt("Session B"))
    assert sorted(r[0] for r in results) == ["conflict", "saved"], results
    async with AsyncSessionLocal() as db:
        await bind_tenant(db, one)
        live = await service.get_page(db, race_id)
        unchanged = __import__("copy").deepcopy(live.draft_tree)
        try:
            await service.save_draft(db, race_id, tree=tree("Stale overwrite"), expected_token=token)
            raise AssertionError("stale save accepted")
        except HTTPException as exc:
            assert exc.status_code == 409
        db.expunge_all()
        live = await service.get_page(db, race_id)
        assert live.draft_tree == unchanged
        fresh = service.page_token(live)
        await service.save_draft(db, race_id, tree=tree("Deliberate fresh save"), expected_token=fresh)
        await unbind_tenant(db)
        await bind_tenant(db, two)
        try:
            await service.save_draft(db, race_id, tree=tree("Wrong tenant"), expected_token=fresh)
            raise AssertionError("cross-tenant save accepted")
        except HTTPException as exc:
            assert exc.status_code == 404
        await db.rollback()
        await unbind_tenant(db)
    print("17. independent session race, stale rejection, fresh retry, tenant isolation  OK")

    # cleanup: drop the throwaway tenants (cascade)
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        await db.execute(text("DELETE FROM tenants WHERE name LIKE 'site-%'"), {} )
        await db.commit()
        left = (await db.execute(text("SELECT count(*) FROM site_pages"))).scalar()
        assert left == 0, left
        print("11. cleanup: test tenants and their pages removed  OK")

    print("ALL DB CHECKS PASSED")


asyncio.run(main())
