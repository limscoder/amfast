import unittest

import StringIO

from amfast.context import (ContextError, Idx, Ref,
    DecoderContext, EncoderContext)

class ContextTestCase(unittest.TestCase):
    def setUp(self):
        self.test_string = 'tester'

    def testIdxMap(self):
        count = 64

        idx = Idx()
        for i in xrange(0, count):
            idx.map('%s' % i)

        for i in xrange(0, count):
            self.assertEquals('%s' % i, idx.ret(i))

    def testBadIndexRaisesException(self):
        idx = Idx()
        idx.map(self.test_string)
        self.assertRaises(ContextError, idx.ret, 1)

    def testRefMap(self):
        count = 64

        ref = Ref()
        strs = [str(i) for i in range(0, count)]
        for i, val in enumerate(strs):
            self.assertEquals(i, ref.map(val))

        for i, val in enumerate(strs):
            self.assertEquals(i, ref.ret(val))

    def testUnmappedObjReturnsNegative(self):
        ref = Ref()
        self.assertEquals(-1, ref.ret(self.test_string))

    def _testDecoderContext(self, con):
        self.assertEquals("Buffer", con.buffer.__class__.__name__)
        self.assertEquals("ClassDefMapper", con.class_def_mapper.__class__.__name__)
        self.assertEquals("Idx", con.obj_refs.__class__.__name__)
        self.assertEquals("Idx", con.string_refs.__class__.__name__)
        self.assertEquals("Idx", con.class_refs.__class__.__name__)

    def _testRead(self, con):
        self.assertEquals(self.test_string[0], con.read(1))
        self.assertEquals(self.test_string[1:len(self.test_string)], con.read(len(self.test_string) - 1 ))

    def testDecoderContext(self):
        self._testDecoderContext(DecoderContext(self.test_string, amf3=True))

    def testCopyDecoderContext(self):
        con = DecoderContext(self.test_string, amf3=True)
        con_2 = con.copy(amf3=True)
        self._testDecoderContext(con_2)

    def testReadString(self):
        self._testRead(DecoderContext(self.test_string))

    def testReadStream(self):
        stream = StringIO.StringIO(self.test_string)
        self._testRead(DecoderContext(stream))

    def _testEncoderContext(self, con):
        self.assertEquals("Buffer", con.buffer.__class__.__name__)
        self.assertEquals("ClassDefMapper", con.class_def_mapper.__class__.__name__)
        self.assertEquals("Ref", con.obj_refs.__class__.__name__)
        self.assertEquals("Ref", con.string_refs.__class__.__name__)
        self.assertEquals("Ref", con.class_refs.__class__.__name__)

    def _testWrite(self, con):
        test = self.test_string[0]
        con.write(test)
        self.assertEquals(test, con.buffer.getvalue())

        test = self.test_string[1:len(self.test_string)]
        con.write(test)
        self.assertEquals(self.test_string, con.buffer.getvalue())

    def testEncoderContext(self):
         self._testEncoderContext(EncoderContext(amf3=True))

    def testWriteString(self):
        self._testWrite(EncoderContext())

    def testWriteStream(self):
        self._testWrite(EncoderContext(StringIO.StringIO()))

    def testCopyEncoderContext(self):
        con = EncoderContext(amf3=True)
        con_2 = con.copy()
        self._testEncoderContext(con_2)

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ContextTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())
