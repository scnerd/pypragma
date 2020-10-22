import ast
import logging

from miniutils import magic_contract

from .collapse_literals import collapse_literals

log = logging.getLogger(__name__)


# Directly reference elements of constant list, removing literal indexing into that list within a function
@magic_contract
def deindex(iterable, iterable_name, *args, **kwargs):
    """
    :param iterable: The list to deindex in the target function
    :type iterable: iterable
    :param iterable_name: The list's name (must be unique if deindexing multiple lists)
    :type iterable_name: str
    :param args: Other command line arguments (see :func:`collapse_literals` for documentation)
    :type args: tuple
    :param kwargs: Any other environmental variables to provide during unrolling
    :type kwargs: dict
    :return: The unrolled function, or its source code if requested
    :rtype: Callable
    """

    if hasattr(iterable, 'items'):  # Support dicts and the like
        sanitized_map = {}
        invalid_chars = [' ', '-', '+', '/', '\\', '.', '!', '@', '#', '$', '%', ':', '?']
        for k in iterable.keys():
            if isinstance(k, int):
                sanitized_map[k] = k
            elif isinstance(k, str) and not any(ic in k for ic in invalid_chars):
                sanitized_map[k] = k
            else:
                sanitized_map[k] = abs(hash(str(k)))
        internal_iterable = {k: '{}_{}'.format(iterable_name, sk) for k, sk in sanitized_map.items()}
        mapping = {internal_iterable[k]: val for k, val in iterable.items()}
        ast_iterable = {k: ast.Name(id=name, ctx=ast.Load()) for k, name in internal_iterable.items()}
    else:  # Support lists, tuples, and the like
        internal_iterable = tuple('{}_{}'.format(iterable_name, i) for i, val in enumerate(iterable))
        mapping = {internal_iterable[i]: val for i, val in enumerate(iterable)}
        ast_iterable = tuple(ast.Name(id=name, ctx=ast.Load()) for name in internal_iterable)
    # attempt to make the ast_iterable the same type as the original, otherwise keep it the builtin type
    try:
        ast_iterable = type(iterable)(ast_iterable)
    except:
        pass
    kwargs[iterable_name] = ast_iterable
    mapping[iterable_name] = iterable

    return collapse_literals(*args, function_globals=mapping, **kwargs)
