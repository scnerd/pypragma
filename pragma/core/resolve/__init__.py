import ast

from pragma.core import _log_call, log
from pragma.core.resolve.literal import log
from .indexable import resolve_indexable
from .iterable import resolve_iterable
from .literal import resolve_literal


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