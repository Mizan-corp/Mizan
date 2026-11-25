"""Compose reviewed scalar headings and one bounded heading repeat, without read effects."""
from copy import deepcopy
from app.framework.manifest import page_problems
from app.framework.storefront_runtime import SourceUnavailable
from .bindings import validate_tree_bindings, resolve_tree
from .repeats import validate_repeat, resolve_repeat


def split_composition(tree):
    if page_problems(tree, ('en', 'ar')):
        raise SourceUnavailable('Invalid native composition.')
    scalar_tree = deepcopy(tree)
    repeat_tree = deepcopy(tree)
    envelopes = {}

    def strip_scalar(node):
        envelope = node.pop('bindings', None)
        if envelope is not None:
            envelopes[node['id']] = envelope
        for child in node.get('children', []):
            strip_scalar(child)

    def strip_repeat(node):
        node.pop('repeat', None)
        for child in node.get('children', []):
            strip_repeat(child)

    strip_scalar(repeat_tree)
    strip_repeat(scalar_tree)
    return scalar_tree, repeat_tree, envelopes


def validate_composition(tree, scalars, collections, context, items=None):
    scalar_tree, repeat_tree, envelopes = split_composition(tree)
    # Every language and both provider families are checked before any provider read.
    validate_tree_bindings(scalar_tree, scalars, context,
                           lambda value: page_problems(value, ('en', 'ar')), items)
    validate_repeat(repeat_tree, collections, context)
    return repeat_tree, envelopes


async def resolve_composition(tree, scalars, collections, context, items=None):
    repeat_tree, envelopes = validate_composition(tree, scalars, collections, context, items)
    expanded = await resolve_repeat(repeat_tree, collections, context)

    def restore(node):
        if node['id'] in envelopes:
            node['bindings'] = deepcopy(envelopes[node['id']])
        for child in node.get('children', []):
            restore(child)

    restore(expanded)
    return await resolve_tree(expanded, scalars, context,
                              lambda value: page_problems(value, ('en', 'ar')), items)
