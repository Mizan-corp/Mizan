"""Experimental S2.1 scoped item bindings: v1 envelopes resolved against consented records.

An individually bound element (heading.text, text.html, image.src) is filled from a
single named record only when the workspace granted that field in the current
consent schema. Pre-read validation performs every check that needs no database
access; the record read itself goes through the inventory consent gate
(read_scoped_item), so a revoked or unconsented product resolves to None and the
element hides, matching the user-approved revocation semantics.
"""
from __future__ import annotations

import html as _html

from app.framework.storefront_runtime import SourceContext, SourceUnavailable

_MODULE = 'inventory'
_SOURCE = 'products'
# Which content field each provider field may fill.
_FIELD_TARGETS = {'name': frozenset({'text', 'html'}), 'price': frozenset({'html'}), 'image': frozenset({'src'})}


class ScopedItems:
    """Validate and resolve experimental v1 item bindings for one request."""

    def __init__(self, db):
        self._db = db

    def validate(self, context: SourceContext, binding: dict, field: str) -> None:
        """Pre-read compatibility check: no database access, no provider call."""
        if not isinstance(binding, dict) or binding.get('module') != _MODULE or binding.get('source') != _SOURCE:
            raise SourceUnavailable('Unsupported item binding source.')
        if binding.get('field') not in _FIELD_TARGETS or field not in _FIELD_TARGETS[binding['field']]:
            raise SourceUnavailable('Incompatible item binding target.')
        if _MODULE not in context.active_modules:
            raise SourceUnavailable('Item binding module is inactive.')

    async def resolve(self, context: SourceContext, binding: dict, field: str):
        """Consent-checked read of one record; None when unconsented, revoked or inactive."""
        import importlib

        cards = importlib.import_module('app.activities.general.modules.inventory.storefront.cards')
        item = await cards.read_scoped_item(self._db, context, binding['item_key'], (binding['field'],))
        if item is None:
            return None
        value = item.get(binding['field'])
        if value is None:
            return None
        if binding['field'] == 'image':
            return value['src']
        if binding['field'] == 'price':
            text = f"{value['amount']} {value['currency']}"
        elif isinstance(value, str):
            text = value
        else:
            raise SourceUnavailable('Item binding value is unavailable.')
        if field == 'html':
            return '<p>%s</p>' % _html.escape(text)
        return text
