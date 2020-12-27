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

``unroll`` is currently smart enough to notice literal defined variables and literals, as well as able to unroll the ``range`` function and unroll nested loops::

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

``unroll`` also supports tuple-target interation with ``enumerate``, ``zip``, and ``items``::

    v = [1, 3, 5]

    @pragma.unroll
    def f():
        for i, elem in enumerate(v):
            yield i, elem

    # ... Becomes ...

    def f():
        yield 0, 1
        yield 1, 3
        yield 2, 5

Partial unrolling and targeted unrolling are supported. ``unroll_targets`` lets you explicitly specify which loops should be unrolled. This is useful in functions with several loops that should behave differently. ``unroll_in_tiers`` is a performance measure for reducing overhead in loop calls. It is a tuple of ``(iterable_name, length_of_loop, number_of_inner_iterations)``, where ``iterable_name`` specifies what to unroll, ``length_of_loop`` is how many iterations in total, and ``number_of_inner_iterations`` is the number of explicit repetitions of the inside of the loop before reaching the end of the new loop. ::

    a = list(range(0, 7))

    @pragma.unroll(unroll_in_tiers=('PRAGMArange', len(a), 2))
    def f():
        for i in PRAGMArange:
            yield a[i]

    # ... Becomes ...

    def f():
        for PRAGMA_iouter in range(0, 6, 2):
            yield a[PRAGMA_iouter]
            yield a[PRAGMA_iouter + 1]
        yield a[6]

In that example, ``pragma`` handled a single remainder call because the length of the iterable was odd, while the step was 2.


When combined with ``deindex``, ``unroll`` can also handle cases where the values being iterated over are not literals. The decorators must be in this order (deindex being applied before unroll), and the ``collapse_iterables`` argument is necessary::

    d = {'a': object(), 'b': object()}

    @pragma.unroll
    @pragma.deindex(d, 'd', collapse_iterables=True)
    def f():
        for k, v in d.items():
            yield k
            yield v

    # ... Becomes ...

    def f():
        yield 'a'
        yield d_a
        yield 'b'
        yield d_b

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



.. todo:: Assignment to known lists and dictionaries
.. todo:: Resolving compile-time known conditionals before detecting top-level breaks