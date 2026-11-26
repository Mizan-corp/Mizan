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
# v4 wording is the first that names category membership linkage (a category
# page reveals which consented products belong to a published category) and
# URL-selected current-record retrieval (one template renders the product
# whose id is in the URL), and the first that may carry the description
# display field (consent-scope change docs/studio-consent-scope-v4.md). v4
# rows add one payload key: show_description. Older rows keep their exact
# five-key shape and never unlock linkage or description.
SCHEMA_V4 = 'mizan.inventory-website-cards.experimental.v4'
_DESCRIPTION_MAX = 2000


def card_policy(raw, *, schema=SCHEMA):
    if raw is None:
        return {'products': (), 'show_price': False, 'show_image': False, 'show_description': False, 'currency': None}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        raise SourceUnavailable('Invalid website card policy.') from None
    expected = {'schema', 'products', 'show_price', 'show_image', 'currency'} | ({'show_description'} if schema == SCHEMA_V4 else set())
    if not isinstance(value, dict) or set(value) != expected or value['schema'] != schema:
        raise SourceUnavailable('Exact website card policy required.')
    if type(value['show_price']) is not bool or type(value['show_image']) is not bool:
        raise SourceUnavailable('Explicit field choices required.')
    if schema == SCHEMA_V4 and type(value['show_description']) is not bool:
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
    # Older wordings never named description: it reads as refused there.
    show_description = bool(value.get('show_description')) if schema == SCHEMA_V4 else False
    return {'products': parsed, 'show_price': value['show_price'], 'show_image': value['show_image'], 'show_description': show_description, 'currency': currency}


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
    if schema not in (SCHEMA, SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4):
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
    # v1/v2 were recorded under previews-only wording; public reads of
    # list fields require the v3 wording that names public pages.
    accepted = (SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4) if context.audience != 'public' else (SCHEMA_V3, SCHEMA_V4)
    if not isinstance(value, dict) or value.get('schema') not in accepted:
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
    # v2 was recorded under previews-only wording; public reads of bound
    # element fields require the v3 wording that names public pages.
    accepted = (SCHEMA_V2, SCHEMA_V3, SCHEMA_V4) if context.audience != 'public' else (SCHEMA_V3, SCHEMA_V4)
    if not isinstance(value, dict) or value.get('schema') not in accepted:
        return None
    return card_policy(raw, schema=value['schema'])


async def read_cards(db, context, limit, products=None):
    if current_tenant_id.get() != context.tenant_id or 'inventory' not in context.active_modules or type(limit) is not int or not 1 <= limit <= 6:
        raise SourceUnavailable('Website card source unavailable.')
    raw = await db.scalar(select(StoreSetting.value).where(StoreSetting.tenant_id == context.tenant_id, StoreSetting.key == SETTING_KEY))
    if context.audience == 'public':
        # Public reads (visitor route and the publish-approval dry run, which
        # simulates exactly that audience) require the v3 wording: v0/v1/v2
        # were recorded under text that promised signed-in previews only, so
        # they can never be the authority for exposing fields publicly.
        try:
            recorded = json.loads(raw).get('schema') if raw is not None else None
        except (TypeError, ValueError):
            raise SourceUnavailable('Invalid website card policy.') from None
        # v3 first named public pages; v4 keeps that wording and adds category
        # linkage, URL-selected detail and the optional description field, so
        # both are authority for public reads (docs/studio-consent-scope-v4.md).
        if recorded not in (SCHEMA_V3, SCHEMA_V4):
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


