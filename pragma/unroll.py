import ast
import copy
import logging
import math
import warnings
from .core import TrackedContextTransformer, make_function_transformer, make_ast_from_literal

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
        self.unroll_targets = None
        self.unroll_in_tiers = None
        super().__init__(*args, **kwargs)
        self.loop_vars = []

    def _names(self, node):
        if isinstance(node, ast.Name):
            yield node.id
        elif isinstance(node, ast.Tuple):
            for elt in node.elts:
                yield from self._names(elt)
        else:
            warnings.warn(
                "Not sure how to handle {} in a for loop target list yet".format(astor.to_source(node).strip()))

    def visit_For(self, node):
        if self.unroll_in_tiers is not None:
            try:
                var, N, n_inner = self.unroll_in_tiers
            except ValueError as err:
                raise ValueError("Invalid specification of unroll_in_tiers: should be tuple(str, int, int)") from err
            if n_inner is None:
                n_inner = 1
            if isinstance(node.iter, ast.Name) and node.iter.id == var:
                return self._visit_ForTiered(node)
            else:
                return self.generic_visit(node)
        else:
            if self.unroll_targets is not None and node.target.id not in self.unroll_targets:
                return self.generic_visit(node)
        return self._visit_ForFlat(node)

    def _visit_ForFlat(self, node, offset=None):
        iterable = self.resolve_iterable(node.iter)
        if iterable is None:
            return self.generic_visit(node)

        if offset is not None:
            if isinstance(offset, int):
                offset = ast.Num(n=offset)
            elif isinstance(offset, str):
                offset = ast.Name(id=offset, ctx=ast.Load())
            elif not isinstance(offset, ast.AST):
                raise TypeError('offset must be an integer, string, or AST type')

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
                log.debug("Failed to unroll loop, %s failed to convert to AST", val)
                return self.generic_visit(node)

            if offset is not None:
                val = ast.BinOp(left=offset, op=ast.Add(), right=val)

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

    def _visit_ForTiered(self, node):
        var, N, n_inner = self.unroll_in_tiers
        n_outer = math.floor(N / n_inner)
        outer_iterable = range(0, n_inner * n_outer, n_inner)
        inner_iterable = list(range(n_inner))
        remainder_iterable = list(range(N % n_inner))

        if n_inner > N // 2:
            node.iter = make_ast_from_literal(list(range(N)))
            return self._visit_ForFlat(node)

        inner_node = ast.For(iter=make_ast_from_literal(inner_iterable),
                             target=node.target, body=node.body, orelse=[])
        inner_node = self._visit_ForFlat(inner_node, offset='PRAGMA_iouter')

        remainder_node = ast.For(iter=make_ast_from_literal(remainder_iterable),
                                 target=node.target, body=node.body, orelse=[])
        remainder_node = self._visit_ForFlat(remainder_node, offset=n_outer * n_inner)

        ast_range_fun = ast.Name(id='range', ctx=ast.Load())
        ast_range_args = [ast.Num(outer_iterable.start), ast.Num(outer_iterable.stop), ast.Num(outer_iterable.step)]
        ast_range_call = ast.Call(func=ast_range_fun, args=ast_range_args, keywords=[])

        outer_node = ast.For(iter=ast_range_call,
                             target=ast.Name(id='PRAGMA_iouter', ctx=ast.Store()), body=inner_node, orelse=[])

        if isinstance(remainder_node, list):
            return [outer_node] + remainder_node
        elif remainder_node is None:
            return outer_node
        else:
            return [outer_node, remainder_node]

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and self.loop_vars and node.id in set.union(*self.loop_vars):
            if node.id in self.ctxt:
                return self.ctxt[node.id]
            raise NameError("'{}' not defined in context".format(node.id))
        return node

    def visit_Subscript(self, node):
        # resolve only if node is an ast.Name in our loop_vars
        if (isinstance(node.value, ast.Name) and isinstance(node.value.ctx, ast.Load)
                and self.loop_vars and node.value.id in set.union(*self.loop_vars)):
            return self.resolve_literal(self.generic_visit(node))
        return self.generic_visit(node)

    def _visit_Assign_withSubscriptLHS(self, target):
        def resolve_attr_of_slice(attr):
            old_val = getattr(target.slice, attr)
            if old_val is None:
                return
            new_val = self.visit(old_val)
            setattr(target.slice, attr, new_val)

        target.value = self.generic_visit(target.value)
        if isinstance(target.slice, ast.Index):
            resolve_attr_of_slice('value')
        elif isinstance(target.slice, ast.Slice):
            resolve_attr_of_slice('lower')
            resolve_attr_of_slice('upper')
            resolve_attr_of_slice('step')
        else:
            target.slice = self.visit(target.slice)  # The index could be anything in 3.8+
            # raise TypeError(type(target.slice))

    def visit_Assign(self, node):
        for it, target in enumerate(node.targets):
            if isinstance(target, ast.Subscript):
                self._visit_Assign_withSubscriptLHS(target)
        return super().visit_Assign(node)

    def visit_AugAssign(self, node):
        if isinstance(node.target, ast.Subscript):
            self._visit_Assign_withSubscriptLHS(node.target)
        return super().visit_AugAssign(node)


# Unroll literal loops
unroll = make_function_transformer(UnrollTransformer, 'unroll', "Unrolls constant loops in the decorated function")
