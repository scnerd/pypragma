import ast

from .core import TrackedContextTransformer, make_function_transformer, resolve_literal, log


# noinspection PyPep8Naming
class CollapseTransformer(TrackedContextTransformer):
    def visit_Name(self, node):
        return self.resolve_literal(node)

    def visit_BinOp(self, node):
        return self.resolve_literal(self.generic_visit(node))

    def visit_UnaryOp(self, node):
        return self.resolve_literal(self.generic_visit(node))

    def visit_BoolOp(self, node):
        return self.resolve_literal(self.generic_visit(node))

    def visit_Compare(self, node):
        return self.resolve_literal(self.generic_visit(node))

    def visit_Subscript(self, node):
        return self.resolve_literal(node)

    def visit_Call(self, node):
        return self.resolve_literal(self.generic_visit(node))

    def visit_If(self, node):
        cond = resolve_literal(node.test, self.ctxt, True)
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
