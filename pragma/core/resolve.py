import ast
import traceback
import warnings

from miniutils import magic_contract

from .stack import DictStack

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


@magic_contract
def constant_iterable(node, ctxt, avoid_side_effects=True):
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
        if resolve_name_or_attribute(node.func, ctxt) == range:
            args = [resolve_literal(arg, ctxt) for arg in node.args]
            if all(isinstance(arg, ast.Num) for arg in args):
                return [ast.Num(n) for n in range(*[arg.n for arg in args])]

        return None
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
            res = constant_iterable(res, ctxt)
        if not isinstance(res, ast.AST):
            try:
                if hasattr(res, 'items'):
                    return dict([(k, wrap(make_ast_from_literal(v), node, k)) for k, v in res.items()])
                else:
                    return [wrap(make_ast_from_literal(res_node), node, i) for i, res_node in enumerate(res)]
            except TypeError:
                pass
    return None


# @magic_contract
def constant_dict(node, ctxt):
    if isinstance(node, (ast.Name, ast.NameConstant, ast.Attribute)):
        res = resolve_name_or_attribute(node, ctxt)
        if hasattr(res, 'items'):
            return dict(res.items())
    return None


@magic_contract
def resolve_name_or_attribute(node, ctxt):
    """
    If the given name of attribute is defined in the current context, return its value. Else, returns the node
    :param node: The node to try to resolve
    :type node: AST
    :param ctxt: The environment stack to use when running the check
    :type ctxt: DictStack
    :return: The object if the name was found, else the original node
    :rtype: *
    """
    if isinstance(node, ast.Name):
        if node.id in ctxt:
            try:
                return ctxt[node.id]
            except KeyError:
                # This occurs if we know that the name was assigned, but we don't know what to... just return the node
                return node
        else:
            return node
    elif isinstance(node, ast.NameConstant):
        return node.value
    elif isinstance(node, ast.Attribute):
        base_obj = resolve_name_or_attribute(node.value, ctxt)
        if not isinstance(base_obj, ast.AST):
            return getattr(base_obj, node.attr, node)
        else:
            return node
    else:
        return node


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


@magic_contract
def _resolve_literal(node, ctxt):
    """
    Collapses literal expressions. Returns literals if they're available, AST nodes otherwise
    :param node: The AST node to be checked
    :type node: AST
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
        res = resolve_name_or_attribute(node, ctxt)
        if isinstance(res, ast.AST) and not isinstance(res, (ast.Name, ast.Attribute, ast.NameConstant)):
            new_res = _resolve_literal(res, ctxt)
            if is_wrappable(new_res):
                # print("{} can be replaced by more specific literal {}".format(res, new_res))
                res = new_res
            # else:
            #     print("{} is an AST node, but can't safely be made more specific".format(res))
        return res
    elif isinstance(node, ast.Num):
        return node.n
    elif isinstance(node, ast.Str):
        return node.s
    elif isinstance(node, ast.Index):
        return _resolve_literal(node.value, ctxt)
    elif isinstance(node, (ast.Slice, ast.ExtSlice)):
        raise NotImplementedError()
    elif isinstance(node, ast.Subscript):
        # print("Attempting to subscript {}".format(astor.to_source(node)))
        lst = constant_iterable(node.value, ctxt)
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
    elif isinstance(node, ast.UnaryOp):
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
    elif isinstance(node, ast.BinOp):
        left = _resolve_literal(node.left, ctxt)
        right = _resolve_literal(node.right, ctxt)
        # print("({} {})".format(repr(node.op), ", ".join(repr(o) for o in operands)))
        lliteral = not isinstance(left, ast.AST)
        rliteral = not isinstance(right, ast.AST)
        if lliteral and rliteral:
            # print("Both operands {} and {} are literals, attempting to collapse".format(left, right))
            try:
                return _collapse_map[type(node.op)](left, right)
            except:
                warnings.warn(
                    "Binary op collapse failed. Collapsing skipped, but executing this function will likely fail."
                    " Error was:\n{}".format(traceback.format_exc()))
                return node
        else:
            left = make_ast_from_literal(left)
            left = left if isinstance(left, ast.AST) else node.left

            right = make_ast_from_literal(right)
            right = right if isinstance(right, ast.AST) else node.right
            # print("Attempting to combine {} and {} ({} op)".format(left, right, node.op))
            return ast.BinOp(left=left, right=right, op=node.op)
    elif isinstance(node, ast.Compare):
        operands = [_resolve_literal(o, ctxt) for o in [node.left] + node.comparators]
        if all(not isinstance(opr, ast.AST) for opr in operands):
            return all(_collapse_map[type(cmp_func)](operands[i - 1], operands[i])
                       for i, cmp_func in zip(range(1, len(operands)), node.ops))
        else:
            return node
    else:
        return node


@magic_contract
def resolve_literal(node, ctxt, give_raw_result=False):
    """
    Collapse literal expressions in the given node. Returns the node with the collapsed literals
    :param node: The AST node to be checked
    :type node: AST
    :param ctxt: The environment stack to use when running the check
    :type ctxt: DictStack
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
