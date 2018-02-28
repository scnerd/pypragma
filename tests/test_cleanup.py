from textwrap import dedent

import pragma
from .test_pragma import PragmaTest


class TestInline(PragmaTest):
    def test_basic_assign(self):
        @pragma.cleanup(return_source=True)
        def f():
            x = 5
            return 3

        result = dedent('''
        def f():
            return 3
        ''')
        self.assertEqual(f.strip(), result.strip())

    def test_retrieval(self):
        @pragma.cleanup(return_source=True)
        @pragma.collapse_literals
        def f():
            x = 5
            return x

        result = dedent('''
        def f():
            return 5
        ''')
        self.assertEqual(f.strip(), result.strip())
