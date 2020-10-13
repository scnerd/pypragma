from collections import namedtuple
from textwrap import dedent

import pragma
from .test_pragma import PragmaTest


class TestUnroll(PragmaTest):
    def test_unroll_range(self):
        @pragma.unroll
        def f():
            for i in range(3):
                yield i

        result = '''
        def f():
            yield 0
            yield 1
            yield 2
        '''

        self.assertSourceEqual(f, result)
        self.assertEqual(list(f()), [0, 1, 2])

    def test_unroll_various(self):
        g = lambda: None
        g.a = [1, 2, 3]
        g.b = 6

        @pragma.unroll
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

        result = '''
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
        '''

        self.assertSourceEqual(f, result)

    def test_unroll_namedtuple(self):
        a = [1, 2, 3]
        nttyp = namedtuple('nttyp', 'x,y,z')
        na = nttyp(*a)

        @pragma.unroll
        def f():
            for i in na:
                yield i
            for j in na._fields:
                yield j
        result = '''
        def f():
            yield 1
            yield 2
            yield 3
            yield 'x'
            yield 'y'
            yield 'z'
        '''
        self.assertSourceEqual(f, result)

    def test_unroll_const_list(self):
        @pragma.unroll
        def f():
            for i in [1, 2, 4]:
                yield i

        result = dedent('''
        def f():
            yield 1
            yield 2
            yield 4
        ''')

        self.assertSourceEqual(f, result)
        self.assertEqual(list(f()), [1, 2, 4])

    def test_unroll_const_tuple(self):
        @pragma.unroll
        def f():
            for i in (1, 2, 4):
                yield i

        self.assertEqual(list(f()), [1, 2, 4])

    def test_unroll_dyn_list_source(self):
        @pragma.unroll
        def f():
            x = 3
            a = [x, x, x]
            for i in a:
                yield i
            x = 4
            a = [x, x, x]
            for i in a:
                yield i

        result = '''
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
        '''

        self.assertSourceEqual(f, result)

    def test_unroll_dyn_list(self):
        @pragma.unroll
        def summation(x=0):
            a = [x, x, x]
            v = 0
            for _a in a:
                v += _a
            return v


        result = '''
        def summation(x=0):
            a = [x, x, x]
            v = 0
            v += x
            v += x
            v += x
            return v
        '''

        self.assertSourceEqual(summation, result)
        self.assertEqual(summation(), 0)
        self.assertEqual(summation(1), 3)
        self.assertEqual(summation(5), 15)

    def test_unroll_dyn_list_const(self):
        @pragma.collapse_literals
        @pragma.unroll(x=3)
        def summation():
            a = [x, x, x]
            v = 0
            for _a in a:
                v += _a
            return v

        result = '''
        def summation():
            a = [x, x, x]
            v = 0
            v += 3
            v += 3
            v += 3
            return 9
        '''

        self.assertSourceEqual(summation, result)

    def test_unroll_2range_source(self):
        @pragma.unroll
        def f():
            for i in range(3):
                for j in range(3):
                    yield i + j

        result = '''
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
        '''

        self.assertSourceEqual(f, result)

    def test_unroll_2list_source(self):
        @pragma.unroll
        def f():
            for i in [[1, 2, 3], [4, 5], [6]]:
                for j in i:
                    yield j

        result = '''
        def f():
            yield 1
            yield 2
            yield 3
            yield 4
            yield 5
            yield 6
        '''

        self.assertSourceEqual(f, result)

    def test_external_definition(self):
        # Known bug: this works when defined as a kwarg, but not as an external variable, but ONLY in unittests...
        # External variables work in practice
        @pragma.unroll(a=range)
        def f():
            for i in a(3):
                print(i)

        result = '''
        def f():
            print(0)
            print(1)
            print(2)
        '''

        self.assertSourceEqual(f, result)

    def test_tuple_assign(self):
        @pragma.unroll
        def f():
            x = 3
            ((y, x), z) = ((1, 2), 3)
            for i in [x, x, x]:
                print(i)

        result = '''
        def f():
            x = 3
            (y, x), z = (1, 2), 3
            print(2)
            print(2)
            print(2)
        '''

        self.assertSourceEqual(f, result)

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
        @pragma.unroll
        def f():
            for i in range(10):
                print(i)
                break

        result = dedent('''
        def f():
            print(0)
        ''')

        self.assertSourceEqual(f, result)

    def test_inner_break(self):
        @pragma.unroll
        def f(y):
            for i in range(10):
                print(i)
                if i == y:
                    break

        result = '''
        def f(y):
            for i in range(10):
                print(i)
                if i == y:
                    break
        '''

        self.assertSourceEqual(f, result)

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
            lst = [g(1), 2, 3]
            print(g(1))
            print(2)
            print(3)
        '''

        self.assertSourceEqual(f, result)

