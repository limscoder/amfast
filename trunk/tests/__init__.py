import unittest

import amf3_encoder_test
import amf0_encoder_test
import amf3_decoder_test
import amf0_decoder_test
import round_trip_test
import remoting_test

def suite():
    return unittest.TestSuite((
        amf3_decoder_test.suite(),
        amf3_encoder_test.suite(),
        amf0_encoder_test.suite(),
        amf0_decoder_test.suite(),
        round_trip_test.suite(),
        remoting_test.suite()
    ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(suite())    
