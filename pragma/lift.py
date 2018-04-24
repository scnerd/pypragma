import ast
import astor
import tempfile
import sys
from miniutils import magic_contract, optional_argument_decorator
from types import ModuleType
import logging
log = logging.getLogger(__name__)

from .core import TrackedContextTransformer, make_function_transformer, resolve_literal
from .core.transformer import function_ast
from .core.resolve import make_ast_from_literal

_exclude = {'__builtin__', '__builtins__', 'builtin', 'builtins'}
if sys.version_info < (3, 6):
    _ast_str_types = ast.Str
else:
    _ast_str_types = (ast.Str, ast.JoinedStr)


@optional_argument_decorator
@magic_contract
def lift(return_source=False, save_source=True, annotate_types=False, defaults=False, lift_globals=None, imports=True):
    """Converts a closure or method into a pure function which accepts locally defined variables as keyword arguments

    :param return_source: Returns the transformed function's source code instead of compiling it
    :type return_source: bool
    :param save_source: Saves the function source code to a tempfile to make it inspectable
    :type save_source: bool
    :param annotate_types: Flag (or list of var names, or mapping) to use the types of closure variables as the type annotation of the keyword arguments
    :type annotate_types: bool|list|set|tuple|dict
    :param defaults: Default values for free arguments. Must be a dictionary of literals or AST expression, or a bool in which case a best effort is made to convert the closure values into default values
    :type defaults: bool|list|set|tuple|dict
    :param lift_globals: List of global variables to lift to keyword arguments
    :type lift_globals: None|list|set|tuple
    :param imports: Flag or list of imports to include within the function body
    :type imports: bool|list|set|tuple
    :return: The transformed function, or its source code if requested
    :rtype: Callable
    """

    @magic_contract(f='Callable', returns='Callable|str')
    def inner(f):
        f_mod, f_body, f_file = function_ast(f)
        # Grab function closure variables
        add_imports = []

        if isinstance(f.__closure__, tuple):
            free_vars = [(k, v.cell_contents) for k, v in zip(f.__code__.co_freevars, f.__closure__)]
        else:
            free_vars = []

        for glbl in lift_globals or []:
            free_vars.append((glbl, f.__globals__[glbl]))

        if imports:
            for k, v in f.__globals__.items():
                if isinstance(v, ModuleType):
                    add_imports.append((k, v))

            old_free_vars = free_vars
            free_vars = []
            for k, v in old_free_vars:
                if isinstance(v, ModuleType):
                    add_imports.append((k, v))
                else:
                    free_vars.append((k, v))

            if isinstance(f_body[0], ast.Expr) and isinstance(f_body[0].value, _ast_str_types):
                f_docstring = f_body[:1]
                f_body = f_body[1:]
            else:
                f_docstring = []

            f_body = f_docstring + [
                ast.Import(names=[ast.alias(name=v.__name__, asname=k if k != v.__name__ else None)])
                for k, v in add_imports
                if (isinstance(imports, bool) or k in imports) and k not in _exclude
            ] + f_body

        func_def = f_mod.body[0]

        def annotate(k, v):
            if annotate_types:
                if isinstance(annotate_types, bool):
                    return ast.Name(id=type(v).__name__, ctx=ast.Load())
                elif isinstance(annotate_types, (tuple, list, set)):
                    if k in annotate_types:
                        return ast.Name(id=type(v).__name__, ctx=ast.Load())
                elif isinstance(annotate_types, dict):
                    if k in annotate_types:
                        result = annotate_types[k]
                        if isinstance(result, str):
                            result = ast.Str(s=result)
                        if result and not isinstance(result, ast.expr):
                            raise TypeError("Type annotation must be a string or AST expression (got {})".format(result))
                        return result
            return None

        def get_default(k, v):
            if defaults:
                if isinstance(defaults, bool):
                    attempt = v
                elif isinstance(defaults, (tuple, list, set)):
                    if k in defaults:
                        attempt = v
                    else:
                        return None
                elif isinstance(defaults, dict):
                    if k in defaults:
                        attempt = defaults[k]
                    else:
                        return None
                else:
                    return None
                attempted = make_ast_from_literal(attempt)
                if isinstance(attempted, ast.expr):
                    return attempted
                else:
                    log.debug("Failed to convert {} to an AST expression (got {})".format(attempt, attempted))
                    return None

            return None

        new_kws = [ast.arg(arg=k, annotation=annotate(k, v)) for k, v in free_vars]
        new_kw_defaults = [get_default(k, v) for k, v in free_vars]

        new_func_def = ast.FunctionDef(
            name=func_def.name,
            body=f_body,
            decorator_list=[],  # func_def.decorator_list,
            returns=func_def.returns,
            args=ast.arguments(
                args=func_def.args.args,
                vararg=func_def.args.vararg,
                kwarg=func_def.args.kwarg,
                defaults=func_def.args.defaults,
                kwonlyargs=func_def.args.kwonlyargs + new_kws,
                kw_defaults=func_def.args.kw_defaults + new_kw_defaults
            )
        )

        f_mod.body[0] = new_func_def

        if return_source or save_source:
            try:
                source = astor.to_source(f_mod)
            except ImportError:  # pragma: nocover
                raise ImportError("miniutils.pragma.{name} requires 'astor' to be installed to obtain source code"
                                  .format(name=lift.__name__))
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
            no_globals = {}
            exec(compile(f_mod, f_file, 'exec'), no_globals)
            func = no_globals[f_mod.body[0].name]
            if save_source:
                func.__tempfile__ = temp
                temp.write(source)
                temp.flush()
            return func

    return inner
