"""Experimental bounded collection/item scope. No DB, discovery, page format or effects.

Not registered in the hosted scalar runtime. Callables and targets are platform-owned.
Collection items have explicit stable keys; no implicit first-item scalar conversion.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Awaitable, Callable, Mapping
from types import MappingProxyType
from .storefront_runtime import SourceContext, SourceUnavailable, ProjectionInvalid

SCHEMA='mizan.collection.experimental.v0'
KEY=re.compile(r'^[a-z][a-z0-9_]{0,47}$')
ITEM_KEY=re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$')


# Typed field kinds beyond plain text. Their bounds come from the reviewed
# value validators (check_money/check_media), not from string lengths, so the
# spec carries no max_length. Consent for any typed value is read at provider
# read time; the declaration alone never supplies a value.
TYPED_FIELD_SEMANTICS = {'money': 'display_money', 'media': 'display_media'}


def collection_problems(value) -> list[str]:
    errors=[]
    if not isinstance(value,dict) or set(value)!={'schema','module','source','key','fields','max_items'}:
        return ['collection: exact reviewed declaration required']
    if value.get('schema')!=SCHEMA:errors.append('collection: unsupported schema')
    for k in ['module','source','key']:
        if not isinstance(value.get(k),str) or not KEY.fullmatch(value[k]):errors.append('collection: invalid identifier')
    if type(value.get('max_items')) is not int or not 1<=value['max_items']<=24:
        errors.append('collection: max_items must be1to24')
    fields=value.get('fields')
    if not isinstance(fields,dict) or not 1<=len(fields)<=12:return errors+['collection:1to12explicit fields required']
    for name,spec in fields.items():
        if not isinstance(name,str) or not KEY.fullmatch(name) or not isinstance(spec,dict):
            errors.append('field: exact bounded public scalar declaration required');continue
        if spec.get('type') in TYPED_FIELD_SEMANTICS:
            if set(spec)!={'type','semantic','nullable'} or spec.get('semantic')!=TYPED_FIELD_SEMANTICS[spec['type']] or type(spec.get('nullable')) is not bool:
                errors.append('field: typed fields use the exact bounded declaration');continue
        else:
            if set(spec)!={'type','semantic','nullable','max_length'}:
                errors.append('field: exact bounded public scalar declaration required');continue
            if spec.get('type')!='text' or spec.get('semantic')!='plain_text' or type(spec.get('nullable')) is not bool:
                errors.append('field: first collection slice supports only plain text')
            if type(spec.get('max_length')) is not int or not 1<=spec['max_length']<=200:
                errors.append('field: length must be1to200')
    if value.get('key') in fields:errors.append('collection: identity key must not be a display field')
    return errors


@dataclass(frozen=True)
class CollectionProvider:
    contract: dict
    read: Callable[[SourceContext,int],Awaitable[list[dict]]]
    platform_core: bool = False


@dataclass(frozen=True)
class ItemContext:
    """Created only from a checked collection result, not an untrusted client index."""
    module: str
    source: str
    key: str
    values: Mapping[str, str | None]
    tenant_id: object
    language: str
    _issuer: object


class CollectionRuntime:
    def __init__(self,providers:tuple[CollectionProvider,...]):
        self._providers={}
        self._issuer=object()
        for provider in providers:
            c=provider.contract
            if collection_problems(c) or not callable(provider.read) or type(provider.platform_core) is not bool:
                raise ValueError('Invalid trusted collection provider.')
            key=(c['module'],c['source'])
            if key in self._providers:raise ValueError('Duplicate collection source.')
            self._providers[key]=CollectionProvider(deepcopy(c),provider.read,provider.platform_core)

    def discover(self,context:SourceContext) -> list[dict]:
        if not isinstance(context,SourceContext):raise SourceUnavailable('Explicit source context required.')
        return [deepcopy(p.contract) for (module,source),p in self._providers.items() if p.platform_core or module in context.active_modules]

    def declaration(self,context:SourceContext,module:str,source:str) -> dict:
        if not isinstance(context,SourceContext) or not isinstance(module,str) or not isinstance(source,str):
            raise SourceUnavailable('Explicit source context required.')
        p=self._providers.get((module,source))
        if p is None or not(p.platform_core or module in context.active_modules):
            raise SourceUnavailable('Collection unavailable.')
        return deepcopy(p.contract)

    async def items(self,context:SourceContext,module:str,source:str,limit:int) -> tuple[ItemContext,...]:
        c=self.declaration(context,module,source)
        p=self._providers[(module,source)]
        if type(limit) is not int or not 1<=limit<=c['max_items']:
            raise SourceUnavailable('Collection limit exceeds reviewed bound.')
        rows=await p.read(context,limit)
        if not isinstance(rows,list) or len(rows)>limit:raise ProjectionInvalid('Collection provider exceeded item bound.')
        seen=set();result=[]
        for row in rows:
            if not isinstance(row,dict) or set(row)!={c['key'],*c['fields']}:
                raise ProjectionInvalid('Collection projection keys differ from reviewed fields.')
            key=row[c['key']]
            if not isinstance(key,str) or not ITEM_KEY.fullmatch(key) or key in seen:
                raise ProjectionInvalid('Collection requires unique stable item identities.')
            seen.add(key)
            for field,spec in c['fields'].items():
                v=row[field]
                if v is None:
                    if not spec['nullable']:raise ProjectionInvalid('Required item field missing.')
                elif spec['type']=='money':
                    from .storefront_values import check_money
                    check_money(v)
                elif spec['type']=='media':
                    from .storefront_values import check_media
                    check_media(v, context.tenant_id)
                elif not isinstance(v,str) or len(v)>spec['max_length']:
                    raise ProjectionInvalid('Collection field has wrong type or exceeds bound.')
            result.append(ItemContext(module,source,key,MappingProxyType({k:deepcopy(row[k]) for k in c['fields']}),context.tenant_id,context.language,self._issuer))
        return tuple(result)

    def text(self,context:SourceContext,item:ItemContext,*,module:str,source:str,field:str,on_missing:str)->str|None:
        # No parent/global/other collection lookup and no client supplied row indexes.
        if not isinstance(context,SourceContext) or not isinstance(item,ItemContext) or item._issuer is not self._issuer or item.tenant_id!=context.tenant_id or item.language!=context.language or (item.module,item.source)!=(module,source):
            raise SourceUnavailable('Item scope mismatch.')
        p=self._providers.get((module,source))
        if p is None or not(p.platform_core or module in context.active_modules) or field not in p.contract['fields'] or on_missing not in ('hide','empty'):
            raise SourceUnavailable('Incompatible item field.')
        value=item.values.get(field)
        spec=p.contract['fields'][field]
        if value is not None and (not isinstance(value,str) or len(value)>spec['max_length']):
            raise ProjectionInvalid('Item value no longer matches projection.')
        if value is None or value=='':return None if on_missing=='hide' else ''
        return value

    def typed_value(self,context:SourceContext,item:ItemContext,*,module:str,source:str,field:str):
        # Same scope discipline as text(); returns the revalidated typed value
        # (money/media dict) or None for a nullable empty slot.
        if not isinstance(context,SourceContext) or not isinstance(item,ItemContext) or item._issuer is not self._issuer or item.tenant_id!=context.tenant_id or item.language!=context.language or (item.module,item.source)!=(module,source):
            raise SourceUnavailable('Item scope mismatch.')
        p=self._providers.get((module,source))
        if p is None or not(p.platform_core or module in context.active_modules) or field not in p.contract['fields']:
            raise SourceUnavailable('Incompatible item field.')
        spec=p.contract['fields'][field]
        if spec['type']=='text':
            raise SourceUnavailable('Text fields use text projection.')
        value=item.values.get(field)
        if value is None:
            if not spec['nullable']:raise ProjectionInvalid('Required item field missing.')
            return None
        if spec['type']=='money':
            from .storefront_values import check_money
            return check_money(value)
        from .storefront_values import check_media
        return check_media(value,context.tenant_id)
