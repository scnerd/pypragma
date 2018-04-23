import ast
import inspect
from copy import deepcopy

from pragma.core import _log_call, resolve_literal, resolve_name_or_attribute
from .literal import can_have_side_effect, make_ast_from_literal, _resolve_argument, _resolve_args, _resolve_keywords


def _resolve_converter(node, ctxt):
    pass


def _resolve_reversed(node, ctxt):
    pass


def _resolve_zip(node, ctxt):
    pass


def _resolve_range(node, ctxt):
    try:
        args = _resolve_args(node.args, ctxt)
        kwargs = _resolve_keywords(node.keywords, ctxt)
    except TypeError:
        return None

    return range(*args, **kwargs)


def _unknown_function(node, ctxt):
    return None


_resolvable_functions = {
    range: _resolve_range,
    zip: _resolve_zip,
    set: _resolve_converter,
    frozenset: _resolve_converter,
    list: _resolve_converter,
    tuple: _resolve_converter,
    # dict: _resolve_converter,
    # iter: _resolve_converter,
    # enumerate: _resolve_converter,
}


@_log_call
@magic_contract
def resolve_iterable(node, ctxt, avoid_side_effects=True):
    """
    If the given node is a known iterable of some sort, return the list of its elements.
    :param node: The AST node to be checked
    :type node: AST
    :param ctxt: The environment stack to use when running the check
    :type ctxt: DictStack
    :param avoid_side_effects: Whether or not to avoid unwrapping side effect-causing AST nodes
    :type avoid_side_effects: bool
    :return: The iterable if possible, else None
    :rtype: iterable|None
    """

    # TODO: Support zipping
    # TODO: Support sets/dicts?
    # TODO: Support for reversed, enumerate, etc.
    # TODO: Support len, in, etc.
    # Check for range(*constants)
    def wrap(return_node, name, idx):
        if not avoid_side_effects:
            return return_node
        if can_have_side_effect(return_node, ctxt):
            return ast.Subscript(name, ast.Index(idx))
        return make_ast_from_literal(return_node)

    if isinstance(node, ast.Call):
        func = resolve_name_or_attribute(node.func, ctxt)
        return _resolvable_functions.get(func, _unknown_function)(node, ctxt)

    elif isinstance(node, (ast.List, ast.Tuple)):
        return [resolve_literal(e, ctxt) for e in node.elts]
        # return [_resolve_name_or_attribute(e, ctxt) for e in node.elts]
    # Can't yet support sets and lists, since you need to compute what the unique values would be
    # elif isinstance(node, ast.Dict):
    #     return node.keys
    elif isinstance(node, (ast.Name, ast.Attribute, ast.NameConstant)):
        res = resolve_name_or_attribute(node, ctxt)
        # print("Trying to resolve '{}' as list, got {}".format(astor.to_source(node), res))
        if isinstance(res, ast.AST) and not isinstance(res, (ast.Name, ast.Attribute, ast.NameConstant)):
            res = resolve_iterable(res, ctxt)
        if not isinstance(res, ast.AST):
            try:
                if hasattr(res, 'items'):
                    return dict([(k, wrap(make_ast_from_literal(v), node, k)) for k, v in res.items()])
                else:
                    return [wrap(make_ast_from_literal(res_node), node, i) for i, res_node in enumerate(res)]
            except TypeError:
                pass
    return None


_builtin_funcs = inspect.getmembers(builtins, lambda o: callable(o))
pure_functions = {func for name, func in _builtin_funcs}