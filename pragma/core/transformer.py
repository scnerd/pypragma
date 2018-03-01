# import ast
import copy
# import inspect
import sys
import tempfile
import textwrap
# import logging

import astor
from miniutils.opt_decorator import optional_argument_decorator

from .resolve import *
from .stack import DictStack


@magic_contract
def function_ast(f):
    """
    Returns ast for the given function. Gives a tuple of (ast_module, function_body, function_file
    :param f: The function to parse
    :type f: Callable
    :return: The relevant AST code: A module including only the function definition; the func body; the func file
    :rtype: tuple(Module, list(AST), str)
    """
    try:
        f_file = sys.modules[f.__module__].__file__
    except (KeyError, AttributeError):
        f_file = ''

    root = ast.parse(textwrap.dedent(inspect.getsource(f)), f_file)
    return root, root.body[0].body, f_file


@magic_contract
def _assign_names(node):
    """
    Gets names from a assign-to tuple in flat form, just to know what's affected
    "x=3" -> "x"
    "a,b=4,5" -> ["a", "b"]
    "(x,(y,z)),(a,) = something" -> ["x", "y", "z", "a"]

    :param node: The AST node to resolve to a list of names
    :type node: AST
    :return: The flattened list of names referenced in this node
    :rtype: iterable
    """
    if isinstance(node, ast.Name):
        yield node.id
    elif isinstance(node, ast.Tuple):
        for e in node.elts:
            yield from _assign_names(e)
    elif isinstance(node, ast.Subscript):
        yield from _assign_names(node.value)
    elif isinstance(node, (tuple, list)):
        for e in node:
            yield from _assign_names(e)


class DebugTransformerMixin:  # pragma: nocover
    def visit(self, node):
        orig_node_code = astor.to_source(node).strip()
        log.debug("Starting to visit >> {} <<".format(orig_node_code))

        new_node = super().visit(node)

        try:
            if new_node is None:
                log.debug("Deleted >>> {} <<<".format(orig_node_code))
            elif isinstance(new_node, ast.AST):
                log.debug("Converted >>> {} <<< to >>> {} <<<".format(orig_node_code, astor.to_source(new_node).strip()))
            elif isinstance(new_node, list):
                log.debug("Converted >>> {} <<< to [[[ {} ]]]".format(orig_node_code, ", ".join(
                    astor.to_source(n).strip() for n in new_node)))
        except Exception as ex:
            raise AssertionError("Failed on {} >>> {}".format(orig_node_code, astor.dump_tree(new_node))) from ex

        return new_node


