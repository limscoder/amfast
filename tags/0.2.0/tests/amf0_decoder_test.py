# -*- coding: utf-8 -*-
import unittest

import amfast.decoder as decoder
import amfast.class_def as class_def

class Amf0DecoderTestCase(unittest.TestCase):
    class Spam(object):
        def __init__(self):
            self.spam = 'eggs'

    def setUp(self):
        self.class_mapper = class_def.ClassDefMapper()

    def testFalse(self):
        self.assertEquals(False, decoder.decode('\x01\x00'))

    def testTrue(self):
        self.assertEquals(True, decoder.decode('\x01\x01'))

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
            self.assertEquals(number, decoder.decode(encoding))

    def testString(self):
        tests = {
            '': '\x02\x00\x00',
            'hello': '\x02\x00\x05hello'
        }

        for string, encoding in tests.iteritems():
            self.assertEquals(string, decoder.decode(encoding))

    def testLongString(self):
        decoded = 's' * 65537
        encoded = '\x0C\x00\x01\x00\x01' + decoded
  
        self.assertEquals(decoded, decoder.decode(encoded))

    def testNull(self):
        self.assertEquals(None, decoder.decode('\x05'))

    def testUndefined(self):
        self.assertEquals(None, decoder.decode('\x06'))

    def testAnonObj(self):
        encoded = '\x03' #header
        encoded += '\x00\x04spam\x02\x00\x04eggs' #values
        encoded += '\x00\x00\t' # terminator
        result = decoder.decode(encoded)
        self.assertEquals('eggs', result['spam'])

    def testMixedArray(self):
        encoded = '\x08\x00\x00\x00\x00' # mixed array header
        encoded += '\x00\x04spam\x02\x00\x04eggs' #values
        encoded += '\x00\x00\t' # terminator

        result = decoder.decode(encoded)
        self.assertEquals('eggs', result['spam'])

    def testArray(self):
        decoded = [0, 1, 1.23456789]
        encoded = '\x0A\x00\x00\x00\x03' # 3 element array header
        encoded += '\x00\x00\x00\x00\x00\x00\x00\x00\x00' # element 1
        encoded += '\x00\x3f\xf0\x00\x00\x00\x00\x00\x00' #element 2
        encoded += '\x00\x3f\xf3\xc0\xca\x42\x83\xde\x1b' #element 3

        result = decoder.decode(encoded)
        for i, obj in enumerate(decoded):
            self.assertEquals(obj, result[i])

    def testDate(self):
        import datetime
        encoded = '\x0BBp+6!\x15\x80\x00\x00\x00'
        result = decoder.decode(encoded)
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

        result = decoder.decode(encoded)
        self.assertEquals(xml.dom.minidom.Document, result.__class__)

    def testDynamicObj(self):
        self.class_mapper.mapClass(class_def.DynamicClassDef(self.Spam, 'alias.spam', ()))

        encoded = '\x10\x00\x0Aalias.spam'
        encoded += '\x00\x04spam\x02\x00\x04eggs\x00\x00\x09' # dynamic attrs

        result = decoder.decode(encoded, class_def_mapper=self.class_mapper)
        self.class_mapper.unmapClass(self.Spam)

        self.assertEquals('eggs', result.spam)

    def testStaticObj(self):
        self.class_mapper.mapClass(class_def = class_def.ClassDef(self.Spam, 'alias.spam', ('spam')))

        encoded = '\x10\x00\x0Aalias.spam'
        encoded += '\x00\x04spam\x02\x00\x04eggs\x00\x00\x09' # dynamic attrs

        result = decoder.decode(encoded, class_def_mapper=self.class_mapper)
        self.class_mapper.unmapClass(self.Spam)

        self.assertEquals('eggs', result.spam)

    # TODO: TEST REFERENCES

    def testUnkownByteRaisesException(self):
        self.assertRaises(decoder.DecodeError, decoder.decode, '\xFF')

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(Amf0DecoderTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())

