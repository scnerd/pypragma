from collections import OrderedDict as odict

from .core import *
import logging
log = logging.getLogger(__name__)

# stmt = FunctionDef(identifier name, arguments args,
#                        stmt* body, expr* decorator_list, expr? returns)
#           | AsyncFunctionDef(identifier name, arguments args,
#                              stmt* body, expr* decorator_list, expr? returns)
#
#           | ClassDef(identifier name,
#              expr* bases,
#              keyword* keywords,
#              stmt* body,
#              expr* decorator_list)
#           | Return(expr? value)
#
#           | Delete(expr* targets)
#           | Assign(expr* targets, expr value)
#           | AugAssign(expr target, operator op, expr value)
#           -- 'simple' indicates that we annotate simple name without parens
#           | AnnAssign(expr target, expr annotation, expr? value, int simple)
#
#           -- use 'orelse' because else is a keyword in target languages
#           | For(expr target, expr iter, stmt* body, stmt* orelse)
#           | AsyncFor(expr target, expr iter, stmt* body, stmt* orelse)
#           | While(expr test, stmt* body, stmt* orelse)
#           | If(expr test, stmt* body, stmt* orelse)
#           | With(withitem* items, stmt* body)
#           | AsyncWith(withitem* items, stmt* body)
#
#           | Raise(expr? exc, expr? cause)
#           | Try(stmt* body, excepthandler* handlers, stmt* orelse, stmt* finalbody)
#           | Assert(expr test, expr? msg)
#
#           | Import(alias* names)
#           | ImportFrom(identifier? module, alias* names, int? level)
#
#           | Global(identifier* names)
#           | Nonlocal(identifier* names)
#           | Expr(expr value)
#           | Pass | Break | Continue
#
#           -- XXX Jython will be different
#           -- col_offset is the byte offset in the utf8 string the parser uses
#           attributes (int lineno, int col_offset)


class _PRAGMA_INLINE_RETURN(BaseException):
    def __init__(self, val=None):
        super().__init__()
        self.return_val = val


DICT_FMT = "_{fname}_{n}"


# @magic_contract
def make_name(fname, var, n, ctx=ast.Load):
    """
    Create an AST node to represent the given argument name in the given function
    :param fname: Function name
    :type fname: str
    :param var: Argument name
    :type var: str
    :param ctx: Context of this name (LOAD or STORE)
    :type ctx: Load|Store
    :param n: The number to append to this name (to allow for finite recursion)
    :type n: int
    :param fmt: Name format (if not stored in a dictionary)
    :type fmt: str
    :return: An AST node representing this argument
    :rtype: Subscript|Call
    """
    return ast.Subscript(value=ast.Name(id=DICT_FMT.format(fname=fname, n=n), ctx=ast.Load()),
                         slice=ast.Index(ast.Str(var)),
                         ctx=ctx())


