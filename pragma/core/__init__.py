import ast
import inspect

import astor
from miniutils.magic_contract import safe_new_contract


def _is_iterable(x):
    try:
        iter(x)
        return True
    except Exception:
        return False


safe_new_contract('iterable', _is_iterable)
safe_new_contract('literal', 'int|float|str|bool|tuple|list|None')
for name, tp in inspect.getmembers(ast, inspect.isclass):
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

from .stack import DictStack
from .resolve import *
from .transformer import *
