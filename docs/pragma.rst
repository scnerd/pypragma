Pragma
++++++

When Python code is being executed abnormally, or being replaced entirely (e.g., by ``numba.jit``), it's sometimes highly relevant how your code is written. However, writing it that way isn't always practical, or you might want the code itself to be dependant on runtime data. In these cases, basic code templating or modification can be useful. This sub-module provides some simple utilities to perform Python code modification at runtime, similar to compiler directives in C.

These functions are designed as decorators that can be stacked together. Each one modifies the provided function's AST, and then re-compiles the function with identical context to the original. A side effect of accomplishing this means that source code is (optionally) made available for each function, either as a return value (replace the function with a string of its modified source code) or, more usefully, by saving it to a temporary file so that ``inspect.getsource`` works correctly on it.

Because Python is an interpreted language and functions are first-order objects, it's possible to use these functions to perform runtime-based code "optimization" or "templating". As a simple example of this, let's consider ``numba.cuda.jit``, which imposes numerous ``nopython`` limitations on what your function can do. One such limitation is that a ``numba.cuda`` kernel can't treat functions as first order objects. It must know, at function definition time, which function it's calling. Take the following example::

    funcs = [lambda x: x, lambda x: x ** 2, lambda x: x ** 3]

    def run_func(i, x):
        return funcs[i](x)

How could we re-define this function such that it both::

1) Is dynamic to a list that's constant at function definition-time
2) Doesn't actually index that list in its definition

We'll start by defining the function as an ``if`` check for the index, and call the appropriate function::

    funcs = [lambda x: x, lambda x: x ** 2, lambda x: x ** 3]

    def run_func(i, x):
        for j in range(len(funcs)):
            if i == j:
                return funcs[j](x)

The ``miniutils.pragma`` module enables us to go from here to accomplish our goal above by re-writing a function's AST and re-compiling it as a closure, while making certain modifications to its syntax and environment. While each function will be fully described lower, the example above can be succinctly solved by unrolling the loop (whose length is known at function definition time) and by assigning the elements of the list to individual variables and swapping out their indexed references with de-indexed references::

    funcs = [lambda x: x, lambda x: x ** 2, lambda x: x ** 3]

    @pragma.deindex(funcs, 'funcs')
    @pragma.unroll(lf=len(funcs))
    def run_func(i, x):
        for j in range(lf):
            if i == j:
                return funcs[j](x)

    # ... gets transformed at definition time into the below code ...

    funcs = [lambda x: x, lambda x: x ** 2, lambda x: x ** 3]
    funcs_0 = funcs[0]
    funcs_1 = funcs[1]
    funcs_2 = funcs[2]

    def run_func(i, x):
        if i == 0:
            return funcs_0(x)
        if i == 1:
            return funcs_1(x)
        if i == 2:
            return funcs_2(x)

Unroll
------

Unroll constant loops. If the `for`-loop iterator is a known value at function definition time, then replace it with its body duplicated for each value. For example::

    def f():
    for i in [1, 2, 4]:
        yield i

could be identically replaced by::

    def f():
        yield 1
        yield 2
        yield 4

The ``unroll`` decorator accomplishes this by parsing the input function, performing the unrolling transformation on the function's AST, then compiling and returning the defined function.

If using a transformational decorator of some sort, such as ``numba.jit`` or ``tangent.grad``, if that function isn't yet able to unwrap loops like this, then using this function might yield cleaner results on constant-length loops.

``unroll`` is currently smart enough to notice singly-defined variables and literals, as well as able to unroll the ``range`` function and unroll nested loops::

    @pragma.unroll
    def summation(x=0):
        a = [x, x, x]
        v = 0
        for _a in a:
            v += _a
        return v

    # ... Becomes ...

    def summation(x=0):
        a = [x, x, x]
        v = 0
        v += x
        v += x
        v += x
        return v

    # ... But ...

    @pragma.unroll
    def f():
        x = 3
        for i in [x, x, x]:
            yield i
        x = 4
        a = [x, x, x]
        for i in a:
            yield i

    # ... Becomes ...

    def f():
        x = 3
        yield 3
        yield 3
        yield 3
        x = 4
        a = [x, x, x]
        yield 4
        yield 4
        yield 4

    # Even nested loops and ranges work!

    @pragma.unroll
    def f():
        for i in range(3):
            for j in range(3):
                yield i + j

    # ... Becomes ...

    def f():
        yield 0 + 0
        yield 0 + 1
        yield 0 + 2
        yield 1 + 0
        yield 1 + 1
        yield 1 + 2
        yield 2 + 0
        yield 2 + 1
        yield 2 + 2

You can also request to get the function source code instead of the compiled callable by using ``return_source=True``::

    In [1]: @pragma.unroll(return_source=True)
       ...: def f():
       ...:     for i in range(3):
       ...:         print(i)
       ...:

    In [2]: print(f)
    def f():
        print(0)
        print(1)
        print(2)

It also supports limited recognition of externally and internally defined values::

    @pragma.unroll(a=range)
    def f():
        for b in a(3):
            print(b)

    # Is equivalent to:

    a = range
    @pragma.unroll
    def f():
        for b in a(3):
            print(b)

    # Both of which become:

    def f():
        print(0)
        print(1)
        print(2)

Also supported are recognizing top-level breaks. Breaks inside conditionals aren't yet supported, though they could eventually be by combining unrolling with literal condition collapsing::

    @pragma.unroll
    def f(y):
        for i in range(100000):
            for x in range(2):
                if i == y:
                    break
            break

    # ... Becomes ...

    def f(y):
        for x in range(2):
            if 0 == y:
                break


