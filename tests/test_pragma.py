from unittest import TestCase
from textwrap import dedent


class PragmaTest(TestCase):
    def setUp(self):
        pass
        # # This is a quick hack to disable contracts for testing if needed
        # import contracts
        # contracts.enable_all()

    def assertSourceEqual(self, a, b):
        return self.assertEqual(a.strip(), dedent(b).strip())

    def assertSourceIn(self, a, *b):
        return self.assertIn(a.strip(), [dedent(_b).strip() for _b in b])

