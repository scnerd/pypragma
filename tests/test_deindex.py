from collections import namedtuple
import inspect
from textwrap import dedent

import pragma
from .test_pragma import PragmaTest


class TestDeindex(PragmaTest):
    def test_with_literals(self):
        v = [1, 2, 3]

        @pragma.collapse_literals
        @pragma.deindex(v, 'v')
        def f():
            return v[0] + v[1] + v[2]

        result = '''
        def f():
            return 6
        '''

        self.assertSourceEqual(f, result)
        self.assertEqual(f(), sum(v))

    def test_with_objects(self):
        v = [object(), object(), object()]

        @pragma.deindex(v, 'v')
        def f():
            return v[0] + v[1] + v[2]

        result = '''
        def f():
            return v_0 + v_1 + v_2
        '''

        self.assertSourceEqual(f, result)

    def test_with_objects_same_instance(self):
        v = [object(), object(), object()]

        @pragma.deindex(v, 'v')
        def f():
            return v[0]

        result = '''
        def f():
            return v_0
        '''

        self.assertSourceEqual(f, result)
        self.assertIs(f(), v[0])

    def test_with_unroll(self):
        v = [None, None, None]

        @pragma.deindex(v, 'v', return_source=True)
        @pragma.unroll
        def f():
            for i in range(len(v)):
                yield v[i]

        result = dedent('''
        def f():
            yield v_0
            yield v_1
            yield v_2
        ''')

        self.assertSourceEqual(f, result)

    def test_enumerate(self):
        v = [0, 3, object()]
        nv = namedtuple('nttyp', 'a,b,c')(*v)

        def f():
            for i, elem in enumerate(v):
                yield i, elem
        result = dedent('''
        def f():
            yield 0, 0
            yield 1, 3
            yield 2, v_2
        ''')
        f_list = pragma.unroll(pragma.deindex(v, 'v', collapse_iterables=True)(f))
        f_namedtuple = pragma.unroll(pragma.deindex(nv, 'v', collapse_iterables=True)(f))

        self.assertSourceEqual(f_list, result)
        self.assertSourceEqual(f_namedtuple, result)

    def test_with_variable_indices(self):
        v = [object(), object(), object()]

        @pragma.deindex(v, 'v')
        def f(x):
            yield v[0]
            yield v[x]

        result = '''
        def f(x):
            yield v_0
            yield v[x]
        '''

        self.assertSourceEqual(f, result)

    def test_dict(self):
        d = {'a': 1, 'b': 2}

        @pragma.deindex(d, 'd')
        def f(x):
            yield d['a']
            yield d[x]

        result = '''
        def f(x):
            yield d_a
            yield d[x]
        '''

        self.assertSourceEqual(f, result)
        self.assertListEqual(list(f('a')), [1, 1])
        self.assertListEqual(list(f('b')), [1, 2])

    def test_dynamic_function_calls(self):
        funcs = [lambda x: x, lambda x: x ** 2, lambda x: x ** 3]

        # TODO: Support tuple assignment in loop transparently

        @pragma.deindex(funcs, 'funcs')
        @pragma.unroll
        def run_func(i, x):
            for j in range(len(funcs)):
                if i == j:
                    return funcs[j](x)

        self.assertEqual(run_func(0, 5), 5)
        self.assertEqual(run_func(1, 5), 25)
        self.assertEqual(run_func(2, 5), 125)

        result = '''
        def run_func(i, x):
            if i == 0:
                return funcs_0(x)
            if i == 1:
                return funcs_1(x)
            if i == 2:
                return funcs_2(x)
        '''

        self.assertSourceEqual(run_func, result)

    def test_len(self):
        a = ['a', 'b', 'c']

        @pragma.deindex(a, 'a')
        @pragma.unroll
        def f():
            for l in range(len(a)):
                print(l)

        result = '''
        def f():
            print(0)
            print(1)
            print(2)
        '''

        self.assertSourceEqual(f, result)

    def test_with_namedtuple(self):
        # See test_collapse_literals::test_namedtuple_without_deindex for comparison
        a = [1, 2., object()]  # heterogeneous types in sequence
        nttyp = namedtuple('nttyp', 'x,y,z')
        na = nttyp(*a)

        @pragma.deindex(na, 'na')
        def f():
            q = na[1]  # getitem(name, literal) -> reference - (roundtrip) -> literal
            r = na.y  # property.get(name, literal) -> reference - (roundtrip) -> literal
            s = 0
            if na.y == na[1]:
                s = 1
            t = na.z  # the result is neither literal nor typeable
        result = '''
        def f():
            q = na_1
            r = na_1
            s = 0
            if 1:
                s = 1
            t = na_2
        '''
        roundtrip_result = '''
        def f():
            q = 2.0
            r = 2.0
            s = 0
            s = 1
            t = na_2
        '''
        self.assertSourceEqual(f, result)
        self.assertSourceEqual(pragma.collapse_literals(f), roundtrip_result)
