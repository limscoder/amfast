# -*- coding: utf-8 -*-
import gc
import json
import re
import sys
import unittest

from guppy import hpy

from amfast.decoder import Decoder
from amfast.encoder import Encoder

class MemTestCase(unittest.TestCase):
    pattern = re.compile(r'Total size = (.+) bytes')

    def heapSize(self):
        # There's got to be a better way to do this???
        hp = hpy()
        size = str(hp.heap())
        m = self.pattern.search(size)
        return int(m.group(1))

    def _testEncoder(self, encoder, json_file):
         in_file = open(json_file)
         try:
             for idx, line in enumerate(in_file):
                 start = self.heapSize()

                 obj = json.loads(line)
                 for count in xrange(1000):
                     out = encoder.encode(obj)

                 obj = None
                 en = None
                 out = None
                 gc.collect()

                 end = self.heapSize()
                 print '%s (%s): %s - %s' % (idx, line[:10], start, end)
                 sys.stdout.flush()
         finally:
             in_file.close()

    def _testDecoder(self, decoder, encoder, json_file):
         in_file = open(json_file)
         try:
             for idx, line in enumerate(in_file):
                 if (not line.startswith('{"status"')):
                     continue

                 start = self.heapSize()

                 obj = json.loads(line)
                 for count in xrange(1000000):
                     out = encoder.encode(obj)
                     new = decoder.decode(out)

                 obj = None
                 en = None
                 out = None
                 new = None
                 gc.collect()

                 end = self.heapSize()
                 print '%s (%s): %s - %s' % (idx, line[:10], start, end)
                 sys.stdout.flush()
         finally:
             in_file.close()

         

    def testEncodeAmf0(self):
         return
         self._testEncoder(Encoder(), 'sample.log')

    def testEncodeAmf3(self):
         return
         self._testEncoder(Encoder(amf3=True), 'sample.log')

    def testDecodeAmf0(self):
         return
         self._testDecoder(Decoder(), Encoder(), 'sample.log')

    def testDecodeAmf3(self):
         return
         self._testDecoder(Decoder(amf3=True), Encoder(amf3=True), 'sample_2.log')

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(MemTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())
