import ast
import logging

from .core import TrackedContextTransformer, make_function_transformer, primitive_ast_types, iterable_ast_types

log = logging.getLogger(__name__)


# noinspection PyPep8Naming
class CollapseTransformer(TrackedContextTransformer):
    collapse_iterables = False

    def visit_Name(self, node):
        res = self.resolve_literal(node)
        if isinstance(res, primitive_ast_types):
            return res
        if isinstance(res, iterable_ast_types):
            if self.collapse_iterables:
                return res
            else:
                log.debug("Not collapsing iterable {}. Change this setting with collapse_literals(collapse_iterables=True)".format(res))
        return node

    def visit_BinOp(self, node):
        return self.resolve_literal(self.generic_visit(node))

    def visit_UnaryOp(self, node):
        return self.resolve_literal(self.generic_visit(node))

    def visit_BoolOp(self, node):
        return self.resolve_literal(self.generic_visit(node))

    def visit_Compare(self, node):
        return self.resolve_literal(self.generic_visit(node))

    def visit_Subscript(self, node):
        return self.resolve_literal(self.generic_visit(node))

    def _visit_AssignSubscriptTarget(self, target):
        def resolve_attr_of_slice(attr):
            old_val = getattr(target.slice, attr)
            if old_val is None:
                return
            new_val = self.resolve_literal(self.generic_visit(old_val))
            setattr(target.slice, attr, new_val)
        if isinstance(target.slice, ast.Index):
            resolve_attr_of_slice('value')
        elif isinstance(target.slice, ast.Slice):
            resolve_attr_of_slice('lower')
            resolve_attr_of_slice('upper')
            resolve_attr_of_slice('step')
        else:
            raise TypeError(type(target.slice))

    def visit_Assign(self, node):
        for it, target in enumerate(node.targets):
            if isinstance(target, ast.Subscript):
                self._visit_AssignSubscriptTarget(target)
        return super().visit_Assign(node)

    def visit_AugAssign(self, node):
        if isinstance(node.target, ast.Subscript):
            self._visit_AssignSubscriptTarget(node.target)
        return super().visit_AugAssign(node)

    def visit_Call(self, node):
        node = self.generic_visit(node)
        try:
            return self.resolve_literal(node)
        except (AssertionError, TypeError, KeyError, IndexError):
            return node

    def visit_If(self, node):
        cond = self.resolve_literal(node.test, raw=True)
        # print("Attempting to collapse IF conditioned on {}".format(cond))
        if not isinstance(cond, ast.AST):
            log.debug("Collapsing if condition ({} resolved to {})".format(node.test, cond))
            body = node.body if cond else node.orelse
            result = []
            for subnode in body:
                res = self.visit(subnode)
                if res is None:
                    pass
                elif isinstance(res, list):
                    result += res
                else:
                    result.append(res)
            return result
        else:
            return super().visit_If(node)


# Collapse defined literal values, and operations thereof, where possible
collapse_literals = make_function_transformer(CollapseTransformer, 'collapse_literals',
                                              "Collapses literal expressions in the decorated function into single literals")
