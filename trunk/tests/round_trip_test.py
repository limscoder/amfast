import unittest

from amfast.encode import encode
from amfast.decode import decode
from amfast.context import EncoderContext, DecoderContext
import amfast.class_def as class_def

class RoundTripTestCase(unittest.TestCase):
    class TestObject(object):
        def __init__(self):
            self.number = None
            self.test_list = ['test']
            self.sub_obj = None
            self.test_dict = {'test': 'ignore'}
            self._float = float(1.234)
            self._int = '1'
            self._str = 123

    class TestSubObject(object):
        def __init__(self):
            self.number = None

    def setUp(self):
        self.class_mapper = class_def.ClassDefMapper()

        self.class_mapper.mapClass(class_def.DynamicClassDef(self.TestObject,
            'test_complex.test', static_attrs=()))
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
	encoded = encode(decoded, EncoderContext(amf3=True))
        result = decode(DecoderContext(encoded, amf3=True))

        self.assertEquals(len(decoded), len(result))
        for char in result:
            self.assertEquals('s', char)

    def testLongListAmf3(self):
        decoded = [None] * 65537
        encoded = encode(decoded, EncoderContext(amf3=True))
        result = decode(DecoderContext(encoded, amf3=True))

        self.assertEquals(len(decoded), len(result))
        for val in result:
            self.assertEquals(None, val)

    def testDictAmf3(self):
        decoded = {'spam': 'eggs'}
        encoded = encode(decoded, EncoderContext(amf3=True))
        result = decode(DecoderContext(encoded, amf3=True))

        self.assertEquals(decoded['spam'], result['spam'])

    def testLongStringAmf0(self):
        decoded = 's' * 65537
        encoded = encode(decoded)
        result = decode(encoded)

        self.assertEquals(len(decoded), len(result))
        for char in result:
            self.assertEquals('s', char)

    def testLongListAmf0(self):
        decoded = [None] * 65537
        encoded = encode(decoded)
        result = decode(encoded)

        self.assertEquals(len(decoded), len(result))
        for val in result:
            self.assertEquals(None, val)

    def testDictAmf0(self):
        decoded = {'spam': 'eggs'}
        encoded = encode(decoded)
        result = decode(encoded)

        self.assertEquals(decoded['spam'], result['spam'])

    def testComplexDictProxies(self):
        complex = {'element': 'ignore', 'objects': self.buildComplex()}
        enc_context = EncoderContext(use_collections=True, use_proxies=True,
            class_def_mapper=self.class_mapper, amf3=True)
        encoded = encode(complex, enc_context)
        decoded = decode(DecoderContext(encoded, class_def_mapper=self.class_mapper, amf3=True))
        self.resultTest(decoded['objects'])

    def testComplexDict(self):
        complex = {'element': 'ignore', 'objects': self.buildComplex()}
        enc_context = EncoderContext(use_collections=False, use_proxies=False,
            class_def_mapper=self.class_mapper, amf3=True)
        encoded = encode(complex, enc_context)
        decoded = decode(DecoderContext(encoded, class_def_mapper=self.class_mapper, amf3=True))
        self.resultTest(decoded['objects'])

    def testEncodeTypes(self):
        enc_mapper = class_def.ClassDefMapper()

        enc_mapper.mapClass(class_def.DynamicClassDef(self.TestObject,
            'test_complex.test', static_attrs=(), encode_types={
                '_float': float, '_int': int, '_str': str}))
        enc_mapper.mapClass(class_def.DynamicClassDef(self.TestSubObject, 'test_complex.sub', ()))

        complex = self.buildComplex()
        enc_context = EncoderContext(class_def_mapper=enc_mapper, amf3=True, include_private=True)
        encoded = encode(complex, enc_context)
        decoded = decode(DecoderContext(encoded, class_def_mapper=self.class_mapper, amf3=True))
        self.assertEquals('float', decoded[0]._float.__class__.__name__)
        self.assertEquals('int', decoded[0]._int.__class__.__name__)
        self.assertEquals('unicode', decoded[0]._str.__class__.__name__)

    def testDecodeTypes(self):
        dec_mapper = class_def.ClassDefMapper()

        dec_mapper.mapClass(class_def.DynamicClassDef(self.TestObject,
            'test_complex.test', static_attrs=(), decode_types={
                '_float': float, '_int': int, '_str': str}))
        dec_mapper.mapClass(class_def.DynamicClassDef(self.TestSubObject, 'test_complex.sub', ()))

        complex = self.buildComplex()
        enc_context = EncoderContext(class_def_mapper=self.class_mapper, amf3=True, include_private=True)
        encoded = encode(complex, enc_context)
        decoded = decode(DecoderContext(encoded, class_def_mapper=dec_mapper, amf3=True))
        self.assertEquals('float', decoded[0]._float.__class__.__name__)
        self.assertEquals('int', decoded[0]._int.__class__.__name__)
        self.assertEquals('str', decoded[0]._str.__class__.__name__)

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(RoundTripTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())

