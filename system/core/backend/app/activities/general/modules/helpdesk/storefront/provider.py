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
# v1 names the checked display fields: service description, and starting price
# (amount + currency, always together). v0 rows keep their exact 2-key shape.
SCHEMA_V1 = 'mizan.helpdesk-website-services.experimental.v1'
FIELD_KEYS = ('show_description', 'show_starting_price')


def publication_ids(raw):
    return service_policy(raw)['offerings']


def service_policy(raw, schema=None):
    if raw is None:
        return {'schema': schema or SCHEMA, 'offerings': (), 'show_description': False, 'show_starting_price': False}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        raise SourceUnavailable('Invalid website services selection.') from None
    if not isinstance(value, dict):
        raise SourceUnavailable('Invalid website services selection.')
    if value.get('schema') == SCHEMA:
        if set(value) != {'schema', 'offerings'}:
            raise SourceUnavailable('Invalid website services selection.')
        fields = {key: False for key in FIELD_KEYS}
    elif value.get('schema') == SCHEMA_V1:
        if set(value) != {'schema', 'offerings', *FIELD_KEYS}:
            raise SourceUnavailable('Invalid website services selection.')
        fields = {key: value[key] for key in FIELD_KEYS}
        if any(not isinstance(flag, bool) for flag in fields.values()):
            raise SourceUnavailable('Invalid website services field selection.')
    else:
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
    return {'schema': value['schema'], 'offerings': parsed, **fields}


CONTRACT = {'schema': 'mizan.collection.experimental.v0', 'module': 'helpdesk', 'source': 'services',
            'key': 'item_key',
            'fields': {'name': {'type': 'text', 'semantic': 'plain_text', 'nullable': False, 'max_length': 200}},
            'max_items': 24}

CONTRACT_V1 = {'schema': 'mizan.collection.experimental.v0', 'module': 'helpdesk', 'source': 'services',
               'key': 'item_key',
               'fields': {'name': {'type': 'text', 'semantic': 'plain_text', 'nullable': False, 'max_length': 200},
                          'description': {'type': 'text', 'semantic': 'plain_text', 'nullable': True, 'max_length': 200},
                          'starting_price': {'type': 'text', 'semantic': 'plain_text', 'nullable': True, 'max_length': 40}},
               'max_items': 24}


def helpdesk_providers(db):
    async def read(context: SourceContext, limit: int):
        if current_tenant_id.get() != context.tenant_id or 'helpdesk' not in context.active_modules:
            raise SourceUnavailable('Helpdesk website source unavailable.')
        raw = await db.scalar(select(StoreSetting.value).where(
            StoreSetting.tenant_id == context.tenant_id, StoreSetting.key == SETTING_KEY))
        policy = service_policy(raw)
        selected = policy['offerings']
        if not selected:
            return []
        # Under v0 wording only the name column is ever selected. Description and
        # starting amount/currency are selected only on a recorded v1 row whose
        # explicit field flags are set.
        columns = [HelpdeskOffering.id, HelpdeskOffering.name]
        if policy['show_description']:
            columns.append(HelpdeskOffering.description)
        if policy['show_starting_price']:
            columns += [HelpdeskOffering.starting_amount, HelpdeskOffering.currency]
        rows = (await db.execute(
            select(*columns)
            .where(HelpdeskOffering.tenant_id == context.tenant_id,
                   HelpdeskOffering.id.in_(selected),
                   HelpdeskOffering.is_active.is_(True))
            .order_by(HelpdeskOffering.id).limit(limit))).all()
        result = []
        for row in rows:
            key, name = row[0], row[1]
            if not isinstance(name, str) or not name.strip() or len(name) > 200:
                raise SourceUnavailable('Selected service text exceeds reviewed bound.')
            item = {'item_key': str(key), 'name': name, 'description': None, 'starting_price': None}
            pos = 2
            if policy['show_description']:
                description = row[pos]; pos += 1
                if description is not None and (not isinstance(description, str) or len(description) > 200):
                    raise SourceUnavailable('Selected service description exceeds reviewed bound.')
                item['description'] = description
            if policy['show_starting_price']:
                amount, currency = row[pos], row[pos + 1]
                if amount is None or not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
                    raise SourceUnavailable('Selected service price exceeds reviewed bound.')
                item['starting_price'] = f'{amount} {currency.upper()}'
            result.append(item)
        return result
    return (CollectionProvider(CONTRACT_V1, read),)
