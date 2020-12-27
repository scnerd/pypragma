# file deepcode ignore E0602: Ignore undefined variables because they never go live if just converting function string
# file deepcode ignore E0102: Ignore function names that are redefined, such as f(x)
from textwrap import dedent
from unittest import SkipTest
import sys
import math

import pragma
from .test_pragma import PragmaTest

dict_order_maintained = (sys.version_info.minor >= 6)


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

    def test_enumerate(self):
        v = [0, 3, object()]

        @pragma.unroll
        @pragma.deindex(v, 'v', collapse_iterables=True)
        def f():
            for i, elem in enumerate(v):
                yield i, elem

        result = '''
        def f():
            yield 0, 0
            yield 1, 3
            yield 2, v_2
        '''

        self.assertSourceEqual(f, result)

    def test_dict_items(self):
        if not dict_order_maintained:
            raise SkipTest()
        d = {'a': 1, 'b': 2}

        @pragma.unroll
        def f():
            for k, v in d.items():
                yield k
                yield v

        result = '''
        def f():
            yield 'a'
            yield 1
            yield 'b'
            yield 2
        '''

        self.assertSourceEqual(f, result)
        self.assertListEqual(list(f()), ['a', 1, 'b', 2])

    def test_nonliteral_dict_items(self):
        if not dict_order_maintained:
            raise SkipTest()
        d = {'a': object(), 'b': object()}

        @pragma.unroll
        @pragma.deindex(d, 'd', collapse_iterables=True)
        def f():
            for k, v in d.items():
                yield k
                yield v

        result = '''
        def f():
            yield 'a'
            yield d_a
            yield 'b'
            yield d_b
        '''

        self.assertSourceEqual(f, result)
        self.assertListEqual(list(f()), ['a', d['a'], 'b', d['b']])

    def test_unroll_special_dict(self):
        if not dict_order_maintained:
            raise SkipTest()
        d = {(15, 20): 1, ('x', 1): 2, 'hyphen-key': 3, 1.25e3: 4, 'regular_key': 5}

        @pragma.unroll
        @pragma.deindex(d, 'd', collapse_iterables=True)
        def f():
            for k, v in d.items():
                yield k
                yield v

        result = '''
        def f():
            yield 15, 20
            yield 1
            yield 'x', 1
            yield 2
            yield 'hyphen-key'
            yield 3
            yield 1250.0
            yield 4
            yield 'regular_key'
            yield 5
        '''

        self.assertSourceEqual(f, result)

    def test_unroll_zip(self):
        a = [1, 2]
        b = [10, 20]

        # assign multiple values
        @pragma.unroll
        def f():
            for _a, _b in zip(a, b):
                yield _a
                yield _b

        result = '''
        def f():
            yield 1
            yield 10
            yield 2
            yield 20
        '''
        self.assertSourceEqual(f, result)

        # assign to a single variable representing a tuple, then deindex
        @pragma.unroll
        def f():
            for z in zip(a, b):
                yield z[0]
                yield z[1]

        self.assertSourceEqual(f, result)
        self.assertListEqual(list(f()), [1, 10, 2, 20])

    def test_unroll_into_subscriptassign(self):
        a = (1, 3)
        x = 1  # make sure that this does not collapse

        @pragma.unroll
        def f():
            for elem in a:
                p[elem] = 5
                p[x] += x

        result = '''
        def f():
            p[1] = 5
            p[x] += x
            p[3] = 5
            p[x] += x
        '''
        self.assertSourceEqual(f, result)

    def test_simple_unrolldeindex(self):
        # to demonstrate exactly what deindex does, this list has non-primitive dicts, but they are *always* subscripted to resolve to literals
        # That means you don't need pragma.deindex or pragma.collapse_literals
        a = [{'a': 1}, {'a': 2}]
        @pragma.unroll
        def f():
            for elem in a:
                yield elem['a']

        result = '''
        def f():
            yield 1
            yield 2
        '''
        self.assertSourceEqual(f, result)

    def test_complex_unrolldeindex(self):
        # This one has elements that are either not deindexed in the function or that fail to resolve a deindex
        a = [
            1,  # this clearly fails to deindex, but we substitute the literal anyways
            object(),  # it is unknown if this can deindex, so we substitute the Name 'a_1'
            {'b': 2}  # this will work. it will collapse all the way, even on the left hand side
        ]

        @pragma.unroll
        @pragma.deindex(a, 'a', collapse_iterables=True)
        def f():
            for elem in a:
                yield elem  # not deindexed
                yield elem['b']  # fails to resolve except when elem == {'b': 2}
                p[elem['b']] = 5

        result = '''
        def f():
            yield 1
            yield 1['b']
            p[1['b']] = 5
            yield a_1
            yield a_1['b']
            p[a_1['b']] = 5
            yield {'b': 2}
            yield 2
            p[2] = 5
        '''
        self.assertSourceEqual(f, result)

    def test_unroll_doubledeindex(self):
        a = [{'b': 2}, {'b': 3}]

        @pragma.unroll
        def f():
            for elem in a:
                yield p[elem['b']]
                p[elem['b']][x, y] = 5
                yield p[1 + 1]  # don't collapse this

        result = '''
        def f():
            yield p[2]
            p[2][x, y] = 5
            yield p[1 + 1]
            yield p[3]
            p[3][x, y] = 5
            yield p[1 + 1]
        '''
        self.assertSourceEqual(f, result)



    def test_targeted_unroll(self):
        a = [1, 2]
        b = [3, 4]

        @pragma.unroll(unroll_targets=['elem'])
        def f():
            for q in a:
                yield q
            for elem in b:
                yield elem

        result = '''
        def f():
            for q in a:
                yield q
            yield 3
            yield 4
        '''
        self.assertSourceEqual(f, result)

    def test_manual_tier(self):
        # pragma.unroll does not unroll a subloop for you, but you can do it manually like this
        a = list(range(0, 7))
        n_inners = 2

        n_outers = math.floor(len(a) / n_inners)
        remainder = len(a) % n_inners

        @pragma.unroll(unroll_targets=['i1'])
        @pragma.collapse_literals()
        def f():
            for iouter in range(n_outers):
                for i1 in range(n_inners):
                    yield a[iouter * n_inners + i1]
            for i1 in range(remainder):
                yield a[n_outers * n_inners + i1]

        result = '''
        def f():
            for iouter in range(3):
                yield a[iouter * 2 + 0]
                yield a[iouter * 2 + 1]
            yield a[6 + 0]
        '''
        self.assertSourceEqual(f, result)
        self.assertEqual(list(f()), a)

        @pragma.unroll(unroll_targets=['i1'])
        @pragma.collapse_literals()
        def f():
            for iouter in range(0, n_inners * n_outers, n_inners):
                for i1 in range(n_inners):
                    yield a[iouter + i1]
            for i1 in range(remainder):
                yield a[n_inners * n_outers + i1]

        result = '''
        def f():
            for iouter in range(0, 6, 2):
                yield a[iouter + 0]
                yield a[iouter + 1]
            yield a[6 + 0]
        '''
        self.assertSourceEqual(f, result)
        self.assertEqual(list(f()), a)

    def test_autotier_basic(self):
        a = list(range(0, 7))

        @pragma.unroll(unroll_in_tiers=('PRAGMArange', len(a), 2))
        def f():
            for i in PRAGMArange:
                yield a[i]

        result = '''
        def f():
            for PRAGMA_iouter in range(0, 6, 2):
                yield a[PRAGMA_iouter]
                yield a[PRAGMA_iouter + 1]
            yield a[6]
        '''
        self.assertSourceEqual(f, result)
        self.assertEqual(list(f()), a)

    def test_autotier_allremainder(self):
        a = list(range(0, 7))

        for L in [4, 7, 100]:
            @pragma.unroll(unroll_in_tiers=('PRAGMArange', len(a), L))
            def f():
                for i in PRAGMArange:
                    yield a[i]

            result = '''
            def f():
                yield a[0]
                yield a[1]
                yield a[2]
                yield a[3]
                yield a[4]
                yield a[5]
                yield a[6]
            '''
            self.assertSourceEqual(f, result)
            self.assertEqual(list(f()), a)