Currently not-yet-supported features include:

- Handling constant sets and dictionaries (since the values contained in the AST's, not the AST nodes themselves, must be uniquely identified)
- Tuple assignments (``a, b = 3, 4``)
- Assignment to known lists and dictionaries
- ``zip``, ``reversed``, and other known operators, when performed on definition-time constant iterables
- Resolving compile-time known conditionals before detecting top-level breaks

.. autofunction:: miniutils.pragma.unroll

Collapse Literals
-----------------

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
- An iterable with known values (such as one that could be unrolled by :func:`miniutils.pragma.unroll`), if indexed, is replaced with the value at that location
- A unary, binary, or logical operation on known values is replaced by the result of that operation on those values
- A `if/elif/else` block is trimmed of options that are known at decoration-time to be impossible. If it can be known which branch runs at decoration time, then the conditional is removed altogether and replaced with the body of that branch

Currently, this decorator is not robust to runtime branches which may or may not affect certain values. For example::

    @pragma.collapse_literals
    def f(y):
        x = 0
        if y:
            x = 1
        return x

Ought to become::

    def f(y):
        x = 0
        if y:
            x = 1
        return x  # This isn't resolved because it isn't known which branch will be taken

But currently this will fail and become::

    def f(y):
        x = 0
        if y:
            x = 1
        return 1  # Since this was the last value we saw assigned to x

If the branch is constant, and thus known at decoration time, then this flaw won't affect anything::

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
.. autofunction:: miniutils.pragma.collapse_literals

De-index Arrays
---------------

Convert literal indexing operations for a given array into named value references. The new value names are de-indexed and stashed in the function's closure so that the resulting code both uses no literal indices and still behaves as if it did. Variable indices are unaffected.

For example::

    v = [object(), object(), object()]

    @pragma.deindex(v, 'v')
    def f(x):
        yield v[0]
        yield v[x]

    # ... f becomes ...

    def f(x):
        yield v_0  # This is defined as v_0 = v[0] by the function's closure
        yield v[x]

    # We can check that this works correctly
    assert list(f(2)) == [v[0], v[2]]

This can be easily stacked with :func:`miniutils.pragma.unroll` to unroll iterables in a function when their values are known at function definition time::

    funcs = [lambda x: x, lambda x: x ** 2, lambda x: x ** 3]

    @pragma.deindex(funcs, 'funcs')
    @pragma.unroll(lf=len(funcs))
    def run_func(i, x):
        for j in range(lf):
            if i == j:
                return funcs[j](x)

    # ... Becomes ...

    def run_func(i, x):
        if i == 0:
            return funcs_0(x)
        if i == 1:
            return funcs_1(x)
        if i == 2:
            return funcs_2(x)

This could be used, for example, in a case where dynamically calling functions isn't supported, such as in ``numba.jit`` or ``numba.cuda.jit``.

Note that because the array being de-indexed is passed to the decorator, the value of the constant-defined variables (e.g. ``v_0`` in the code above) is "compiled" into the code of the function, and won't update if the array is updated. Again, variable-indexed calls remain unaffected.

Since names are (and must) be used as references to the array being de-indexed, it's worth noting that any other local variable of the format ``"{iterable_name}_{i}"`` will get shadowed by this function. The string passed to ``iterable_name`` must be the name used for the iterable within the wrapped function.

.. autofunction:: miniutils.pragma.deindex

Inlining Functions
------------------

Inline specified functions into the decorated function. Unlike in C, this directive is placed not on the function getting inlined, but rather the function into which it's getting inlined (since that's the one whose code needs to be modified and hence decorated). Currently, this is implemented in the following way:

- When a function is called, its call code is placed within the current code block immediately before the line where its value is needed
- The code is wrapped in a one-iteration ``for`` loop (effectively a ``do {} while(0)``), and the ``return`` statement is replaced by a ``break``
- Arguments are stored into a dictionary, and variadic keyword arguments are passed as ``dict_name.update(kwargs)``; this dictionary has the name ``_[funcname]`` where ``funcname`` is the name of the function being inlined, so other variables of this name should not be used or relied upon
- The return value is assigned to the function name as well, deleting the argument dictionary, freeing its memory, and making the return value usable when the function's code is exited by the ``break``
- The call to the function is replaced by the variable holding the return value

As a result, ``miniutils.pragma.inline`` cannot currently handle functions which contain a ``return`` statement within a loop. Since Python doesn't support anything like ``goto`` besides wrapping the code in a function (which this function implicitly shouldn't do), I don't know how to surmount this problem. Without much effort, it can be overcome by tailoring the function to be inlined.

To inline a function ``f`` into the code of another function ``g``, use ``pragma.inline(g)(f)``, or, as a decorator::

    def f(x):
        return x**2

    @pragma.inline(f)
    def g(y):
        z = y + 3
        return f(z * 4)

    # ... g Becomes ...

    def g(y):
        z = y + 3
        _f = {}
        _f['x'] = z * 4
        for ____ in [None]:
            _f = _f['x'] ** 2
            break
        return _f

This loop can be removed, if it's not necessary, using :func:``miniutils.pragma.unroll``. This can be accomplished if there are no returns within a conditional or loop block. In this case::

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

Eventually, this could be collapsed using :func:``miniutils.pragma.collapse_literals``, to produce simply ``return ((y + 3) * 4) ** 2``, but dictionaries aren't yet supported for collapsing.

.. autofunction:: miniutils.pragma.inline