# -*- coding: utf-8 -*-
import unittest

from amfast.context import EncoderContext
import amfast.encode as encode
from amfast.encoder import Encoder
import amfast.class_def as class_def

class Amf0EncoderTestCase(unittest.TestCase):
    class Spam(object):
        def __init__(self):
            self.spam = 'eggs'

    def setUp(self):
        self.class_mapper = class_def.ClassDefMapper()
        self.encoder = Encoder()

    def testFalse(self):
        self.assertEquals('\x01\x00', encode.encode(False))

    def testEncoderContext(self):
        self.assertEquals('\x01\x00', encode.encode(False, EncoderContext()))

    def testEncoderObj(self):
        self.assertEquals('\x01\x00', self.encoder.encode(False))

    def testTrue(self):
        self.assertEquals('\x01\x01', encode.encode(True))

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
            self.assertEquals(encoding, encode.encode(number))

    def testString(self):
        tests = {
            '': '\x02\x00\x00',
            'hello': '\x02\x00\x05hello'
        }

        for string, encoding in tests.iteritems():
            self.assertEquals(encoding, encode.encode(string))

    def testLongString(self):
        decoded = 's' * 65537
        encoded = '\x0C\x00\x01\x00\x01' + decoded

        self.assertEquals('\x0C\x00\x01\x00\x01', encode.encode(decoded)[0:5])
        self.assertEquals(65537 + 5, len(encode.encode(decoded)))

    def testNull(self):
        self.assertEquals('\x05', encode.encode(None))

    def testTuple(self):
        decoded = (0, 1, 1.23456789)
        encoded = '\x0A\x00\x00\x00\x03' # 3 element array header
        encoded += '\x00\x00\x00\x00\x00\x00\x00\x00\x00' # element 1
        encoded += '\x00\x3f\xf0\x00\x00\x00\x00\x00\x00' #element 2
        encoded += '\x00\x3f\xf3\xc0\xca\x42\x83\xde\x1b' #element 3

        self.assertEquals(encoded, encode.encode(decoded))

    def testList(self):
        decoded = [0, 1, 1.23456789]
        encoded = '\x0A\x00\x00\x00\x03' # 3 element array header
        encoded += '\x00\x00\x00\x00\x00\x00\x00\x00\x00' # element 1
        encoded += '\x00\x3f\xf0\x00\x00\x00\x00\x00\x00' #element 2
        encoded += '\x00\x3f\xf3\xc0\xca\x42\x83\xde\x1b' #element 3

        self.assertEquals(encoded, encode.encode(decoded))

    def testCollection(self):
        from amfast.class_def.as_types import AsProxy
        decoded = [0, 1, 1.23456789]
        encoded = '\x0A\x00\x00\x00\x03' # 3 element array header
        encoded += '\x00\x00\x00\x00\x00\x00\x00\x00\x00' # element 1
        encoded += '\x00\x3f\xf0\x00\x00\x00\x00\x00\x00' #element 2
        encoded += '\x00\x3f\xf3\xc0\xca\x42\x83\xde\x1b' #element 3

        self.assertEquals(encoded, encode.encode(AsProxy(decoded)))

    def testNoCollection(self):
        from amfast.class_def.as_types import AsNoProxy
        decoded = [0, 1, 1.23456789]
        encoded = '\x0A\x00\x00\x00\x03' # 3 element array header
        encoded += '\x00\x00\x00\x00\x00\x00\x00\x00\x00' # element 1
        encoded += '\x00\x3f\xf0\x00\x00\x00\x00\x00\x00' #element 2
        encoded += '\x00\x3f\xf3\xc0\xca\x42\x83\xde\x1b' #element 3

        self.assertEquals(encoded, encode.encode(AsNoProxy(decoded)))

    def testDict(self):
        encoded = '\x03' #header
        encoded += '\x00\x04spam\x02\x00\x04eggs' #values
        encoded += '\x00\x00\t' # terminator
        self.assertEquals(encoded, encode.encode({'spam': 'eggs'}))

    def testNoProxy(self):
        from amfast.class_def.as_types import AsProxy
        encoded = '\x03' #header
        encoded += '\x00\x04spam\x02\x00\x04eggs' #values
        encoded += '\x00\x00\t' # terminator
        self.assertEquals(encoded, encode.encode(AsNoProxy({'spam': 'eggs'})))

    def testProxy(self):
        from amfast.class_def.as_types import AsProxy
        encoded = '\x03' #header
        encoded += '\x00\x04spam\x02\x00\x04eggs' #values
        encoded += '\x00\x00\t' # terminator
        self.assertEquals(encoded, encode.encode(AsProxy({'spam': 'eggs'})))

    def testNoProxy(self):
        from amfast.class_def.as_types import AsNoProxy
        encoded = '\x03' #header
        encoded += '\x00\x04spam\x02\x00\x04eggs' #values
        encoded += '\x00\x00\t' # terminator
        self.assertEquals(encoded, encode.encode(AsNoProxy({'spam': 'eggs'})))

    def testDate(self):
        import datetime
        decoded = datetime.datetime(2005, 3, 18, 1, 58, 31)
        encoded = '\x0BBp+6!\x15\x80\x00\x00\x00'
        self.assertEquals(encoded, encode.encode(decoded))

    def testXml(self):
        import xml.dom.minidom
        
        xml_str = '<?xml version="1.0" ?><test>\n            <test_me>tester</test_me>\n           </test>' # encoded XML
        decoded = xml.dom.minidom.parseString(xml_str)

        encoded = '\x0F' # XML header
        encoded += '\x00\x00\x00\x55' # String header
        encoded += xml_str

        self.assertEquals(encoded, encode.encode(decoded))

    def testAnonymousObj(self):
        decoded = self.Spam()
        decoded.spam = 'eggs'

        encoded = '\x03' #header
        encoded += '\x00\x04spam\x02\x00\x04eggs' #values
        encoded += '\x00\x00\t' # terminator
        self.assertEquals(encoded, encode.encode(decoded))

    def testDynamicObj(self):
        self.class_mapper.mapClass(class_def.DynamicClassDef(self.Spam, alias='alias.spam',
            static_attrs=(), amf3=False))

        decoded = self.Spam()
        decoded.spam = 'eggs'

        encoded = '\x10\x00\x0Aalias.spam'
        encoded += '\x00\x04spam\x02\x00\x04eggs\x00\x00\x09' # dynamic attrs

        context = EncoderContext(class_def_mapper=self.class_mapper)
        self.assertEquals(encoded, encode.encode(decoded, context))
        self.class_mapper.unmapClass(self.Spam)

    def testStaticObj(self):
        self.class_mapper.mapClass(class_def.ClassDef(self.Spam, alias='alias.spam',
            static_attrs=('spam', ), amf3=False))

        decoded = self.Spam()
        decoded.spam = 'eggs'

        encoded = '\x10\x00\x0Aalias.spam'
        encoded += '\x00\x04spam\x02\x00\x04eggs\x00\x00\x09' # dynamic attrs

        context = EncoderContext(class_def_mapper=self.class_mapper)
        self.assertEquals(encoded, encode.encode(decoded, context))
        self.class_mapper.unmapClass(self.Spam)

    def testReferences(self):
        obj = {'spam': 'eggs'}
        decoded = [obj, obj, obj]
        decoded.append(decoded)

        encoded = '\x0A\x00\x00\x00\x04' # 3 element array header
        encoded += '\x03\x00\x04spam\x02\x00\x04eggs\x00\x00\t' # obj 1
        encoded += '\x07\x00\x01' # ref to obj 1
        encoded += '\x07\x00\x01' # ref to obj 1
        encoded += '\x07\x00\x00' # circular ref

        self.assertEquals(encoded, encode.encode(decoded))

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(Amf0EncoderTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())
