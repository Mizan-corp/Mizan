"""Experimental S2 binding projection, not yet accepted by storage or wired to UI.

This is a render-time copy, never a second page format, persisted snapshot, or value cache.
Only heading.text has a trusted target in this first slice. All static content is kept.
"""
from __future__ import annotations
from copy import deepcopy
import json
from app.framework.manifest import PAGE_BINDINGS_ITEM_SCHEMA, page_binding_problems
from app.framework.storefront_runtime import ProviderRegistry, SourceContext, SourceUnavailable

TARGETS={'heading': {'text':{'type':'text','semantic':'plain_text','cardinality':'one','element':'heading'}}}
# Experimental v1 (individually bound elements): content fields a node type may
# bind to a consented record. Shape is checked by manifest page_binding_problems;
# consent and record scope are runtime checks in item_bindings.ScopedItems.
ITEM_TARGETS={'heading': frozenset({'text'}), 'text': frozenset({'html'}), 'image': frozenset({'src'})}


def separate_bindings(tree: dict, validate_static, items=None):
    """Check bounded binding envelope then validate the ordinary static native tree.

    validate_static is the platform page_problems callable, never client supplied.
    """
    try:
        if len(json.dumps(tree,allow_nan=False).encode()) > 200000:
            raise SourceUnavailable('Page exceeds binding runtime limit.')
        static=deepcopy(tree)
    except (TypeError,ValueError,RecursionError):
        raise SourceUnavailable('Page must be bounded finite JSON.') from None
    bindings=[];item_bindings=[]
    def visit(node,depth=0):
        if not isinstance(node,dict) or depth>12:
            raise SourceUnavailable('Malformed native page.')
        envelope=node.pop('bindings',None)
        if envelope is not None and page_binding_problems(envelope,node.get('type'),('en','ar')):
            raise SourceUnavailable('Invalid versioned binding declaration.')
        local={} if envelope is None else envelope['content']
        if not isinstance(local,dict) or set(local)-{'en','ar'}:
            raise SourceUnavailable('Unsupported binding language.')
        item_envelope=envelope is not None and envelope.get('schema')==PAGE_BINDINGS_ITEM_SCHEMA
        if item_envelope and len(local)!=1:
            raise SourceUnavailable('Item bindings address one language at a time.')
        for language,fields in local.items():
            if not isinstance(fields,dict) or not fields:
                raise SourceUnavailable('Malformed binding fields.')
            for field,binding in fields.items():
                if not isinstance(binding,dict):
                    raise SourceUnavailable('Unsupported binding target.')
                if item_envelope:
                    if field not in ITEM_TARGETS.get(node.get('type'),frozenset()):
                        raise SourceUnavailable('Unsupported item binding target.')
                    if len(item_bindings)>=100:
                        raise SourceUnavailable('Too many page bindings.')
                    item_bindings.append((node.get('id'),language,field,deepcopy(binding)))
                    continue
                if field not in TARGETS.get(node.get('type'),{}):
                    raise SourceUnavailable('Unsupported binding target.')
                if len(bindings)>=100:
                    raise SourceUnavailable('Too many page bindings.')
                bindings.append((node.get('id'),language,field,deepcopy(binding)))
        children=node.get('children',[])
        if not isinstance(children,list):raise SourceUnavailable('Malformed children.')
        for child in children:visit(child,depth+1)
    visit(static)
    if validate_static(static):raise SourceUnavailable('Native page is invalid.')
    if item_bindings and items is None:
        raise SourceUnavailable('Element binding source is unavailable.')
    return static,bindings,item_bindings


def validate_tree_bindings(tree: dict, registry: ProviderRegistry, context: SourceContext, validate_static, items=None) -> None:
    static,bindings,item_bindings=separate_bindings(tree,validate_static,items)
    # Validate every language and target before any source is called. This prevents
    # an invalid later binding from causing a partial provider-read sequence.
    for node_id,language,field,binding in bindings:
        registry.validate_binding(context,binding,TARGETS['heading'][field])
    for node_id,language,field,binding in item_bindings:
        items.validate(context,binding,field)


async def resolve_tree(tree: dict, registry: ProviderRegistry, context: SourceContext, validate_static, items=None) -> dict:
    static,bindings,item_bindings=separate_bindings(tree,validate_static,items)
    for node_id,language,field,binding in bindings:
        registry.validate_binding(context,binding,TARGETS['heading'][field])
    for node_id,language,field,binding in item_bindings:
        items.validate(context,binding,field)
    nodes={}
    def index(node):
        nodes[node['id']]=node
        for child in node.get('children',[]):index(child)
    index(static);hide=set()
    for node_id,language,field,binding in bindings:
        if language != context.language:continue
        node=nodes[node_id]
        value=await registry.resolve(context,binding,TARGETS[node['type']][field])
        if value is None:hide.add(node_id)
        else:node.setdefault('content',{}).setdefault(language,{})[field]=value
    for node_id,language,field,binding in item_bindings:
        if language != context.language:continue
        node=nodes[node_id]
        value=await items.resolve(context,binding,field)
        if value is None:hide.add(node_id)
        else:node.setdefault('content',{}).setdefault(language,{})[field]=value
    def prune(node):
        if 'children' in node:
            node['children']=[child for child in node['children'] if child['id'] not in hide]
            for child in node['children']:prune(child)
    prune(static)
    return static
