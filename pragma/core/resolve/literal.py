import ast
import traceback
import warnings

from miniutils import magic_contract

from pragma.core.resolve import CollapsableNode
from pragma.core.stack import DictStack
from pragma.core import _log_call

import logging
log = logging.getLogger(__name__)


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
    if isinstance(lit, CollapsableNode):
        return make_ast_from_literal(lit.node)
    elif isinstance(lit, ast.AST):
        return lit
    elif isinstance(lit, (list, tuple)):
        res = [make_ast_from_literal(e) for e in lit]
        tp = ast.List if isinstance(lit, list) else ast.Tuple
        return tp(elts=res, ctx=ast.Load())
    elif isinstance(lit, dict):
        return ast.Dict(keys=[make_ast_from_literal(k) for k in lit.keys()],
                        values=[make_ast_from_literal(v) for v in lit.values()])
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
    elif isinstance(lit, (bool, type(None))):
        return ast.NameConstant(lit)
    else:
        # warnings.warn("'{}' of type {} is not able to be made into an AST node".format(lit, type(lit)))
        # return lit
        raise TypeError("'{}' of type {} is not able to be made into an AST node".format(lit, type(lit)))


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
    try:
        make_ast_from_literal(lit)
        return True
    except TypeError:
        return False


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


@_log_call
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


@_log_call
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


@_log_call
def resolve_literal_subscript(node, ctxt):
    indexable = resolve_indexable(node.value, ctxt)
    if indexable is not None:
        slice = _resolve_literal(node.slice, ctxt)
        if not isinstance(slice, ast.AST):
            try:
                if isinstance(indexable, dict):
                    indexable = {_resolve_literal(k, ctxt): v for k, v in indexable.items()}
                # return _resolve_literal(indexable[slice], ctxt)
                return indexable[slice]
            except (KeyError, IndexError):
                log.debug("Cannot index {}[{}]".format(indexable, slice))
                return node
        else:
            log.debug("Cannot resolve index to literal '{}'".format(node.slice))
    else:
        log.debug("Cannot resolve '{}' to indexable object".format(node.value))

    return node


@_log_call
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


@_log_call
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
        # Get the best resolution of the left and right, as AST nodes
        left = resolve_literal(node.left, ctxt)
        right = resolve_literal(node.right, ctxt)

        return ast.BinOp(left=left, right=right, op=node.op)


@_log_call
def resolve_literal_compare(node, ctxt):
    operands = [_resolve_literal(o, ctxt) for o in [node.left] + node.comparators]
    if all(not isinstance(opr, ast.AST) for opr in operands):
        return all(_collapse_map[type(cmp_func)](operands[i - 1], operands[i])
                   for i, cmp_func in zip(range(1, len(operands)), node.ops))
    else:
        return node


@_log_call
@magic_contract(node='Call', ctxt='DictStack')
def resolve_literal_call(node, ctxt):
    func = _resolve_literal(node.func, ctxt)
    if isinstance(func, ast.AST):  # We don't even know what's being called
        return node
    if func not in pure_functions:
        log.info("Function {} isn't known to be a pure function, can't resolve".format(func))
        return node

    args = None
    kwargs = None

    try:
        args = _resolve_args(node.args, ctxt)
        kwargs = _resolve_keywords(node.keywords, ctxt)
        # If we've made it this far, we know the function and its arguments. Run it and return the result
        return func(*args, **kwargs)
    except Exception as ex:
        log.debug("Failed to run '{}(*{}, **{})'".format(func, args, kwargs), exc_info=ex)
        return node



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
    try:
        return make_ast_from_literal(result)
    except TypeError:
        log.debug("Failed to convert {} into AST".format(result))
        return node


from pragma.core.resolve import _collapse_map, num_types, float_types, resolve_name_or_attribute, pure_functions, _resolve_args, _resolve_keywords
from pragma.core.resolve.indexable import resolve_indexable
