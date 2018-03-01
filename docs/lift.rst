Lambda Lift
===========

.. autofunction:: pragma.lift
.. highlight:: ipython3

Lifts a function out of its environment to convert it into a pure function. This is accomplished by converting all `free variables <https://docs.python.org/3/reference/executionmodel.html#binding-of-names>`_ into keyword-only arguments. This works best on closures, where free variables can be automatically detected (Python stores them with the function object), but global variables can also be explicitly lifted as well.

For example, consider the following closure::

    def make_f(x):
        def f(y):
            return x + y
        return f

    my_f = make_f(5)
    my_f(3)  # 8

Closures are handy programming tools, but are not purely functional and hence can cause issues with code generators. Converting the closure into a pure function is relatively simple, by simply replacing all free variables with parameters. For example, the above code could be converted to::

    def f(y, *, x):
        return x + y

    f(3, x=5)

There are minor quirks to this process in Python to handle global variables and imports (both of which are mutable state around the function, but aren't necessarily labelled as "free variables"), but the essential process remains the same. :func:`pragma.lift` enables the above tranformation easily, either when the closure is created, or once it has been obtained::

    In [1]: def make_f(x):
       ...:     @pragma.lift(imports=False)
       ...:     def f(y):
       ...:         return x + y
       ...:     return f
       ...:

    In [2]: my_f = make_f(5)

    In [3]: my_f??
    Signature: my_f(y, *, x)
    Source:
    def f(y, *, x):
        return x + y

Note that, by default, lift attempts to return the simplest possible function that mimics the wrapped function while including all closure variables as arguments. However, several features are available to produce more useful and transparent pure functions. These features will be discussed below.

Defaults and Annotations
++++++++++++++++++++++++

It should be noticed that, in the above example, the produced function ``f`` requires that ``x`` be provided on every function call. While this makes the function pure and free of its closure, perhaps we want to infer some information from the closure to simplify the use of the produced pure function. By using the value of the free variable in the function's closure, we can infer the variable's default value and general type, if desired. For example, the above closure could also have been rewritten as the following pure function::

    def f(y, *, x=3): ...

Or even more specifically as::

    def f(y, *, x: int=3): ...

If the variable's value can be converted into a Python literal, and if its type can be converted to a string, then its default value and type annotation, respectively, may be added by :func:`pragma.lift` at decoration time::

    In [1]: def make_f(x):
       ...:     @pragma.lift(defaults=True, annotate_types=True, imports=False)
       ...:     def f(y):
       ...:         return x + y
       ...:     return f
       ...:

    In [2]: f = make_f(5)

    In [3]: f??
    Signature: f(y, *, x:int=5)
    Source:
    def f(y, *, x: int=5):
        return x + y

Additionally, both ``defaults`` and ``annotate_types`` can take a list to selectively apply to certain free variables::

    In [1]: def make_g(x, y):
       ...:     @pragma.lift(defaults=['x'], annotate_types=['y'], imports=False)
       ...:     def g(z):
       ...:         return x + y + z
       ...:     return g
       ...:

    In [2]: g = make_g(1, 2)

    In [3]: g??
    Signature: g(z, *, x=1, y:int)
    Source:
    def g(z, *, x=1, y: int):
        return x + y + z

If complete control is needed, these may also be dictionaries, where the key is the free variable name. ``defaults`` requires that the value of the dictionary entry, if it exists, must be a Python literal or any ``ast.AST`` expression (``ast.expr``). For ``annotate_types``, the value of the dictionary entry, if it exists, must be a string or ``ast.AST`` expression (``ast.expr``).

Globals
+++++++

Python does not annotate free variables that are available in the function's global context (versus its closure). This information might theoretically be statically extracted from the function's code, it is safest simply to require this to be specified explicitly at decoration time. This is done using the ``lift_globals`` list::

    x = 5

    @pragma.lift(lift_globals=['x'], imports=False)
    def f(y):
        return x + y

    f(7, x=7)  # 14

Imports
+++++++

For the produced function to be truly functional (as much as can be in Python), it cannot rely on its global environment at all. Most practical functions, however, rely on imported modules, which are often imported at the module level. Re-writing a function to contain all of its own needed imports is tedious and prone to accidentally using globally imported modules anyway. To make this utility practical, by default it finds all imports in the global and closure context and includes them within the function. The performance impact of this should be minimal, since module imports are cached in Python. If imports are not suppressed like in the above examples, module imports are added to the top of the function's code (respecting the docstring, if any)::

    In [1]: import pragma
       ...: import sys
       ...:
       ...: @pragma.lift
       ...: def f():
       ...:     return sys.version_info
       ...:
    f
    In [2]: f??
    Signature: f()
    Source:
    def f():
        import pragma
        import sys
        return sys.version_info

Note that, just like global variables, global imports can't be checked for necessity and so are universally included. Which modules get imported can be filtered by passing a list to ``imports``::

    In [1]: import pragma
       ...: import sys
       ...:
       ...: @pragma.lift(imports=['sys'])
       ...: def f():
       ...:     return sys.version_info
       ...:

    In [2]: f??
    Signature: f()
    Source:
    def f():
        import sys
        return sys.version_info


