"""Reviewed native product-card expansion, editable native card template expansion.

The column and its children are ordinary editable native blocks. Data can replace
only mapped name, typed display price and product-owned media in the render copy.
"""
from copy import deepcopy
import hashlib
import html
import json
from app.framework.manifest import page_problems, PAGE_MAX_NODES, PAGE_NODE_ID
from app.framework.storefront_runtime import SourceUnavailable, ProjectionInvalid
from app.framework.storefront_values import check_money, money_text, check_media


def checked_card_template(tree, plan):
    if not isinstance(plan, dict) or set(plan) not in ({'template_id', 'module', 'source', 'limit', 'targets'}, {'template_id', 'module', 'source', 'limit', 'targets', 'products'}):
        raise SourceUnavailable('Exact reviewed card plan required.')
    if plan['module'] != 'inventory' or plan['source'] != 'website_cards' or type(plan['limit']) is not int or not 1 <= plan['limit'] <= 6:
        raise SourceUnavailable('Unsupported card source or bound.')
    if 'products' in plan:
        from uuid import UUID
        products=plan['products']
        try:
            if not isinstance(products,list) or len(products)>6 or any(not isinstance(x,str) or str(UUID(x))!=x for x in products) or len(set(products))!=len(products):
                raise SourceUnavailable('Exact bounded section products required.')
        except (TypeError,ValueError):
            raise SourceUnavailable('Invalid section products.') from None
    targets = plan['targets']
    if not isinstance(targets, dict) or set(targets) != {'name', 'price', 'image'}:
        raise SourceUnavailable('Exact reviewed card targets required.')
    if any(not isinstance(v, str) or not PAGE_NODE_ID.fullmatch(v) for v in [plan['template_id'], *targets.values()]):
        raise SourceUnavailable('Invalid native card target identity.')
    if len(set(targets.values())) != 3:
        raise SourceUnavailable('Card fields require distinct targets.')
    try:
        if len(json.dumps(tree, allow_nan=False).encode()) > 200000 or page_problems(tree, ('en', 'ar')):
            raise SourceUnavailable('Invalid bounded native card page.')
        static = deepcopy(tree)
    except (TypeError, ValueError, RecursionError):
        raise SourceUnavailable('Finite bounded card page required.') from None
    nodes = {}; parents = {}

    def visit(node, parent=None):
        if 'bindings' in node or 'repeat' in node or 'card' in node:
            raise SourceUnavailable('Card projection cannot contain unresolved bindings.')
        nodes[node['id']] = node
        parents[node['id']] = parent
        for child in node.get('children', []):
            visit(child, node)

    visit(static)
    template = nodes.get(plan['template_id'])
    parent = parents.get(plan['template_id'])
    if template is None or template['type'] != 'column' or parent is None or parent['type'] != 'columns' or len(parent['children']) != 1:
        raise SourceUnavailable('One column in its own native row is required as card template.')
    direct = {node['id']: node for node in template.get('children', [])}
    for field, kind in [('name', 'heading'), ('price', 'text'), ('image', 'image')]:
        if targets[field] not in direct or direct[targets[field]]['type'] != kind:
            raise SourceUnavailable('Card targets must be direct native heading, text and image children.')
    def count(node):
        return 1 + sum(count(child) for child in node.get('children', []))
    subtree_count = count(template)
    if len(nodes) + (plan['limit'] - 1) * subtree_count > PAGE_MAX_NODES:
        raise SourceUnavailable('Expanded cards exceed native node bound.')
    return static, parent, template


def project_cards(tree, plan, rows, context):
    static, parent, template = checked_card_template(tree, plan)
    if not isinstance(rows, list) or len(rows) > plan['limit']:
        raise ProjectionInvalid('Card result exceeds reviewed bound.')
    seen = set(); result = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'item_key', 'name', 'price', 'image'}:
            raise ProjectionInvalid('Exact card fields required.')
        key = row['item_key']
        if not isinstance(key, str) or not 1 <= len(key) <= 80 or key in seen:
            raise ProjectionInvalid('Unique stable product identities required.')
        seen.add(key)
        if not isinstance(row['name'], str) or not row['name'].strip() or len(row['name']) > 200:
            raise ProjectionInvalid('Invalid product name.')
        if row['price'] is not None:
            check_money(row['price'])
        if row['image'] is not None:
            check_media(row['image'], context.tenant_id)
        clone = deepcopy(template)
        target_ids = plan['targets']; hidden = set()

        def fill(node):
            original_id = node['id']
            identity = json.dumps(['inventory', 'website_cards', template['id'], key, original_id], separators=(',', ':'))
            node['id'] = 'n_' + hashlib.sha256(identity.encode()).hexdigest()[:16]
            content = node.setdefault('content', {}).setdefault(context.language, {})
            if original_id == target_ids['name']:
                content['text'] = row['name']
            elif original_id == target_ids['price']:
                if row['price'] is None:
                    hidden.add(node['id'])
                else:
                    content['html'] = '<p>' + html.escape(money_text(row['price'])) + '</p>'
            elif original_id == target_ids['image']:
                if row['image'] is None:
                    hidden.add(node['id'])
                else:
                    content['src'] = row['image']['src']; content['alt'] = row['image']['alt']
            for child in node.get('children', []):
                fill(child)
            if 'children' in node:
                node['children'] = [child for child in node['children'] if child['id'] not in hidden]

        fill(clone); result.append(clone)
    # Native columns cannot be empty: hide the entire rendered row on zero records.
    if not result:
        def remove(node):
            if 'children' in node:
                node['children'] = [child for child in node['children'] if child['id'] != parent['id']]
                for child in node['children']:
                    remove(child)
        remove(static)
    else:
        parent['children'] = result
        # The row keeps the author's designed column count as a cap: more cards wrap to
        # further rows instead of squeezing onto one, fewer cards take only their own tracks.
        designed = (parent.get('settings') or {}).get('desktop', {}).get('columns')
        count = len(result)
        if isinstance(designed, int) and not isinstance(designed, bool) and 1 <= designed <= 6:
            count = min(count, designed)
        parent.setdefault('settings', {}).setdefault('desktop', {})['columns'] = count
    if page_problems(static, ('en', 'ar')) or len(json.dumps(static, allow_nan=False).encode()) > 200000:
        raise ProjectionInvalid('Projected cards violate bounded native page contract.')
    return static