class _InlineBodyTransformer(TrackedContextTransformer):
    def __init__(self, func_name, param_names, n):
        self.func_name = func_name
        # print("Func {} takes parameters {}".format(func_name, param_names))
        self.local_names = set(param_names)
        self.nonlocal_names = set()
        self.has_global_catch = False
        self.n = n
        self.had_return = False
        self.had_yield = False
        super().__init__()

    def __setitem__(self, key, value):
        self.local_names.add(key)
        super().__setitem__(key, value)

    def visit_Global(self, node):
        self.nonlocal_names |= node.names
        self.local_names -= node.names
        return self.generic_visit(node)

    def visit_Nonlocal(self, node):
        self.nonlocal_names |= node.names
        self.local_names -= node.names
        return self.generic_visit(node)

    def visit_Name(self, node):
        # Check if this is a parameter, and hasn't had another value assigned to it
        # if node.id in self.param_names:
        #     # print("Found parameter reference {}".format(node.id))
        #     if node.id not in self.ctxt:
        #         # If so, get its value from the argument dictionary
        #         return make_name(self.func_name, node.id, self.n, ctx=type(getattr(node, 'ctx', ast.Load())))
        #     else:
        #         # print("But it's been overwritten to {} = {}".format(node.id, self.ctxt[node.id]))
        #         pass
        # return node
        if isinstance(node.ctx, ast.Store) and node.id not in self.nonlocal_names:
            self.local_names.add(node.id)

        if node.id in self.local_names:
            return make_name(self.func_name, node.id, self.n, ctx=type(getattr(node, 'ctx', ast.Load())))
        return node

    def visit_Return(self, node):
        # if self.in_break_block:
        #     raise NotImplementedError("miniutils.pragma.inline cannot handle returns from within a loop")
        # result = []
        # if node.value:
        #     result.append(ast.Assign(targets=[make_name(self.func_name, 'return', self.n, ctx=ast.Store)],
        #                              value=self.visit(node.value)))
        # result.append(ast.Break())
        self.had_return = True
        return ast.Raise(
            exc=ast.Call(
                func=ast.Name(id=_PRAGMA_INLINE_RETURN.__name__, ctx=ast.Load()),
                args=[self.visit(node.value)] if node.value is not None else [],
                keywords=[]
            ),
            cause=None
        )

    def visit_Yield(self, node):
        self.had_yield = True
        if node.value:
            return ast.Call(func=ast.Attribute(value=make_name(self.func_name, 'yield', self.n),
                                               attr='append',
                                               ctx=ast.Load()),
                            args=[self.visit(node.value)],
                            keywords=[])
        return node

    def visit_YieldFrom(self, node):
        self.had_yield = True
        return ast.Call(func=ast.Attribute(value=make_name(self.func_name, 'yield', self.n),
                                           attr='extend',
                                           ctx=ast.Load()),
                        args=[self.visit(node.value)],
                        keywords=[])

    def visit_ExceptHandler(self, node):
        node = self.generic_visit(node)
        if node.type is None or issubclass(BaseException, self.resolve_name_or_attribute(node.type)):
            self.has_global_catch = True
        return node


