from textwrap import dedent

import pragma
from .test_pragma import PragmaTest


class TestUnroll(PragmaTest):
    def test_unroll_range(self):
        @pragma.unroll
        def f():
            for i in range(3):
                yield i

        self.assertEqual(list(f()), [0, 1, 2])

    def test_unroll_various(self):
        g = lambda: None
        g.a = [1, 2, 3]
        g.b = 6

        @pragma.unroll(return_source=True)
        def f(x):
            y = 5
            a = range(3)
            b = [1, 2, 4]
            c = (1, 2, 5)
            d = reversed(a)
            e = [x, x, x]
            f = [y, y, y]
            for i in a:
                yield i
            for i in b:
                yield i
            for i in c:
                yield i
            for i in d:
                yield i
            for i in e:
                yield i
            for i in f:
                yield i
            for i in g.a:
                yield i
            for i in [g.b + 0, g.b + 1, g.b + 2]:
                yield i

        result = dedent('''
        def f(x):
            y = 5
            a = range(3)
            b = [1, 2, 4]
            c = 1, 2, 5
            d = reversed(a)
            e = [x, x, x]
            f = [y, y, y]
            yield 0
            yield 1
            yield 2
            yield 1
            yield 2
            yield 4
            yield 1
            yield 2
            yield 5
            yield 2
            yield 1
            yield 0
            yield x
            yield x
            yield x
            yield 5
            yield 5
            yield 5
            yield 1
            yield 2
            yield 3
            yield 6
            yield 7
            yield 8
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_unroll_const_list(self):
        @pragma.unroll
        def f():
            for i in [1, 2, 4]:
                yield i

        self.assertEqual(list(f()), [1, 2, 4])

    def test_unroll_const_tuple(self):
        @pragma.unroll
        def f():
            for i in (1, 2, 4):
                yield i

        self.assertEqual(list(f()), [1, 2, 4])

    def test_unroll_range_source(self):
        @pragma.unroll(return_source=True)
        def f():
            for i in range(3):
                yield i

        result = dedent('''
        def f():
            yield 0
            yield 1
            yield 2
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_unroll_list_source(self):
        @pragma.unroll(return_source=True)
        def f():
            for i in [1, 2, 4]:
                yield i

        result = dedent('''
        def f():
            yield 1
            yield 2
            yield 4
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_unroll_dyn_list_source(self):
        @pragma.unroll(return_source=True)
        def f():
            x = 3
            a = [x, x, x]
            for i in a:
                yield i
            x = 4
            a = [x, x, x]
            for i in a:
                yield i

        result = dedent('''
        def f():
            x = 3
            a = [x, x, x]
            yield 3
            yield 3
            yield 3
            x = 4
            a = [x, x, x]
            yield 4
            yield 4
            yield 4
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_unroll_dyn_list(self):
        def summation(x=0):
            a = [x, x, x]
            v = 0
            for _a in a:
                v += _a
            return v

        summation_source = pragma.unroll(return_source=True)(summation)
        summation = pragma.unroll(summation)

        code = dedent('''
        def summation(x=0):
            a = [x, x, x]
            v = 0
            v += x
            v += x
            v += x
            return v
        ''')
        self.assertEqual(summation_source.strip(), code.strip())
        self.assertEqual(summation(), 0)
        self.assertEqual(summation(1), 3)
        self.assertEqual(summation(5), 15)

    def test_unroll_dyn_list_const(self):
        @pragma.collapse_literals(return_source=True)
        @pragma.unroll(x=3)
        def summation():
            a = [x, x, x]
            v = 0
            for _a in a:
                v += _a
            return v

        code = dedent('''
        def summation():
            a = [x, x, x]
            v = 0
            v += 3
            v += 3
            v += 3
            return 9
        ''')
        self.assertEqual(summation.strip(), code.strip())

    def test_unroll_2range_source(self):
        @pragma.unroll(return_source=True)
        def f():
            for i in range(3):
                for j in range(3):
                    yield i + j

        result = dedent('''
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
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_unroll_2list_source(self):
        @pragma.unroll(return_source=True)
        def f():
            for i in [[1, 2, 3], [4, 5], [6]]:
                for j in i:
                    yield j

        result = dedent('''
        def f():
            yield 1
            yield 2
            yield 3
            yield 4
            yield 5
            yield 6
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_external_definition(self):
        # Known bug: this works when defined as a kwarg, but not as an external variable, but ONLY in unittests...
        # External variables work in practice
        @pragma.unroll(return_source=True, a=range)
        def f():
            for i in a(3):
                print(i)

        result = dedent('''
        def f():
            print(0)
            print(1)
            print(2)
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_tuple_assign(self):
        # This is still early code, so just make sure that it recognizes when a name is assigned to... we don't get values yet
        # TODO: Implement tuple assignment
        @pragma.unroll(return_source=True)
        def f():
            x = 3
            ((y, x), z) = ((1, 2), 3)
            for i in [x, x, x]:
                print(i)

        result = dedent('''
        def f():
            x = 3
            (y, x), z = (1, 2), 3
            print(2)
            print(2)
            print(2)
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_tuple_loop(self):
        @pragma.unroll
        def f():
            for x, y in zip([1, 2, 3], [5, 6, 7]):
                yield x + y

        result = '''
        def f():
            yield 1 + 5
            yield 2 + 6
            yield 3 + 7
        '''

        self.assertSourceEqual(f, result)
        self.assertListEqual(list(f()), [6, 8, 10])

    def test_top_break(self):
        @pragma.unroll(return_source=True)
        def f():
            for i in range(10):
                print(i)
                break

        result = dedent('''
        def f():
            print(0)
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_inner_break(self):
        @pragma.unroll(return_source=True)
        def f(y):
            for i in range(10):
                print(i)
                if i == y:
                    break

        result = dedent('''
        def f(y):
            for i in range(10):
                print(i)
                if i == y:
                    break
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_nonliteral_iterable(self):
        def g(x):
            return -x

        @pragma.unroll
        def f():
            lst = [g(1), 2, 3]
            for l in lst:
                print(l)

        result = '''
        def f():
            print(g(1))
            print(2)
            print(3)
        '''

        self.assertSourceEqual(f, result)
