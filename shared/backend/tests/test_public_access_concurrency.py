"""Real two-session concurrency proof for the synthetic public-access boundary.

F3 (review): the publish-vs-enable-public race is guarded by the page row lock
both operations take first. These tests run the REAL service functions against
a REAL local Postgres (userspace pgserver), forcing each interleaving by
holding the page row lock in one session while the other blocks on it.

Skipped unless MIZAN_CONCURRENCY_DB is set to a reachable asyncpg URL
(e.g. postgresql+asyncpg://postgres@/postgres?host=/tmp/pgdata). The offline
suite never sets it. MIZAN_DB_APP_ROLE is forced empty so no SET LOCAL ROLE is
attempted; row-lock semantics being proven are identical under the superuser.

Invariant proven under BOTH orders: no final state has an enabled activation
covering a bound published tree; the loser refuses with 409 and the winner's
committed state is exactly what the loser re-reads (populate_existing).
"""
import asyncio
import os
import sys
import unittest
import uuid
from pathlib import Path

os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://unused:unused@127.0.0.1/unused')
os.environ.setdefault('SECRET_KEY', 'offline-test-not-used-for-signing')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DB_URL = os.environ.get('MIZAN_CONCURRENCY_DB', '')


def _available() -> bool:
    if not DB_URL:
        return False
    try:
        import asyncpg  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_available(), 'MIZAN_CONCURRENCY_DB not set to a reachable Postgres')
class PublicAccessConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        os.environ['MIZAN_DB_APP_ROLE'] = ''
        from app.platform.tenancy.context import install_tenancy_events
        install_tenancy_events()  # normally done by the app factory; stamps tenant_id on flush
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlalchemy import text
        self.engine = create_async_engine(DB_URL)
        self.sm = async_sessionmaker(self.engine, expire_on_commit=False)
        from app.db.base import Base
        from app.platform.tenancy import models as tenancy_models  # noqa: F401
        from app.platform.site import models as site_models  # noqa: F401
        from app.platform.auth.models import owner as owner_models  # noqa: F401
        tables = [Base.metadata.tables[name] for name in (
            'owner_accounts', 'tenants', 'site_pages', 'site_page_revisions', 'site_settings')]
        async with self.engine.begin() as conn:
            await conn.execute(text('DROP TABLE IF EXISTS site_activation CASCADE'))
            for t in reversed(tables):
                await conn.run_sync(t.drop, checkfirst=True)
            for t in tables:
                await conn.run_sync(t.create, checkfirst=True)
            # site_activation has no ORM model; mirror the migration shape the
            # service SQL uses (upsert key = host/slug/page_path).
            await conn.execute(text('''
                CREATE TABLE site_activation (
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    host TEXT NOT NULL, slug TEXT NOT NULL, page_path TEXT NOT NULL,
                    enabled BOOLEAN NOT NULL DEFAULT false,
                    allow_connected_data BOOLEAN NOT NULL DEFAULT false,
                    theme JSONB, audience_policy_version TEXT,
                    activated_by UUID, created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now(),
                    PRIMARY KEY (host, slug, page_path))'''))
        self.tid = uuid.uuid4()
        async with self.sm() as s:
            await s.execute(text(
                "INSERT INTO tenants (id, name, slug) VALUES (:id, 'Concurrency', :slug)"),
                {'id': self.tid, 'slug': 'concurrency-' + uuid.uuid4().hex[:8]})
            await s.commit()
        self.page_id = uuid.uuid4()
        self.slug = 'conc-' + uuid.uuid4().hex[:10]

    async def asyncTearDown(self):
        await self.engine.dispose()

    def _static_tree(self, marker):
        return {"type": "section", "children": [
            {"type": "text", "content": {"en": marker}}]}

    def _bound_tree(self):
        return {"type": "section", "children": [
            {"type": "text", "content": {"en": "bound"},
             "bindings": {"schema": "mizan.page-bindings.experimental.v0",
                          "content": {"en": {"text": {"mode": "dynamic", "field": "brand",
                                                     "module": "site", "source": "appearance",
                                                     "on_missing": "hide"}}}}}]}

    async def _seed_page(self):
        from sqlalchemy import text
        async with self.sm() as s:
            await s.execute(text(
                "INSERT INTO site_pages (id, tenant_id, slug, titles, status, draft_tree, published_tree)"
                " VALUES (:id, :tid, :slug, '{\"en\": \"Concurrency\"}', 'published',"
                " CAST(:draft AS jsonb), CAST(:pub AS jsonb))"),
                {'id': self.page_id, 'tid': self.tid, 'slug': self.slug,
                 'draft': __import__('json').dumps(self._bound_tree()),
                 'pub': __import__('json').dumps(self._static_tree('v1'))})
            await s.commit()

    def _ctx(self):
        from app.platform.tenancy.context import current_tenant_id
        current_tenant_id.set(self.tid)

    def _patch_binding_validation(self):
        # Provider-chain validation is covered elsewhere; these tests target the
        # row-lock/activation race only, and the minimal local schema has no
        # provider tables. Everything past this point in publish() stays real.
        from unittest.mock import AsyncMock, patch
        from app.platform.site import service
        p = patch.object(service, 'check_bound_tree', new=AsyncMock())
        p.start()
        self.addCleanup(p.stop)

    async def test_enable_public_first_then_publish_bound_refused(self):
        """A holds the page lock and enables public access (static page); B's
        publish of a bound draft blocks on the row lock, then must 409 with
        the previously published tree byte-identical."""
        from fastapi import HTTPException
        from app.core.config import settings
        from app.platform.site import service
        settings.PUBLIC_SITE_HOST = 'mizan-studio-feature-test.vercel.app'
        self._patch_binding_validation()
        await self._seed_page()
        self._ctx()
        sa = self.sm()
        await service.get_page(sa, self.page_id, locked=True)  # A holds the row lock

        async def publish_b():
            self._ctx()
            async with self.sm() as sb:
                await service.publish(sb, self.page_id)

        task = asyncio.ensure_future(publish_b())
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(task), 1.0)  # B is blocked on A's lock
        await service.set_public_access(sa, self.page_id, enabled=True)  # commits, releases lock
        with self.assertRaises(HTTPException) as cm:
            await task
        self.assertEqual(cm.exception.status_code, 409)
        self.assertIn('public in synthetic scope', cm.exception.detail)
        from sqlalchemy import text
        async with self.sm() as s:
            row = (await s.execute(text(
                "SELECT published_tree, draft_tree FROM site_pages WHERE id=:id"),
                {'id': self.page_id})).first()
            act = (await s.execute(text(
                "SELECT enabled, allow_connected_data FROM site_activation"
                " WHERE page_path=:p"), {'p': self.slug})).first()
        self.assertEqual(row[0], self._static_tree('v1'))  # published snapshot untouched
        self.assertEqual(row[1], self._bound_tree())        # draft kept
        self.assertTrue(act[0])                             # activation stayed enabled
        self.assertFalse(act[1])
        await sa.rollback()
        await sa.close()

    async def test_publish_bound_first_then_enable_public_refused(self):
        """A holds the page lock and publishes a bound draft (no enabled
        activation: allowed, private); B's enable-public blocks on the row
        lock, then must 409 and no activation row may appear."""
        from fastapi import HTTPException
        from app.core.config import settings
        from app.platform.site import service
        settings.PUBLIC_SITE_HOST = 'mizan-studio-feature-test.vercel.app'
        self._patch_binding_validation()
        await self._seed_page()
        self._ctx()
        sa = self.sm()
        await service.get_page(sa, self.page_id, locked=True)  # A holds the row lock

        async def enable_b():
            self._ctx()
            async with self.sm() as sb:
                await service.set_public_access(sb, self.page_id, enabled=True)

        task = asyncio.ensure_future(enable_b())
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(task), 1.0)  # B is blocked on A's lock
        await service.publish(sa, self.page_id)                # commits, releases lock
        with self.assertRaises(HTTPException) as cm:
            await task
        self.assertEqual(cm.exception.status_code, 409)
        self.assertIn('business data', cm.exception.detail)
        from sqlalchemy import text
        async with self.sm() as s:
            row = (await s.execute(text(
                "SELECT published_tree FROM site_pages WHERE id=:id"),
                {'id': self.page_id})).first()
            act = (await s.execute(text(
                "SELECT count(*) FROM site_activation WHERE page_path=:p"),
                {'p': self.slug})).first()
        self.assertEqual(row[0], self._bound_tree())  # publish won, page bound and private
        self.assertEqual(act[0], 0)                   # no activation was created
        await sa.rollback()
        await sa.close()


if __name__ == '__main__':
    unittest.main()
