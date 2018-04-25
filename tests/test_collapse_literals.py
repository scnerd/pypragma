from textwrap import dedent

import pragma
from .test_pragma import PragmaTest


class TestCollapseLiterals(PragmaTest):
    def test_full_run(self):
        def f(y):
            x = 3
            r = 1 + x
            for z in range(2):
                r *= 1 + 2 * 3
                for abc in range(x):
                    for a in range(abc):
                        for b in range(y):
                            r += 1 + 2 + y
            return r

        deco_f = pragma.collapse_literals(f)
        self.assertEqual(f(0), deco_f(0))
        self.assertEqual(f(1), deco_f(1))
        self.assertEqual(f(5), deco_f(5))
        self.assertEqual(f(-1), deco_f(-1))

        deco_f = pragma.collapse_literals(pragma.unroll(f))
        self.assertEqual(f(0), deco_f(0))
        self.assertEqual(f(1), deco_f(1))
        self.assertEqual(f(5), deco_f(5))
        self.assertEqual(f(-1), deco_f(-1))

    def test_basic(self):
        @pragma.collapse_literals(return_source=True)
        def f():
            return 1 + 1

        result = dedent('''
        def f():
            return 2
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_vars(self):
        @pragma.collapse_literals(return_source=True)
        def f():
            x = 3
            y = 2
            return x + y

        result = dedent('''
        def f():
            x = 3
            y = 2
            return 5
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_partial(self):
        @pragma.collapse_literals(return_source=True)
        def f(y):
            x = 3
            return x + 2 + y

        result = dedent('''
        def f(y):
            x = 3
            return 5 + y
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_constant_index(self):
        @pragma.collapse_literals
        def f():
            x = [1, 2, 3]
            return x[0]

        result = '''
        def f():
            x = [1, 2, 3]
            return 1
        '''
        self.assertSourceEqual(f, result)
        self.assertEqual(f(), 1)

    def test_with_unroll(self):
        @pragma.collapse_literals(return_source=True)
        @pragma.unroll
        def f():
            for i in range(3):
                print(i + 2)

        result = dedent('''
        def f():
            print(2)
            print(3)
            print(4)
        ''')
        self.assertEqual(f.strip(), result.strip())

    # # TODO: Figure out variable levels of specificity...
    # def test_with_objects(self):
    #     @pragma.collapse_literals(return_source=True)
    #     def f():
    #         v = [object(), object()]
    #         return v[0]
    #
    #     result = dedent('''
    #     def f():
    #         v = [object(), object()]
    #         return v[0]
    #     ''')
    #     self.assertEqual(f.strip(), result.strip())

    def test_invalid_collapse(self):
        import warnings
        warnings.resetwarnings()
        with warnings.catch_warnings(record=True) as w:
            @pragma.collapse_literals
            def f():
                return 1 + "2"

            self.assertIsInstance(w[-1].category(), UserWarning)

        warnings.resetwarnings()
        with warnings.catch_warnings(record=True) as w:
            @pragma.collapse_literals
            def f():
                return -"5"

            self.assertIsInstance(w[-1].category(), UserWarning)

    def test_conditional_erasure(self):
        @pragma.collapse_literals
        def f(y):
            x = 0
            if y == x:
                x = 1
            return x

        result = '''
        def f(y):
            x = 0
            if y == 0:
                x = 1
            return x
        '''

        self.assertSourceEqual(f, result)
        self.assertEqual(f(0), 1)
        self.assertEqual(f(1), 0)

    # # TODO: Implement the features to get this test to pass
    # def test_conditional_partial_erasure(self):
    #     @pragma.collapse_literals(return_source=True)
    #     def f(y):
    #         x = 0
    #         if y == x:
    #             x = 1
    #             return x
    #         return x
    #
    #     result = dedent('''
    #     def f(y):
    #         x = 0
    #         if y == 0:
    #             x = 1
    #             return 1
    #         return x
    #     ''')
    #     self.assertEqual(f.strip(), result.strip())

    def test_constant_conditional_erasure(self):
        @pragma.collapse_literals(return_source=True)
        def f(y):
            x = 0
            if x <= 0:
                x = 1
            return x

        result = dedent('''
        def f(y):
            x = 0
            x = 1
            return 1
        ''')
        self.assertEqual(f.strip(), result.strip())

        def fn():
            if x == 0:
                x = 'a'
            elif x == 1:
                x = 'b'
            else:
                x = 'c'
            return x

        result0 = dedent('''
        def fn():
            x = 'a'
            return 'a'
        ''')
        result1 = dedent('''
        def fn():
            x = 'b'
            return 'b'
        ''')
        result2 = dedent('''
        def fn():
            x = 'c'
            return 'c'
        ''')
        self.assertEqual(pragma.collapse_literals(return_source=True, x=0)(fn).strip(), result0.strip())
        self.assertEqual(pragma.collapse_literals(return_source=True, x=1)(fn).strip(), result1.strip())
        self.assertEqual(pragma.collapse_literals(return_source=True, x=2)(fn).strip(), result2.strip())

    def test_unary(self):
        @pragma.collapse_literals(return_source=True)
        def f():
            return 1 + -5

        result = dedent('''
        def f():
            return -4
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_funcs(self):
        @pragma.collapse_literals(return_source=True)
        def f():
            return sum(range(5))

        result = dedent('''
        def f():
            return 10
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_funcs2(self):
        my_list = [1, 2, 3]

        @pragma.collapse_literals
        def f(x):
            return x + sum([sum(my_list), min(my_list), max(my_list)])

        result = '''
        def f(x):
            return x + 10
        '''

        self.assertSourceEqual(f, result)
        self.assertEqual(f(5), 15)

    # # Implement the functionality to get this test to pass
    # def test_assign_to_iterable(self):
    #     @pragma.collapse_literals(return_source=True)
    #     def f():
    #         x = [1, 2, 3]
    #         x[1] = 4
    #         return x[1]
    #
    #     self.assertSourceEqual(f, '''
    #     def f():
    #         x = [1, 2, 3]
    #         x[1] = 4
    #         return 4
    #     ''')

    def test_tuple_assign(self):
        @pragma.collapse_literals
        def f():
            x = 3
            ((y, x), z) = ((1, 2), 3)
            return x

        result = dedent('''
        def f():
            x = 3
            (y, x), z = (1, 2), 3
            return 2
        ''')
        self.assertSourceEqual(f, result)
        self.assertEqual(f(), 2)

    def test_simple_functions(self):
        a = [1, 2, 3, 4]

        @pragma.collapse_literals
        def f():
            print(len(a))
            print(sum(a))
            print(a)

        result = '''
        def f():
            print(4)
            print(10)
            print(a)
        '''

        self.assertSourceEqual(f, result)

    def test_reduction(self):
        a = [1, 2, 3]

        @pragma.collapse_literals
        def f():
            b = a
            c = b
            d = c
            e = d
            print(e)
            print(e[0])

        result = '''
        def f():
            b = a
            c = b
            d = c
            e = d
            print(e)
            print(1)
        '''

        self.assertSourceEqual(f, result)

    def test_odd_binop(self):
        @pragma.collapse_literals
        def f():
            l = [[0]] * 5
            print(l[4][0])

        result = '''
        def f():
            l = [[0], [0], [0], [0], [0]]
            print(0)
        '''

        self.assertSourceEqual(f, result)
