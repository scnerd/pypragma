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

    def test_with_unroll(self):
        v = [None, None, None]

        @pragma.deindex(v, 'v', return_source=True)
        @pragma.unroll(lv=len(v))
        def f():
            for i in range(lv):
                yield v[i]

        result = dedent('''
        def f():
            yield v_0
            yield v_1
            yield v_2
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_with_objects_run(self):
        v = [object(), object(), object()]
        @pragma.deindex(v, 'v')
        def f():
            return v[0]

        self.assertEqual(f(), v[0])

    def test_with_variable_indices(self):
        v = [object(), object(), object()]
        @pragma.deindex(v, 'v', return_source=True)
        def f(x):
            yield v[0]
            yield v[x]

        result = dedent('''
        def f(x):
            yield v_0
            yield v[x]
        ''')
        self.assertEqual(f.strip(), result.strip())

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

        # TODO: Support enumerate transparently
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

        result = dedent('''
        def run_func(i, x):
            if i == 0:
                return funcs_0(x)
            if i == 1:
                return funcs_1(x)
            if i == 2:
                return funcs_2(x)
        ''')
        self.assertEqual(inspect.getsource(run_func).strip(), result.strip())

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
