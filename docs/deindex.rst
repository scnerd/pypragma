De-index Arrays
===============

.. autofunction:: pragma.deindex

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

This can be easily stacked with :func:`pragma.unroll` to unroll iterables in a function when their values are known at function definition time::

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
