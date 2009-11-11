import optparse
from timeit import Timer

try:
    import pyamf
    from pyamf.util import BufferedByteStream
    use_pyamf = True
except ImportError:
    use_pyamf = False

from amfast.context import DecoderContext, EncoderContext
import amfast.encode as encode
import amfast.decode as decode
import amfast.class_def as class_def

class SpeedTestCase():
    class TestObject(object):
        STRING_REF = 'string reference'
        
        def __init__(self):
            self.null = None
            self.test_list = ['test', 'tester']
            self.test_dict = {'test': 'ignore'}

    class TestSubObject(object):
        def __init__(self):
            self.number = None

    class TestStaticObject(object):
        class __amf__:
            static = ('name', 'score', 'rank')

        def __init__(self, name='', score='', rank=''):
            self.name = name
            self.score = score
            self.rank = rank

    def setUp(self):
        self.class_mapper = class_def.ClassDefMapper()

        self.class_mapper.mapClass(class_def.DynamicClassDef(self.TestObject,
            'test_complex.test', (), amf3=False))
        self.class_mapper.mapClass(class_def.DynamicClassDef(self.TestSubObject,
            'test_complex.sub', (), amf3=False))
        self.class_mapper.mapClass(class_def.ClassDef(self.TestStaticObject,
            'test_complex.static', ('name', 'score', 'rank'), amf3=False))

        if use_pyamf is True:
            pyamf.register_class(self.TestObject, 'test_complex.test')
            pyamf.register_class(self.TestSubObject, 'test_complex.sub')
            pyamf.register_class(self.TestStaticObject, 'test_complex.static')

    def tearDown(self):
        self.class_mapper.unmapClass(self.TestObject)
        self.class_mapper.unmapClass(self.TestSubObject)

        if use_pyamf is True:
            pyamf.unregister_class(self.TestObject)
            pyamf.unregister_class(self.TestSubObject)

    def buildSimple(self, max=5):
        test_objects = []
        
        for i in xrange(0, max):
            test_obj = {
                'number': 10,
                'float': 3.24,
                'string': 'foo number %i' % i
            }
            test_objects.append(test_obj)
        return test_objects

    def buildComplex(self, max=5):
        test_objects = []

        for i in xrange(0, max):
            test_obj = self.TestObject()
            test_obj.number = i
            test_obj.float = 3.14
            test_obj.unicode = u'spam'
            test_obj.str = 'a l' + 'o' * 500 + 'ng string'
            test_obj.str_ref = self.TestObject.STRING_REF
            test_obj.sub_obj = self.TestSubObject()
            test_obj.sub_obj.number = i
            test_obj.ref = test_obj.sub_obj
            test_objects.append(test_obj)

        return test_objects

    def buildBig(self, object_size=5, object_count=1000):
        test_objects = []
        for i in xrange(0, object_count):
            test_objects.append(self.buildSimple())

    def buildStatic(self, max=5):
        test_objects = []

        for i in xrange(0, max):
            test_objects.append(self.TestStaticObject('name %s' % i, 5.5555555, i))
        return test_objects

    def buildReference(self, object_size=1000):
        obj = {'foo': 'bar'}

        objs = []
        for i in xrange(0, object_size):
            objs.append(obj)
 
    def encode(self, obj, pyamf=False, amf3=False, use_proxies=False):
        if pyamf is True:
            return self.pyamfEncode(obj, amf3, use_proxies)
        else:
            return self.amfastEncode(obj, amf3, use_proxies)

    def amfastEncode(self, obj, amf3=False, use_proxies=False):        
        enc_context = EncoderContext(use_collections=use_proxies,
            use_proxies=use_proxies, class_def_mapper=self.class_mapper,
            amf3=amf3)

        return encode.encode(obj, enc_context)

    def decode(self, str, amf3=False, pyamf=False):
        if pyamf is True:
            return self.pyamfDecode(str, amf3)
        else:
            return self.amfastDecode(str, amf3)

    def amfastDecode(self, str, amf3=False):
        decoded = decode.decode(DecoderContext(str,
            class_def_mapper=self.class_mapper, amf3=amf3))

    def pyamfEncode(self, obj, amf3=False, use_proxies=False):
        if amf3 is True:
            context = pyamf.get_context(pyamf.AMF3)
        else:
            context = pyamf.get_context(pyamf.AMF0)

        stream = BufferedByteStream()

        if amf3 is True:
            pyamf_encoder = pyamf.get_encoder(pyamf.AMF3, stream=stream, context=context)
        else:
            pyamf_encoder = pyamf.get_encoder(pyamf.AMF0, stream=stream, context=context)

        pyamf_encoder.writeElement(obj)
        return pyamf_encoder.stream.getvalue()

    def pyamfDecode(self, str, amf3=False):
        if amf3 is True:
            context = pyamf.amf3.Context()
            decoded = pyamf.amf3.Decoder(str, context).readElement()
        else:
            context = pyamf.amf0.Context()
            decoded = pyamf.amf0.Decoder(str, context).readElement()

    def simple(self, decode=False, amf3=False, pyamf=False):
        self.doTest(self.buildSimple, 50000, decode=decode, amf3=amf3, pyamf=pyamf)

    def complex(self, decode=False, amf3=False, pyamf=False):
        self.doTest(self.buildComplex, 10000, decode=decode, amf3=amf3, pyamf=pyamf)

    def big(self, decode=False, amf3=False, pyamf=False):
        self.doTest(self.buildBig, 1000, decode=decode, amf3=amf3, pyamf=pyamf)

    def static(self, decode=False, amf3=False, pyamf=False):
        self.doTest(self.buildStatic, 50000, decode=decode, amf3=amf3, pyamf=pyamf)

    def reference(self, decode=False, amf3=False, pyamf=False):
        self.doTest(self.buildReference, 25000, decode=decode, amf3=amf3, pyamf=pyamf)

    def doTest(self, obj_func, obj_count=10, decode=False, amf3=False, pyamf=False):
        for i in xrange(obj_count):
            obj = obj_func()
            encoded = self.encode(obj, pyamf=pyamf, amf3=amf3, use_proxies=False)
            if decode is True:
                decoded = self.decode(encoded, pyamf=pyamf, amf3=amf3)

    def benchmarkTest(self, function_name, label, repeat=3, print_result=True):
        self.setUp()

        t = Timer("%s()" % function_name, "from __main__ import %s" % function_name)
        e_time = t.timeit(repeat)

        if print_result is True:
            print "----"
            print "Running %s %ix:" % (label, repeat)
            print "%s seconds" % e_time
            print "----"

        self.tearDown()
        return e_time

    def runBenchmarks(self, tests, results, pyamf=False, repeat=3, print_result=True):
        for test in tests:
            def _test():
                test['test'](*test['args'], **test['kwargs'])

            global current_test
            current_test = _test

            if pyamf is True:
                label = 'PyAmf: ' + test['label']
            else:
                label = 'AmFast: ' + test['label']
            e_time = tester.benchmarkTest('current_test', label, repeat, print_result)

            if pyamf is True:
                result = results[test['label']]
                result['PyAmf'] = e_time
                result['diff'] = e_time / result['AmFast']
            else:
                results[test['label']] = {'AmFast': e_time}


