"""Experimental trusted provider runtime, not an auto-importer or public endpoint.

Only platform-registered providers execute. A module declaration never authorizes code,
queries, data access or activation. Callers supply an already authorized tenant context.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Awaitable, Callable
from uuid import UUID

from .storefront import storefront_binding_problems, storefront_contract_problems


class SourceUnavailable(ValueError):
    """No source metadata or value is disclosed for this context."""


class ProjectionInvalid(ValueError):
    """Trusted provider returned values beyond its reviewed projection."""


@dataclass(frozen=True)
class SourceContext:
    tenant_id: UUID
    language: str
    active_modules: frozenset[str]
    # 'preview' is the signed-in Studio preview. 'public' is the anonymous
    # visitor audience; the publish-approval dry run simulates exactly it.
    # Consent recorded under previews-only wording never authorizes public
    # reads: public consumers require the wording version that names public
    # pages (see inventory storefront cards.py).
    audience: str = 'preview'

    def __post_init__(self):
        if not isinstance(self.tenant_id, UUID) or self.language not in ('en', 'ar'):
            raise SourceUnavailable('An explicit tenant and supported language are required.')
        if not isinstance(self.active_modules, frozenset) or not all(isinstance(m, str) for m in self.active_modules):
            raise SourceUnavailable('Verified module state is required.')
        if self.audience not in ('preview', 'public'):
            raise SourceUnavailable('An explicit audience is required.')


@dataclass(frozen=True)
class Provider:
    module: str
    contract: dict
    read: Callable[[SourceContext, str], Awaitable[dict | None]]
    # Platform capability, never accepted from module JSON. Site is a platform core module.
    platform_core: bool = False


class ProviderRegistry:
    def __init__(self, providers: tuple[Provider, ...]):
        self._providers: dict[str, Provider] = {}
        for p in providers:
            if p.module in self._providers or storefront_contract_problems(p.contract, p.module):
                raise ValueError('Invalid or duplicate reviewed provider.')
            if not callable(p.read) or type(p.platform_core) is not bool:
                raise ValueError('Provider requires a trusted callable and platform classification.')
            self._providers[p.module] = Provider(p.module, deepcopy(p.contract), p.read, p.platform_core)

    def _provider(self, context: SourceContext, module: str) -> Provider:
        if not isinstance(context, SourceContext):
            raise SourceUnavailable('An explicit authorized context is required.')
        p = self._providers.get(module)
        if p is None or not (p.platform_core or module in context.active_modules):
            raise SourceUnavailable('Source unavailable.')
        return p

    def discover(self, context: SourceContext) -> list[dict]:
        if not isinstance(context, SourceContext):
            raise SourceUnavailable('An explicit authorized context is required.')
        return [deepcopy(p.contract) for p in self._providers.values()
                if p.platform_core or p.module in context.active_modules]

    def validate_binding(self, context: SourceContext, binding: dict, target: dict) -> None:
        if not isinstance(binding, dict) or not isinstance(binding.get('module'), str):
            raise SourceUnavailable('Invalid binding.')
        p = self._provider(context, binding['module'])
        if storefront_binding_problems(binding, p.contract, target):
            raise SourceUnavailable('Binding is not compatible with this target.')
        source = next(s for s in p.contract['sources'] if s['id'] == binding['source'])
        if source['cardinality'] != 'one' or target['type'] != 'text' or target['semantic'] != 'plain_text':
            raise SourceUnavailable('Runtime supports scalar plain text only.')

    async def resolve(self, context: SourceContext, binding: dict, target: dict) -> str | None:
        # Target must come from the platform block schema, never client metadata.
        self.validate_binding(context, binding, target)
        p = self._provider(context, binding['module'])
        source = next(s for s in p.contract['sources'] if s['id'] == binding['source'])
        row = await p.read(context, source['id'])
        if row is not None:
            if not isinstance(row, dict) or set(row) - {f['id'] for f in source['fields']}:
                raise ProjectionInvalid('Provider violated its reviewed projection.')
            for f in source['fields']:
                value = row.get(f['id'])
                if value is None:
                    if not f['nullable']:
                        raise ProjectionInvalid('Required projection value missing.')
                elif f['type'] != 'text' or not isinstance(value, str) or len(value) > 200:
                    raise ProjectionInvalid('Invalid scalar projection value.')
        value = None if row is None else row.get(binding['field'])
        if value is None or value == '':
            return None if binding['on_missing'] == 'hide' else ''
        return value  # Renderer escapes this as text, never interpreted as HTML.