class TrackedContextTransformer(ast.NodeTransformer):
    def __init__(self, ctxt=None):
        super().__init__()
        self.ctxt = ctxt or DictStack()
        self.conditional_execution = False
        self.in_main_func = False
        self.code_blocks = []

    def visit_many(self, nodes):
        for n in nodes:
            n = self.visit(n)
            if n is None:
                continue
            elif isinstance(n, (list, tuple)):
                yield from n
            else:
                yield n

    def nested_visit(self, nodes, set_conditional_exec=True):
        """When we visit a block of statements, create a new "code block" and push statements into it"""
        was_conditional_exec = self.conditional_execution
        if set_conditional_exec:
            self.conditional_execution = True

        lst = []
        self.code_blocks.append(lst)

        for line in self.visit_many(nodes):
            lst.append(line)

        self.code_blocks.pop()

        self.conditional_execution = was_conditional_exec
        return lst

    def resolve_literal(self, node):
        log.debug("Attempting to resolve {}".format(node))
        resolution = resolve_literal(node, self.ctxt)
        log.debug("Resolved {} to {}".format(node, resolution) if resolution is not node
                  else "Failed to resolve {}".format(node))
        return resolution

    def constant_iterable(self, node):
        log.debug("Attempting to resolve {} as iterable".format(node))
        resolution = constant_iterable(node, self.ctxt)
        log.debug("Resolved {} to {}".format(node, resolution) if resolution is not None
                  else "Failed to resolve {} as iterable".format(node))
        return resolution

    def generic_visit_less(self, node, *without):
        for field, old_value in ast.iter_fields(node):
            if field in without:
                continue
            elif isinstance(old_value, list):
                new_values = []
                for value in old_value:
                    if isinstance(value, ast.AST):
                        value = self.visit(value)
                        if value is None:
                            continue
                        elif not isinstance(value, ast.AST):
                            new_values.extend(value)
                            continue
                    new_values.append(value)
                old_value[:] = new_values
            elif isinstance(old_value, ast.AST):
                new_node = self.visit(old_value)
                if new_node is None:
                    delattr(node, field)
                else:
                    setattr(node, field, new_node)
        return node

    def __setitem__(self, key, value):
        log.debug("Context setting {} to {}".format(key, "?UNKNOWN?" if value is None else astor.to_source(value).strip()))
        self.ctxt[key] = value

    def __getitem__(self, item):
        res = self.ctxt[item]
        log.debug("Context resolving {} to {}".format(item, "?UNKNOWN?" if res is None else astor.to_source(res).strip()))
        return res

    def __delitem__(self, key):
        log.debug("Context deleting {}".format(key))
        del self.ctxt[key]

    def _assign(self, name, val):
        if isinstance(name, (ast.Tuple, tuple, list)):  # (a, b) = ...
            if isinstance(name, ast.Tuple):
                names = name.elts
            else:
                names = name
            if len(names) == 1:
                self._assign(names[0], val)
            elif val is None or self.conditional_execution:  # Something above us failed, we have no idea what this value is getting assigned
                for subname in names:
                    self._assign(subname, None)
            else:
                iterable_val = self.constant_iterable(val)
                if iterable_val is not None:  # (a, b) = 1, 2
                    iterable_val = iter(iterable_val)
                    try:
                        for subname in names:
                            if isinstance(subname, ast.Starred):  # (a, _*b_) = 1, _2, 3_
                                self._assign(subname.value, list(iterable_val))
                            else:  # (_a_, b) = _1_, 2
                                self._assign(subname, next(iterable_val))
                    except StopIteration:
                        raise IndexError("Failed to unpack {} into {}, either had too few elements or values after a starred variable".format(val, name))
                else:
                    self._assign(name, None)

        elif isinstance(name, ast.Name):  # a = ...
            if val is None or self.conditional_execution:  # a = ???
                self[name.id] = None
            else:
                literal_val = self.resolve_literal(val)
                if not isinstance(literal_val, ast.AST):  # a = 5
                    self[name.id] = make_ast_from_literal(literal_val)
                else:  # a = f(x)
                    self[name.id] = make_ast_from_literal(self.constant_iterable(val)) or val
                    # self[name.id] = val

        elif isinstance(name, ast.Attribute):  # a.x = ...
            log.debug("Can't handle assignment to attributes yet")

        elif isinstance(name, ast.Subscript):  # ...[i] = ...
            arr = name.value
            if val is None or self.conditional_execution:  # a[i] = ???
                log.debug("Partial assignment to an iterable is not yet supported, killing entire iterable")
                self._assign(arr, None)
            elif isinstance(arr, ast.Name):  # a[i] = ...
                idx = name.slice
                cur_iterable = self.constant_iterable(arr)
                if cur_iterable is not None:  # a[i] = ... where a = [1,2,3]
                    literal_idx = self.resolve_literal(idx)
                    if not isinstance(literal_idx, ast.AST):  # a[i] = ... where a = [1,2,3], i =
                        try:
                            cur_iterable[literal_idx] = val
                        except (IndexError, KeyError):
                            raise IndexError("Cannot assigned {arr}[{idx}] = {set} where {arr}={arr_val} and {idx}={idx_val}".format(
                                arr=arr.id, idx=idx, set=val, arr_val=cur_iterable, idx_val=literal_idx
                            ))
                        self[arr.id] = make_ast_from_literal(cur_iterable)
                    else:  # a[???] = val
                        self[arr.id] = None
                else:  # ???[i] = val
                    self[arr.id] = None
            else:  # a.x[i] = val, or f(x)[i] = val
                log.debug("Can't handle assignment to subscript of non-variables yet")

        else:  # wtf?
            log.warning("Unhandled assignment of {} to {}".format(val, name))

    def visit_Assign(self, node):
        node.value = self.visit(node.value)
        self._assign(node.targets, node.value)
        return node

    def visit_AugAssign(self, node):
        node = copy.deepcopy(node)
        node.value = self.visit(node.value)
        new_val = self.resolve_literal(ast.BinOp(op=node.op, left=node.target, right=node.value))
        if not isinstance(new_val, ast.BinOp):
            self._assign(node.target, new_val)
        else:
            self._assign(node.target, None)
        return node

    def visit_Delete(self, node):
        for targ in node.targets:
            for assgn in _assign_names(targ):
                del self[assgn]
        return self.generic_visit(node)

    ###################################################
    # From here on down, we just have handlers for every AST node that has a "code block" (stmt*)
    ###################################################

    def visit_FunctionDef(self, node):
        if not self.in_main_func:
            self.ctxt.push({}, False)
            node.body = self.nested_visit(node.body, set_conditional_exec=False)
            self.ctxt.pop()
            return self.generic_visit_less(node, 'body')
        else:
            return node

    def visit_AsyncFunctionDef(self, node):
        return self.visit_FunctionDef(node)

    def visit_ClassDef(self, node):
        # self.ctxt.push({}, False)
        # node.body = self.nested_visit(node.body)
        # self.ctxt.pop()
        # return self.generic_visit_less(node, 'body')
        return node

    def visit_For(self, node):
        node.iter = self.visit(node.iter)
        node.body = self.nested_visit(node.body)
        node.orelse = self.nested_visit(node.orelse)
        return self.generic_visit_less(node, 'body', 'orelse', 'iter')

    def visit_AsyncFor(self, node):
        node.iter = self.visit(node.iter)
        node.body = self.nested_visit(node.body)
        node.orelse = self.nested_visit(node.orelse)
        return self.generic_visit_less(node, 'body', 'orelse', 'iter')

    def visit_While(self, node):
        node.body = self.nested_visit(node.body)
        node.orelse = self.nested_visit(node.orelse)
        return self.generic_visit_less(node, 'body', 'orelse')

    def visit_If(self, node):
        node.test = self.visit(node.test)
        node.body = self.nested_visit(node.body)
        node.orelse = self.nested_visit(node.orelse)
        return self.generic_visit_less(node, 'body', 'orelse', 'test')

    def visit_With(self, node):
        node.body = self.nested_visit(node.body, set_conditional_exec=False)
        return self.generic_visit_less(node, 'body')

    def visit_AsyncWith(self, node):
        node.body = self.nested_visit(node.body, set_conditional_exec=False)
        return self.generic_visit_less(node, 'body')

    def visit_Try(self, node):
        node.body = self.nested_visit(node.body)
        node.orelse = self.nested_visit(node.orelse)
        node.finalbody = self.nested_visit(node.finalbody, set_conditional_exec=False)
        return self.generic_visit_less(node, 'body', 'orelse', 'finalbody')

    def visit_Module(self, node):
        node.body = self.nested_visit(node.body, set_conditional_exec=False)
        return self.generic_visit_less(node, 'body')

    def visit_ExceptHandler(self, node):
        node.body = self.nested_visit(node.body)
        return self.generic_visit_less(node, 'body')


