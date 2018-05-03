from textwrap import dedent

import pragma
from .test_pragma import PragmaTest


class TestInline(PragmaTest):
    def test_basic(self):
        def g(x):
            return x**2

        @pragma.inline(g)
        def f(y):
            return g(y + 3)

        result = '''
        def f(y):
            _g_0 = dict(x=y + 3)
            try:
                raise _PRAGMA_INLINE_RETURN(_g_0['x'] ** 2)
            except _PRAGMA_INLINE_RETURN as _g_return_0_exc:
                _g_return_0 = _g_return_0_exc.return_val
            else:
                _g_return_0 = None
            finally:
                del _g_0
            return _g_return_0
        '''

        self.assertSourceEqual(f, result)
        self.assertEqual(f(1), ((1 + 3) ** 2))

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

        inline_f = pragma.inline(g)(f)

        result1 = '''
        def f():
            _g_0 = dict(x=1, args=(2, 3, 4), y=5, kwargs={'z': 6, 'w': 7})
            try:
                print('X = {}'.format(_g_0['x']))
                for _g_0['i'], _g_0['a'] in enumerate(_g_0['args']):
                    print('args[{}] = {}'.format(i, a))
                print('Y = {}'.format(_g_0['y']))
                for _g_0['k'], _g_0['v'] in _g_0['kwargs'].items():
                    print('{} = {}'.format(k, v))
            finally:
                del _g_0
            _g_return_0
        '''
        result2 = '''
        def f():
            _g_0 = dict(x=1, args=(2, 3, 4), y=5, kwargs={'w': 7, 'z': 6})
            try:
                print('X = {}'.format(_g_0['x']))
                for _g_0['i'], _g_0['a'] in enumerate(_g_0['args']):
                    print('args[{}] = {}'.format(i, a))
                print('Y = {}'.format(_g_0['y']))
                for _g_0['k'], _g_0['v'] in _g_0['kwargs'].items():
                    print('{} = {}'.format(k, v))
            finally:
                del _g_0
            _g_return_0
        '''

        self.assertSourceIn(inline_f, result1, result2)
        self.assertEqual(f(), inline_f())

    def test_recursive(self):
        def fib(n):
            if n <= 0:
                return 1
            elif n == 1:
                return 1
            else:
                return fib(n-1) + fib(n-2)

        from miniutils import tic
        known_fibs = {
            0: 1,
            1: 1,
            2: 2,
            3: 3,
            4: 5,
            5: 8,
        }
        toc = tic()
        for depth in range(1, 4):
            inline_fib = pragma.inline(fib, max_depth=depth)(fib)
            toc('Inlined fibonacci function to depth of {}'.format(inline_fib))
            for k, v in known_fibs.items():
                self.assertEqual(fib(k), v)
                toc("Ran fib_{}({})=={}".format(depth, k, v))

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

        f_code = pragma.inline(g)(f)

        result = '''
        def f(y):
            if y <= 0:
                return 0
            _g_0 = dict(x=y - 1)
            try:
                raise _PRAGMA_INLINE_RETURN(f(x / 2))
            except _PRAGMA_INLINE_RETURN as _g_return_0_exc:
                _g_return_0 = _g_return_0_exc.return_val
            else:
                _g_return_0 = None
            finally:
                del _g_0
            return _g_return_0
        '''

        self.assertSourceEqual(f_code, result)

        f2_code = pragma.inline(f, g, f=f)(f)

        result2 = dedent('''
        def f(y):
            if y <= 0:
                return 0
            _g_0 = dict(x=y - 1)
            _f_0 = dict(y=x / 2)
            try:
                if _f_0['y'] <= 0:
                    raise _PRAGMA_INLINE_RETURN(0)
                raise _PRAGMA_INLINE_RETURN(g(y - 1))
            except _PRAGMA_INLINE_RETURN as _f_return_0:
                _f_return_0 = _f_return_0.return_val
            else:
                _f_return_0 = None
            finally:
                del _f_0
            try:
                raise _PRAGMA_INLINE_RETURN(_f_return_0)
            except _PRAGMA_INLINE_RETURN as _g_return_0:
                _g_return_0 = _g_return_0.return_val
            else:
                _g_return_0 = None
            finally:
                del _g_0
            return _g_return_0
        ''')

        self.assertSourceEqual(f2_code, result2)

    def test_generator(self):
        def g(y):
            for i in range(y):
                yield i
            yield from range(y)

        @pragma.inline(g)
        def f(x):
            return sum(g(x))

        result = '''
        def f(x):
            _g_0 = dict([('yield', [])], y=x)
            try:
                for _g_0['i'] in range(_g_0['y']):
                    _g_0['yield'].append(_g_0['i'])
                _g_0['yield'].extend(range(_g_0['y']))
            finally:
                _g_return_0 = _g_0['yield']
                del _g_0
            return sum(_g_return_0)
        '''

        self.assertSourceEqual(f, result)
        self.assertEqual(f(3), 6)

    def test_variable_starargs(self):
        def g(a, b, c):
            return a + b + c

        @pragma.inline(g)
        def f(x):
            return g(*x)

        result = '''
        def f(x):
            return g(*x)
        '''

        self.assertSourceEqual(f, result)

    def test_multiple_inline(self):
        def a(x):
            return x ** 2

        def b(x):
            return x + 2

        @pragma.unroll
        @pragma.inline(a, b)
        def f(x):
            return a(x) + b(x)

        result = '''
        def f(x):
            _a_0 = dict(x=x)
            try:
                raise _PRAGMA_INLINE_RETURN(_a_0['x'] ** 2)
            except _PRAGMA_INLINE_RETURN as _a_return_0_exc:
                _a_return_0 = _a_return_0_exc.return_val
            else:
                _a_return_0 = None
            finally:
                del _a_0
            _b_0 = dict(x=x)
            try:
                raise _PRAGMA_INLINE_RETURN(_b_0['x'] + 2)
            except _PRAGMA_INLINE_RETURN as _b_return_0_exc:
                _b_return_0 = _b_return_0_exc.return_val
            else:
                _b_return_0 = None
            finally:
                del _b_0
            return _a_return_0 + _b_return_0
        '''

        self.assertSourceEqual(f, result)
        self.assertEqual(f(5), 32)

    def test_coverage(self):
        def g(y):
            while False:
                print(y)

        def f():
            try:
                g(5)
            except:
                raise

        print(pragma.inline(g)(f))
        self.assertEqual(f(), pragma.inline(g)(f)())

    def test_bug_my_range(self):
        def my_range(x):
            i = 0
            while i < x:
                yield i
                i += 1

        @pragma.unroll
        @pragma.inline(my_range)
        def test_my_range():
            return list(my_range(5))

        result = '''
        def test_my_range():
            _my_range_0 = dict([('yield', [])], x=5)
            try:
                _my_range_0['i'] = 0
                while _my_range_0['i'] < _my_range_0['x']:
                    _my_range_0['yield'].append(_my_range_0['i'])
                    _my_range_0['i'] += 1
            finally:
                _my_range_return_0 = _my_range_0['yield']
                del _my_range_0
            return list(_my_range_return_0)
        '''

        self.assertSourceEqual(test_my_range, result)
        self.assertEqual(test_my_range(), [0, 1, 2, 3, 4])

    def test_return_inside_loop(self):
        def g(x):
            for i in range(x + 1):
                if i == x:
                    return i
            return None

        @pragma.inline(g)
        def f(y):
            return g(y + 2)

        result = '''
        def f(y):
            _g_0 = dict(x=y + 2)
            try:
                for _g_0['i'] in range(_g_0['x'] + 1):
                    if _g_0['i'] == _g_0['x']:
                        raise _PRAGMA_INLINE_RETURN(_g_0['i'])
                raise _PRAGMA_INLINE_RETURN(None)
            except _PRAGMA_INLINE_RETURN as _g_return_0_exc:
                _g_return_0 = _g_return_0_exc.return_val
            else:
                _g_return_0 = None
            finally:
                del _g_0
            return _g_return_0
        '''

        self.assertSourceEqual(f, result)
        self.assertEqual(f(3), 5)

