import os
import sys
import time
import unittest

from amfast.remoting.connection_manager import NotConnectedError, \
    SessionAttrError, MemoryConnectionManager

class ConnectionTestCase(unittest.TestCase):

    class TestChannel(object):
        def __init__(self):
            self.name = 'test'

    def setUp(self):
        self.manager.reset()
        self.channel = self.TestChannel()

    def _testConnectionProps(self, connection):
        """Checks newly inited props."""
        self.assertEquals(36, len(connection.id))
        self.assertEquals(self.channel.name, connection.channel_name)
        self.assertTrue(connection.connected)
        self.assertFalse(connection.authenticated)
        self.assertEquals(None, connection.flex_user)
        self.assertTrue(connection.last_active > 0)
        self.assertTrue(time.time() * 1000 > connection.last_active)

    def _testCompare(self, connection, connection_2):
        self.assertEquals(connection.id, connection_2.id)
        self.assertEquals(connection.channel_name, connection_2.channel_name)
        self.assertEquals(connection.timeout, connection_2.timeout)
        self.assertEquals(connection.connected, connection_2.connected)
        self.assertEquals(connection.authenticated, connection_2.authenticated)
        self.assertEquals(connection.flex_user, connection_2.flex_user)
        self.assertEquals(connection.last_active, connection_2.last_active)
        self.assertEquals(connection.last_polled, connection_2.last_polled)

    def testCreateConnection(self):
        connection = self.manager.createConnection(self.channel)
        self._testConnectionProps(connection)

    def testGetConnection(self):
        connection = self.manager.createConnection(self.channel)
        last_active = connection.last_active

        new_connection = self.manager.getConnection(connection.id, touch=True)
        self._testConnectionProps(new_connection)
        self.assertTrue(last_active < new_connection.last_active)
        last_active = new_connection.last_active

        new_connection = self.manager.getConnection(connection.id, touch=False)
        self.assertEquals(last_active, new_connection.last_active)

        self._testCompare(connection, new_connection)

    def testGetConnectionRaisesNotConnectedError(self):
        self.assertRaises(NotConnectedError, self.manager.getConnection, 'not_connected')

    def testDeleteConnection(self):
        connection = self.manager.createConnection(self.channel)
        self.manager.deleteConnection(connection)
        self.assertFalse(connection.connected)
        self.assertRaises(NotConnectedError, self.manager.getConnection, connection.id)

    def testConnectConnection(self):
        connection = self.manager.createConnection(self.channel)
        connection.disconnect()
        self.assertFalse(connection.connected)
        connection.connect()
        self.assertTrue(connection.connected)

    def testTouch(self):
        connection = self.manager.createConnection(self.channel)
        last_active = connection.last_active
        connection.touch()
        self.assertTrue(connection.last_active > last_active)

    def testTouchPoll(self):
        connection = self.manager.createConnection(self.channel)
        last_polled = connection.last_polled
        connection.touchPolled()
        self.assertTrue(connection.last_polled > last_polled)

    def testAuthenticate(self):
        connection = self.manager.createConnection(self.channel)
        user = 'tester'
        connection.authenticate(user)
        self.assertTrue(connection.authenticated)
        self.assertEquals(user, connection.flex_user)

        connection.unAuthenticate()
        self.assertFalse(connection.authenticated)
        self.assertEquals(None, connection.flex_user)

    def testNotifyFunc(self):
        def notify():
            return True

        connection = self.manager.createConnection(self.channel)
        connection.setNotifyFunc(notify)
        self.assertTrue(connection.notify_func())
        connection.unSetNotifyFunc()
        self.assertEquals(None, connection.notify_func)

    def testSessionAttrs(self):
        connection = self.manager.createConnection(self.channel)
        key_1 = 'key_1'
        key_2 = 'key_2'
        val_1 = 'val_1'
        val_2 = 'val_2'

        connection.setSessionAttr(key_1, val_1)
        connection.setSessionAttr(key_2, val_2)
        self.assertEquals(val_1, connection.getSessionAttr(key_1))
        self.assertEquals(val_2, connection.getSessionAttr(key_2))

        connection = self.manager.getConnection(connection.id)
        self.assertEquals(val_1, connection.getSessionAttr(key_1))
        self.assertEquals(val_2, connection.getSessionAttr(key_2))

        connection.delSessionAttr(key_1)
        self.assertEquals(val_2, connection.getSessionAttr(key_2))

        connection = self.manager.getConnection(connection.id) 
        self.assertRaises(SessionAttrError, connection.getSessionAttr, key_1)

    def testReset(self):
        connection = self.manager.createConnection(self.channel)
        self.manager.reset()
        self.assertRaises(NotConnectedError, self.manager.getConnection, connection.id)

    def testChannelCount(self):
        count = 5
        ids = []
        for i in xrange(count):
            connection = self.manager.createConnection(self.channel)
            ids.append(connection.id)

        self.assertEquals(count, self.manager.getConnectionCount(self.channel.name))

        for connection_id in ids:
            connection = self.manager.getConnection(connection_id)
            connection.delete()

        self.assertEquals(0, self.manager.getConnectionCount(self.channel.name))

