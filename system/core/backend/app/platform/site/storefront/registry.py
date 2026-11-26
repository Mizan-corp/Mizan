"""Explicit trusted module registrations. Never imports a path from client metadata."""
from app.framework.storefront_runtime import ProviderRegistry
from app.framework.storefront_collections import CollectionRuntime
from app.platform.core.storefront.provider import core_provider
from app.activities.general.modules.inventory.storefront.provider import inventory_providers
from app.activities.general.modules.helpdesk.storefront.provider import helpdesk_providers
from .provider import site_provider
from .collections import navigation_labels_provider

def scalar_registry(db):return ProviderRegistry((site_provider(db),core_provider(db)))
def collection_registry(db):return CollectionRuntime((navigation_labels_provider(db),*inventory_providers(db),*helpdesk_providers(db)))
def item_resolver(db):
    from .item_bindings import ScopedItems
    return ScopedItems(db)

def route_probe(db):
    """Approval dry-run probe sampler for route-parameterized sources.

    (context, kind, module, source) -> real record identities the approval
    re-resolves the published tree against. kind 'p' is the URL item segment
    (v2 route item bindings), 'c' the URL category segment (v2 category
    card-repeat). An empty list means nothing is currently exposable: the
    visitor render is then empty/hidden by design and the probe is skipped.
    Explicit trusted registrations, never client metadata."""
    from app.activities.general.modules.inventory.storefront import cards as inventory_cards
    async def sample(context, kind, module, source):
        if kind == 'p' and (module, source) == ('inventory', 'products'):
            return await inventory_cards.probe_route_items(db, context)
        if kind == 'c' and (module, source) == ('inventory', 'category_products'):
            return await inventory_cards.probe_route_categories(db, context)
        return []
    return sample

def route_availability(db):
    """Visitor-notice gate for dynamic template routes (/site/.../{p|c}/<id>).

    (context, kind, route_item) -> bool: may the URL-selected record drive the
    template render? Goes through the same consent-checked readers as the
    render itself, so the answer can never diverge from what the page would
    show. False is one answer for nonexistent, unconsented, revoked and
    unpublished records alike; the router turns it into a single generic
    visitor notice. Explicit trusted registrations, never client metadata."""
    from app.activities.general.modules.inventory.storefront import cards as inventory_cards
    async def check(context, kind, route_item):
        if kind == 'p':
            return await inventory_cards.read_route_item(db, context, route_item, ('name',)) is not None
        if kind == 'c':
            return await inventory_cards.route_category_available(db, context, route_item)
        return False
    return check
