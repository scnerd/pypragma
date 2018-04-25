import warnings

from .core import *
import logging
log = logging.getLogger(__name__)


def has_break(node):
    for field, value in ast.iter_fields(node):
        if isinstance(value, list):
            for item in value:
                if isinstance(item, (ast.Break, ast.Continue)):
                    return True
                if isinstance(item, ast.AST):
                    if has_break(item):
                        return True
        elif isinstance(value, ast.AST):
            if has_break(value):
                return True
    return False


# noinspection PyPep8Naming
class UnrollTransformer(TrackedContextTransformer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop_vars = []

    def _names(self, node):
        if isinstance(node, ast.Name):
            yield node.id
        elif isinstance(node, ast.Tuple):
            for elt in node.elts:
                yield from self._names(elt)
        else:
            warnings.warn("Not sure how to handle {} in a for loop target list yet".format(astor.to_source(node).strip()))

    def visit_For(self, node):
        iterable = self.resolve_iterable(node.iter)
        if iterable is None:
            return self.generic_visit(node)

        top_level_break = False
        for n in node.body:
            if isinstance(n, ast.Break):
                top_level_break = True
            # We don't need to check if there's a break in an inner loop, since that doesn't affect this loop
            elif isinstance(n, ast.If) and has_break(n):
                # If there's a conditional break, there's not much we can do about that
                # TODO: If the conditional is resolvable at unroll time, then do so
                return self.generic_visit(node)

        result = []
        # loop_var = node.target.id
        # orig_loop_vars = self.loop_vars
        # print("Unrolling 'for {} in {}'".format(loop_var, list(iterable)))
        for val in iterable:
            # self.ctxt.push({loop_var: val})
            # self.loop_vars = orig_loop_vars | {loop_var}
            # self.ctxt.push()
            # self.visit(ast.Assign(targets=(node.target,), value=make_ast_from_literal(val)))
            try:
                val = make_ast_from_literal(val)
            except TypeError:
                log.debug("Failed to unroll loop, {} failed to convert to AST".format(val))
                return self.generic_visit(node)
            self.loop_vars.append(set(self.assign(node.target, val)))
            for body_node in copy.deepcopy(node.body):
                res = self.visit(body_node)
                if isinstance(res, list):
                    result.extend(res)
                elif res is None:
                    continue
                else:
                    result.append(res)
            # result.extend([self.visit(body_node) for body_node in copy.deepcopy(node.body)])
            # self.ctxt.pop()
            if top_level_break:
                first_result = result
                result = []
                for n in first_result:
                    if isinstance(n, ast.Break):
                        break
                    result.append(n)
                break
        # self.loop_vars = orig_loop_vars
        return result

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and self.loop_vars and node.id in set.union(*self.loop_vars):
            if node.id in self.ctxt:
                return self.ctxt[node.id]
            raise NameError("'{}' not defined in context".format(node.id))
        return node


# Unroll literal loops
unroll = make_function_transformer(UnrollTransformer, 'unroll', "Unrolls constant loops in the decorated function")
