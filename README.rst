.. image:: https://travis-ci.org/scnerd/pypragma.svg?branch=master
    :target: https://travis-ci.org/scnerd/pypragma

.. image:: https://coveralls.io/repos/github/scnerd/pypragma/badge.svg?branch=master
    :target: https://coveralls.io/github/scnerd/pypragma?branch=master

.. image:: https://readthedocs.org/projects/pypragma/badge/?version=latest
    :target: http://pypragma.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

Overview
========

PyPragma is a set of tools for performing in-place code modification, inspired by compiler directives in C. These modifications are intended to make no functional changes to the execution of code. In C, this is used to increase code performance or make certain tradeoffs (often between the size of the binary and its execution speed). In Python, these changes are most applicable when leveraging code generation libraries (such as Numba or Tangent) where the use of certain Python features is disallowed. By transforming the code in-place, disallowed features can be converted to allowed syntax at runtime without sacrificing the dynamic nature of python code.

For example, with Numba, it is not possible to compile a function which dynamically references and calls other functions (e.g., you may not select a function from a list and then execute it, you may only call functions by their explicit name):

.. code-block:: python

   fns = [sin, cos, tan]

   @numba.jit
   def call(i, x):
      return fns[i](x)  # Not allowed, since it's unknown which function is getting called

If the dynamism is static by the time the function is defined, such as in this case, then these dynamic language features can be flattened to simpler features that such code generation libraries are more likely to support (e.g., the function can be extracted into a closure variable, then called directly by that name):

.. code-block:: python

   fns = [sin, cos, tan]

   fns_0 = fns[0]
   fns_1 = fns[1]
   fns_2 = fns[2]

   @numba.jit
   def call(i, x):
      if i == 0:
         return fns_0(x)
      if i == 1:
         return fns_1(x)
      if i == 2:
         return fns_2(x)

Such a modification can only be done by the programmer if the dynamic features are known *before* runtime, that is, if ``fns`` is dynamically computed, then this modification cannot be performed by the programmer, even though this example demonstrates the the original function is not inherently dynamic, it just appears so. PyPragma enables this transformation at runtime, which for this example function would look like:

.. code-block:: python

   fns = [sin, cos, tan]

   @numba.jit
   @pragma.deindex(fns, 'fns')
   @pragma.unroll(num_fns=len(fns))
   def call(i, x):
      for j in range(num_fns):
         if i == j:
            return fns[j](x)  # Still dynamic call, but decorators convert to static

This example is converted, in place and at runtime, to exactly the unrolled code above.


Documentation
=============

Complete documentation can be found over at `RTFD <http://pypragma.readthedocs.io/en/latest/>`_.


Installation
============

As usual, you have the choice of installing from PyPi:

.. code-block:: bash

   pip install pragma

or directly from Github:

.. code-block:: bash

   pip install git+https://github.com/scnerd/pypragma


Usage
===========

PyPragma has a small number of stackable decorators, each of which transforms a function in-place without changing its execution behavior. These can be imported as such:

.. code-block:: python

   import pragma

Each decorator can be applied to a function using either the standard decorator syntax, or as a function call:

.. code-block:: python

   @pragma.unroll
   def pows(i):
      for x in range(3):
         yield i ** x

   pows(5)

   # Is identical to...

   def pows(i):
      for x in range(3):
         yield i ** x

   pragma.unroll(pows)(5)

   # Both of which become...

   def pows(i):
      yield i ** 0
      yield i ** 1
      yield i ** 2

   pows(5)

Each decorator can be used bare, as in the example above, or can be given initial parameters before decorating the given function. Any non-specified keyword arguments are added to the resulting function's closure as variables. In addition, the decorated function's closure is preserved, so external variables are also included. As a simple example, the above code could also be written as:

.. code-block:: python

   @pragma.unroll(num_pows=3)
   def pows(i):
      for x in range(num_pows):
         yield i ** x

   # Or...

   num_pows = 3
   @pragma.unroll
   def pows(i):
      for x in range(num_pows):
         yield i ** x

Certain keywords are reserved, of course, as will be defined in the documentation for each decorator. Additionally, the resulting function is an actual, proper Python function, and hence must adhere to Python syntax rules. As a result, some modifications depend upon using certain variable names, which may collide with other variable names used by your function. Every effort has been made to make this unlikely by using mangled variable names, but the possibility for collision remains.

A side effect of the proper Python syntax is that functions can have their source code retrieved by any normal Pythonic reflection:

.. code-block:: python

   In [1]: @pragma.unroll(num_pows=3)
      ...: def pows(i):
      ...:    for x in range(num_pows):
      ...:       yield i ** x
      ...:

   In [2]: pows??
   Signature: pows(i)
   Source:
   def pows(i):
       yield i ** 0
       yield i ** 1
       yield i ** 2
   File:      /tmp/tmpmn5bza2j
   Type:      function

