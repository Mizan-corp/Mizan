"""Site page storage (ADR-015 S2): validation runs anywhere; the draft/publish/revision
lifecycle needs the database (DATABASE_URL) and is skipped without it, like the themes tests."""
import os
import uuid

import main  # noqa: F401
import pytest


def tree(text="مرحبا"):
    """A page tree the SDK-shared validator accepts (the studio builds this shape)."""
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
                     "content": {"ar": {"html": "<p>أهلاً بالعالم</p>"}, "en": {"html": "<p>Hello world</p>"}}},
                ],
            }],
        }],
    }


def test_tree_validation_uses_the_sdk_shared_validator():
    from fastapi import HTTPException

    from app.platform.site.service import check_tree

    check_tree(tree())  # a valid tree passes
    bad = tree()
    bad["children"][0]["children"][0]["children"][0]["content"]["fr"] = {"text": "Bonjour"}
    with pytest.raises(HTTPException) as exc:  # a language the site doesn't have is rejected
        check_tree(bad)
    assert exc.value.status_code == 422
    bad = tree()
    bad["children"][0]["children"][0]["children"][0]["type"] = "script"
    with pytest.raises(HTTPException):  # an unknown block is rejected
        check_tree(bad)
    bad = tree()
    bad["children"][0]["children"][0]["children"][0]["content"]["ar"]["text"] = "x" * 201
    with pytest.raises(HTTPException):  # a heading holds at most 200 characters
        check_tree(bad)
    # Markup inside text/html fields is a render-time concern: the server renderer sanitises
    # with nh3 (app/platform/site/render.py), so storage accepts and the output is safe.
    with pytest.raises(HTTPException):  # the root is a section
        check_tree({"id": "n_root", "type": "heading"})
    with pytest.raises(HTTPException):  # a bound on the stored size
        check_tree(tree("x" * 200_001))


def test_titles_and_slug_validation():
    from fastapi import HTTPException

    from app.platform.site.service import check_slug, check_titles

    assert check_slug("about-us") == "about-us"
    assert check_titles({"ar": "من نحن"}) == {"ar": "من نحن"}
    for slug in ("", "About", "a_b", "-x", "x-", "x" * 81, "حول"):
        with pytest.raises(HTTPException):
            check_slug(slug)
    for titles in ({}, {"fr": "Salut"}, {"ar": ""}, {"ar": "x" * 121}, {"ar": 5}, "عنوان"):
        with pytest.raises(HTTPException):
            check_titles(titles)


pytestmark_db = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs the database")


@pytest.fixture
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


@pytestmark_db
async def test_draft_publish_revision_rollback_lifecycle(fresh_engine):
    from fastapi import HTTPException

    from app.db.base import AsyncSessionLocal
    from app.platform.site import service
    from app.platform.tenancy.context import bind_tenant, unbind_tenant
    from app.platform.tenancy.models import Tenant

    tid = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        tenant = Tenant(id=tid, name=f"site-{tid.hex[:8]}", sector="retail", scale="small")
        db.add(tenant)
        await db.commit()
        await bind_tenant(db, tid)
        try:
            page = await service.create_page(db, slug="home", titles={"ar": "الرئيسية", "en": "Home"})
            assert page.status == "draft" and page.draft_tree is None and page.published_tree is None

            # Autosave writes the draft only: nothing is published yet.
            await service.save_draft(db, page.id, tree=tree(), titles={"ar": "الرئيسية", "en": "Home"})
            page = await service.get_page(db, page.id)
            assert page.draft_tree is not None and page.published_tree is None and page.status == "draft"

            # Publish copies the draft to the published tree and writes revision 1.
            await service.publish(db, page.id, None)
            page = await service.get_page(db, page.id)
            assert page.published_tree == page.draft_tree and page.status == "published"
            revs = await service.list_revisions(db, page.id)
            assert [r.number for r in revs] == [1] and revs[0].tree == page.published_tree

            # A later draft + publish writes revision 2 and keeps revision 1.
            await service.save_draft(db, page.id, tree=tree("أهلاً"))
            await service.publish(db, page.id, None)
            revs = await service.list_revisions(db, page.id)
            assert [r.number for r in revs] == [2, 1]

            # Rollback copies revision 1 into the draft; the published tree waits for publish.
            await service.rollback(db, page.id, revs[1].id)
            page = await service.get_page(db, page.id)
            first = revs[1].tree["children"][0]["children"][0]["children"][0]["content"]["ar"]["text"]
            draft = page.draft_tree["children"][0]["children"][0]["children"][0]["content"]["ar"]["text"]
            live = page.published_tree["children"][0]["children"][0]["children"][0]["content"]["ar"]["text"]
            assert draft == first == "مرحبا" and live == "أهلاً"

            # Archive keeps everything, stops serving; reopen restores the previous state.
            await service.archive(db, page.id)
            page = await service.get_page(db, page.id)
            assert page.status == "archived" and page.published_tree is not None
            with pytest.raises(HTTPException):
                await service.save_draft(db, page.id, tree=tree())
            await service.reopen(db, page.id)
            assert (await service.get_page(db, page.id)).status == "published"

            # Slugs are unique inside the workspace.
            with pytest.raises(HTTPException):
                await service.create_page(db, slug="home", titles={"ar": "أخرى"})
        finally:
            await db.rollback()
            await unbind_tenant(db)


