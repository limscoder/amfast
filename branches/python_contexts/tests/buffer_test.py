import unittest

from amfast.buffer import Buffer, BufferError

class BufferTestCase(unittest.TestCase):
    def setUp(self):
        self.test_string = 'tester'

    def testRead(self):
        buf = Buffer(self.test_string)
        self.assertEquals(self.test_string[0], buf.read(1))
        self.assertEquals(self.test_string[1:6], buf.read(5))

    def testReadLongRaisesException(self):
        buf = Buffer(self.test_string)
        self.assertRaises(BufferError, buf.read, (len(self.test_string) + 1))

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(BufferTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())
