from textwrap import dedent

import pragma
from .test_pragma import PragmaTest


class TestInline(PragmaTest):
    def test_basic(self):
        def g(x):
            return x**2

        @pragma.inline(g, return_source=True)
        def f(y):
            return g(y + 3)

        result = dedent('''
        def f(y):
            _g_0 = dict(x=y + 3)
            for ____ in [None]:
                _g_0['return'] = _g_0['x'] ** 2
                break
            _g_return_0 = _g_0.get('return', None)
            del _g_0
            return _g_return_0
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_basic_run(self):
        def g(x):
            return x**2

        @pragma.inline(g)
        def f(y):
            return g(y + 3)

        self.assertEqual(f(1), ((1 + 3) ** 2))

    def test_basic_unroll(self):
        def g(x):
            return x**2

        @pragma.unroll(return_source=True)
        @pragma.inline(g)
        def f(y):
            return g(y + 3)

        result = dedent('''
        def f(y):
            _g_0 = dict(x=y + 3)
            _g_0['return'] = _g_0['x'] ** 2
            _g_return_0 = _g_0.get('return', None)
            del _g_0
            return _g_return_0
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_more_complex(self):
        def g(x, *args, y, **kwargs):
            print("X = {}".format(x))
            for i, a in enumerate(args):
                print("args[{}] = {}".format(i, a))
            print("Y = {}".format(y))
            for k, v in kwargs.items():
                print("{} = {}".format(k, v))

        def f():
            g(1, 2, 3, 4, y=5, z=6, w=7)

        result1 = dedent('''
        def f():
            _g_0 = dict(x=1, args=(2, 3, 4), y=5, kwargs={'z': 6, 'w': 7})
            for ____ in [None]:
                print('X = {}'.format(_g_0['x']))
                for i, a in enumerate(_g_0['args']):
                    print('args[{}] = {}'.format(i, a))
                print('Y = {}'.format(_g_0['y']))
                for k, v in _g_0['kwargs'].items():
                    print('{} = {}'.format(k, v))
            del _g_0
            None
        ''')
        result2 = dedent('''
        def f():
            _g_0 = dict(x=1, args=(2, 3, 4), y=5, kwargs={'w': 7, 'z': 6})
            for ____ in [None]:
                print('X = {}'.format(_g_0['x']))
                for i, a in enumerate(_g_0['args']):
                    print('args[{}] = {}'.format(i, a))
                print('Y = {}'.format(_g_0['y']))
                for k, v in _g_0['kwargs'].items():
                    print('{} = {}'.format(k, v))
            del _g_0
            None
        ''')
        self.assertIn(pragma.inline(g, return_source=True)(f).strip(),
                      [result1.strip(), result2.strip()])

        self.assertEqual(f(), pragma.inline(g)(f)())

    def test_recursive(self):
        def fib(n):
            if n <= 0:
                return 1
            elif n == 1:
                return 1
            else:
                return fib(n-1) + fib(n-2)

        from miniutils import tic
        toc = tic()
        fib_code = pragma.inline(fib, max_depth=1, return_source=True)(fib)
        toc("Inlined recursive function to depth 1")
        print(fib_code)
        # fib_code = pragma.inline(fib, max_depth=3, return_source=True)(fib)
        # toc("Inlined recursive function to depth 3")
        # print(fib_code)

        fib = pragma.inline(fib, max_depth=2)(fib)
        toc("Inlined executable function")
        self.assertEqual(fib(0), 1)
        toc("Ran fib(0)")
        self.assertEqual(fib(1), 1)
        toc("Ran fib(1)")
        self.assertEqual(fib(2), 2)
        toc("Ran fib(2)")
        self.assertEqual(fib(3), 3)
        toc("Ran fib(3)")
        self.assertEqual(fib(4), 5)
        toc("Ran fib(4)")
        self.assertEqual(fib(5), 8)
        toc("Ran fib(5)")

    # def test_failure_cases(self):
    #     def g_for(x):
    #         for i in range(5):
    #             yield x
    #
    #     def f(y):
    #         return g_for(y)
    #
    #     self.assertRaises(AssertionError, pragma.inline(g_for), f)

    def test_flip_flop(self):
        def g(x):
            return f(x / 2)

        def f(y):
            if y <= 0:
                return 0
            return g(y - 1)

        f_code = pragma.inline(g, return_source=True)(f)

        result = dedent('''
        def f(y):
            if y <= 0:
                return 0
            _g_0 = dict(x=y - 1)
            for ____ in [None]:
                _g_0['return'] = f(_g_0['x'] / 2)
                break
            _g_return_0 = _g_0.get('return', None)
            del _g_0
            return _g_return_0
        ''')
        self.assertEqual(f_code.strip(), result.strip())

        f_unroll_code = pragma.unroll(return_source=True)(pragma.inline(g)(f))

        result_unroll = dedent('''
        def f(y):
            if y <= 0:
                return 0
            _g_0 = dict(x=y - 1)
            _g_0['return'] = f(_g_0['x'] / 2)
            _g_return_0 = _g_0.get('return', None)
            del _g_0
            return _g_return_0
        ''')
        self.assertEqual(f_unroll_code.strip(), result_unroll.strip())

        f2_code = pragma.inline(f, g, return_source=True, f=f)(f)

        result2 = dedent('''
        def f(y):
            if y <= 0:
                return 0
            _g_0 = dict(x=y - 1)
            _f_0 = dict(y=_g_0['x'] / 2)
            for ____ in [None]:
                if _f_0['y'] <= 0:
                    _f_0['return'] = 0
                    break
                _f_0['return'] = g(_f_0['y'] - 1)
                break
            _f_return_0 = _f_0.get('return', None)
            del _f_0
            for ____ in [None]:
                _g_0['return'] = _f_return_0
                break
            _g_return_0 = _g_0.get('return', None)
            del _g_0
            return _g_return_0
        ''')
        print(f2_code)
        self.assertEqual(f2_code.strip(), result2.strip())

    def test_generator(self):
        def g(y):
            for i in range(y):
                yield i
            yield from range(y)

        @pragma.inline(g, return_source=True)
        def f(x):
            return sum(g(x))

        result = dedent('''
        def f(x):
            _g_0 = dict(y=x, yield=[])
            for ____ in [None]:
                for i in range(_g_0['y']):
                    _g_0['yield'].append(i)
                _g_0['yield'].extend(range(_g_0['y']))
            _g_return_0 = _g_0['yield']
            del _g_0
            return sum(_g_return_0)
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_variable_starargs(self):
        def g(a, b, c):
            return a + b + c

        @pragma.inline(g, return_source=True)
        def f(x):
            return g(*x)

        result = dedent('''
        def f(x):
            return g(*x)
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_multiple_inline(self):
        def a(x):
            return x ** 2

        def b(x):
            return x + 2

        @pragma.unroll(return_source=True)
        @pragma.inline(a, b)
        def f(x):
            return a(x) + b(x)

        result = dedent('''
        def f(x):
            _a_0 = dict(x=x)
            _a_0['return'] = _a_0['x'] ** 2
            _a_return_0 = _a_0.get('return', None)
            del _a_0
            _b_0 = dict(x=x)
            _b_0['return'] = _b_0['x'] + 2
            _b_return_0 = _b_0.get('return', None)
            del _b_0
            return _a_return_0 + _b_return_0
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_coverage(self):
        def g(y):
            while False:
                print(y)

        def f():
            try:
                g(5)
            except:
                raise

        print(pragma.inline(g, return_source=True)(f))
        self.assertEqual(f(), pragma.inline(g)(f)())