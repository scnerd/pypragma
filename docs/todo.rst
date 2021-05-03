TODO List
=========

.. todo:: Replace custom stack implementation with ``collections.ChainMap``
.. todo:: Implement decorator to eliminate unused lines of code (assignments to unused values)
.. todo:: Technically, ``x += y`` doesn't have to be the same thing as ``x = x + y``. Handle it as its own operation of the form ``x += y; return x``
.. todo:: Support efficiently inlining simple functions, i.e. where there is no return or only one return as the last line of the function, using pure name substitution without loops, try/except, or anything else fancy
.. todo:: Catch replacement of loop variables that conflict with globals, or throw a more descriptive error when detected. See ``test_iteration_variable``
.. todo:: Python 3.8/3.9+ support: https://docs.python.org/3/library/ast.html . ``ast.Constant`` is taking over for ``ast.[Num, Str, Bytes, NameConstant, Ellipsis]``. Simple-valued indexes are now values, and extended slices are now tuples: ``ast.[Index, ExtSlice]`` no longer exist.

.. todolist::