@pytestmark_db
async def test_form_submission_roundtrip_and_isolation(fresh_engine):
    """site_form_submissions (contact-form V1): the public endpoint's writes are
    tenant-stamped, readable by the owning workspace, and invisible to another
    workspace through a fresh session (empty identity map) under RLS."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.db.base import AsyncSessionLocal
    from app.platform.site import service
    from app.platform.site.models import SiteFormSubmission
    from app.platform.tenancy.context import bind_tenant, unbind_tenant
    from app.platform.tenancy.models import Tenant

    one, two = uuid.uuid4(), uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add_all([Tenant(id=one, name=f"site-{one.hex[:8]}", sector="retail", scale="small"),
                    Tenant(id=two, name=f"site-{two.hex[:8]}", sector="retail", scale="small")])
        await db.commit()
        await bind_tenant(db, one)
        try:
            page = await service.create_page(db, slug="contact", titles={"en": "Contact"})
            sub = SiteFormSubmission(page_id=page.id, block_id="n_form01",
                                     payload={"email": "a@b.co", "message": "hi"})
            db.add(sub)
            await db.commit()
            sub_id = sub.id
            rows = (await db.execute(select(SiteFormSubmission))).scalars().all()
            assert [r.id for r in rows] == [sub_id]
            assert rows[0].tenant_id == one and rows[0].read_at is None
            # The owning workspace marks it read.
            rows[0].read_at = datetime.now(timezone.utc)
            await db.commit()
        finally:
            await unbind_tenant(db)
        await bind_tenant(db, two)
        try:
            assert (await db.execute(select(SiteFormSubmission))).scalars().all() == []
            # A real cross-workspace read is a NEW request: a fresh session (empty
            # identity map, so db.get() can't answer without SQL), tenant two
            # bound, RLS through mizan_app.
            async with AsyncSessionLocal() as db2:
                await bind_tenant(db2, two)
                assert await db2.get(SiteFormSubmission, sub_id) is None
        finally:
            await db.rollback()
            await unbind_tenant(db)


@pytestmark_db
async def test_workspaces_cannot_see_each_others_pages(fresh_engine):
    from fastapi import HTTPException

    from app.db.base import AsyncSessionLocal
    from app.platform.site import service
    from app.platform.tenancy.context import bind_tenant, unbind_tenant
    from app.platform.tenancy.models import Tenant

    one, two = uuid.uuid4(), uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add_all([Tenant(id=one, name=f"site-{one.hex[:8]}", sector="retail", scale="small"),
                    Tenant(id=two, name=f"site-{two.hex[:8]}", sector="retail", scale="small")])
        await db.commit()
        await bind_tenant(db, one)
        page = await service.create_page(db, slug="home", titles={"ar": "الرئيسية"})
        await unbind_tenant(db)
        await bind_tenant(db, two)
        try:
            # The same slug is free in another workspace, and the first workspace's page is invisible.
            assert await service.list_pages(db) == []
            other = await service.create_page(db, slug="home", titles={"ar": "الرئيسية"})
            assert other.id != page.id
            # A real cross-workspace read is a NEW request: a fresh session (empty identity
            # map, so db.get() can't answer without SQL), tenant two bound, RLS through
            # mizan_app. The plain read AND the locked read (a raw select) must both miss.
            async with AsyncSessionLocal() as db2:
                await bind_tenant(db2, two)
                with pytest.raises(HTTPException):
                    await service.get_page(db2, page.id)
                with pytest.raises(HTTPException):
                    await service.get_page(db2, page.id, locked=True)
        finally:
            await db.rollback()
            await unbind_tenant(db)
