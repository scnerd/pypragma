import ast
from miniutils import magic_contract
import logging
log = logging.getLogger(__name__)

from pragma.core import _log_call, DictStack


@_log_call
def _resolve_indexable_name_or_attr(node, ctxt):
    resolution = resolve_name_or_attribute(node, ctxt)
    if resolution != node:
        if isinstance(resolution, ast.AST):
            resolution = _resolve_indexable(resolution, ctxt)
        return resolution


@_log_call
def _resolve_indexable_subscript(node, ctxt):
    indexable = resolve_indexable(node.value, ctxt)
    if indexable is not None:
        slice = resolve_literal(node.slice, ctxt, True)
        if not isinstance(slice, ast.AST):
            return _resolve_indexable(indexable[slice], ctxt)


@_log_call
def _resolve_indexable_unop(node, ctxt):
    iterable = _resolve_indexable(node.operand, ctxt)
    if iterable is not None:
        return _collapse_map[type(node.op)](iterable)


@_log_call
def _resolve_indexable_binop(node, ctxt):
    left = _resolve_indexable(node.left, ctxt)
    right = _resolve_indexable(node.right, ctxt)
    if left is not None and right is not None:
        return _collapse_map[type(node.op)](left, right)


@_log_call
def _resolve_indexable_call(node, ctxt):
    func = resolve_literal(node.func, ctxt, True)
    if isinstance(func, ast.AST):  # We don't even know what's being called
        raise TypeError("Unknown function, cannot evaluate")
    if func not in pure_functions:
        raise ValueError("Function {} isn't known to be a pure function, can't resolve as iterable".format(func))

    args = _resolve_args(node.args, ctxt)
    kwargs = _resolve_keywords(node.keywords, ctxt)
    result = func(*args, **kwargs)

    return result


@_log_call
def _resolve_indexable_dict(node, ctxt):
    return dict(zip(node.keys, node.values))


@_log_call
def _resolve_indexable_list_or_tuple(node, ctxt):
    return node.elts


@_log_call
@magic_contract
def _resolve_indexable(node, ctxt):
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
        return node

    elif isinstance(node, (ast.Name, ast.Attribute, ast.NameConstant)):
        return _resolve_indexable_name_or_attr(node, ctxt)

    elif isinstance(node, (ast.List, ast.Tuple)):
        return _resolve_indexable_list_or_tuple(node, ctxt)

    elif isinstance(node, ast.Subscript):
        return _resolve_indexable_subscript(node, ctxt)

    elif isinstance(node, ast.UnaryOp):
        return _resolve_indexable_unop(node, ctxt)

    elif isinstance(node, ast.BinOp):
        return _resolve_indexable_binop(node, ctxt)

    elif isinstance(node, ast.Call):
        return _resolve_indexable_call(node, ctxt)

    elif isinstance(node, ast.Dict):
        return _resolve_indexable_dict(node, ctxt)

@_log_call
@magic_contract
def resolve_indexable(node, ctxt):
    """Resolves the given node to an object that can be indexed

    :param node: The AST node to be resolved, if possible
    :type node: AST
    :param ctxt: The current environment
    :type ctxt: DictStack
    :return: An object that can be indexed, returning an ast.AST value, if possible, else None
    :rtype: indexable|None
    """
    try:
        result = _resolve_indexable(node, ctxt)
        if hasattr(result, '__getitem__'):
            return result
    except (AssertionError, TypeError, KeyError, IndexError) as ex:
        log.debug("Failed to resolve as indexable, trying to resolve as iterable", exc_info=ex)
        return resolve_iterable(node, ctxt)


from pragma.core.resolve import resolve_name_or_attribute, _resolve_args, _resolve_keywords, pure_functions, _collapse_map
from pragma.core.resolve.iterable import resolve_iterable
from pragma.core.resolve.literal import resolve_literal
