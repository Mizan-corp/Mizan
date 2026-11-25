"""Bounded independent native card sections plus scalar headings, preview only."""
from copy import deepcopy
import json
from app.framework.manifest import page_problems, page_card_problems
from app.framework.storefront_runtime import SourceContext, SourceUnavailable
from .card_projection import checked_card_template, project_cards
from .bindings import validate_tree_bindings, resolve_tree
from .registry import scalar_registry
from app.activities.general.modules.inventory.storefront.cards import read_cards


def len_nodes(tree):
    return 1+sum(len_nodes(child) for child in tree.get('children',[]))

def has_card(tree):
    return 'card' in tree or any(has_card(child) for child in tree.get('children', []))


def card_plan(tree, registry, context):
    try:
        if len(json.dumps(tree, allow_nan=False).encode()) > 200000 or page_problems(tree, ('en', 'ar')):
            raise SourceUnavailable('Invalid bounded native card page.')
        static = deepcopy(tree)
    except (TypeError, ValueError, RecursionError):
        raise SourceUnavailable('Finite card page required.') from None
    declarations = []; scalars = {}

    def visit(node, inside=False):
        if 'repeat' in node:
            raise SourceUnavailable('Card and heading repeats cannot be mixed yet.')
        card = node.pop('card', None)
        if card is not None:
            if inside or page_card_problems(card, node['type'], ('en', 'ar')):
                raise SourceUnavailable('Invalid native card declaration.')
            declarations.append((node['id'], card['content']))
            inside = True
        envelope = node.pop('bindings', None)
        if envelope is not None:
            if inside:
                raise SourceUnavailable('Scalar sources cannot be embedded in repeated item scope.')
            scalars[node['id']] = envelope
        for child in node.get('children', []):
            visit(child, inside)

    visit(static)
    if not 1 <= len(declarations) <= 4 or 'inventory' not in context.active_modules:
        raise SourceUnavailable('One to four active inventory card sections required.')
    totals={language:len_nodes(static) for language in ('en','ar')}
    counts={language:0 for language in ('en','ar')}
    for node_id,content in declarations:
        for language,plan in content.items():
            _,_,template=checked_card_template(static, {'template_id':node_id,**plan})
            totals[language]+=(plan['limit']-1)*len_nodes(template)
            counts[language]+=plan['limit']
    if max(totals.values())>500 or max(counts.values())>12:
        raise SourceUnavailable('Aggregate card section expansion exceeds page bound.')
    scalar_tree = deepcopy(static)

    def restore(node):
        if node['id'] in scalars:
            node['bindings'] = deepcopy(scalars[node['id']])
        for child in node.get('children', []):
            restore(child)

    restore(scalar_tree)
    validate_tree_bindings(scalar_tree, registry, context, lambda value: page_problems(value, ('en', 'ar')))
    return static, declarations, scalars


async def resolve_cards(db, tree, context):
    registry = scalar_registry(db)
    static, declarations, scalars = card_plan(tree, registry, context)
    plans=[(node_id,content.get(context.language)) for node_id,content in declarations]
    if any(plan is None for _,plan in plans):
        raise SourceUnavailable('Every card section language must be explicitly configured.')
    for node_id,plan in plans:
        rows = await read_cards(db, context, plan['limit'], **({'products':plan['products']} if 'products' in plan else {}))
        static = project_cards(static, {'template_id':node_id,**plan}, rows, context)

    def restore(node):
        if node['id'] in scalars:
            node['bindings'] = deepcopy(scalars[node['id']])
        for child in node.get('children', []):
            restore(child)

    restore(static)
    return await resolve_tree(static, registry, context, lambda value: page_problems(value, ('en', 'ar')))
