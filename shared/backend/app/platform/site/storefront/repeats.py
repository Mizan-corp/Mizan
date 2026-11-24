"""Experimental persisted heading repeat adapter. Internal authenticated preview only."""
from copy import deepcopy
import json
from app.framework.manifest import page_problems, page_repeat_problems
from app.framework.storefront_runtime import SourceContext, SourceUnavailable
from app.framework.storefront_collections import CollectionRuntime
from .collection_projection import checked_template, expand_heading_collection


def separate_repeat(tree: dict):
    try:
        if len(json.dumps(tree,allow_nan=False).encode())>200000:
            raise SourceUnavailable('Repeat page exceeds byte limit.')
        static=deepcopy(tree)
    except (ValueError,TypeError,RecursionError):
        raise SourceUnavailable('Repeat page must be bounded finite JSON.') from None
    if page_problems(static,('en','ar')):
        raise SourceUnavailable('Invalid native repeat page.')
    declarations=[];has_scalar=False
    def visit(node):
        nonlocal has_scalar
        if 'bindings' in node:has_scalar=True
        repeat=node.pop('repeat',None)
        if repeat is not None:
            if page_repeat_problems(repeat,node['type'],('en','ar')):
                raise SourceUnavailable('Invalid repeat declaration.')
            declarations.append((node['id'],repeat['content']))
        for child in node.get('children',[]):visit(child)
    visit(static)
    if len(declarations)!=1 or has_scalar:
        raise SourceUnavailable('First repeat slice requires one template and no scalar bindings.')
    return static,declarations[0]


def validate_repeat(tree:dict,runtime:CollectionRuntime,context:SourceContext):
    static,(node_id,content)=separate_repeat(tree)
    # Validate every language before any collection read, including inactive languages.
    for language,plan in content.items():
        checked_template(static,{'template_id':node_id,**plan},runtime,
                         SourceContext(context.tenant_id,language,context.active_modules))
    return static,node_id,content


async def resolve_repeat(tree:dict,runtime:CollectionRuntime,context:SourceContext)->dict:
    static,node_id,content=validate_repeat(tree,runtime,context)
    plan=content.get(context.language)
    if plan is None:return static
    return await expand_heading_collection(static,{'template_id':node_id,**plan},runtime,context)


def has_repeat(tree:dict)->bool:
    return 'repeat' in tree or any(has_repeat(c) for c in tree.get('children',[]))
