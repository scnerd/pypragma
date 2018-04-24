import ast
from miniutils import magic_contract

import logging
log = logging.getLogger(__name__)

from pragma.core import _log_call, DictStack

import builtins
import inspect
_builtin_funcs = inspect.getmembers(builtins, lambda o: callable(o))
pure_functions = {func for name, func in _builtin_funcs}

@_log_call
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
                log.debug("'{}' has been assigned to, but with an unknown value".format(node.id))
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
            log.debug("Could not resolve '{}.{}'".format(node.value, node.attr))
            return node
    else:
        return node


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

try:
    import numpy

    num_types = (int, float, numpy.number)
    float_types = (float, numpy.floating)
except ImportError:  # pragma: nocover
    numpy = None
    num_types = (int, float)
    float_types = (float,)


class CollapsableNode:
    def __init__(self, node, ctxt):
        self.node = node
        self.ctxt = ctxt

    @property
    def as_literal(self):
        return resolve_literal(self.node, self.ctxt, True)

    @property
    def as_iterable(self):
        return resolve_iterable(self.node, self.ctxt)

    @property
    def as_indexable(self):
        return resolve_indexable(self.node, self.ctxt)

    def __int__(self):
        return int(self.as_literal)

    def __index__(self):
        import operator
        return operator.index(self.as_literal)

    def __float__(self):
        return float(self.as_literal)

    def __str__(self):
        res = self.as_literal
        assert not isinstance(res, ast.AST)
        return str(res)

    def __bool__(self):
        return bool(self.as_literal)

    def __iter__(self):
        return iter(self.as_iterable)

    def __getitem__(self, item):
        return self.as_indexable[item]

    def __getattr__(self, item):
        return getattr(self.as_literal, item)

    # hash
    # lt, le, gt, ge, eq, ne
    # bytes
    # instancecheck, subclasscheck
    # call
    # len
    # contains
    # all math ops


from .literal import resolve_literal, make_ast_from_literal
from .iterable import resolve_iterable, pure_functions
from .indexable import resolve_indexable
