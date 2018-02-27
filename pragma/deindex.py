import ast

from miniutils import magic_contract

from .collapse_literals import collapse_literals


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
        internal_iterable = {k: '{}_{}'.format(iterable_name, k) for k, val in iterable.items()}
        mapping = {internal_iterable[k]: val for k, val in iterable.items()}
        raise NotImplementedError('Dictionary indices are not yet supported')
    else:  # Support lists, tuples, and the like
        internal_iterable = {i: '{}_{}'.format(iterable_name, i) for i, val in enumerate(iterable)}
        mapping = {internal_iterable[i]: val for i, val in enumerate(iterable)}

    kwargs[iterable_name] = {k: ast.Name(id=name, ctx=ast.Load()) for k, name in internal_iterable.items()}

    return collapse_literals(*args, function_globals=mapping, **kwargs)
