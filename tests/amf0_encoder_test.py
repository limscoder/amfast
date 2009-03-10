# -*- coding: utf-8 -*-
import unittest

import amfast.encoder as encoder
import amfast.class_def as class_def

class Amf0EncoderTestCase(unittest.TestCase):
    class Spam(object):
        def __init__(self):
            self.spam = 'eggs'

    def setUp(self):
        self.class_mapper = class_def.ClassDefMapper()

    def testFalse(self):
        self.assertEquals('\x01\x00', encoder.encode(False))

    def testTrue(self):
        self.assertEquals('\x01\x01', encoder.encode(True))

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
            self.assertEquals(encoding, encoder.encode(number))

    def testString(self):
        tests = {
            '': '\x02\x00\x00',
            'hello': '\x02\x00\x05hello'
        }

        for string, encoding in tests.iteritems():
            self.assertEquals(encoding, encoder.encode(string))

    def testLongString(self):
        decoded = 's' * 65537
        encoded = '\x0C\x00\x01\x00\x01' + decoded

        self.assertEquals('\x0C\x00\x01\x00\x01', encoder.encode(decoded)[0:5])
        self.assertEquals(65537 + 5, len(encoder.encode(decoded)))

    def testNull(self):
        self.assertEquals('\x05', encoder.encode(None))

    def testTuple(self):
        decoded = (0, 1, 1.23456789)
        encoded = '\x0A\x00\x00\x00\x03' # 3 element array header
        encoded += '\x00\x00\x00\x00\x00\x00\x00\x00\x00' # element 1
        encoded += '\x00\x3f\xf0\x00\x00\x00\x00\x00\x00' #element 2
        encoded += '\x00\x3f\xf3\xc0\xca\x42\x83\xde\x1b' #element 3

        self.assertEquals(encoded, encoder.encode(decoded))

    def testList(self):
        decoded = [0, 1, 1.23456789]
        encoded = '\x0A\x00\x00\x00\x03' # 3 element array header
        encoded += '\x00\x00\x00\x00\x00\x00\x00\x00\x00' # element 1
        encoded += '\x00\x3f\xf0\x00\x00\x00\x00\x00\x00' #element 2
        encoded += '\x00\x3f\xf3\xc0\xca\x42\x83\xde\x1b' #element 3

        self.assertEquals(encoded, encoder.encode(decoded))

    def testDict(self):
        encoded = '\x03' #header
        encoded += '\x00\x04spam\x02\x00\x04eggs' #values
        encoded += '\x00\x00\t' # terminator
        self.assertEquals(encoded, encoder.encode({'spam': 'eggs'}))

    def testDate(self):
        import datetime
        decoded = datetime.datetime(2005, 3, 18, 1, 58, 31)
        encoded = '\x0BBp+6!\x15\x80\x00\x00\x00'
        self.assertEquals(encoded, encoder.encode(decoded))

    def testXml(self):
        import xml.dom.minidom
        
        xml_str = '<?xml version="1.0" ?><test>\n            <test_me>tester</test_me>\n           </test>' # encoded XML
        decoded = xml.dom.minidom.parseString(xml_str)

        encoded = '\x0F' # XML header
        encoded += '\x00\x00\x00\x55' # String header
        encoded += xml_str

        self.assertEquals(encoded, encoder.encode(decoded))

    def testAnonymousObj(self):
        decoded = self.Spam()
        decoded.spam = 'eggs'

        encoded = '\x03' #header
        encoded += '\x00\x04spam\x02\x00\x04eggs' #values
        encoded += '\x00\x00\t' # terminator
        self.assertEquals(encoded, encoder.encode(decoded))

    def testDynamicObj(self):
        self.class_mapper.mapClass(class_def.DynamicClassDef(self.Spam, alias='alias.spam',
            static_attrs=(), amf3=False))

        decoded = self.Spam()
        decoded.spam = 'eggs'

        encoded = '\x10\x00\x0Aalias.spam'
        encoded += '\x00\x04spam\x02\x00\x04eggs\x00\x00\x09' # dynamic attrs

        self.assertEquals(encoded, encoder.encode(decoded, class_def_mapper=self.class_mapper))
        self.class_mapper.unmapClass(self.Spam)

    def testStaticObj(self):
        self.class_mapper.mapClass(class_def.ClassDef(self.Spam, alias='alias.spam',
            static_attrs=('spam', ), amf3=False))

        decoded = self.Spam()
        decoded.spam = 'eggs'

        encoded = '\x10\x00\x0Aalias.spam'
        encoded += '\x00\x04spam\x02\x00\x04eggs\x00\x00\x09' # dynamic attrs

        self.assertEquals(encoded, encoder.encode(decoded, class_def_mapper=self.class_mapper))
        self.class_mapper.unmapClass(self.Spam)

    # TODO: TEST REFERENCES

    def testUnkownByteRaisesException(self):
        return
        self.assertRaises(decoder.DecodeError, decoder.decode, '\xFF')

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(Amf0EncoderTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())

