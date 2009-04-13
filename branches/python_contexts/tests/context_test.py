import unittest

from amfast.context import Idx

class ContextTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def testMap(self):
        count = 64

        idx = Idx()
        for i in xrange(0, count):
            idx.map('%s' % i)

        for i in xrange(0, count):
            self.assertEquals('%s' % i, idx.ret(i))

    def testBadIndexRaisesException(self):
        #buf = Buffer(self.test_string)
        #self.assertRaises(BufferError, buf.read, (len(self.test_string) + 1))
        pass

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ContextTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())