async def read_category_products(db, context, category_id, limit):
    """Consented products belonging to one published category (v4 linkage consent).

    Category membership was first named by the v4 wording, so a recorded v4
    policy is required for previews AND public reads alike. The category must
    be in the workspace's publication allowlist; only consented, active
    products in it are returned (revoked products drop out, user-approved
    2026-11-24 semantics). Returns the same row shape as read_cards.
    """
    if current_tenant_id.get() != context.tenant_id or 'inventory' not in context.active_modules or type(limit) is not int or not 1 <= limit <= 24:
        raise SourceUnavailable('Website category source unavailable.')
    if not isinstance(category_id, str) or len(category_id) > 64:
        raise SourceUnavailable('Invalid website category identity.')
    try:
        category_uuid = UUID(category_id)
    except (ValueError, TypeError):
        raise SourceUnavailable('Invalid website category identity.') from None
    if str(category_uuid) != category_id:
        raise SourceUnavailable('Invalid website category identity.')
    raw = await db.scalar(select(StoreSetting.value).where(
        StoreSetting.tenant_id == context.tenant_id, StoreSetting.key == SETTING_KEY))
    if raw is None:
        return []
    try:
        recorded = json.loads(raw).get('schema')
    except (TypeError, ValueError, AttributeError):
        raise SourceUnavailable('Invalid website card policy.') from None
    if recorded != SCHEMA_V4:
        # Linkage is named only by the v4 wording; older consents never
        # authorized revealing category membership, for any audience.
        return []
    policy = card_policy(raw, schema=SCHEMA_V4)
    # Lazy import: provider imports this module's display_consent lazily too,
    # so neither file holds a module-level cycle.
    from app.activities.general.modules.inventory.storefront import provider as _provider
    publication_raw = await db.scalar(select(StoreSetting.value).where(
        StoreSetting.tenant_id == context.tenant_id,
        StoreSetting.key == _provider.SETTING_KEY))
    if category_uuid not in _provider.publication_ids(publication_raw)['categories']:
        return []
    if not policy['products']:
        return []
    from app.activities.general.modules.inventory.models.product import Subcategory
    columns = [Product.id, Product.name]
    if policy['show_price']:
        columns.append(Product.retail_price)
    if policy['show_image']:
        columns.append(Product.image_url)
    rows = (await db.execute(
        select(*columns)
        .join(Subcategory, Product.subcategory_id == Subcategory.id)
        .where(Product.tenant_id == context.tenant_id, Product.is_active.is_(True),
               Product.id.in_(policy['products']), Subcategory.category_id == category_uuid)
        .order_by(Product.id).limit(limit))).all()
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
                record = await db.scalar(select(WorkspaceFile.id).where(
                    WorkspaceFile.tenant_id == context.tenant_id,
                    WorkspaceFile.kind == 'product_image',
                    WorkspaceFile.owner_id == str(product_id),
                    WorkspaceFile.url == url,
                    WorkspaceFile.content_type.in_(['image/png', 'image/jpeg', 'image/gif', 'image/webp'])))
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
    if not isinstance(fields, (list, tuple)) or not fields or len(fields) > 4 or set(fields) - {'name', 'price', 'image', 'description'}:
        raise SourceUnavailable('Invalid bound field selection.')
    consent = await element_consent(db, context)
    if consent is None or product_id not in consent['products']:
        return None
    return await _read_item_row(db, context, product_id, fields, consent)


async def route_category_available(db, context, category_id):
    """Whether the URL-selected category may drive a category template render.

    Companion to read_category_products for the visitor notice gate: True only
    when a v4 policy is recorded AND the category sits in the workspace's
    publication allowlist. An allowlisted category with zero consented
    products is available - an empty list is a legitimate render, not a
    missing record. False is deliberately one answer for a nonexistent id, an
    unpublished category and a pre-v4 consent, so the visitor notice never
    says which case it was. Same fail-closed input validation as the readers.
    """
    if current_tenant_id.get() != context.tenant_id or 'inventory' not in context.active_modules:
        raise SourceUnavailable('Website category source unavailable.')
    if not isinstance(category_id, str) or len(category_id) > 64:
        raise SourceUnavailable('Invalid website category identity.')
    try:
        category_uuid = UUID(category_id)
    except (ValueError, TypeError):
        raise SourceUnavailable('Invalid website category identity.') from None
    if str(category_uuid) != category_id:
        raise SourceUnavailable('Invalid website category identity.')
    raw = await db.scalar(select(StoreSetting.value).where(
        StoreSetting.tenant_id == context.tenant_id, StoreSetting.key == SETTING_KEY))
    if raw is None:
        return False
    try:
        recorded = json.loads(raw).get('schema')
    except (TypeError, ValueError, AttributeError):
        raise SourceUnavailable('Invalid website card policy.') from None
    if recorded != SCHEMA_V4:
        return False
    from app.activities.general.modules.inventory.storefront import provider as _provider
    publication_raw = await db.scalar(select(StoreSetting.value).where(
        StoreSetting.tenant_id == context.tenant_id,
        StoreSetting.key == _provider.SETTING_KEY))
    return category_uuid in _provider.publication_ids(publication_raw)['categories']


