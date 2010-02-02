import unittest

import amfast
amfast.use_dummy_threading = True

def suite():
    import amf3_encoder_test
    import amf0_encoder_test
    import amf3_decoder_test
    import amf0_decoder_test
    import round_trip_test
    import remoting_test
    import buffer_test
    import context_test
    import connection_test
    import subscription_test
    import messaging_test

    return unittest.TestSuite((
        amf3_decoder_test.suite(),
        amf3_encoder_test.suite(),
        amf0_encoder_test.suite(),
        amf0_decoder_test.suite(),
        round_trip_test.suite(),
        remoting_test.suite(),
        buffer_test.suite(),
        context_test.suite(),
        connection_test.suite(),
        subscription_test.suite(),
        messaging_test.suite()
    ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(suite())    
