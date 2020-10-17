from unittest import TestCase
from textwrap import dedent
from inspect import getsource


class PragmaTest(TestCase):
    def setUp(self):
        pass
        # # This is a quick hack to disable contracts for testing if needed
        # import contracts
        # contracts.enable_all()

    def assertSourceEqual(self, a, b, skip_pytest_imports=False):
        if callable(a):
            a = dedent(getsource(a))
        if skip_pytest_imports:
            pytest_imports = [
                'import builtins as @py_builtins',
                'import _pytest.assertion.rewrite as @pytest_ar'
            ]
            a_builder = []
            for line in a.split('\n'):
                if line.strip() not in pytest_imports:
                    a_builder.append(line)
            a = '\n'.join(a_builder)
        return self.assertEqual(a.strip(), dedent(b).strip())

    def assertSourceIn(self, a, *b):
        if callable(a):
            a = dedent(getsource(a))
        return self.assertIn(a.strip(), [dedent(_b).strip() for _b in b])