async def read_route_item(db, context, item_key, fields):
    """URL-selected current record ("current item", v2 route bindings).

    The record identity comes from the visitor URL, not from an owner-pinned
    binding, so the consent wording must name URL-selected retrieval: only a
    recorded v4 policy authorizes these reads, for previews AND public alike
    (v0-v3 wordings never named it). Everything else matches read_scoped_item:
    the product must be consented and active, optional columns are selected
    only after their field-level opt-in, malformed input fails closed.
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
    if not isinstance(fields, (list, tuple)) or not fields or len(fields) > 4 or set(fields) - {'name', 'price', 'image', 'description'}:
        raise SourceUnavailable('Invalid bound field selection.')
    raw = await db.scalar(select(StoreSetting.value).where(
        StoreSetting.tenant_id == context.tenant_id, StoreSetting.key == SETTING_KEY))
    try:
        recorded = json.loads(raw).get('schema') if raw is not None else None
    except (TypeError, ValueError):
        raise SourceUnavailable('Invalid website card policy.') from None
    if recorded != SCHEMA_V4:
        return None
    consent = card_policy(raw, schema=SCHEMA_V4)
    if product_id not in consent['products']:
        return None
    return await _read_item_row(db, context, product_id, fields, consent)


async def _read_item_row(db, context, product_id, fields, consent):
    columns = [Product.id, Product.name]
    if 'price' in fields and consent['show_price']:
        columns.append(Product.retail_price)
    if 'image' in fields and consent['show_image']:
        columns.append(Product.image_url)
    if 'description' in fields and consent['show_description']:
        columns.append(Product.description)
    row = (await db.execute(select(*columns).where(
        Product.tenant_id == context.tenant_id, Product.is_active.is_(True),
        Product.id == product_id))).first()
    if row is None:
        return None
    product_id, name, *optional = row
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        raise SourceUnavailable('Invalid bounded website product name.')
    item = {'name': name, 'price': None, 'image': None, 'description': None}
    if 'description' in fields and consent['show_description']:
        text = optional.pop()
        if text is not None and (not isinstance(text, str) or len(text) > _DESCRIPTION_MAX):
            raise SourceUnavailable('Invalid bounded website product description.')
        item['description'] = text
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


async def probe_route_items(db, context, limit=24):
    """Currently exposable product identities for an approval dry-run probe read.

    The no-route approval dry-run resolves route-mode ("current item") reads
    empty, so record-driven failures used to surface only at visitor request
    time (gap register item 16). The approval re-resolves the tree against
    these real records instead. Empty when nothing is currently exposable
    under the recorded v4 policy: the visitor render then hides the element
    by design and there is nothing to probe. Bounded like every website
    selection; identities only, no field values.
    """
    if current_tenant_id.get() != context.tenant_id or 'inventory' not in context.active_modules:
        raise SourceUnavailable('Website element source unavailable.')
    raw = await db.scalar(select(StoreSetting.value).where(
        StoreSetting.tenant_id == context.tenant_id, StoreSetting.key == SETTING_KEY))
    try:
        recorded = json.loads(raw).get('schema') if raw is not None else None
    except (TypeError, ValueError):
        raise SourceUnavailable('Invalid website card policy.') from None
    if recorded != SCHEMA_V4:
        return []
    consent = card_policy(raw, schema=SCHEMA_V4)
    if not consent['products']:
        return []
    rows = (await db.execute(
        select(Product.id)
        .where(Product.tenant_id == context.tenant_id, Product.is_active.is_(True),
               Product.id.in_(consent['products']))
        .order_by(Product.id).limit(limit))).all()
    return [str(row[0]) for row in rows]


async def probe_route_categories(db, context, limit=24):
    """Currently published category identities for an approval dry-run probe read.

    Same contract as probe_route_items for the v2 category card-repeat: the
    no-route dry-run never expands the template because the category read
    returns nothing without a route item, so record-driven expansion failures
    first appeared at the visitor. Empty when no category is currently
    published or linkage is not v4-recorded: the visitor list is then empty
    by design and there is nothing to probe.
    """
    if current_tenant_id.get() != context.tenant_id or 'inventory' not in context.active_modules:
        raise SourceUnavailable('Website category source unavailable.')
    raw = await db.scalar(select(StoreSetting.value).where(
        StoreSetting.tenant_id == context.tenant_id, StoreSetting.key == SETTING_KEY))
    try:
        recorded = json.loads(raw).get('schema') if raw is not None else None
    except (TypeError, ValueError):
        raise SourceUnavailable('Invalid website card policy.') from None
    if recorded != SCHEMA_V4:
        return []
    # Lazy import: provider imports this module's display_consent lazily too,
    # so neither file holds a module-level cycle.
    from app.activities.general.modules.inventory.storefront import provider as _provider
    publication_raw = await db.scalar(select(StoreSetting.value).where(
        StoreSetting.tenant_id == context.tenant_id,
        StoreSetting.key == _provider.SETTING_KEY))
    categories = _provider.publication_ids(publication_raw)['categories']
    return [str(c) for c in sorted(categories, key=str)[:limit]]
