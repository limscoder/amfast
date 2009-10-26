# -*- coding: utf-8 -*-
import unittest

from StringIO import StringIO

from amfast.context import DecoderContext
import amfast.decode as decode
import amfast.buffer as buffer
import amfast.class_def as class_def

class Amf3DecoderTestCase(unittest.TestCase):
    class Spam(object):
        def __init__(self):
            self.spam = 'eggs'

    def setUp(self):
        self.class_mapper = class_def.ClassDefMapper()

    def testNone(self):
        self.assertEquals(None, decode.decode(DecoderContext('\x01', amf3=True)))

    def testFalse(self):
        self.assertEquals(False, decode.decode(DecoderContext('\x02', amf3=True)))

    def testTrue(self):
        self.assertEquals(True, decode.decode(DecoderContext('\x03', amf3=True)))

    def testInt(self):
        tests = {
            0: '\x04\x00',
            0x35: '\x04\x35',
            0x7f: '\x04\x7f',
            0x80: '\x04\x81\x00',
            0xd4: '\x04\x81\x54',
            0x3fff: '\x04\xff\x7f',
            0x4000: '\x04\x81\x80\x00',
            0x1a53f: '\x04\x86\xca\x3f',
            0x1fffff: '\x04\xff\xff\x7f',
            0x200000: '\x04\x80\xc0\x80\x00',
            -0x01: '\x04\xff\xff\xff\xff',
            -0x2a: '\x04\xff\xff\xff\xd6',
            0xfffffff: '\x04\xbf\xff\xff\xff',
            -0x10000000: '\x04\xc0\x80\x80\x00'
        }

        for integer, encoding in tests.iteritems():
            self.assertEquals(integer, decode.decode(DecoderContext(encoding, amf3=True)))

    def testEncodeFloat(self):
        tests = {
            0.1: '\x05\x3f\xb9\x99\x99\x99\x99\x99\x9a',
            0.123456789: '\x05\x3f\xbf\x9a\xdd\x37\x39\x63\x5f'
        }

        for number, encoding in tests.iteritems():
            self.assertEquals(number, decode.decode(DecoderContext(encoding, amf3=True)))

    def testEncodeLong(self):
        tests = {
            0x10000000: '\x05\x41\xb0\x00\x00\x00\x00\x00\x00',
            -0x10000001: '\x05\xc1\xb0\x00\x00\x01\x00\x00\x00',
            -0x10000000: '\x04\xc0\x80\x80\x00'
        }

        for number, encoding in tests.iteritems():
            self.assertEquals(number, decode.decode(DecoderContext(encoding, amf3=True)))

    def testUnicode(self):
        tests = {
            u'': '\x06\x01',
            u'hello': '\x06\x0bhello',
            u'ᚠᛇᚻ': '\x06\x13\xe1\x9a\xa0\xe1\x9b\x87\xe1\x9a\xbb'
        }

        for string, encoding in tests.iteritems():
            self.assertEquals(string, decode.decode(DecoderContext(encoding, amf3=True)))

    def testUnicodeRefs(self):
        test = ['hello', 'hello', 'hello', 'hello']

        encoded = '\x09\x09\x01' # array header
        encoded  += '\x06\x0bhello' # array element 1 (hello encoded)
        encoded += '\x06\x00' #array element 2 (reference to hello)
        encoded += '\x06\x00' #array element 3 (reference to hello)
        encoded += '\x06\x00' #array element 4 (reference to hello)

        results = decode.decode(DecoderContext(encoded, amf3=True))
        for result in results:
            self.assertEquals('hello', result)

    def testArray(self):
        encoded = '\x09\x09\x01' #array header
        encoded += '\x04\x00' #array element 1
        encoded += '\x04\x01' #array element 2
        encoded += '\x04\x02' #array element 3
        encoded += '\x04\x03' #array element 4

        result = decode.decode(DecoderContext(encoded, amf3=True))
        for i, val in enumerate(result):
            self.assertEquals(i, val);

    def testXml(self):
        import xml.dom.minidom

        encoded = '\x0B' # XML header
        encoded += '\x81\x2B' # String header
        encoded += '<?xml version="1.0" ?><test>\n            <test_me>tester</test_me>\n           </test>' # encoded XML

        result = decode.decode(DecoderContext(encoded, amf3=True))
        self.assertEquals(xml.dom.minidom.Document, result.__class__)

    def testEncodeXmlRef(self):
        import xml.dom.minidom
        encoded = '\x09\x05\x01' #array header
        encoded += '\x0B\x81\x2B<?xml version="1.0" ?><test>\n            <test_me>tester</test_me>\n           </test>' # array element 1 (encoded dom)
        encoded += '\x0B\x02' # array element 2 (reference to dom)

        result = decode.decode(DecoderContext(encoded, amf3=True))
        self.assertEquals(xml.dom.minidom.Document, result[0].__class__)
        self.assertEquals(result[0], result[1])

    def testDict(self):
        encoded = '\x0A\x0B\x01' # Object header
        encoded += '\x09spam' # key
        encoded += '\x06\x09eggs' #value
        encoded += '\x01' # empty string terminator

        result = decode.decode(DecoderContext(encoded, amf3=True))
        self.assertEquals('eggs', result['spam']);

    def testObjectProxy(self):
        encoded = '\x0A\x07\x3Bflex.messaging.io.ObjectProxy' # Object header 
        encoded += '\x0A\x0B\x01' # Object header
        encoded += '\x09spam' # key
        encoded += '\x06\x09eggs' #value
        encoded += '\x01' # empty string terminator

        result = decode.decode(DecoderContext(encoded, amf3=True))
        self.assertEquals('eggs', result['spam']);

    def testDictRef(self):
        encoded = '\x09\x05\x01' #array header
        encoded += '\x0A\x0B\x01\x09spam\x06\x09eggs\x01' #array element 1 (dict encoded)
        encoded += '\x0A\x02' # array element 2 (reference to dict)

        result = decode.decode(DecoderContext(encoded, amf3=True))
        self.assertEquals('eggs', result[0]['spam'])
        self.assertEquals(result[0], result[1])

    def testArrayCollection(self):
        encoded = '\x0A\x07\x43flex.messaging.io.ArrayCollection' # Object header 
        encoded += '\x09\x09\x01' #array header
        encoded += '\x04\x00' #array element 1
        encoded += '\x04\x01' #array element 2
        encoded += '\x04\x02' #array element 3
        encoded += '\x04\x03' #array element 4

        result = decode.decode(DecoderContext(encoded, amf3=True))
        for i in range(4):
            self.assertEquals(i, result[i])

        result = decode.decode(DecoderContext(StringIO(encoded), amf3=True))
        for i in range(4):
            self.assertEquals(i, result[i])

    def testArrayCollectionRef(self):
        encoded = '\x0A\x07\x43flex.messaging.io.ArrayCollection\x09\x05\x01' # array header
        encoded += '\x0A\x01\x09\x09\x01\x04\x00\x04\x01\x04\x02\x04\x03' # array element 1 (test_tuple encoded)
        encoded += '\x0A\x04' # array element 2 (reference to test_tuple)

        result = decode.decode(DecoderContext(encoded, amf3=True))
        self.assertEquals([].__class__, result.__class__)
        self.assertEquals(result[0], result[1])
        for i in range(4):
            self.assertEquals(i, result[0][i])

    def testClassRef(self):
        self.class_mapper.mapClass(class_def.ClassDef(self.Spam, 'alias.spam', ('spam',)))

        encoded = '\x09\x05\x01' #array header
        encoded += '\x0A\x13\x15alias.spam\x09spam\x06\x09eggs' # array element 1
        encoded += '\x0A\x01\x06\x07foo' # array element 2

        result = decode.decode(DecoderContext(encoded,
            class_def_mapper=self.class_mapper, amf3=True))
        self.class_mapper.unmapClass(self.Spam)

        self.assertEquals(result[0].__class__, result[1].__class__)

    def testStaticObj(self):
        self.class_mapper.mapClass(class_def.ClassDef(self.Spam, 'alias.spam', ('spam',)))

        encoded = '\x0A\x13\x15alias.spam'
        encoded += '\x09spam' # static attr definition
        encoded += '\x06\x09eggs' # static attrs

        result = decode.decode(DecoderContext(encoded,
            class_def_mapper=self.class_mapper, amf3=True))
        self.assertEquals('eggs', result.spam)

        result = decode.decode(DecoderContext(StringIO(encoded),
            class_def_mapper=self.class_mapper, amf3=True))
        self.assertEquals('eggs', result.spam)

        self.class_mapper.unmapClass(self.Spam)

    def testDynamicObj(self):
        self.class_mapper.mapClass(class_def.DynamicClassDef(self.Spam, 'alias.spam', ()))

        encoded = '\x0A\x0B\x15alias.spam'
        encoded += '\x09spam\x06\x09eggs\x01' # dynamic attrs

        result = decode.decode(DecoderContext(encoded,
            class_def_mapper=self.class_mapper, amf3=True))
        self.assertEquals('eggs', result.spam)

        result = decode.decode(DecoderContext(StringIO(encoded),
            class_def_mapper=self.class_mapper, amf3=True))
        self.assertEquals('eggs', result.spam)

        self.class_mapper.unmapClass(self.Spam)

    def testStaticDynamicObj(self):
        self.class_mapper.mapClass(class_def.DynamicClassDef(self.Spam, 'alias.spam', ('spam',)))

        test = self.Spam()
        test.ham = 'foo'

        encoded = '\x0A\x1B\x15alias.spam' # obj header
        encoded += '\x09spam' # static attr definition
        encoded += '\x06\x09eggs' # static attrs
        encoded += '\x07ham\x06\x07foo\x01' #dynamic attrs

        result = decode.decode(DecoderContext(encoded,
            class_def_mapper=self.class_mapper, amf3=True))
        self.assertEquals('eggs', result.spam)
        self.assertEquals('foo', result.ham)

        result = decode.decode(DecoderContext(StringIO(encoded),
            class_def_mapper=self.class_mapper, amf3=True))
        self.assertEquals('eggs', result.spam)
        self.assertEquals('foo', result.ham)

        self.class_mapper.unmapClass(self.Spam)

    def testExternizeable(self):
        custom_encoding = '\x01\x02\x03\x04\x05'

        class ExternClass(class_def.ExternClassDef):
            def readExternal(ext_self, obj, context):
                byte_string = context.buffer.read(5);
                self.assertEquals(custom_encoding, byte_string)
                obj.spam = 'eggs'

        self.class_mapper.mapClass(ExternClass(self.Spam, 'alias.spam', ('spam',)))

        encoded = '\x0A\x07\x15alias.spam'
        encoded += custom_encoding # raw bytes

        result = decode.decode(DecoderContext(encoded,
            class_def_mapper=self.class_mapper, amf3=True))
        self.class_mapper.unmapClass(self.Spam)

        self.assertEquals('eggs', result.spam)

    def testDate(self):
        import datetime
        encoded = '\x08\x01Bp+6!\x15\x80\x00'
        result = decode.decode(DecoderContext(encoded, amf3=True))
        self.assertEquals(2005, result.year)
        self.assertEquals(3, result.month)
        self.assertEquals(18, result.day)
        self.assertEquals(1, result.hour)
        self.assertEquals(58, result.minute)
        self.assertEquals(31, result.second)

        encoded = '\x08\x01Bo%\xe2\xb2\x80\x00\x00'
        result = decode.decode(DecoderContext(encoded, amf3=True))
        self.assertEquals(2003, result.year)
        self.assertEquals(12, result.month)
        self.assertEquals(1, result.day)

    def testUnkownByteRaisesException(self):
        self.assertRaises(decode.DecodeError, decode.decode, DecoderContext('\x0D'))

    def testBadArgRaisesException(self):
        self.assertRaises(decode.DecodeError, decode.decode, 1)

    def testReusableDecoderContext(self):
        import amfast.encoder
        encoder = amfast.encoder.Encoder(amf3=True)
        pre = {'foo' : 'bar'}
        post = encoder.encode(pre)
        ct = DecoderContext(post, amf3=True)

        result = decode.decode(ct)
        assert result == pre

        self.assertRaises(buffer.BufferError, decode.decode, ct) 

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(Amf3DecoderTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())

