import unittest

from amfast.buffer import Buffer, BufferError

class BufferTestCase(unittest.TestCase):
    def setUp(self):
        self.test_string = 'tester'

    def testRead(self):
        buf = Buffer(self.test_string)
        self.assertEquals(self.test_string[0], buf.read(1))
        self.assertEquals(1, buf.tell())
        self.assertEquals(self.test_string[1:len(self.test_string)], buf.read(len(self.test_string) - 1 ))

    def testSeek(self):
        buf = Buffer(self.test_string)
        buf.seek(len(self.test_string) - 1)
        self.assertEquals(self.test_string[-1], buf.read(1))
        buf.seek(0)
        self.assertEquals(self.test_string[0], buf.read(1))

    def testGetValue(self):
        buf = Buffer(self.test_string)
        self.assertEquals(self.test_string, buf.getvalue())

    def testWrite(self):
        buf = Buffer()
        buf.write(self.test_string)
        self.assertEquals(self.test_string, buf.getvalue())
  
    def testWriteLong(self):
        tester = 's' * 65537
        buf = Buffer()
        buf.write(tester)
        self.assertEquals(tester, buf.getvalue())

    def testWriteNonStringRaisesException(self):
        buf = Buffer()
        self.assertRaises(BufferError, buf.write, (len(self.test_string)))

    def testReadFromWriteRaisesException(self):
        buf = Buffer()
        self.assertRaises(BufferError, buf.read, 1)

    def testWriteFromReadRaisesException(self):
        buf = Buffer(self.test_string)
        self.assertRaises(BufferError, buf.write, self.test_string)

    def testReadLongRaisesException(self):
        buf = Buffer(self.test_string)
        self.assertRaises(BufferError, buf.read, (len(self.test_string) + 1))

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(BufferTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())
