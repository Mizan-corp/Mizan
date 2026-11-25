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
# that covers product LISTS/repeats as well as cards.
SCHEMA_V1 = 'mizan.inventory-website-cards.experimental.v1'
# v2: identical shape, written only after the owner re-consents under wording
# that ALSO covers individually bound elements (per-property scalar binding),
# in addition to cards and repeating lists (consent-scope change
# docs/studio-consent-scope-v2.md). v1 rows never unlock scalar fields.
SCHEMA_V2 = 'mizan.inventory-website-cards.experimental.v2'
# v3 wording is the first that names PUBLIC pages (per-page publish approval),
# not only signed-in previews. Older recorded versions keep their recorded
# preview scope: valid for previews, never authority for public reads.
SCHEMA_V3 = 'mizan.inventory-website-cards.experimental.v3'


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


def stored_policy(raw):
    """Read path for the settings UI: accept either consent version.

    v0 rows stay valid for cards; v1 rows are the list-aware re-consent.
    """
    if raw is None:
        return card_policy(None)
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        raise SourceUnavailable('Invalid website card policy.') from None
    schema = value.get('schema') if isinstance(value, dict) else None
    if schema not in (SCHEMA, SCHEMA_V1, SCHEMA_V2, SCHEMA_V3):
        raise SourceUnavailable('Exact website card policy required.')
    return card_policy(raw, schema=schema)


async def display_consent(db, context):
    """Field-level consent for product LISTS/repeats: requires a v1+ policy.

    A v0 (cards-worded) policy is NOT read as list consent: owners saved it
    under text that named cards only.
    """
    raw = await db.scalar(select(StoreSetting.value).where(
        StoreSetting.tenant_id == context.tenant_id, StoreSetting.key == SETTING_KEY))
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        raise SourceUnavailable('Invalid website card policy.') from None
    if not isinstance(value, dict) or value.get('schema') not in (SCHEMA_V1, SCHEMA_V2, SCHEMA_V3):
        return None
    return card_policy(raw, schema=value['schema'])


async def element_consent(db, context):
    """Field-level consent for INDIVIDUALLY BOUND elements: requires the v2 policy.

    v0 (cards-worded) and v1 (cards+lists-worded) policies are NOT read as
    scalar element consent: owners saved them under text that never named
    individually bound elements. Only a v2+ re-consent unlocks scalar reads.
    Public scope for those elements still follows the card/public rules.
    """
    raw = await db.scalar(select(StoreSetting.value).where(
        StoreSetting.tenant_id == context.tenant_id, StoreSetting.key == SETTING_KEY))
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        raise SourceUnavailable('Invalid website card policy.') from None
    if not isinstance(value, dict) or value.get('schema') not in (SCHEMA_V2, SCHEMA_V3):
        return None
    return card_policy(raw, schema=value['schema'])


async def read_cards(db, context, limit, products=None, *, public=False):
    if current_tenant_id.get() != context.tenant_id or 'inventory' not in context.active_modules or type(limit) is not int or not 1 <= limit <= 6:
        raise SourceUnavailable('Website card source unavailable.')
    raw = await db.scalar(select(StoreSetting.value).where(StoreSetting.tenant_id == context.tenant_id, StoreSetting.key == SETTING_KEY))
    if public:
        # Public reads (visitor route and the publish-approval dry run, which
        # simulates exactly that audience) require the v3 wording: v0/v1/v2
        # were recorded under text that promised signed-in previews only, so
        # they can never be the authority for exposing fields publicly.
        try:
            recorded = json.loads(raw).get('schema') if raw is not None else None
        except (TypeError, ValueError):
            raise SourceUnavailable('Invalid website card policy.') from None
        if recorded != SCHEMA_V3:
            raise SourceUnavailable('Public product display requires the current website display consent.')
    # Cards were covered by every consent wording (v0 cards, v1 +lists, v2
    # +bound elements), so the render path accepts any recorded version via the
    # same multi-version read the settings UI uses. Parsing with the v0 default
    # here refused every row saved by the current (v2-stamping) writer.
    policy = stored_policy(raw)
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


async def read_scoped_item(db, context, item_key, fields):
    """One consented product for an individually bound element (v2 consent only).

    `fields` is a platform-chosen subset of {'name', 'price', 'image'} from the
    binding target, never client-supplied free text. Returns None when the
    record is not currently consented or active (revoked drops out, per the
    user-approved revocation semantics); malformed identities and out-of-scope
    field selections fail closed. Optional columns are selected only after the
    matching field-level opt-in.
    """
    if current_tenant_id.get() != context.tenant_id or 'inventory' not in context.active_modules:
        raise SourceUnavailable('Website element source unavailable.')
    if not isinstance(item_key, str) or len(item_key) > 64:
        raise SourceUnavailable('Invalid bound record identity.')
    try:
        product_id = UUID(item_key)
    except (ValueError, TypeError):
        raise SourceUnavailable('Invalid bound record identity.') from None
    if str(product_id) != item_key:
        raise SourceUnavailable('Invalid bound record identity.')
    if not isinstance(fields, (list, tuple)) or not fields or len(fields) > 3 or set(fields) - {'name', 'price', 'image'}:
        raise SourceUnavailable('Invalid bound field selection.')
    consent = await element_consent(db, context)
    if consent is None or product_id not in consent['products']:
        return None
    columns = [Product.id, Product.name]
    if 'price' in fields and consent['show_price']:
        columns.append(Product.retail_price)
    if 'image' in fields and consent['show_image']:
        columns.append(Product.image_url)
    row = (await db.execute(select(*columns).where(
        Product.tenant_id == context.tenant_id, Product.is_active.is_(True),
        Product.id == product_id))).first()
    if row is None:
        return None
    product_id, name, *optional = row
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        raise SourceUnavailable('Invalid bounded website product name.')
    item = {'name': name, 'price': None, 'image': None}
    if 'price' in fields and consent['show_price']:
        item['price'] = money_value(optional.pop(0), consent['currency'])
    if 'image' in fields and consent['show_image']:
        url = optional.pop(0)
        if url:
            record = await db.scalar(select(WorkspaceFile.id).where(
                WorkspaceFile.tenant_id == context.tenant_id,
                WorkspaceFile.kind == 'product_image',
                WorkspaceFile.owner_id == str(product_id),
                WorkspaceFile.url == url,
                WorkspaceFile.content_type.in_(['image/png', 'image/jpeg', 'image/gif', 'image/webp'])))
            if record is None:
                raise SourceUnavailable('Product image provenance unavailable.')
            item['image'] = media_value(url, name, context.tenant_id)
    return item