As a utility, primarily for testing and debugging, the source code can be easily retrieved from each decorator *instead* of the transformed function by using the ``return_source=True`` argument.

Quick Examples
==============

Collapse Literals
+++++++++++++++++

.. code-block:: python

   In [1]: @pragma.collapse_literals(x=5)
      ...: def f(y):
      ...:     z = x // 2
      ...:     return y * 10**z
      ...:

   In [2]: f??
   Signature: f(y)
   Source:
   def f(y):
       z = 2
       return y * 100

De-index Arrays
+++++++++++++++

.. code-block:: python

   In [1]: fns = [math.sin, math.cos, math.tan]

   In [2]: @pragma.deindex(fns, 'fns')
      ...: def call(i, x):
      ...:     if i == 0:
      ...:         return fns[0](x)
      ...:     if i == 1:
      ...:         return fns[1](x)
      ...:     if i == 2:
      ...:         return fns[2](x)
      ...:

   In [3]: call??
   Signature: call(i, x)
   Source:
   def call(i, x):
       if i == 0:
           return fns_0(x)
       if i == 1:
           return fns_1(x)
       if i == 2:
           return fns_2(x)

Note that, while it's not evident from the above printed source code, each variable ``fns_X`` is assigned to the value of ``fns[X]`` at the time when the decoration occurs:

.. code-block:: python

   In [4]: call(0, math.pi)
   Out[4]: 1.2246467991473532e-16  # AKA, sin(pi) = 0

   In [5]: call(1, math.pi)
   Out[5]: -1.0  # AKA, cos(pi) = -1

Unroll
++++++

.. code-block:: python

   In [1]: p_or_m = [1, -1]

   In [2]: @pragma.unroll
      ...: def f(x):
      ...:     for j in range(3):
      ...:         for sign in p_or_m:
      ...:             yield sign * (x + j)
      ...:

   In [3]: f??
   Signature: f(x)
   Source:
   def f(x):
       yield 1 * (x + 0)
       yield -1 * (x + 0)
       yield 1 * (x + 1)
       yield -1 * (x + 1)
       yield 1 * (x + 2)
       yield -1 * (x + 2)

Inline
++++++

.. code-block:: python

   In [1]: def sqr(x):
      ...:     return x ** 2
      ...:

   In [2]: @pragma.inline(sqr)
      ...: def sqr_sum(a, b):
      ...:     return sqr(a) + sqr(b)
      ...:

   In [3]: sqr_sum??
   Signature: sqr_sum(a, b)
   Source:
   def sqr_sum(a, b):
       _sqr_0 = dict(x=a)  # Prepare for 'sqr(a)'
       for ____ in [None]:  # Wrap function in block
           _sqr_0['return'] = _sqr_0['x'] ** 2  # Compute returned value
           break  # 'return'
       _sqr_return_0 = _sqr_0.get('return', None)  # Extract the returned value
       del _sqr_0  # Delete the arguments dictionary, the function call is finished
       _sqr_0 = dict(x=b)  # Do the same thing for 'sqr(b)'
       for ____ in [None]:
           _sqr_0['return'] = _sqr_0['x'] ** 2
           break
       _sqr_return_1 = _sqr_0.get('return', None)
       del _sqr_0
       return _sqr_return_0 + _sqr_return_1  # Substitute the returned values for the function calls

Stacking Transformations
++++++++++++++++++++++++

The above examples demonstrate how to perform `pragma` transformations to a function. It should be especially noted, however, that since each transformer returns a proper Python function, they can stack seamlessly:

.. code-block:: python

    In [1]: def make_dynamic_caller(*fns):
       ...:     @pragma.deindex(fns, 'fns')
       ...:     @pragma.unroll(num_fns=len(fns))
       ...:     def dynamic_call(i, x):
       ...:         for j in range(num_fns):
       ...:             if i == j:
       ...:                 return fns[j](x)
       ...:
       ...:     return dynamic_call

    In [2]: f = make_dynamic_caller(math.sin, math.cos, math.tan)

    In [3]: f??
    Signature: f(i, x)
    Source:
    def dynamic_call(i, x):
        if i == 0:
            return fns_0(x)
        if i == 1:
            return fns_1(x)
        if i == 2:
            return fns_2(x)
    File:      /tmp/tmpf9tjaffi
    Type:      function

    In [4]: g = pragma.collapse_literals(i=1)(f)

    In [5]: g??
    Signature: g(i, x)
    Source:
    def dynamic_call(i, x):
        return fns_1(x)
    File:      /tmp/tmpbze5i__2
    Type:      function
