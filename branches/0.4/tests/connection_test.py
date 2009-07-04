import unittest

from amfast.remoting.connection_manager import NotConnectedError, MemoryConnectionManager

class MemoryConnectionTestCase(unittest.TestCase):

    def setUp(self):
        self.manager = MemoryConnectionManager()

    def testCreateConnection(self):
        connection = self.manager.createConnection()
        self.assertEquals(36, len(connection.id))

    def testGetConnection(self):
        connection = self.manager.createConnection()
        connection['test'] = True
        id = connection.id
        last_active = connection.last_active
        connection.save()

        connection = self.manager.getConnection(id, True)
        self.assertTrue('test' in connection)
        self.assertNotEqual(last_active, connection.last_active)
        last_active = connection.last_active

        #connection = self.manager.getConnection(id, False)
        #self.assertEqual(last_active, connection.last_active)

    def testDelAttr(self):
        connection = self.manager.createConnection()
        connection['test'] = True
        id = connection.id
        connection.save()

        connection = self.manager.getConnection(id, True)
        self.assertTrue('test' in connection)
        del connection['test']
        connection.save()

        connection = self.manager.getConnection(id, True)
        self.assertFalse('test' in connection)

    def testGetConnectionRaisesNotConnectedError(self):
        self.assertRaises(NotConnectedError, self.manager.getConnection, 'not connected')

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(MemoryConnectionTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())
