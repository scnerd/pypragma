import pragma
from .test_pragma import PragmaTest


class TestDictStack(PragmaTest):
    def test_most(self):
        stack = pragma.core.DictStack()
        stack.push({'x': 3})
        stack.push()
        stack['x'] = 4
        self.assertEqual(stack['x'], 4)
        res = stack.pop()
        self.assertEqual(res['x'], 4)
        self.assertEqual(stack['x'], 3)
        self.assertIn('x', stack)
        stack.items()
        stack.keys()
        del stack['x']
        self.assertNotIn('x', stack)