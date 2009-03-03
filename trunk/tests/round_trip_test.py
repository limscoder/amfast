import unittest

import pyamf
from pyamf import amf3
from pyamf.util import BufferedByteStream

import amfast.encoder as encoder
import amfast.decoder as decoder
import amfast.class_def as class_def

class RoundTripTestCase(unittest.TestCase):
    class TestObject(object):
        def __init__(self):
            self.number = None
            self.test_list = ['test']
            self.sub_obj = None
            self.test_dict = {'test': 'ignore'}

    class TestSubObject(object):
        def __init__(self):
            self.number = None

    def setUp(self):
        class_def.map_class(self.TestObject, class_def.DynamicClassDef, 'test_complex.test', ())
        class_def.map_class(self.TestSubObject, class_def.DynamicClassDef, 'test_complex.sub', ())

        pyamf.register_class(self.TestObject, 'test_complex.test')
        pyamf.register_class(self.TestSubObject, 'test_complex.sub')

    def tearDown(self):
        class_def.unmap_class(self.TestObject)
        class_def.unmap_class(self.TestSubObject)

        pyamf.unregister_class(self.TestObject)
        pyamf.unregister_class(self.TestSubObject)

    def buildComplex(self, max=5):
        test_objects = []

        for i in range(0, max):
            test_obj = self.TestObject()
            test_obj.number = i
            test_obj.sub_obj = self.TestSubObject()
            test_obj.sub_obj.number = i
            test_objects.append(test_obj)

        return test_objects

    def resultTest(self, decoded):
        for obj in decoded:
            self.assertEquals(self.TestObject, obj.__class__)
            self.assertEquals(self.TestSubObject, obj.sub_obj.__class__)

    def testComplexDict(self):
        complex = {'element': 'ignore', 'objects': self.buildComplex()}
        encoded = encoder.encode(complex)
        decoded = decoder.decode(encoded)
        self.resultTest(decoded['objects'])

    def testComplexDictProxies(self):
        complex = {'element': 'ignore', 'objects': self.buildComplex()}
        encoded = encoder.encode(complex, use_array_collections=True, use_object_proxies=True)
        decoded = decoder.decode(encoded, use_array_collections=True, use_object_proxies=True)
        self.resultTest(decoded['objects'])

    def testPyamfComplexDict(self):
        complex = {'element': 'ignore', 'objects': self.buildComplex()}
        self.context = pyamf.get_context(pyamf.AMF3)
        self.stream = BufferedByteStream()
        self.pyamf_encoder = pyamf.get_encoder(pyamf.AMF3, data=self.stream, context=self.context)

        self.pyamf_encoder.writeElement(complex)
        encoded = self.pyamf_encoder.stream.getvalue()
        context = amf3.Context()
        decoded = amf3.Decoder(encoded, context).readElement()

        self.resultTest(decoded['objects'])

    def testSpeed(self):
        return
        for i in range(10000):
            print "%s ..." % i
            self.testComplexDict()

    def testPyamfSpeed(self):
        return
        for i in range(10000):
            print "%s ..." % i
            self.testPyamfComplexDict()


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(RoundTripTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())

