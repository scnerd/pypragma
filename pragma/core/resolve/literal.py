import ast
import traceback
import warnings
import logging

from miniutils import magic_contract

from pragma.core.resolve.iterable import resolve_iterable, pure_functions
from pragma.core.stack import DictStack
from pragma.core import _log_call, resolve_name_or_attribute

log = logging.getLogger(__name__.split('.')[0])

try:
    import numpy

    num_types = (int, float, numpy.number)
    float_types = (float, numpy.floating)
except ImportError:  # pragma: nocover
    numpy = None
    num_types = (int, float)
    float_types = (float,)

_collapse_map = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,

    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
    ast.LShift: lambda a, b: a << b,
    ast.RShift: lambda a, b: a >> b,
    ast.MatMult: lambda a, b: a @ b,

    ast.BitAnd: lambda a, b: a & b,
    ast.BitOr: lambda a, b: a | b,
    ast.BitXor: lambda a, b: a ^ b,
    ast.And: lambda a, b: a and b,
    ast.Or: lambda a, b: a or b,
    ast.Invert: lambda a: ~a,
    ast.Not: lambda a: not a,

    ast.UAdd: lambda a: a,
    ast.USub: lambda a: -a,

    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
}

@magic_contract
def can_have_side_effect(node, ctxt):
    """
    Checks whether or not copying the given AST node could cause side effects in the resulting function
    :param node: The AST node to be checked
    :type node: AST
    :param ctxt: The environment stack to use when running the check
    :type ctxt: DictStack
    :return: Whether or not duplicating this node could cause side effects
    :rtype: bool
    """
    if isinstance(node, ast.AST):
        # print("Can {} have side effects?".format(node))
        if isinstance(node, ast.Call):
            # print("  Yes!")
            return True
        else:
            for field, old_value in ast.iter_fields(node):
                if isinstance(old_value, list):
                    return any(can_have_side_effect(n, ctxt) for n in old_value if isinstance(n, ast.AST))
                elif isinstance(old_value, ast.AST):
                    return can_have_side_effect(old_value, ctxt)
                else:
                    # print("  No!")
                    return False
    else:
        return False


@_log_call
@magic_contract
def make_ast_from_literal(lit):
    """
    Converts literals into their AST equivalent
    :param lit: The literal to attempt to turn into an AST
    :type lit: *
    :return: The AST version of the literal, or the original AST node if one was given
    :rtype: *
    """
    if isinstance(lit, ast.AST):
        return lit
    elif isinstance(lit, (list, tuple)):
        res = [make_ast_from_literal(e) for e in lit]
        tp = ast.List if isinstance(lit, list) else ast.Tuple
        return tp(elts=res)
    elif isinstance(lit, dict):
        return ast.Dict(keys=list(lit.keys()), values=list(lit.values()))
    elif isinstance(lit, num_types):
        if isinstance(lit, float_types):
            lit2 = float(lit)
        else:
            lit2 = int(lit)
        if lit2 != lit:
            raise AssertionError("({}){} != ({}){}".format(type(lit), lit, type(lit2), lit2))
        return ast.Num(lit2)
    elif isinstance(lit, str):
        return ast.Str(lit)
    elif isinstance(lit, bool):
        return ast.NameConstant(lit)
    else:
        # warnings.warn("'{}' of type {} is not able to be made into an AST node".format(lit, type(lit)))
        return lit


@_log_call
@magic_contract
def is_wrappable(lit):
    """
    Checks if the given object either is or can be made into a known AST node
    :param lit: The object to try to wrap
    :type lit: *
    :return: Whether or not this object can be wrapped as an AST node
    :rtype: bool
    """
    return isinstance(make_ast_from_literal(lit), ast.AST)


@_log_call
@magic_contract
def _resolve_literal(node, ctxt):
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

    if isinstance(node, (ast.Name, ast.Attribute, ast.NameConstant)):
        return resolve_literal_name(node, ctxt)
    elif isinstance(node, ast.Num):
        return node.n
    elif isinstance(node, ast.Str):
        return node.s
    elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return resolve_literal_list(node, ctxt)
    elif isinstance(node, ast.Index):
        return _resolve_literal(node.value, ctxt)
    elif isinstance(node, (ast.Slice, ast.ExtSlice)):
        raise NotImplementedError()
    elif isinstance(node, ast.Subscript):
        return resolve_literal_subscript(node, ctxt)
    elif isinstance(node, ast.UnaryOp):
        return resolve_literal_unop(node, ctxt)
    elif isinstance(node, ast.BinOp):
        return resolve_literal_binop(node, ctxt)
    elif isinstance(node, ast.Compare):
        return resolve_literal_compare(node, ctxt)
    elif isinstance(node, ast.Call):
        return resolve_literal_call(node, ctxt)
    else:
        return node


def resolve_literal_name(node, ctxt):
    res = resolve_name_or_attribute(node, ctxt)
    if isinstance(res, ast.AST) and not isinstance(res, (ast.Name, ast.Attribute, ast.NameConstant)):
        new_res = _resolve_literal(res, ctxt)
        if is_wrappable(new_res):
            log.debug("{} can be replaced by more specific literal {}".format(res, new_res))
            res = new_res
        else:
            log.debug("{} is an AST node, but can't safely be made more specific".format(res))
    return res


