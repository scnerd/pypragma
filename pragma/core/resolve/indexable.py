import ast

from pragma.core import resolve_name_or_attribute


def constant_dict(node, ctxt):
    if isinstance(node, (ast.Name, ast.NameConstant, ast.Attribute)):
        res = resolve_name_or_attribute(node, ctxt)
        if hasattr(res, 'items'):
            return dict(res.items())
    return None

def resolve_indexable(node, ctxt):
    pass