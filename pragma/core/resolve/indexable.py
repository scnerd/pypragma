import ast
from miniutils import magic_contract
import logging
log = logging.getLogger(__name__)

from pragma.core import _log_call, DictStack


# def constant_dict(node, ctxt):
#     if isinstance(node, (ast.Name, ast.NameConstant, ast.Attribute)):
#         res = resolve_name_or_attribute(node, ctxt)
#         if hasattr(res, 'items'):
#             return dict(res.items())
#     return None
#

@_log_call
@magic_contract
def resolve_indexable(node, ctxt):
    """Resolves the given node to an object that can be indexed

    :param node: The AST node to be resolved, if possible
    :type node: AST
    :param ctxt: The current environment
    :type ctxt: DictStack
    :return: An object that can be indexed, returning an ast.AST value, if possible, else None
    :rtype: dict|None
    """
    iterable = resolve_iterable(node, ctxt)
    if iterable is not None:
        return dict(enumerate(iterable))

    obj = resolve_name_or_attribute(node, ctxt)
    if isinstance(obj, dict):
        return obj
    elif isinstance(obj, ast.Dict):
        return dict(zip(obj.keys, obj.values))


from pragma.core.resolve import resolve_name_or_attribute
from pragma.core.resolve.iterable import resolve_iterable
