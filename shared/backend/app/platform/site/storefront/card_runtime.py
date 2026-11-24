"""One persisted native card template plus independent scalar headings, preview only."""
from copy import deepcopy
import json
from app.framework.manifest import page_problems, page_card_problems
from app.framework.storefront_runtime import SourceContext, SourceUnavailable
from .card_projection import checked_card_template, project_cards
from .bindings import validate_tree_bindings, resolve_tree
from .registry import scalar_registry
from app.activities.general.modules.inventory.storefront.cards import read_cards


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
    if len(declarations) != 1 or 'inventory' not in context.active_modules:
        raise SourceUnavailable('Exactly one active inventory card template required.')
    node_id, content = declarations[0]
    for language, plan in content.items():
        checked_card_template(static, {'template_id': node_id, **plan})
    scalar_tree = deepcopy(static)

    def restore(node):
        if node['id'] in scalars:
            node['bindings'] = deepcopy(scalars[node['id']])
        for child in node.get('children', []):
            restore(child)

    restore(scalar_tree)
    validate_tree_bindings(scalar_tree, registry, context, lambda value: page_problems(value, ('en', 'ar')))
    return static, node_id, content, scalars


async def resolve_cards(db, tree, context):
    registry = scalar_registry(db)
    static, node_id, content, scalars = card_plan(tree, registry, context)
    plan = content.get(context.language)
    if plan is None:
        raise SourceUnavailable('Card language is not explicitly configured.')
    if plan is not None:
        rows = await read_cards(db, context, plan['limit'])
        static = project_cards(static, {'template_id': node_id, **plan}, rows, context)

    def restore(node):
        if node['id'] in scalars:
            node['bindings'] = deepcopy(scalars[node['id']])
        for child in node.get('children', []):
            restore(child)

    restore(static)
    return await resolve_tree(static, registry, context, lambda value: page_problems(value, ('en', 'ar')))
