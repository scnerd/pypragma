import ast

from .core import TrackedContextTransformer, make_function_transformer, resolve_literal, log


# noinspection PyPep8Naming
class CleanupTransformer(TrackedContextTransformer):
    pass

# Collapse defined literal values, and operations thereof, where possible
cleanup = make_function_transformer(CleanupTransformer, 'cleanup', "Removes lines that have no effect")