class MemoryTestCase(ConnectionTestCase):

    def setUp(self):
        self.manager = MemoryConnectionManager()
        ConnectionTestCase.setUp(self)

class GaeTestCase(ConnectionTestCase):

    def setUp(self):
        from amfast.remoting.gae_connection_manager import GaeConnectionManager
        self.manager = GaeConnectionManager()
        ConnectionTestCase.setUp(self)

    def testNotifyFunc(self):
        pass

class MemcacheTestCase(ConnectionTestCase):

    def setUp(self):
        from amfast.remoting.memcache_connection_manager import MemcacheConnectionManager
        self.manager = MemcacheConnectionManager()
        ConnectionTestCase.setUp(self)

    def testNotifyFunc(self):
        pass

class SaTestCase(ConnectionTestCase):

    def setUp(self):
        import sqlalchemy as sa
        from amfast.remoting.sa_connection_manager import SaConnectionManager

        engine = sa.create_engine('sqlite:///sa_test_case.db', echo=False)
        metadata = sa.MetaData()

        self.manager = SaConnectionManager(engine, metadata)
        self.manager.createTables()
        ConnectionTestCase.setUp(self)

def suite():
    tests = [
        unittest.TestLoader().loadTestsFromTestCase(MemoryTestCase)
    ]

    print "\n---- Optional Connection Tests ----"
    try:
        from amfast.remoting.gae_connection_manager import GaeConnectionManager
    except Exception:
        # Skip if we're not in Gae environment.
        print "Skipping GAE test."
    else:
        print "Running GAE test."
        tests.append(unittest.TestLoader().loadTestsFromTestCase(GaeTestCase))

    try:
        import sqlalchemy as sa
        from amfast.remoting.sa_connection_manager import SaConnectionManager
    except Exception:
        # Skip if SQLAlchemy is not installed.
        print "Skipping SA test."
    else:
        print "Running SA test."
        tests.append(unittest.TestLoader().loadTestsFromTestCase(SaTestCase))

    try:
        from amfast.remoting.memcache_connection_manager import MemcacheConnectionManager

        # Check connection
        manager = MemcacheConnectionManager()
        if manager.mc.set("test", True) is not True:
            print "Memcache set failed."
            raise Error("Memcache connection failed.")
        if manager.mc.get("test") != True:
            print "Memcache get failed."
            raise Error("Memcache connection failed.")
    except Exception:
        # Skip if memcache support is not installed.
        print "Skipping Memcache test."
    else:
        print "Running Memcache test."
        tests.append(unittest.TestLoader().loadTestsFromTestCase(MemcacheTestCase))

    print "--------"

    return unittest.TestSuite(tests)

if __name__ == '__main__':
    unittest.TextTestRunner().run(suite())   
