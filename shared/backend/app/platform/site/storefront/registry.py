"""Explicit trusted module registrations. Never imports a path from client metadata."""
from app.framework.storefront_runtime import ProviderRegistry
from app.framework.storefront_collections import CollectionRuntime
from app.platform.core.storefront.provider import core_provider
from app.activities.general.modules.inventory.storefront.provider import inventory_providers
from .provider import site_provider
from .collections import navigation_labels_provider

def scalar_registry(db):return ProviderRegistry((site_provider(db),core_provider(db)))
def collection_registry(db):return CollectionRuntime((navigation_labels_provider(db),*inventory_providers(db)))