if __name__ == "__main__":
    usage = """usage: %s [options]""" % __file__
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-r", "--repeat", dest="repeat", default=1, help="Number of times to repeat each test.")
    parser.add_option("-p", action="store_true", dest="print_result", help="Print live output")
    parser.add_option("-a", action="store_true", dest="pyamf", help="Test PyAmf")
    (options, args) = parser.parse_args()

    tester = SpeedTestCase()
    tests = [
        {'test': tester.simple, 'label': 'AMF0 Encode Simple',
            'args': [], 'kwargs': {'decode': False, 'amf3': False, 'pyamf': False}},
        {'test': tester.simple, 'label': 'AMF0 Encode/Decode Simple',
            'args': [], 'kwargs': {'decode': True, 'amf3': False, 'pyamf': False}},

        {'test': tester.complex, 'label': 'AMF0 Encode Complex',
            'args': [], 'kwargs': {'decode': False, 'amf3': False, 'pyamf': False}},
        {'test': tester.complex, 'label': 'AMF0 Encode/Decode Complex',
            'args': [], 'kwargs': {'decode': True, 'amf3': False, 'pyamf': False}},


        {'test': tester.big, 'label': 'AMF0 Encode Big',
            'args': [], 'kwargs': {'decode': False, 'amf3': False, 'pyamf': False}},
        {'test': tester.big, 'label': 'AMF0 Encode/Decode Big',
            'args': [], 'kwargs': {'decode': True, 'amf3': False, 'pyamf': False}},

        {'test': tester.static, 'label': 'AMF0 Encode Static',
            'args': [], 'kwargs': {'decode': False, 'amf3': False, 'pyamf': False}},
        {'test': tester.static, 'label': 'AMF0 Encode/Decode Static',
            'args': [], 'kwargs': {'decode': True, 'amf3': False, 'pyamf': False}},

        {'test': tester.reference, 'label': 'AMF0 Encode Reference',
            'args': [], 'kwargs': {'decode': False, 'amf3': False, 'pyamf': False}},
        {'test': tester.reference, 'label': 'AMF0 Encode/Decode Reference',
            'args': [], 'kwargs': {'decode': True, 'amf3': False, 'pyamf': False}},
    ]

    # Add AMF3 tests
    amf3_tests = []
    for test in tests:
        amf3_test = {
            'test': test['test'],
            'label': test['label'].replace('AMF0', 'AMF3'),
            'args': [],
            'kwargs': {}
        }


        amf3_test['args'].extend(test['args'])
        amf3_test['kwargs'].update(test['kwargs'])
        amf3_test['kwargs']['amf3'] = True
        amf3_tests.append(amf3_test);
    tests.extend(amf3_tests)

    # Run AmFast tests
    results = {}
    tester.runBenchmarks(tests, results, pyamf=False, repeat=options.repeat, print_result=options.print_result)

    if options.pyamf:
        pyamf_tests = []
        for test in tests:
            pyamf_test = {
                'test': test['test'],
                'label': test['label'],
                'args': [],
                'kwargs': {}
            }

            pyamf_test['args'].extend(test['args'])
            pyamf_test['kwargs'].update(test['kwargs'])
            pyamf_test['kwargs']['pyamf'] = True
            pyamf_tests.append(pyamf_test);

        # Run PyAmf tests
        tester.runBenchmarks(pyamf_tests, results, pyamf=True, repeat=options.repeat, print_result=options.print_result)

    # Print results
    header = ('', 'AmFast')
    if options.pyamf:
        header.extend(['PyAmf', 'Diff'])
    print ','.join(header)
    for label, result in results.iteritems():
        row = [label, '%s' % result['AmFast']]
        if options.pyamf:
            row.extend(['%s' % result['PyAmf'], '%s' % result['diff']])
        print ','.join(row)
