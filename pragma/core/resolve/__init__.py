import ast
from miniutils import magic_contract
from functools import wraps
import operator as ops
import math

import logging
log = logging.getLogger(__name__)

from pragma.core import _log_call, DictStack, _pretty_str

import builtins
import inspect
_builtin_funcs = inspect.getmembers(builtins, lambda o: callable(o))
pure_functions = {func for name, func in _builtin_funcs} - {print, delattr, exec, eval, input, open, setattr, super}

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
        try:
            return ctxt[node.id]
        except KeyError:
            log.debug("'{}' has been assigned to, but with an unknown value".format(node.id))
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

primitive_types = tuple([str, bytes, bool, type(None)] + list(num_types) + list(float_types))

try:
    primitive_ast_types = (ast.Num, ast.Str, ast.Bytes, ast.NameConstant, ast.Constant, ast.JoinedStr)
except AttributeError:  # Python <3.6
    primitive_ast_types = (ast.Num, ast.Str, ast.Bytes, ast.NameConstant)


def make_binop(op):
    def f(self, other):
        try:
            return op(self.as_literal, other)
        except:
            try:
                return op(type(other)(self.as_literal), other)
            except:
                try:
                    return op(self.as_iterable, other)
                except:
                    raise AssertionError('Not able to perform {} on {} and {}'.format(op, self, other))

    return f


def make_rbinop(op):
    def f(self, other):
        try:
            return op(other, self.as_literal)
        except:
            try:
                return op(other, type(other)(self.as_literal))
            except:
                try:
                    return op(other, self.as_iterable)
                except:
                    raise AssertionError('Not able to perform {} on {} and {}'.format(op, self, other))

    return f


def make_unop(op):
    def f(self):
        try:
            return op(self.as_literal)
        except:
            try:
                return op(self.as_iterable)
            except:
                raise AssertionError('Not able to perform {} on {}'.format(op, self))

    return f


class CollapsableNode:
    def __init__(self, node, ctxt):
        self.node = node
        self.ctxt = ctxt

    def __repr__(self):
        return 'CollapsableNode({})'.format(_pretty_str(self.node))

    def __format__(self, format_spec):
        return repr(self)

    @property
    def as_literal(self):
        res = resolve_literal(self.node, self.ctxt, True) if isinstance(self.node, ast.AST) else self.node
        assert not isinstance(res, ast.AST), res
        return res

    @property
    def as_iterable(self):
        res = resolve_iterable(self.node, self.ctxt) if isinstance(self.node, ast.AST) else self.node
        assert res is not None, res
        return res

    @property
    def as_indexable(self):
        res = resolve_indexable(self.node, self.ctxt) if isinstance(self.node, ast.AST) else self.node
        assert res is not None, res
        return res

    def __int__(self):
        return int(self.as_literal)

    def __index__(self):
        import operator
        return operator.index(self.as_literal)

    def __float__(self):
        return float(self.as_literal)

    def __complex__(self):
        return complex(self.as_literal)

    def __str__(self):
        return str(self.as_literal)

    def __bytes__(self):
        return bytes(self.as_literal)

    def __bool__(self):
        return bool(self.as_literal)

    def __iter__(self):
        return (CollapsableNode(v, self.ctxt) for v in self.as_iterable)

    def __getitem__(self, item):
        return self.as_indexable[item]

    def __getattr__(self, item):
        return getattr(self.as_literal, item)

    def __hash__(self):
        return hash(self.as_literal)

    def __len__(self):
        return len(self.as_iterable)

    def __contains__(self, item):
        return item in self.as_indexable

    def __call__(self, *args, **kwargs):
        return self.as_literal(*args, **kwargs)

    __add__ = make_binop(ops.add)
    __sub__ = make_binop(ops.sub)
    __mul__ = make_binop(ops.mul)
    __truediv__ = make_binop(ops.truediv)
    __floordiv__ = make_binop(ops.floordiv)
    __matmul__ = make_binop(ops.matmul)
    __mod__ = make_binop(ops.mod)
    __divmod__ = make_binop(divmod)
    __pow__ = make_binop(ops.pow)
    __lshift__ = make_binop(ops.lshift)
    __rshift__ = make_binop(ops.rshift)
    __and__ = make_binop(ops.and_)
    __xor__ = make_binop(ops.xor)
    __or__ = make_binop(ops.or_)

    __radd__ = make_rbinop(ops.add)
    __rsub__ = make_rbinop(ops.sub)
    __rmul__ = make_rbinop(ops.mul)
    __rtruediv__ = make_rbinop(ops.truediv)
    __rfloordiv__ = make_rbinop(ops.floordiv)
    __rmatmul__ = make_rbinop(ops.matmul)
    __rmod__ = make_rbinop(ops.mod)
    __rdivmod__ = make_rbinop(divmod)
    __rpow__ = make_rbinop(ops.pow)
    __rlshift__ = make_rbinop(ops.lshift)
    __rrshift__ = make_rbinop(ops.rshift)
    __rand__ = make_rbinop(ops.and_)
    __rxor__ = make_rbinop(ops.xor)
    __ror__ = make_rbinop(ops.or_)

    __iadd__ = make_binop(ops.iadd)
    __isub__ = make_binop(ops.isub)
    __imul__ = make_binop(ops.imul)
    __itruediv__ = make_binop(ops.itruediv)
    __ifloordiv__ = make_binop(ops.ifloordiv)
    __imatmul__ = make_binop(ops.imatmul)
    __imod__ = make_binop(ops.imod)
    __ipow__ = make_binop(ops.ipow)
    __ilshift__ = make_binop(ops.ilshift)
    __irshift__ = make_binop(ops.irshift)
    __iand__ = make_binop(ops.iand)
    __ixor__ = make_binop(ops.ixor)
    __ior__ = make_binop(ops.ior)

    __lt__ = make_binop(ops.lt)
    __le__ = make_binop(ops.le)
    __gt__ = make_binop(ops.gt)
    __ge__ = make_binop(ops.ge)
    __eq__ = make_binop(ops.eq)
    __ne__ = make_binop(ops.ne)

    __neg__ = make_unop(ops.neg)
    __pos__ = make_unop(ops.pos)
    __abs__ = make_unop(ops.abs)
    __invert__ = make_unop(ops.invert)

    __round__ = make_unop(round)
    __trunc__ = make_unop(math.trunc)
    __floor__ = make_unop(math.floor)
    __ceil__ = make_unop(math.ceil)


@_log_call
def _resolve_args(args, ctxt):
    return [
        CollapsableNode(arg, ctxt)
        for a_in in args
        for arg in (a_in.value if isinstance(a_in, ast.Starred) else [a_in])
    ]


@_log_call
def _resolve_keywords(keywords, ctxt):
    kwargs = {kw.arg: CollapsableNode(kw.value, ctxt) for kw in keywords}
    if None in kwargs:
        kwargs.update(kwargs[None])
        del kwargs[None]
    return kwargs

@_log_call
def _try_collapse(op, ctxt, *args):
    return _collapse_map[op](*[CollapsableNode(a, ctxt) for a in args])


from .literal import resolve_literal, make_ast_from_literal
from .iterable import resolve_iterable, pure_functions
from .indexable import resolve_indexable
