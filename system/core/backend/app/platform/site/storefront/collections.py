"""Local-only site collection provider. Not registered in authenticated/public APIs.

Existing chrome links have no persisted IDs. A unique href fingerprint is stable
across label edits and list reordering. Duplicate hrefs fail closed rather than
pretending positional indexes are durable identities. Only labels leave here.
"""
from __future__ import annotations
import hashlib
from app.framework.storefront_collections import CollectionProvider
from app.framework.storefront_runtime import SourceContext, SourceUnavailable
from app.platform.tenancy.context import current_tenant_id
from app.platform.site.service import get_settings

NAVIGATION_LABELS = {
    'schema': 'mizan.collection.experimental.v0', 'module': 'site',
    'source': 'navigation_labels', 'key': 'item_key',
    'fields': {'label': {'type': 'text', 'semantic': 'plain_text',
                         'nullable': False, 'max_length': 40}},
    'max_items': 8,
}


def navigation_labels_provider(db) -> CollectionProvider:
    async def read(context: SourceContext, limit: int) -> list[dict]:
        if current_tenant_id.get() != context.tenant_id:
            raise SourceUnavailable('Source unavailable.')
        value = await get_settings(db)
        header = value.get('header', {})
        if not isinstance(header, dict):
            raise SourceUnavailable('Saved website navigation is invalid.')
        links = header.get('links', [])
        if not isinstance(links, list) or len(links) > 8:
            raise SourceUnavailable('Saved website navigation is invalid.')
        seen = set()
        rows = []
        for link in links:
            if not isinstance(link, dict):
                raise SourceUnavailable('Saved website navigation is invalid.')
            label, href = link.get('label'), link.get('href')
            if (not isinstance(label, str) or not label.strip() or len(label) > 40
                    or not isinstance(href, str) or len(href) > 200
                    or not href.startswith(('#', '/', 'https://')) or href in seen):
                raise SourceUnavailable('Saved website navigation needs valid unique link identities.')
            seen.add(href)
            key = 'nav_' + hashlib.sha256(href.encode('utf-8')).hexdigest()
            rows.append({'item_key': key, 'label': label})
        # Explicit top-N selection is part of this source, not silent runtime truncation.
        return rows[:limit]
    return CollectionProvider(NAVIGATION_LABELS, read, platform_core=True)
