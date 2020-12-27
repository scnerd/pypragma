Collapse Literals
=================

.. autofunction:: pragma.collapse_literals

Collapse literal operations in code to their results, e.g. ``x = 1 + 2`` gets converted to ``x = 3``.

For example::

    @pragma.collapse_literals
    def f(y):
        x = 3
        return x + 2 + y

    # ... Becomes ...

    def f(y):
        x = 3
        return 5 + y

This is capable of resolving expressions of numerous sorts:

- A variable with a known value is replaced by that value
- An iterable with known values (such as one that could be unrolled by :func:`pragma.unroll`), if indexed, is replaced with the value at that location
- A unary, binary, or logical operation on known values is replaced by the result of that operation on those values
- A `if/elif/else` block is trimmed of options that are known at decoration-time to be impossible. If it can be known which branch runs at decoration time, then the conditional is removed altogether and replaced with the body of that branch

If a branch is constant, and thus known at decoration time, then only the correct branch will be left::

    @pragma.collapse_literals
    def f():
        x = 1
        if x > 0:
            x = 2
        return x

    # ... Becomes ...

    def f():
        x = 1
        x = 2
        return 2

This decorator is actually very powerful, understanding any definition-time known collections, primitives, or even dictionaries. Subscripts are resolved if the list or dictionary, and the key into it, can be resolved. Names are replaced by their values if they are not containers (since re-writing a container, such as a tuple or list, could duplicate object references). Functions, such as ``len`` and ``sum`` can be computed and replaced with their value if their arguments are known.

Only primitive types are resolved, and this does not include iterable types. To control this behavior, use the ``collapse_iterables`` argument. Example::

    v = [1, 2]

    @pragma.collapse_literals
    def f():
        yield v

    # ^ nothing happens ^

    @pragma.collapse_literals(collapse_iterables=True)
    def f():
        yield v

    # ... Becomes ...

    def f():
        yield [1, 2]

There are cases where you don't want to collapse all literals. It often happens when you have lots of global variables and long functions, or if you want to apply different pragma patterns to different parts of the function. Fine control is possible with the ``explicit_only`` argument. When True, only explicit keyword arguments and the value of the ``function_globals`` argument (itself a dictionary) are collapsed.

``pragma`` is capable of logical and mathematical deduction, meaning that expressions with unknowns can be collapsed if the known elements determine the result. For example, ``False and anything`` is logically equivalent to ``False``. ``True or anything`` is always ``True``. Mathematical: ``anything ** 0`` -> ``1``. ``0 * anything`` -> ``0``.

.. todo:: Always commit changes within a block, and only mark values as non-deterministic outside of conditional blocks
.. todo:: Support list/set/dict comprehensions
.. todo:: Attributes are too iffy, since properties abound, but assignment to a known index of a known indexable should be remembered
