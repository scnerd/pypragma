from unittest import TestCase
from textwrap import dedent
from inspect import getsource


class PragmaTest(TestCase):
    def setUp(self):
        pass
        # # This is a quick hack to disable contracts for testing if needed
        # import contracts
        # contracts.enable_all()

    def assertSourceEqual(self, a, b):
        if callable(a):
            a = dedent(getsource(a))
        return self.assertEqual(a.strip(), dedent(b).strip())

    def assertSourceIn(self, a, *b):
        if callable(a):
            a = dedent(getsource(a))
        return self.assertIn(a.strip(), [dedent(_b).strip() for _b in b])

