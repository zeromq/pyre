import unittest


class FailingTestCase(unittest.TestCase):
    def test_fails(self):
        self.assertTrue(False)
    # end test_fails
# end FailingTestCase
