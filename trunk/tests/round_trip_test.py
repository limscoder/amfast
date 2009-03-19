import unittest

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
        self.class_mapper = class_def.ClassDefMapper()

        self.class_mapper.mapClass(class_def.DynamicClassDef(self.TestObject, 'test_complex.test', ()))
        self.class_mapper.mapClass(class_def.DynamicClassDef(self.TestSubObject, 'test_complex.sub', ()))

    def tearDown(self):
        self.class_mapper.unmapClass(self.TestObject)
        self.class_mapper.unmapClass(self.TestSubObject)

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

    def testLongStringAmf3(self):
        decoded = 's' * 65537
	encoded = encoder.encode(decoded, amf3=True)
        result = decoder.decode(encoded, amf3=True)

        self.assertEquals(len(decoded), len(result))
        for char in result:
            self.assertEquals('s', char)

    def testLongListAmf3(self):
        decoded = [None] * 65537
        encoded = encoder.encode(decoded, amf3=True)
        result = decoder.decode(encoded, amf3=True)

        self.assertEquals(len(decoded), len(result))
        for val in result:
            self.assertEquals(None, val)

    def testDictAmf3(self):
        decoded = {'spam': 'eggs'}
        encoded = encoder.encode(decoded, amf3=True)
        result = decoder.decode(encoded, amf3=True)

        self.assertEquals(decoded['spam'], result['spam'])

    def testLongStringAmf0(self):
        decoded = 's' * 65537
        encoded = encoder.encode(decoded)
        result = decoder.decode(encoded)

        self.assertEquals(len(decoded), len(result))
        for char in result:
            self.assertEquals('s', char)

    def testLongListAmf0(self):
        decoded = [None] * 65537
        encoded = encoder.encode(decoded)
        result = decoder.decode(encoded)

        self.assertEquals(len(decoded), len(result))
        for val in result:
            self.assertEquals(None, val)

    def testDictAmf0(self):
        decoded = {'spam': 'eggs'}
        encoded = encoder.encode(decoded)
        result = decoder.decode(encoded)

        self.assertEquals(decoded['spam'], result['spam'])

    def testComplexDictProxies(self):
        complex = {'element': 'ignore', 'objects': self.buildComplex()}
        encoded = encoder.encode(complex, use_array_collections=True, use_object_proxies=True, class_def_mapper=self.class_mapper, amf3=True)
        decoded = decoder.decode(encoded, class_def_mapper=self.class_mapper, amf3=True)
        self.resultTest(decoded['objects'])

    def testComplexDict(self):
        complex = {'element': 'ignore', 'objects': self.buildComplex()}
        encoded = encoder.encode(complex, use_array_collections=False, use_object_proxies=False, class_def_mapper=self.class_mapper, amf3=True)
        decoded = decoder.decode(encoded, class_def_mapper=self.class_mapper, amf3=True)
        self.resultTest(decoded['objects'])

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(RoundTripTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())

