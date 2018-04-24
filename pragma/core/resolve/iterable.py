import ast
import warnings
from copy import deepcopy
from miniutils import magic_contract

from pragma.core import _log_call
from pragma.core.resolve import pure_functions
import logging
log = logging.getLogger(__name__)

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
        resolution = resolve_name_or_attribute(node, ctxt)
        if resolution != node:
            return _resolve_iterable(resolution, ctxt)

    elif isinstance(node, (ast.List, ast.Tuple)):
        return node.elts

    elif isinstance(node, ast.Subscript):
        indexable = resolve_indexable(node.value, ctxt)
        if indexable is not None:
            slice = resolve_literal(node.slice, ctxt, True)
            if not isinstance(slice, ast.AST):
                return _resolve_iterable(indexable[slice], ctxt)

    elif isinstance(node, ast.UnaryOp):
        iterable = _resolve_iterable(node.operand, ctxt)
        if iterable is not None:
            return _collapse_map[type(node.op)](iterable)

    elif isinstance(node, ast.BinOp):
        left = _resolve_iterable(node.left, ctxt)
        right = _resolve_iterable(node.right, ctxt)
        if left is not None and right is not None:
            return _collapse_map[type(node.op)](left, right)

    elif isinstance(node, ast.Call):
        func = resolve_literal(node.func, ctxt, True)
        if isinstance(func, ast.AST):  # We don't even know what's being called
            raise TypeError("Unknown function, cannot evaluate")
        if func not in pure_functions:
            raise ValueError("Function {} isn't known to be a pure function, can't resolve as iterable".format(func))

        args = _resolve_args(node.args, ctxt)
        kwargs = _resolve_keywords(node.keywords, ctxt)
        result = func(*args, **kwargs)

        return iter(result)

    elif isinstance(node, (ast.Set, ast.Dict)):
        if isinstance(node, ast.Dict):
            vals = node.keys
        else:
            vals = node.elts
        if any(isinstance(v, ast.AST) for v in vals):
            return None
        return iter(set(vals))


def _resolve_args(args, ctxt):
    out_args = []
    for a in args:
        if isinstance(a, ast.Starred):
            starargs = resolve_iterable(a.value)
            for _a in starargs:
                out_args.append(CollapsableNode(_a, ctxt))
        else:
            out_args.append(CollapsableNode(a, ctxt))
    return out_args


def _resolve_keywords(keywords, ctxt):
    kwargs = {kw.arg: CollapsableNode(kw.value, ctxt)[1] for kw in keywords}
    if None in kwargs:
        kwargs.update(kwargs[None])
        del kwargs[None]
    return kwargs


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
    except (TypeError, KeyError, IndexError) as ex:
        log.debug("Failed to resolve as iterable", exc_info=ex)
        return None
    #
    # # TODO: Support zipping
    # # TODO: Support sets/dicts?
    # # TODO: Support for reversed, enumerate, etc.
    # # TODO: Support len, in, etc.
    # # Check for range(*constants)
    # def wrap(return_node, name, idx):
    #     if not avoid_side_effects:
    #         return return_node
    #     if can_have_side_effect(return_node, ctxt):
    #         return ast.Subscript(name, ast.Index(idx))
    #     return make_ast_from_literal(return_node)
    #
    # if isinstance(node, ast.Call):
    #     func = resolve_name_or_attribute(node.func, ctxt)
    #     return _resolvable_functions.get(func, _unknown_function)(node, ctxt)
    #
    # elif isinstance(node, (ast.List, ast.Tuple)):
    #     return [resolve_literal(e, ctxt) for e in node.elts]
    #     # return [_resolve_name_or_attribute(e, ctxt) for e in node.elts]
    # # Can't yet support sets and lists, since you need to compute what the unique values would be
    # # elif isinstance(node, ast.Dict):
    # #     return node.keys
    # elif isinstance(node, (ast.Name, ast.Attribute, ast.NameConstant)):
    #     res = resolve_name_or_attribute(node, ctxt)
    #     # print("Trying to resolve '{}' as list, got {}".format(astor.to_source(node), res))
    #     if isinstance(res, ast.AST) and not isinstance(res, (ast.Name, ast.Attribute, ast.NameConstant)):
    #         res = resolve_iterable(res, ctxt)
    #     if not isinstance(res, ast.AST):
    #         try:
    #             if hasattr(res, 'items'):
    #                 return dict([(k, wrap(make_ast_from_literal(v), node, k)) for k, v in res.items()])
    #             else:
    #                 return [wrap(make_ast_from_literal(res_node), node, i) for i, res_node in enumerate(res)]
    #         except TypeError:
    #             pass
    # return None


from pragma.core.resolve import _collapse_map, CollapsableNode, resolve_name_or_attribute
from pragma.core.resolve.indexable import resolve_indexable
from pragma.core.resolve.literal import resolve_literal
