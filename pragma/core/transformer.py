# import ast
import copy
import inspect
import sys
import tempfile
import textwrap

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


class DebugTransformerMixin:  # pragma: nocover
    def visit(self, node):
        orig_node_code = astor.to_source(node).strip()
        print("Starting to visit >> {} <<".format(orig_node_code))

        new_node = super().visit(node)

        try:
            if new_node is None:
                print("Deleted >>> {} <<<".format(orig_node_code))
            elif isinstance(new_node, ast.AST):
                print("Converted >>> {} <<< to >>> {} <<<".format(orig_node_code, astor.to_source(new_node).strip()))
            elif isinstance(new_node, list):
                print("Converted >>> {} <<< to [[[ {} ]]]".format(orig_node_code, ", ".join(
                    astor.to_source(n).strip() for n in new_node)))
        except Exception as ex:
            raise AssertionError("Failed on {} >>> {}".format(orig_node_code, astor.dump_tree(new_node))) from ex
            # print("Failed on {} >>> {}".format(astor.dump_tree(orig_node), astor.dump_tree(new_node)))
            # return orig_node

        return new_node


class TrackedContextTransformer(ast.NodeTransformer):
    def __init__(self, ctxt=None):
        self.ctxt = ctxt or DictStack()
        super().__init__()

    def visit_many(self, nodes):
        for n in nodes:
            n = self.visit(n)
            if n is not None:
                if isinstance(n, ast.AST):
                    yield n
                else:
                    yield from n

    def visit_Assign(self, node):
        node.value = self.visit(node.value)
        erase_targets = True
        # print(node.value)
        # TODO: Support tuple assignments
        if len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name):
                nvalue = copy.deepcopy(node.value)
                var = node.targets[0].id
                val = constant_iterable(nvalue, self.ctxt)
                if val is not None:
                    # print("Setting {} = {}".format(var, val))
                    self.ctxt[var] = val
                else:
                    val = resolve_literal(nvalue, self.ctxt)
                    # print("Setting {} = {}".format(var, val))
                    self.ctxt[var] = val
                erase_targets = False
            # elif isinstance(node.targets[0], ast.Subscript):
            #     targ = node.targets[0]
            #     iterable = constant_iterable(targ.value, self.ctxt, False)
            #     if iterable is None:
            #         iterable = constant_dict(targ.value, self.ctxt)
            #     if iterable is None:
            #         return node
            #     key = resolve_literal(targ.slice, self.ctxt)
            #     if isinstance(key, ast.AST):
            #         return node
            #
            #     nvalue = copy.deepcopy(node.value)
            #     val = constant_iterable(nvalue, self.ctxt)
            #     warnings.warn("Iterable assignment not fully implemented yet...")
            #     if val is not None:
            #         # print("Setting {} = {}".format(var, val))
            #         iterable[key] = val
            #     else:
            #         val = resolve_literal(nvalue, self.ctxt)
            #         # print("Setting {} = {}".format(var, val))
            #         iterable[key] = val
            #     erase_targets = False

        if erase_targets:
            for targ in node.targets:
                for assgn in _assign_names(targ):
                    self.ctxt[assgn] = None
        return node

    def visit_AugAssign(self, node):
        for assgn in _assign_names(node.target):
            self.ctxt[assgn] = None
        return super().generic_visit(node)

    def visit_Delete(self, node):
        for targ in node.targets:
            for assgn in _assign_names(targ):
                del self.ctxt[assgn]
        return super().generic_visit(node)

    def visit_FunctionDef(self, node):
        self.ctxt.push({}, False)
        node.body = list(self.visit_many(node.body))
        self.ctxt.pop()
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.ctxt.push({}, False)
        node.body = list(self.visit_many(node.body))
        self.ctxt.pop()
        return self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.ctxt.push({}, False)
        node.body = list(self.visit_many(node.body))
        self.ctxt.pop()
        return self.generic_visit(node)


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
                except ImportError:  # pragma: nocover
                    raise ImportError("miniutils.pragma.{name} requires 'astor' to be installed to obtain source code"
                                      .format(name=name))
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
