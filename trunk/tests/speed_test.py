import unittest

import pyamf
from pyamf import amf3, amf0
from pyamf.util import BufferedByteStream

from amfast.context import DecoderContext, EncoderContext
import amfast.encode as encode
import amfast.decode as decode
import amfast.class_def as class_def

class SpeedTestCase(unittest.TestCase):
    class TestObject(object):
        def __init__(self):
            self.null = None
            self.test_list = ['test', 'tester']
            self.test_dict = {'test': 'ignore'}

    class TestSubObject(object):
        def __init__(self):
            self.number = None

    def setUp(self):
        self.test_nu = 10000
        self.class_mapper = class_def.ClassDefMapper()

        self.class_mapper.mapClass(class_def.DynamicClassDef(self.TestObject,
            'test_complex.test', (), amf3=False))
        self.class_mapper.mapClass(class_def.DynamicClassDef(self.TestSubObject,
            'test_complex.sub', (), amf3=False))

        pyamf.register_class(self.TestObject, 'test_complex.test')
        pyamf.register_class(self.TestSubObject, 'test_complex.sub')

    def tearDown(self):
        self.class_mapper.unmapClass(self.TestObject)
        self.class_mapper.unmapClass(self.TestSubObject)

        pyamf.unregister_class(self.TestObject)
        pyamf.unregister_class(self.TestSubObject)

    def buildComplex(self, max=5):
        test_objects = []

        for i in range(0, max):
            test_obj = self.TestObject()
            test_obj.number = i
            test_obj.float = 3.14
            test_obj.unicode = u'spam'
            test_obj.str = 'a l' + 'o' * 500 + 'ng string'
            test_obj.sub_obj = self.TestSubObject()
            test_obj.sub_obj.number = i
            test_obj.ref = test_obj.sub_obj
            test_objects.append(test_obj)

        return test_objects

    def resultTest(self, decoded):
        for obj in decoded:
            self.assertEquals(self.TestObject, obj.__class__)
            self.assertEquals(self.TestSubObject, obj.sub_obj.__class__)

    def speedTestComplexDict(self, amf3=False):
        complex = {'element': 'ignore', 'objects': self.buildComplex()}
 
        enc_context = EncoderContext(use_collections=True, use_proxies=True,
            class_def_mapper=self.class_mapper, amf3=amf3)
        
        encoded = encode.encode(complex, enc_context)

        decoded = decode.decode(DecoderContext(encoded,
            class_def_mapper=self.class_mapper, amf3=amf3))

    def testPyamfComplexDict(self, amf3=False):
        complex = {'element': 'ignore', 'objects': self.buildComplex()}
        self.context = pyamf.get_context(pyamf.AMF0)
        self.stream = BufferedByteStream()
        self.pyamf_encoder = pyamf.get_encoder(pyamf.AMF0, data=self.stream, context=self.context)

        self.pyamf_encoder.writeElement(complex)
        encoded = self.pyamf_encoder.stream.getvalue()
        context = amf0.Context()
        decoded = amf0.Decoder(encoded, context).readElement()

        self.resultTest(decoded['objects'])

    def testSpeedAmf0(self):
        return
        for i in xrange(self.test_nu):
            print i
            self.speedTestComplexDict(amf3=False)

    def testPyamfSpeedAmf0(self):
        return
        for i in xrange(self.test_nu):
            print i
            self.speedTestPyamfComplexDict(amf3=False)

    def testSpeedAmf3(self):
        for i in xrange(self.test_nu):
            print i
            self.speedTestComplexDict(amf3=True)

    def testPyamfSpeedAmf3(self):
        return
        for i in xrange(self.test_nu):
            print i
            self.testPyamfComplexDict(amf3=True)

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(SpeedTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())

