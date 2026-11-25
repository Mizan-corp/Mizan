"""Local-only native-tree projection. No persisted page extension or API registration.

One existing heading is the visual template. Expansion uses ordinary heading nodes,
not a parallel renderer or arbitrary expressions. Sources never supply structure.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
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


async def expand_heading_collection(tree:dict, plan:dict, runtime:CollectionRuntime, context:SourceContext)->dict:
    # All plan/native/source metadata checks precede the first provider read.
    static,(parent,template)=checked_template(tree,plan,runtime,context)
    items=await runtime.items(context,plan['module'],plan['source'],plan['limit'])
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