def make_function_transformer(transformer_type, name, description, **transformer_kwargs):
    @optional_argument_decorator
    @magic_contract
    def transform(return_source=False, save_source=True, function_globals=None, **kwargs):
        """
        :param return_source: Returns the transformed function's source code instead of compiling it
        :type return_source: bool
        :param save_source: Saves the function source code to a tempfile to make it inspectable
        :type save_source: bool
        :param function_globals: Overridden global name assignments to use when processing the function
        :type function_globals: dict|None
        :param kwargs: Any other environmental variables to provide during unrolling
        :type kwargs: dict
        :return: The transformed function, or its source code if requested
        :rtype: Callable
        """

        @magic_contract(f='Callable', returns='Callable|str')
        def inner(f):
            f_mod, f_body, f_file = function_ast(f)
            # Grab function globals
            glbls = f.__globals__
            # Grab function closure variables
            if isinstance(f.__closure__, tuple):
                glbls.update({k: v.cell_contents for k, v in zip(f.__code__.co_freevars, f.__closure__)})
            # Apply manual globals override
            if function_globals is not None:
                glbls.update(function_globals)
            # print({k: v for k, v in glbls.items() if k not in globals()})
            trans = transformer_type(DictStack(glbls, kwargs), **transformer_kwargs)
            f_mod.body[0].decorator_list = []
            f_mod = trans.visit(f_mod)
            # print(astor.dump_tree(f_mod))
            if return_source or save_source:
                try:
                    source = astor.to_source(f_mod)
                except Exception as ex:  # pragma: nocover
                    raise RuntimeError(astor.dump_tree(f_mod)) from ex
            else:
                source = None

            if return_source:
                return source
            else:
                f_mod = ast.fix_missing_locations(f_mod)
                if save_source:
                    temp = tempfile.NamedTemporaryFile('w', delete=True)
                    f_file = temp.name
                exec(compile(f_mod, f_file, 'exec'), glbls)
                func = glbls[f_mod.body[0].name]
                if save_source:
                    func.__tempfile__ = temp
                    temp.write(source)
                    temp.flush()
                return func

        return inner

    transform.__name__ = name
    transform.__doc__ = '\n'.join([description, transform.__doc__])
    return transform
