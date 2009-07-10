import unittest

from amfast.remoting.connection_manager import NotConnectedError, MemoryConnectionManager

class MemoryConnectionTestCase(unittest.TestCase):

    class TestChannel(object):
        def __init__(self):
            self.name = 'test'

    def setUp(self):
        self.manager = MemoryConnectionManager()
        self.channel = self.TestChannel()        

    def testCreateConnection(self):
        connection = self.manager.createConnection(self.channel)
        self.assertEquals(36, len(connection.id))

    def testGetConnection(self):
        connection = self.manager.createConnection(self.channel)
        id = connection.id
        last_active = connection.last_active

        connection = self.manager.getConnection(id, True)
        self.assertNotEqual(last_active, connection.last_active)
        last_active = connection.last_active

    def testGetConnectionRaisesNotConnectedError(self):
        self.assertRaises(NotConnectedError, self.manager.getConnection, 'not connected')

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(MemoryConnectionTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())
