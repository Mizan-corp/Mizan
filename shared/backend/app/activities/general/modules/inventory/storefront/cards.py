"""Inventory-owned optional website card fields, independent of name-only selection."""
import json
from uuid import UUID
from sqlalchemy import select
from app.framework.storefront_runtime import SourceUnavailable
from app.framework.storefront_values import money_value, media_value
from app.platform.settings.models import StoreSetting
from app.platform.tenancy.context import current_tenant_id
from app.framework.files import WorkspaceFile
from app.activities.general.modules.inventory.models.product import Product

SETTING_KEY = 'inventory_website_cards_v0'
SCHEMA = 'mizan.inventory-website-cards.experimental.v0'
# v1: identical shape, written only after the owner re-consents under wording
# that covers product LISTS/repeats as well as cards (consent-scope change
# pending review - nothing writes v1 yet, so reads below always see v0).
SCHEMA_V1 = 'mizan.inventory-website-cards.experimental.v1'


def card_policy(raw, *, schema=SCHEMA):
    if raw is None:
        return {'products': (), 'show_price': False, 'show_image': False, 'currency': None}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        raise SourceUnavailable('Invalid website card policy.') from None
    if not isinstance(value, dict) or set(value) != {'schema', 'products', 'show_price', 'show_image', 'currency'} or value['schema'] != schema:
        raise SourceUnavailable('Exact website card policy required.')
    if type(value['show_price']) is not bool or type(value['show_image']) is not bool:
        raise SourceUnavailable('Explicit field choices required.')
    ids = value['products']
    if not isinstance(ids, list) or len(ids) > 200 or any(not isinstance(x, str) for x in ids):
        raise SourceUnavailable('Bounded website product selection required.')
    try:
        parsed = tuple(UUID(x) for x in ids)
    except (ValueError, TypeError):
        raise SourceUnavailable('Invalid website product identity.') from None
    if len(set(parsed)) != len(parsed):
        raise SourceUnavailable('Duplicate product selection.')
    from app.framework.storefront_values import CURRENCIES
    currency = value['currency']
    if value['show_price']:
        if not isinstance(currency, str) or currency not in CURRENCIES:
            raise SourceUnavailable('Explicit supported website display currency required.')
    elif currency is not None:
        raise SourceUnavailable('No implicit unused currency.')
    return {'products': parsed, 'show_price': value['show_price'], 'show_image': value['show_image'], 'currency': currency}


async def display_consent(db, context):
    """Field-level consent for product LISTS/repeats: requires the v1 policy.

    A v0 (cards-worded) policy is NOT read as list consent: owners saved it
    under text that named cards only. Until the consent-scope wording change
    ships, no v1 exists and every collection read returns no consent.
    """
    raw = await db.scalar(select(StoreSetting.value).where(
        StoreSetting.tenant_id == context.tenant_id, StoreSetting.key == SETTING_KEY))
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        raise SourceUnavailable('Invalid website card policy.') from None
    if not isinstance(value, dict) or value.get('schema') != SCHEMA_V1:
        return None
    return card_policy(raw, schema=SCHEMA_V1)


async def read_cards(db, context, limit, products=None):
    if current_tenant_id.get() != context.tenant_id or 'inventory' not in context.active_modules or type(limit) is not int or not 1 <= limit <= 6:
        raise SourceUnavailable('Website card source unavailable.')
    raw = await db.scalar(select(StoreSetting.value).where(StoreSetting.tenant_id == context.tenant_id, StoreSetting.key == SETTING_KEY))
    policy = card_policy(raw)
    selected=policy['products']
    if products is not None:
        try:
            if not isinstance(products,list) or len(products)>6 or any(not isinstance(x,str) or str(UUID(x))!=x for x in products) or len(set(products))!=len(products):
                raise SourceUnavailable('Exact bounded section product selection required.')
            selected=tuple(UUID(x) for x in products)
        except (ValueError,TypeError):
            raise SourceUnavailable('Invalid section product identity.') from None
        # Revoked products drop out of the rendered rows; still-consented
        # selections and the rest of the page keep rendering. An empty
        # remainder hides the card row downstream (project_cards zero rows).
        selected=tuple(x for x in selected if x in policy['products'])
    if not selected:
        return []
    # Do not even select optional fields before explicit field-level opt-in.
    columns = [Product.id, Product.name]
    if policy['show_price']:
        columns.append(Product.retail_price)
    if policy['show_image']:
        columns.append(Product.image_url)
    rows = (await db.execute(select(*columns).where(Product.tenant_id == context.tenant_id, Product.is_active.is_(True), Product.id.in_(selected)).order_by(Product.id).limit(limit))).all()
    out = []
    for row in rows:
        product_id, name, *optional = row
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise SourceUnavailable('Invalid bounded website product name.')
        price = money_value(optional.pop(0), policy['currency']) if policy['show_price'] else None
        image = None
        if policy['show_image']:
            url = optional.pop(0)
            if url:
                record = await db.scalar(select(WorkspaceFile.id).where(WorkspaceFile.tenant_id == context.tenant_id, WorkspaceFile.kind == 'product_image', WorkspaceFile.owner_id == str(product_id), WorkspaceFile.url == url, WorkspaceFile.content_type.in_(['image/png', 'image/jpeg', 'image/gif', 'image/webp'])))
                if record is None:
                    raise SourceUnavailable('Product image provenance unavailable.')
                image = media_value(url, name, context.tenant_id)
        out.append({'item_key': str(product_id), 'name': name, 'price': price, 'image': image})
    return out
