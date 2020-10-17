import ast
import inspect
import logging
import functools

import astor
from miniutils.magic_contract import safe_new_contract

log = logging.getLogger(__name__.split('.')[0])


def _is_iterable(x):
    return hasattr(x, '__iter__')

def _is_indexable(x):
    return hasattr(x, '__getitem__')


safe_new_contract('iterable', _is_iterable)
safe_new_contract('indexable', _is_indexable)
safe_new_contract('literal', 'int|float|str|bool|tuple|list|None')
for name, tp in inspect.getmembers(ast, inspect.isclass):
    if name[0] == '_':  # python 3.8 added ast._AST which pycontracts does not like
        continue
    safe_new_contract(name, tp)

# Astor tries to get fancy by failing nicely, but in doing so they fail when traversing non-AST type node properties.
#  By deleting this custom handler, it'll fall back to the default ast visit pattern, which skips these missing
# properties. Everything else seems to be implemented, so this will fail silently if it hits an AST node that isn't
# supported but should be.
try:
    del astor.node_util.ExplicitNodeVisitor.visit
except AttributeError:
    # visit isn't defined in this version of astor
    pass


def _pretty_str(o):
    if isinstance(o, ast.AST):
        if isinstance(o, ast.Name):
            return o.id
        elif isinstance(o, ast.Call):
            return "{}(...)".format(_pretty_str(o.func))
        elif isinstance(o, ast.Attribute):
            return "{}.{}".format(_pretty_str(o.value), o.attr)

        return astor.to_source(o).strip()
    else:
        return repr(o)


_log_call_depth = 0


def _log_call(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        global _log_call_depth

        result = None
        ex = None
        log.debug("START {}{}({})".format(
            ' ' * _log_call_depth,
            f.__name__,
            ', '.join(
                [_pretty_str(a) for a in args] +
                ["{}={}".format(_pretty_str(k), _pretty_str(v)) for k, v in kwargs.items()]
            )
        ))

        _log_call_depth += 1
        try:
            result = f(*args, **kwargs)
            return result

        except Exception as e:
            ex = e
            raise e
        finally:
            _log_call_depth -= 1

            log.debug("END   {}{}({}) -> {}".format(
                ' ' * _log_call_depth,
                f.__name__,
                ', '.join(
                    [_pretty_str(a) for a in args] +
                    ["{}={}".format(_pretty_str(k), _pretty_str(v)) for k, v in kwargs.items()]
                ),
                _pretty_str(result)
            ), exc_info=ex)

    return inner


from .stack import DictStack
from .resolve import *
from .transformer import *
