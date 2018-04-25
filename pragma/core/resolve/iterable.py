import ast
import warnings
from copy import deepcopy
from miniutils import magic_contract

from pragma.core import _log_call
from pragma.core.resolve import pure_functions
import logging
log = logging.getLogger(__name__)


def _resolve_iterable_name_or_attr(node, ctxt):
    resolution = resolve_name_or_attribute(node, ctxt)
    if resolution != node:
        return _resolve_iterable(resolution, ctxt)


def _resolve_iterable_subscript(node, ctxt):
    indexable = resolve_indexable(node.value, ctxt)
    if indexable is not None:
        slice = resolve_literal(node.slice, ctxt, True)
        if not isinstance(slice, ast.AST):
            return _resolve_iterable(indexable[slice], ctxt)


def _resolve_iterable_unop(node, ctxt):
    iterable = _resolve_iterable(node.operand, ctxt)
    if iterable is not None:
        return _collapse_map[type(node.op)](iterable)


def _resolve_iterable_binop(node, ctxt):
    left = _resolve_iterable(node.left, ctxt)
    right = _resolve_iterable(node.right, ctxt)
    if left is not None and right is not None:
        return _collapse_map[type(node.op)](left, right)


def _resolve_iterable_call(node, ctxt):
    func = resolve_literal(node.func, ctxt, True)
    if isinstance(func, ast.AST):  # We don't even know what's being called
        raise TypeError("Unknown function, cannot evaluate")
    if func not in pure_functions:
        raise ValueError("Function {} isn't known to be a pure function, can't resolve as iterable".format(func))

    args = _resolve_args(node.args, ctxt)
    kwargs = _resolve_keywords(node.keywords, ctxt)
    result = func(*args, **kwargs)

    return iter(result)


def _resolve_iterable_set_or_dict(node, ctxt):
    if isinstance(node, ast.Dict):
        vals = node.keys
    else:
        vals = node.elts
    if any(isinstance(v, ast.AST) for v in vals):
        return None
    return iter(set(vals))


def _resolve_iterable_list_or_tuple(node, ctxt):
    return node.elts


@_log_call
@magic_contract
def _resolve_iterable(node, ctxt):
    """
    Collapses literal expressions. Returns literals if they're available, AST nodes otherwise
    :param node: The AST node to be checked
    :type node: *
    :param ctxt: The environment stack to use when running the check
    :type ctxt: DictStack
    :return: The given AST node with literal operations collapsed as much as possible
    :rtype: *
    """
    # try:
    #     print("Trying to collapse {}".format(astor.to_source(node)))
    # except:
    #     print("Trying to collapse (source not possible) {}".format(astor.dump_tree(node)))
    if not isinstance(node, ast.AST):
        return iter(node)

    elif isinstance(node, (ast.Name, ast.Attribute, ast.NameConstant)):
        return _resolve_iterable_name_or_attr(node, ctxt)

    elif isinstance(node, (ast.List, ast.Tuple)):
        return _resolve_iterable_list_or_tuple(node, ctxt)

    elif isinstance(node, ast.Subscript):
        return _resolve_iterable_subscript(node, ctxt)

    elif isinstance(node, ast.UnaryOp):
        return _resolve_iterable_unop(node, ctxt)

    elif isinstance(node, ast.BinOp):
        return _resolve_iterable_binop(node, ctxt)

    elif isinstance(node, ast.Call):
        return _resolve_iterable_call(node, ctxt)

    elif isinstance(node, (ast.Set, ast.Dict)):
        return _resolve_iterable_set_or_dict(node, ctxt)


@_log_call
@magic_contract
def resolve_iterable(node, ctxt):
    """
    If the given node is a known iterable of some sort, return the list of its elements.
    :param node: The AST node to be checked
    :type node: AST
    :param ctxt: The environment stack to use when running the check
    :type ctxt: DictStack
    :return: The iterable if possible, else None
    :rtype: iterable|None
    """
    try:
        return list(_resolve_iterable(node, ctxt))
    except (AssertionError, TypeError, KeyError, IndexError) as ex:
        log.debug("Failed to resolve as iterable", exc_info=ex)
        return None


from pragma.core.resolve import _collapse_map, CollapsableNode, resolve_name_or_attribute, _resolve_args, _resolve_keywords
from pragma.core.resolve.indexable import resolve_indexable
from pragma.core.resolve.literal import resolve_literal
