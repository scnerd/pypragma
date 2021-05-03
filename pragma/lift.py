import ast
import logging
import sys
import tempfile
from types import ModuleType

import astor
from miniutils import magic_contract, optional_argument_decorator

from .core.resolve import make_ast_from_literal
from .core.transformer import function_ast
from .utils import save_or_return_source

log = logging.getLogger(__name__)

_exclude = {'__builtin__', '__builtins__', 'builtin', 'builtins'}
if sys.version_info < (3, 6):
    _ast_str_types = ast.Str
else:
    _ast_str_types = (ast.Str, ast.JoinedStr)


@optional_argument_decorator
class lift:
    @magic_contract
    def __init__(self, return_source=False, save_source=True, annotate_types=False, defaults=False, lift_globals=None, imports=True):
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
        """

        self.return_source = return_source
        self.save_source = save_source
        self.annotate_types = annotate_types
        self.defaults = defaults
        self.lift_globals = lift_globals
        self.imports = imports

    def _annotate(self, k, v):
        if self.annotate_types:
            if isinstance(self.annotate_types, bool):
                return ast.Name(id=type(v).__name__, ctx=ast.Load())
            elif isinstance(self.annotate_types, (tuple, list, set)):
                if k in self.annotate_types:
                    return ast.Name(id=type(v).__name__, ctx=ast.Load())
            elif isinstance(self.annotate_types, dict):
                if k in self.annotate_types:
                    result = self.annotate_types[k]
                    if isinstance(result, str):
                        result = ast.Str(s=result)
                    if result and not isinstance(result, ast.expr):
                        raise TypeError("Type annotation must be a string or AST expression (got {})".format(result))
                    return result
        return None

    def _get_default(self, k, v):
        if self.defaults:
            if isinstance(self.defaults, bool):
                attempt = v
            elif isinstance(self.defaults, (tuple, list, set)):
                if k in self.defaults:
                    attempt = v
                else:
                    return None
            elif isinstance(self.defaults, dict):
                if k in self.defaults:
                    attempt = self.defaults[k]
                else:
                    return None
            else:
                return None

            try:
                res = make_ast_from_literal(attempt)
                assert isinstance(res, ast.expr)
                return res
            except (TypeError, AssertionError):
                log.debug("Failed to convert {} to an AST expression".format(attempt))
                return None

        return None

    def _get_free_vars(self, f):
        if isinstance(f.__closure__, tuple):
            free_vars = [(k, v.cell_contents) for k, v in zip(f.__code__.co_freevars, f.__closure__)]
        else:
            free_vars = []

        for glbl in self.lift_globals or []:
            free_vars.append((glbl, f.__globals__[glbl]))

        return free_vars

    def _insert_imports(self, f, f_body, free_vars):
        add_imports = []

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
            if (isinstance(self.imports, bool) or k in self.imports) and k not in _exclude
        ] + f_body
        return f_body, free_vars

    @magic_contract(f='Callable', returns='Callable|str')
    def __call__(self, f):
        f_mod, f_body, f_file = function_ast(f)

        # Grab function closure variables
        free_vars = self._get_free_vars(f)

        if self.imports:
            f_body, free_vars = self._insert_imports(f, f_body, free_vars)

        func_def = f_mod.body[0]

        new_kws = [ast.arg(arg=k, annotation=self._annotate(k, v)) for k, v in free_vars]
        new_kw_defaults = [self._get_default(k, v) for k, v in free_vars]

        # python 3.8 introduced a new signature for ast.arguments.__init__, so use whatever they use
        ast_arguments_dict = func_def.args.__dict__
        ast_arguments_dict['kwonlyargs'] += new_kws
        ast_arguments_dict['kw_defaults'] += new_kw_defaults

        new_func_def = ast.FunctionDef(
            name=func_def.name,
            body=f_body,
            decorator_list=[],  # func_def.decorator_list,
            returns=func_def.returns,
            args=ast.arguments(**ast_arguments_dict)
        )

        f_mod.body[0] = new_func_def
        return save_or_return_source(f_file, f_mod, {}, self.return_source, self.save_source)
