"""Local-only native-tree projection. No persisted page extension or API registration.

One existing heading or bounded card column is the visual template. Expansion
uses ordinary native nodes, not a parallel renderer or arbitrary expressions.
Sources never supply structure.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import html
import json
from app.framework.manifest import page_problems, PAGE_MAX_NODES, PAGE_NODE_ID
from app.framework.storefront_collections import CollectionRuntime, KEY
from app.framework.storefront_runtime import SourceContext, SourceUnavailable


def checked_template(tree: dict, plan: dict, runtime: CollectionRuntime, context: SourceContext):
    if not isinstance(plan,dict) or set(plan)!={'template_id','module','source','field','limit','on_missing'}:
        raise SourceUnavailable('Exact heading collection plan required.')
    if not isinstance(plan['template_id'],str) or not PAGE_NODE_ID.fullmatch(plan['template_id']):
        raise SourceUnavailable('Invalid heading template identity.')
    for name in ('module','source','field'):
        if not isinstance(plan[name],str) or not KEY.fullmatch(plan[name]):
            raise SourceUnavailable('Invalid collection identifier.')
    c=runtime.declaration(context,plan['module'],plan['source'])
    if (plan['field'] not in c['fields'] or plan['on_missing'] not in ('hide','empty')
            or type(plan['limit']) is not int or not 1<=plan['limit']<=c['max_items']):
        raise SourceUnavailable('Incompatible bounded heading collection plan.')
    if c['fields'][plan['field']].get('type')!='text':
        # Heading expansion renders plain text only; typed money/media fields
        # are read by card/multi-field paths, never interpolated as text.
        raise SourceUnavailable('Heading collection field must be plain text.')
    try:
        if len(json.dumps(tree,allow_nan=False).encode())>200000:
            raise SourceUnavailable('Page exceeds collection runtime limit.')
        static=deepcopy(tree)
    except (TypeError,ValueError,RecursionError):
        raise SourceUnavailable('Page must be bounded finite JSON.') from None
    if page_problems(static,('en','ar')):
        raise SourceUnavailable('Native template page is invalid.')
    count=0;found=None
    def visit(node,parent=None):
        nonlocal count,found
        count+=1
        if 'bindings' in node:
            raise SourceUnavailable('Mixed scalar and collection projection is not supported yet.')
        if node['id']==plan['template_id']:
            if node['type']!='heading' or parent is None or parent['type']!='column':
                raise SourceUnavailable('First collection template must be a heading in a column.')
            found=(parent,node)
        for child in node.get('children',[]):visit(child,node)
    visit(static)
    if found is None or count+plan['limit']-1>PAGE_MAX_NODES:
        raise SourceUnavailable('Missing template or expanded page exceeds native node bound.')
    return static,found


def _filter_items(items, field, plan, runtime, context, query):
    # Public search: case-insensitive substring on the item's display text.
    # Filtering only ever narrows what consent already exposes.
    if not query:
        return items
    needle = query.casefold()
    return [it for it in items
            if needle in (runtime.text(context, it, module=plan['module'], source=plan['source'],
                                       field=field, on_missing='hide') or '').casefold()]


async def expand_heading_collection(tree:dict, plan:dict, runtime:CollectionRuntime, context:SourceContext, query:str|None=None)->dict:
    # All plan/native/source metadata checks precede the first provider read.
    static,(parent,template)=checked_template(tree,plan,runtime,context)
    items=await runtime.items(context,plan['module'],plan['source'],plan['limit'])
    items=_filter_items(items,plan['field'],plan,runtime,context,query)
    result=[]
    for item in items:
        text=runtime.text(context,item,module=plan['module'],source=plan['source'],field=plan['field'],on_missing=plan['on_missing'])
        if text is None:continue
        node=deepcopy(template)
        identity=json.dumps([plan['module'],plan['source'],template['id'],item.key],separators=(',',':'))
        node['id']='n_'+hashlib.sha256(identity.encode()).hexdigest()[:16]
        node.setdefault('content',{}).setdefault(context.language,{})['text']=text
        result.append(node)
    index=parent['children'].index(template)
    parent['children'][index:index+1]=result
    # Includes duplicate generated IDs, global node/layout limits and per-device styles.
    if page_problems(static,('en','ar')) or len(json.dumps(static,allow_nan=False).encode())>200000:
        raise SourceUnavailable('Expanded page is not a valid bounded native tree.')
    return static


_CARD_SLOT_TYPES={'heading':('text',),'text':('text','money'),'image':('media',)}


def checked_card_template(tree:dict, plan:dict, slots:dict, runtime:CollectionRuntime, context:SourceContext):
    """v1 bounded card template: a column whose heading/text/image children are
    filled from one collection item each. All checks precede any provider read."""
    if not isinstance(plan,dict) or set(plan)!={'template_id','module','source','limit','on_missing'}:
        raise SourceUnavailable('Exact card collection plan required.')
    if not isinstance(plan['template_id'],str) or not PAGE_NODE_ID.fullmatch(plan['template_id']):
        raise SourceUnavailable('Invalid card template identity.')
    for name in ('module','source'):
        if not isinstance(plan[name],str) or not KEY.fullmatch(plan[name]):
            raise SourceUnavailable('Invalid collection identifier.')
    if not isinstance(slots,dict) or 'heading' not in slots or not set(slots)<={'heading','text','image'}:
        raise SourceUnavailable('Card slots need a heading and only heading/text/image keys.')
    for field in slots.values():
        if not isinstance(field,str) or not KEY.fullmatch(field):
            raise SourceUnavailable('Invalid collection identifier.')
    c=runtime.declaration(context,plan['module'],plan['source'])
    if plan['on_missing'] not in ('hide','empty') or type(plan['limit']) is not int or not 1<=plan['limit']<=c['max_items']:
        raise SourceUnavailable('Incompatible bounded card collection plan.')
    for kind,field in slots.items():
        spec=c['fields'].get(field)
        if spec is None or spec.get('type') not in _CARD_SLOT_TYPES[kind]:
            raise SourceUnavailable('Card slot field has an incompatible collection type.')
        if spec.get('type')=='text' and spec.get('semantic')!='plain_text':
            raise SourceUnavailable('Card text slots render plain text only.')
    try:
        if len(json.dumps(tree,allow_nan=False).encode())>200000:
            raise SourceUnavailable('Page exceeds collection runtime limit.')
        static=deepcopy(tree)
    except (TypeError,ValueError,RecursionError):
        raise SourceUnavailable('Page must be bounded finite JSON.') from None
    if page_problems(static,('en','ar')):
        raise SourceUnavailable('Native template page is invalid.')
    count=0;found=None
    def visit(node,parent=None):
        nonlocal count,found
        count+=1
        if 'bindings' in node:
            raise SourceUnavailable('Mixed scalar and collection projection is not supported yet.')
        if node['id']==plan['template_id']:
            if node['type']!='column' or parent is None or parent['type']!='columns':
                raise SourceUnavailable('Card template must be a column in a columns block.')
            found=(parent,node)
        for child in node.get('children',[]):visit(child,node)
    visit(static)
    if found is None:
        raise SourceUnavailable('Missing template or expanded page exceeds native node bound.')
    template=found[1]
    children=template.get('children',[])
    kinds=[child['type'] for child in children]
    if sorted(kinds)!=sorted(slots) or any('children' in child for child in children):
        raise SourceUnavailable('Card template children must match the declared slots exactly.')
    subtree=1+len(children)
    if count+(plan['limit']-1)*subtree>PAGE_MAX_NODES:
        raise SourceUnavailable('Missing template or expanded page exceeds native node bound.')
    return static,found


def _derived_id(module:str,source:str,node_id:str,item_key:str)->str:
    identity=json.dumps([module,source,node_id,item_key],separators=(',',':'))
    return 'n_'+hashlib.sha256(identity.encode()).hexdigest()[:16]


async def expand_card_collection(tree:dict, plan:dict, slots:dict, runtime:CollectionRuntime, context:SourceContext, query:str|None=None)->dict:
    # All plan/native/source metadata checks precede the first provider read.
    static,(parent,template)=checked_card_template(tree,plan,slots,runtime,context)
    contract=runtime.declaration(context,plan['module'],plan['source'])
    items=await runtime.items(context,plan['module'],plan['source'],plan['limit'])
    items=_filter_items(items,slots['heading'],plan,runtime,context,query)
    result=[]
    for item in items:
        name=runtime.text(context,item,module=plan['module'],source=plan['source'],field=slots['heading'],on_missing=plan['on_missing'])
        if name is None:
            continue  # on_missing hide drops the whole card when its heading is absent
        clone=deepcopy(template)
        kept=[]
        for child in clone['children']:
            kind=child['type'];field=slots[kind];spec=contract['fields'][field]
            if kind=='heading':
                child.setdefault('content',{}).setdefault(context.language,{})['text']=name
            elif spec['type']=='media':
                value=runtime.typed_value(context,item,module=plan['module'],source=plan['source'],field=field)
                if value is None:
                    continue  # no renderable empty image; the card keeps its other slots
                child['content'][context.language]={'src':value['src'],'alt':value['alt']}
            elif spec['type']=='money':
                value=runtime.typed_value(context,item,module=plan['module'],source=plan['source'],field=field)
                if value is None and plan['on_missing']=='hide':
                    continue
                display='' if value is None else f"{value['amount']} {value['currency']}"
                child.setdefault('content',{}).setdefault(context.language,{})['html']=f'<p>{html.escape(display)}</p>'
            else:
                value=runtime.text(context,item,module=plan['module'],source=plan['source'],field=field,on_missing=plan['on_missing'])
                if value is None:
                    continue
                child.setdefault('content',{}).setdefault(context.language,{})['html']=f'<p>{html.escape(value)}</p>'
            kept.append(child)
        clone['children']=kept
        for node in [clone,*kept]:
            node['id']=_derived_id(plan['module'],plan['source'],node['id'],item.key)
        result.append(clone)
    index=parent['children'].index(template)
    parent['children'][index:index+1]=result
    if not parent['children']:
        # Every item was hidden: an empty columns row is not a valid native
        # node, so the row itself is dropped (empty sections stay valid).
        def _prune(node):
            if parent in node.get('children',[]):
                node['children'].remove(parent)
                return True
            return any(_prune(child) for child in node.get('children',[]))
        _prune(static)
    # Includes duplicate generated IDs, global node/layout limits and per-device styles.
    if page_problems(static,('en','ar')) or len(json.dumps(static,allow_nan=False).encode())>200000:
        raise SourceUnavailable('Expanded page is not a valid bounded native tree.')
    return static
