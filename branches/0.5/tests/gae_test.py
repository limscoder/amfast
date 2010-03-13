"""Tests to be run from Google App Engine."""
import unittest

import connection_test
import subscription_test

def suite():
    return unittest.TestSuite((
        unittest.TestLoader().loadTestsFromTestCase(connection_test.GaeTestCase),
        unittest.TestLoader().loadTestsFromTestCase(subscription_test.GaeTestCase),
        unittest.TestLoader().loadTestsFromTestCase(connection_test.MemcacheTestCase),
        unittest.TestLoader().loadTestsFromTestCase(subscription_test.MemcacheTestCase)
    ))
  
