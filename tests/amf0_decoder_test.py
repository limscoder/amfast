# -*- coding: utf-8 -*-
import unittest

from StringIO import StringIO

from amfast.context import DecoderContext
import amfast.decode as decode
from amfast.decoder import Decoder
import amfast.class_def as class_def

class Amf0DecoderTestCase(unittest.TestCase):
    class Spam(object):
        def __init__(self):
            self.spam = 'eggs'

    def setUp(self):
        self.class_mapper = class_def.ClassDefMapper()
        self.decoder = Decoder()

    def testFalse(self):
        self.assertEquals(False, decode.decode(DecoderContext('\x01\x00')))

    def testStringInput(self):
        self.assertEquals(False, decode.decode('\x01\x00'))

    def testDecoderObj(self):
        self.assertEquals(False, decode.decode('\x01\x00'))

    def testTrue(self):
        self.assertEquals(True, self.decoder.decode('\x01\x01'))

    def testNumber(self):
        tests = {
            0: '\x00\x00\x00\x00\x00\x00\x00\x00\x00',
            0.2: '\x00\x3f\xc9\x99\x99\x99\x99\x99\x9a',
            1: '\x00\x3f\xf0\x00\x00\x00\x00\x00\x00',
            42: '\x00\x40\x45\x00\x00\x00\x00\x00\x00',
            -123: '\x00\xc0\x5e\xc0\x00\x00\x00\x00\x00',
            1.23456789: '\x00\x3f\xf3\xc0\xca\x42\x83\xde\x1b'
        }

        for number, encoding in tests.iteritems():
            self.assertEquals(number, decode.decode(DecoderContext(encoding)))

    def testString(self):
        tests = {
            '': '\x02\x00\x00',
            'hello': '\x02\x00\x05hello'
        }

        for string, encoding in tests.iteritems():
            self.assertEquals(string, decode.decode(DecoderContext(encoding)))

    def testLongString(self):
        decoded = 's' * 65537
        encoded = '\x0C\x00\x01\x00\x01' + decoded
  
        self.assertEquals(decoded, decode.decode(DecoderContext(encoded)))

    def testNull(self):
        self.assertEquals(None, decode.decode(DecoderContext('\x05')))

    def testUndefined(self):
        self.assertEquals(None, decode.decode(DecoderContext('\x06')))

    def testAnonObj(self):
        encoded = '\x03' #header
        encoded += '\x00\x04spam\x02\x00\x04eggs' #values
        encoded += '\x00\x00\t' # terminator
        result = decode.decode(DecoderContext(encoded))
        self.assertEquals('eggs', result['spam'])

        result = decode.decode(DecoderContext(StringIO(encoded)))
        self.assertEquals('eggs', result['spam'])

    def testMixedArray(self):
        encoded = '\x08\x00\x00\x00\x00' # mixed array header
        encoded += '\x00\x04spam\x02\x00\x04eggs' #values
        encoded += '\x00\x00\t' # terminator

        result = decode.decode(DecoderContext(encoded))
        self.assertEquals('eggs', result['spam'])

        result = decode.decode(DecoderContext(StringIO(encoded)))
        self.assertEquals('eggs', result['spam'])

    def testArray(self):
        decoded = [0, 1, 1.23456789]
        encoded = '\x0A\x00\x00\x00\x03' # 3 element array header
        encoded += '\x00\x00\x00\x00\x00\x00\x00\x00\x00' # element 1
        encoded += '\x00\x3f\xf0\x00\x00\x00\x00\x00\x00' #element 2
        encoded += '\x00\x3f\xf3\xc0\xca\x42\x83\xde\x1b' #element 3

        result = decode.decode(DecoderContext(encoded))
        for i, obj in enumerate(decoded):
            self.assertEquals(obj, result[i])

        result = decode.decode(DecoderContext(StringIO(encoded)))
        for i, obj in enumerate(decoded):
            self.assertEquals(obj, result[i])

    def testDate(self):
        import datetime
        encoded = '\x0BBp+6!\x15\x80\x00\x00\x00'
        result = decode.decode(DecoderContext(encoded))
        self.assertEquals(2005, result.year)
        self.assertEquals(3, result.month)
        self.assertEquals(18, result.day)
        self.assertEquals(1, result.hour)
        self.assertEquals(58, result.minute)
        self.assertEquals(31, result.second)

    def testXml(self):
        import xml.dom.minidom

        encoded = '\x0F' # XML header
        encoded += '\x00\x00\x00\x55' # String header
        encoded += '<?xml version="1.0" ?><test>\n            <test_me>tester</test_me>\n           </test>' # encoded XML

        result = decode.decode(DecoderContext(encoded))
        self.assertEquals(xml.dom.minidom.Document, result.__class__)

    def testDynamicObj(self):
        self.class_mapper.mapClass(class_def.DynamicClassDef(self.Spam, 'alias.spam', ()))

        encoded = '\x10\x00\x0Aalias.spam'
        encoded += '\x00\x04spam\x02\x00\x04eggs\x00\x00\x09' # dynamic attrs

        result = decode.decode(DecoderContext(encoded, class_def_mapper=self.class_mapper))
        self.class_mapper.unmapClass(self.Spam)

        self.assertEquals('eggs', result.spam)

    def testStaticObj(self):
        self.class_mapper.mapClass(class_def = class_def.ClassDef(self.Spam, 'alias.spam', ('spam')))

        encoded = '\x10\x00\x0Aalias.spam'
        encoded += '\x00\x04spam\x02\x00\x04eggs\x00\x00\x09' # dynamic attrs

        result = decode.decode(DecoderContext(encoded, class_def_mapper=self.class_mapper))
        self.class_mapper.unmapClass(self.Spam)

        self.assertEquals('eggs', result.spam)

    def testReferences(self):
        encoded = '\x0A\x00\x00\x00\x04' # 3 element array header
        encoded += '\x03\x00\x04spam\x02\x00\x04eggs\x00\x00\t' # obj 1
        encoded += '\x07\x00\x01' # ref to obj 1
        encoded += '\x07\x00\x01' # ref to obj 1
        encoded += '\x07\x00\x00' # circular ref
        result = decode.decode(DecoderContext(encoded))

        self.assertEquals(4, len(result))
        self.assertEquals(result, result.pop(-1))
        for obj in result:
            self.assertEquals('eggs', obj['spam'])

    def testUnkownByteRaisesException(self):
        self.assertRaises(decode.DecodeError, decode.decode, DecoderContext('\xFF'))

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(Amf0DecoderTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())

