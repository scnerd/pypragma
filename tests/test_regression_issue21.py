import pragma
from tests.test_pragma import PragmaTest


class TestIssue21(PragmaTest):
    def test_unroll_setitem(self):
        # This is expected to work properly
        biglist = list(range(20))

        @pragma.unroll
        def hey():
            for i in range(10):
                biglist.__setitem__(i, 0)

        result = '''
        def hey():
            biglist.__setitem__(0, 0)
            biglist.__setitem__(1, 0)
            biglist.__setitem__(2, 0)
            biglist.__setitem__(3, 0)
            biglist.__setitem__(4, 0)
            biglist.__setitem__(5, 0)
            biglist.__setitem__(6, 0)
            biglist.__setitem__(7, 0)
            biglist.__setitem__(8, 0)
            biglist.__setitem__(9, 0)
        '''

        self.assertSourceEqual(hey, result)
        hey()
        self.assertListEqual(
            biglist,
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0] + list(range(10, 20))
        )

    def test_unroll_set_index(self):
        # This did not work as expected
        biglist = list(range(20))

        @pragma.unroll
        def hey2():
            for i in range(10):
                biglist[i] = 1

        result = '''
        def hey2():
            biglist[0] = 1
            biglist[1] = 1
            biglist[2] = 1
            biglist[3] = 1
            biglist[4] = 1
            biglist[5] = 1
            biglist[6] = 1
            biglist[7] = 1
            biglist[8] = 1
            biglist[9] = 1
        '''

        self.assertSourceEqual(hey2, result)
        hey2()
        self.assertListEqual(
            biglist,
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1] + list(range(10, 20))
        )
