Unroll
======

.. autofunction:: pragma.unroll

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