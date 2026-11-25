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




def _empty_results_node(plan: dict, query: str) -> dict:
    # Search UX: a zero-match query must say so on the page, not silently
    # vanish the section. Only used when a query was applied; query-less
    # pages keep the existing empty/prune behavior.
    identity = json.dumps([plan['module'], plan['source'], 'empty-results', query], separators=(',', ':'))
    nid = 'n_' + hashlib.sha256(identity.encode()).hexdigest()[:16]
    shown = html.escape(query)
    return {'id': nid, 'type': 'text', 'content': {
        'en': {'html': f'<p>No results for "{shown}".</p>'},
        'ar': {'html': f'<p>لا توجد نتائج عن "{shown}".</p>'}}}

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
    if query and not result:
        result=[_empty_results_node(plan,query)]
    index=parent['children'].index(template)
    parent['children'][index:index+1]=result
    # Includes duplicate generated IDs, global node/layout limits and per-device styles.
    if page_problems(static,('en','ar')) or len(json.dumps(static,allow_nan=False).encode())>200000:
        raise SourceUnavailable('Expanded page is not a valid bounded native tree.')
    return static


# One heading slot, up to three ordered text slots (text, text2, text3) bound
# to successive text children in visual order, and one image slot.
_CARD_SLOT_TYPES={'heading':('text',),'text':('text','money'),'text2':('text','money'),'text3':('text','money'),'image':('media',)}
_SLOT_NODE_KIND={'heading':'heading','text':'text','text2':'text','text3':'text','image':'image'}

def _slot_assignment(slots:dict,children:list)->list:
    """Bind successive same-kind template children to the ordered slots of that
    kind: first text child -> text, second -> text2, third -> text3."""
    queues={kind:sorted(k for k in slots if _SLOT_NODE_KIND[k]==kind) for kind in ('heading','text','image')}
    return [slots[queues[child['type']].pop(0)] for child in children]


def checked_card_template(tree:dict, plan:dict, slots:dict, runtime:CollectionRuntime, context:SourceContext):
    """v1 bounded card template: a column whose heading/text/image children are
    filled from one collection item each. All checks precede any provider read."""
    if not isinstance(plan,dict) or set(plan) not in ({'template_id','module','source','limit','on_missing'},{'template_id','module','source','category','limit','on_missing'}):
        raise SourceUnavailable('Exact card collection plan required.')
    if 'category' in plan and plan['category']!='route':
        raise SourceUnavailable('Exact card collection plan required.')
    if not isinstance(plan['template_id'],str) or not PAGE_NODE_ID.fullmatch(plan['template_id']):
        raise SourceUnavailable('Invalid card template identity.')
    for name in ('module','source'):
        if not isinstance(plan[name],str) or not KEY.fullmatch(plan[name]):
            raise SourceUnavailable('Invalid collection identifier.')
    if not isinstance(slots,dict) or 'heading' not in slots or not set(slots)<=set(_CARD_SLOT_TYPES):
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
    if sorted(kinds)!=sorted(_SLOT_NODE_KIND[k] for k in slots) or any('children' in child for child in children):
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
        assignment=_slot_assignment(slots,clone['children'])
        for child,field in zip(clone['children'],assignment):
            kind=child['type'];spec=contract['fields'][field]
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
    if query and not result:
        wrapper={'id':_derived_id(plan['module'],plan['source'],template['id'],'empty-results'),
                 'type':'column','children':[_empty_results_node(plan,query)]}
        result=[wrapper]
    index=parent['children'].index(template)
    if not result:
        # Every item was hidden: an empty columns row is not a valid native
        # node, so the row itself is dropped (empty sections stay valid).
        def _prune(node):
            if parent in node.get('children',[]):
                node['children'].remove(parent)
                return True
            return any(_prune(child) for child in node.get('children',[]))
        _prune(static)
    elif len(result)<=6:
        parent['children'][index:index+1]=result
    else:
        # A columns block holds 1..6 columns. More items than that are split
        # into sibling rows cloned from the template's row (settings carried,
        # fresh derived identities), never into an invalid over-full row. When
        # the row declares a track count, chunks honor it so split rows stay
        # uniform (4+4, not 6+2) and the row's own grid gap applies within
        # every chunk exactly as within one row.
        declared=(parent.get('settings') or {}).get('desktop',{}).get('columns')
        chunk=declared if type(declared) is int and 1<=declared<=6 else 6
        rows=[result[i:i+chunk] for i in range(0,len(result),chunk)]
        blocks=[]
        for row_index,chunk in enumerate(rows):
            block={key:deepcopy(value) for key,value in parent.items() if key!='children'}
            block['children']=chunk
            block['id']=_derived_id(plan['module'],plan['source'],parent['id'],'row%d'%row_index)
            blocks.append(block)
        def _replace(node):
            if parent in node.get('children',[]):
                at=node['children'].index(parent)
                node['children'][at:at+1]=blocks
                return True
            return any(_replace(child) for child in node.get('children',[]))
        if not _replace(static):
            raise SourceUnavailable('Card repeat template row is unreachable.')
    # Includes duplicate generated IDs, global node/layout limits and per-device styles.
    if page_problems(static,('en','ar')) or len(json.dumps(static,allow_nan=False).encode())>200000:
        raise SourceUnavailable('Expanded page is not a valid bounded native tree.')
    return static