def resolve_literal_list(node, ctxt):
    """Returns, if possible, the entirely literal list or tuple.

    This differs from constant iterable in that the entire list, including all elements, must resolve to literals
    It is not sufficient for the top level structure to be iterable
    """
    val = []
    for e in node.elts:
        e = _resolve_literal(e, ctxt)
        if isinstance(e, ast.AST):
            return node
        val.append(e)
    if isinstance(node, ast.Tuple):
        return tuple(val)
    elif isinstance(node, ast.List):
        return list(val)
    elif isinstance(node, ast.Set):
        return set(val)
    else:
        raise TypeError("Attempted to resolve {} as if it were a literal list, tuple, or set".format(node))


def resolve_literal_subscript(node, ctxt):
    # print("Attempting to subscript {}".format(astor.to_source(node)))
    lst = resolve_iterable(node.value, ctxt)
    # print("Can I subscript {}?".format(lst))
    if lst is None:
        return node
    slc = _resolve_literal(node.slice, ctxt)
    # print("Getting subscript at {}".format(slc))
    if isinstance(slc, ast.AST):
        return node
    # print("Value at {}[{}] = {}".format(lst, slc, lst[slc]))
    val = lst[slc]
    if isinstance(val, ast.AST):
        new_val = _resolve_literal(val, ctxt)
        if is_wrappable(new_val):
            # print("{} can be replaced by more specific literal {}".format(val, new_val))
            val = new_val
    #     else:
    #         print("{} is an AST node, but can't safely be made more specific".format(val))
    # print("Final value at {}[{}] = {}".format(lst, slc, val))
    return val


def resolve_literal_unop(node, ctxt):
    operand = _resolve_literal(node.operand, ctxt)
    if isinstance(operand, ast.AST):
        return node
    else:
        try:
            return _collapse_map[type(node.op)](operand)
        except:
            warnings.warn(
                "Unary op collapse failed. Collapsing skipped, but executing this function will likely fail."
                " Error was:\n{}".format(traceback.format_exc()))
            return node


def resolve_literal_binop(node, ctxt):
    left = _resolve_literal(node.left, ctxt)
    right = _resolve_literal(node.right, ctxt)
    lliteral = not isinstance(left, ast.AST)
    rliteral = not isinstance(right, ast.AST)
    if lliteral and rliteral:
        try:
            return _collapse_map[type(node.op)](left, right)
        except Exception:
            warnings.warn(
                "Binary op collapse failed. Collapsing skipped, but executing this function will likely fail."
                " Error was:\n{}".format(traceback.format_exc()))
            return node
    else:
        left = make_ast_from_literal(left)
        left = left if isinstance(left, ast.AST) else node.left

        right = make_ast_from_literal(right)
        right = right if isinstance(right, ast.AST) else node.right
        return ast.BinOp(left=left, right=right, op=node.op)


def resolve_literal_compare(node, ctxt):
    operands = [_resolve_literal(o, ctxt) for o in [node.left] + node.comparators]
    if all(not isinstance(opr, ast.AST) for opr in operands):
        return all(_collapse_map[type(cmp_func)](operands[i - 1], operands[i])
                   for i, cmp_func in zip(range(1, len(operands)), node.ops))
    else:
        return node


def _resolve_argument(arg, ctxt):
    starred = False
    if isinstance(arg, ast.Starred):
        starred = True
        arg = arg.value
    arg = _resolve_literal(arg, ctxt)
    if isinstance(arg, ast.AST):  # We don't know the value of this argument
        raise TypeError()

    return starred, arg


def _resolve_args(args, ctxt):
    return [
        a
        for a_in in args
        for starred, a_out in _resolve_argument(a_in, ctxt)
        for a in (a_out if starred else [a_out])
    ]


def _resolve_keywords(keywords, ctxt):
    kwargs = {kw.arg: _resolve_argument(kw.value, ctxt)[1] for kw in keywords}
    if None in kwargs:
        kwargs.update(kwargs[None])
        del kwargs[None]


def resolve_literal_call(node, ctxt):
    func = _resolve_literal(node.func, ctxt)
    if isinstance(func, ast.AST):  # We don't even know what's being called
        return node
    if func not in pure_functions:
        log.info("Function {} isn't known to be a pure function, can't resolve".format(func))
        return node

    try:
        args = _resolve_args(node.args, ctxt)
        kwargs = _resolve_keywords(node.keywords, ctxt)
    except TypeError:
        return node

    # If we've made it this far, we know the function and its arguments. Run it and return the result
    return func(*args, **kwargs)


@magic_contract
def resolve_literal(node, ctxt, give_raw_result=False):
    """
    Collapse literal expressions in the given node. Returns the node with the collapsed literals
    :param node: The AST node to be checked
    :type node: AST
    :param ctxt: The environment stack to use when running the check
    :type ctxt: DictStack
    :param give_raw_result: Return the resolved value, not its AST-form
    :type give_raw_result: bool
    :return: The given AST node with literal operations collapsed as much as possible
    :rtype: *
    """
    result = _resolve_literal(node, ctxt)
    if give_raw_result:
        return result
    result = make_ast_from_literal(result)
    if not isinstance(result, ast.AST):
        return node
    return result
