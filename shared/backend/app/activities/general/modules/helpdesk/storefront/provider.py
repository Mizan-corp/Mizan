"""Helpdesk-owned explicit website opt-in for service offerings. No offering chosen by default.

The module owns its website allowlist in tenant StoreSetting, default empty. Names only:
no description, starting amount, currency, internal notes or work data is ever a website
field in this schema. Typed display fields need their own reviewed consent wording first,
the same path the inventory cards consent took.
"""
import json
from uuid import UUID
from sqlalchemy import select
from app.framework.storefront_collections import CollectionProvider
from app.framework.storefront_runtime import SourceContext, SourceUnavailable
from app.platform.tenancy.context import current_tenant_id
from app.platform.settings.models import StoreSetting
from app.activities.general.modules.helpdesk.models import HelpdeskOffering

SETTING_KEY = 'helpdesk_website_publication_v0'
SCHEMA = 'mizan.helpdesk-website-services.experimental.v0'


def publication_ids(raw):
    if raw is None:
        return ()
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        raise SourceUnavailable('Invalid website services selection.') from None
    if not isinstance(value, dict) or set(value) != {'schema', 'offerings'} or value['schema'] != SCHEMA:
        raise SourceUnavailable('Invalid website services selection.')
    ids = value['offerings']
    if not isinstance(ids, list) or len(ids) > 200 or any(not isinstance(x, str) for x in ids):
        raise SourceUnavailable('Invalid bounded website services selection.')
    try:
        parsed = tuple(UUID(x) for x in ids)
    except (ValueError, TypeError):
        raise SourceUnavailable('Invalid service record identity.') from None
    if len(set(parsed)) != len(parsed):
        raise SourceUnavailable('Duplicate website services selection.')
    return parsed


CONTRACT = {'schema': 'mizan.collection.experimental.v0', 'module': 'helpdesk', 'source': 'services',
            'key': 'item_key',
            'fields': {'name': {'type': 'text', 'semantic': 'plain_text', 'nullable': False, 'max_length': 200}},
            'max_items': 24}


def helpdesk_providers(db):
    async def read(context: SourceContext, limit: int):
        if current_tenant_id.get() != context.tenant_id or 'helpdesk' not in context.active_modules:
            raise SourceUnavailable('Helpdesk website source unavailable.')
        raw = await db.scalar(select(StoreSetting.value).where(
            StoreSetting.tenant_id == context.tenant_id, StoreSetting.key == SETTING_KEY))
        selected = publication_ids(raw)
        if not selected:
            return []
        # Names only: no description, amount, currency or internal field is ever selected.
        rows = (await db.execute(
            select(HelpdeskOffering.id, HelpdeskOffering.name)
            .where(HelpdeskOffering.tenant_id == context.tenant_id,
                   HelpdeskOffering.id.in_(selected),
                   HelpdeskOffering.is_active.is_(True))
            .order_by(HelpdeskOffering.id).limit(limit))).all()
        result = []
        for key, name in rows:
            if not isinstance(name, str) or not name.strip() or len(name) > 200:
                raise SourceUnavailable('Selected service text exceeds reviewed bound.')
            result.append({'item_key': str(key), 'name': name})
        return result
    return (CollectionProvider(CONTRACT, read),)