class InlineTransformer(TrackedContextTransformer):
    def __init__(self, *args, funs=None, max_depth=1, **kwargs):
        assert funs is not None
        super().__init__(*args, **kwargs)

        self.funs = funs
        self.max_depth = max_depth

    def visit_Call(self, node):
        """When we see a function call, insert the function body into the current code block, then replace the call
        with the return expression """

        node = self.generic_visit(node)
        node_fun = self.resolve_name_or_attribute(self.resolve_literal(node.func))

        try:
            fun, fname, fsig, fbody = next(f for f in self.funs if f[0] == node_fun)
        except StopIteration:
            return node

        possible_dict_names = ((i, DICT_FMT.format(fname=fname, n=i)) for i in range(self.max_depth))
        possible_dict_names = ((i, name) for i, name in possible_dict_names if name not in self.ctxt)
        try:
            n, args_dict_name = next(possible_dict_names)
        except StopIteration:
            warnings.warn("Inline hit recursion limit, using normal function call")
            return node

        func_for_inlining = _InlineBodyTransformer(fname, fsig.parameters, n)
        fbody = list(func_for_inlining.visit_many(copy.deepcopy(fbody)))

        if func_for_inlining.has_global_catch:
            warnings.warn("Unable to inline function with an unbound except statement")
            return node

        # print(self.code_blocks)
        cur_block = self.code_blocks[-1]
        new_code = []

        # Load arguments into their appropriate variables
        args = node.args
        flattened_args = []
        for a in args:
            if isinstance(a, ast.Starred):
                a = self.resolve_iterable(a.value)
                if a:
                    flattened_args.extend(a)
                else:
                    warnings.warn("Cannot inline function call that uses non-constant star args")
                    return node
            else:
                flattened_args.append(a)

        keywords = [(kw.arg, kw.value) for kw in node.keywords if kw.arg is not None]
        kw_dict = [kw.value for kw in node.keywords if kw.arg is None]
        kw_dict = kw_dict[0] if kw_dict else None

        bound_args = fsig.bind(*flattened_args, **odict(keywords))
        bound_args.apply_defaults()

        # Create args dictionary
        final_args = []
        final_kwargs = []

        for arg_name, arg_value in bound_args.arguments.items():
            if isinstance(arg_value, tuple):
                arg_value = ast.Tuple(elts=list(arg_value), ctx=ast.Load())
            elif isinstance(arg_value, dict):
                keys, values = zip(*list(arg_value.items()))
                keys = [ast.Str(k) for k in keys]
                values = list(values)
                arg_value = ast.Dict(keys=keys, values=values)
            # fun_name['param_name'] = param_value
            final_kwargs.append((arg_name, arg_value))

        if kw_dict:
            final_kwargs.append((None, kw_dict))

        if func_for_inlining.had_yield:
            final_args.append(ast.List(elts=[ast.Tuple(elts=[ast.Str('yield'), ast.List(elts=[], ctx=ast.Load())],
                                                       ctx=ast.Load())],
                                       ctx=ast.Load()))

        # fun_name = {}
        dict_call = ast.Call(
            func=ast.Name(id='dict', ctx=ast.Load()),
            args=final_args,
            keywords=[ast.keyword(arg=name, value=val) for name, val in final_kwargs]
        )
        new_code.append(ast.Assign(
            targets=[ast.Name(id=args_dict_name, ctx=ast.Store())],
            value=dict_call
        ))

        # Process assignments before resolving body
        cur_block.extend(self.visit_many(new_code))

        # Inline function code
        new_body = list(self.visit_many(fbody))

        for j in range(100000):
            output_name = DICT_FMT.format(fname=fname + '_return', n=j)
            if output_name not in self.ctxt:
                break
        else:
            raise RuntimeError("Function {} called and returned too many times during inlining, not able to "
                               "put the return value into a uniquely named variable".format(fname))

        return_node = ast.Name(id=output_name, ctx=ast.Load())

        if func_for_inlining.had_yield:
            afterwards_body = ast.Assign(targets=[ast.Name(id=output_name, ctx=ast.Store())],
                                         value=make_name(fname, 'yield', n))
        elif func_for_inlining.had_return:
            afterwards_body = ast.Assign(targets=[ast.Name(id=output_name, ctx=ast.Store())],
                                         value=ast.Attribute(
                                             value=ast.Name(id=output_name + "_exc", ctx=ast.Load()),
                                             attr='return_val',
                                             ctx=ast.Load()
                                         ))
        else:
            afterwards_body = ast.Pass()

        self.visit(afterwards_body)
        afterwards_body = [afterwards_body] if isinstance(afterwards_body, ast.AST) else afterwards_body

        if func_for_inlining.had_return:
            cur_block.append(ast.Try(
                body=new_body,
                handlers=[ast.ExceptHandler(
                    type=ast.Name(id=_PRAGMA_INLINE_RETURN.__name__, ctx=ast.Load()),
                    name=output_name + "_exc",
                    body=afterwards_body
                )],
                orelse=afterwards_body if func_for_inlining.had_yield else [
                    self.visit(ast.Assign(targets=[ast.Name(id=output_name, ctx=ast.Store())],
                                          value=ast.NameConstant(None)))
                ],
                finalbody=[
                    self.visit(ast.Delete(targets=[ast.Name(id=args_dict_name, ctx=ast.Del())]))
                ]
            ))
        else:
            cur_block.append(ast.Try(
                body=new_body,
                handlers=[],
                orelse=[],
                finalbody=(afterwards_body if not isinstance(afterwards_body[0], ast.Pass) else []) + [
                    self.visit(ast.Delete(targets=[ast.Name(id=args_dict_name, ctx=ast.Del())]))
                ]
            ))

        return return_node


# @magic_contract
def inline(*funs_to_inline, max_depth=1, **kwargs):
    """
    :param funs_to_inline: The inner called function that should be inlined in the wrapped function
    :type funs_to_inline: tuple(function)
    :param max_depth: The maximum number of times to inline the provided function (limits recursion)
    :type max_depth: int
    :return: The unrolled function, or its source code if requested
    :rtype: Callable
    """
    funs = []
    for fun_to_inline in funs_to_inline:
        fname = fun_to_inline.__name__
        fsig = inspect.signature(fun_to_inline)
        _, fbody, _ = function_ast(fun_to_inline)

        funs.append((fun_to_inline, fname, fsig, fbody))

    kwargs['function_globals'] = kwargs.get('function_globals', {})
    kwargs['function_globals'].update({_PRAGMA_INLINE_RETURN.__name__: _PRAGMA_INLINE_RETURN})
    # kwargs[_PRAGMA_INLINE_RETURN.__name__] = _PRAGMA_INLINE_RETURN
    return make_function_transformer(InlineTransformer,
                                     'inline',
                                     'Inline the specified function within the decorated function',
                                     funs=funs,
                                     max_depth=max_depth)(**kwargs)
