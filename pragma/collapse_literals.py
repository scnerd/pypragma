import ast

from .core import TrackedContextTransformer, make_function_transformer, resolve_literal


# noinspection PyPep8Naming
class CollapseTransformer(TrackedContextTransformer):
    def visit_Name(self, node):
        return resolve_literal(node, self.ctxt)

    def visit_BinOp(self, node):
        return resolve_literal(node, self.ctxt)

    def visit_UnaryOp(self, node):
        return resolve_literal(node, self.ctxt)

    def visit_BoolOp(self, node):
        return resolve_literal(node, self.ctxt)

    def visit_Compare(self, node):
        return resolve_literal(node, self.ctxt)

    def visit_Subscript(self, node):
        return resolve_literal(node, self.ctxt)

    def visit_If(self, node):
        cond = resolve_literal(node.test, self.ctxt, True)
        # print("Attempting to collapse IF conditioned on {}".format(cond))
        if not isinstance(cond, ast.AST):
            # print("Yes, this IF can be consolidated, condition is {}".format(bool(cond)))
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
            # print("No, this IF cannot be consolidated")
            return super().generic_visit(node)


# Collapse defined literal values, and operations thereof, where possible
collapse_literals = make_function_transformer(CollapseTransformer, 'collapse_literals',
                                              "Collapses literal expressions in the decorated function into single literals")
