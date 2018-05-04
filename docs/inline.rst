Inlining Functions
==================

.. autofunction:: pragma.inline

Inline specified functions into the decorated function. Unlike in C, this directive is placed not on the function getting inlined, but rather the function into which it's getting inlined (since that's the one whose code needs to be modified and hence decorated). Currently, this is implemented in the following way:

- When a function is called, its call code is placed within the current code block immediately before the line where its value is needed
- The code is wrapped in a ``try/except`` block, and the return value is passed back out using a special exception type
- Arguments are stored into a dictionary, and variadic keyword arguments are passed as ``dict_name.update(kwargs)``; this dictionary has the name ``_[funcname]`` where ``funcname`` is the name of the function being inlined, so other variables of this name should not be used or relied upon
- The return value is assigned to the function name as well, deleting the argument dictionary, freeing its memory, and making the return value usable when the function's code is exited by the ``break``
- The call to the function is replaced by the variable holding the return value

As a result, ``pragma.inline`` cannot currently handle functions which contain a ``return`` statement within a bare ``try/except`` or ``except BaseException``. Since Python doesn't support anything like ``goto`` besides wrapping the code in a function (which this function implicitly shouldn't do), I don't know how to surmount this problem. Without much effort, it can be overcome by tailoring the function to be inlined. In general, it's bad practice to use a bare ``except:`` or ``except BaseException:``, and such calls should generally be replaced with ``except Exception:``, which would this issue.

To inline a function ``f`` into the code of another function ``g``, use ``pragma.inline(g)(f)``, or, as a decorator::

    def f(x):
        return x**2

    @pragma.inline(f)
    def g(y):
        z = y + 3
        return f(z * 4)

    # ... g Becomes...

    def g(y):
        z = y + 3
        _f_0 = dict(x=z * 4)
        try:  # Function body
            raise _PRAGMA_INLINE_RETURN(_f_0['x'] ** 2)
        except _PRAGMA_INLINE_RETURN as _f_return_0_exc:
            _f_return_0 = _f_return_0_exc.return_val
        else:
            _f_return_0 = None
        finally:  # Discard artificial stack frame
            del _f_0
        return _f_return_0

.. todo:: Fix name collision by name-mangling non-free variables

Eventually, this could be collapsed using :func:``pragma.collapse_literals``, to produce simply ``return ((y + 3) * 4) ** 2``, but there are numerous hurtles in the way toward making this happen.

When inlining a generator function, the function's results are collapsed into a list, which is then returned. This is equivalent to calling ``list(generator_func(*args, **kwargs))``. This will break in two main scenarios:

- The generator never ends, or consumes excessive amounts of resources.
- The calling code relies on the resulting generator being more than just iterable, e.g. if data is passed back in using calls to ``next``.

.. todo:: Fix generators to return something more like ``iter(list(f(*args, **kwargs))``, since ``list`` itself is not an iterator, but the return of a generator is.

In general, either this won't be an issue, or you should know better than to try to inline the infinite generator.

.. todo:: Support inlining a generator into another generator by merging the functions together. E.g., ``for x in my_range(5): yield x + 2`` becomes ``i = 0; while i < 5: yield i + 2; i += 1`` (or something vaguely like that).
.. todo:: Support inlining closures; if the inlined function refers to global or nonlocal variables, import them into the closure of the final function.

Recursive calls are handled by keeping a counter of the inlined recursion depth, and changing the suffix number of the local variables dictionary (e.g., ``_f_0``). These dictionaries serve as stack frames: their unique naming permits multiple, even stacked, inlined function calls, and their deletion enforces the usual life span of function-local variables.

.. todo:: Support option to either inline as loop or exception