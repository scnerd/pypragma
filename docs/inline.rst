Inlining Functions
==================

.. autofunction:: pragma.inline

Inline specified functions into the decorated function. Unlike in C, this directive is placed not on the function getting inlined, but rather the function into which it's getting inlined (since that's the one whose code needs to be modified and hence decorated). Currently, this is implemented in the following way:

- When a function is called, its call code is placed within the current code block immediately before the line where its value is needed
- The code is wrapped in a one-iteration ``for`` loop (effectively a ``do {} while(0)``), and the ``return`` statement is replaced by a ``break``
- Arguments are stored into a dictionary, and variadic keyword arguments are passed as ``dict_name.update(kwargs)``; this dictionary has the name ``_[funcname]`` where ``funcname`` is the name of the function being inlined, so other variables of this name should not be used or relied upon
- The return value is assigned to the function name as well, deleting the argument dictionary, freeing its memory, and making the return value usable when the function's code is exited by the ``break``
- The call to the function is replaced by the variable holding the return value

As a result, ``pragma.inline`` cannot currently handle functions which contain a ``return`` statement within a loop. Since Python doesn't support anything like ``goto`` besides wrapping the code in a function (which this function implicitly shouldn't do), I don't know how to surmount this problem. Without much effort, it can be overcome by tailoring the function to be inlined.

To inline a function ``f`` into the code of another function ``g``, use ``pragma.inline(g)(f)``, or, as a decorator::

    def f(x):
        return x**2

    @pragma.inline(f)
    def g(y):
        z = y + 3
        return f(z * 4)

    # ... g Becomes something like ...

    def g(y):
        z = y + 3
        _f = dict(x=z * 4)  # Store arguments
        for ____ in [None]:  # Function body
            _f['return'] = _f['x'] ** 2  # Store the "return"ed value
            break  # Return, terminate the function body
        _f_return = _f.get('return', None)  # Retrieve the returned value
        del _f  # Discard everything else
        return _f_return

This loop can be removed, if it's not necessary, using :func:``pragma.unroll``. This can be accomplished if there are no returns within a conditional or loop block. In this case::

    def f(x):
        return x**2

    @pragma.unroll
    @pragma.inline(f)
    def g(y):
        z = y + 3
        return f(z * 4)

    # ... g Becomes ...

    def g(y):
        z = y + 3
        _f = {}
        _f['x'] = z * 4
        _f = _f['x'] ** 2
        return _f

It needs to be noted that, besides arguments getting stored into a dictionary, other variable names remain unaltered when inlined. Thus, if there are shared variable names in the two functions, they might overwrite each other in the resulting inlined function.

.. todo:: Fix name collision by name-mangling non-free variables

Eventually, this could be collapsed using :func:``pragma.collapse_literals``, to produce simply ``return ((y + 3) * 4) ** 2``, but dictionaries aren't yet supported for collapsing.

When inlining a generator function, the function's results are collapsed into a list, which is then returned. This will break in two main scenarios:

- The generator never ends, or consumes excessive amounts of resources.
- The calling code relies on the resulting generator being more than just iterable.

In general, either this won't be an issue, or you should know better than to try to inline the infinite generator.

.. todo:: Support inlining a generator into another generator by merging the functions together. E.g., ``for x in my_range(5): yield x + 2`` becomes ``i = 0; while i < 5: yield i + 2; i += 1`` (or something vaguely like that).
.. todo:: Support inlining closures; if the inlined function refers to global or nonlocal variables, import them into the closure of the final function.