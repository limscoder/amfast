import unittest
import time
import random

from amfast.remoting.channel import ChannelSet, Channel, HttpChannel, ChannelError
from amfast.remoting.connection_manager import NotConnectedError

class MessagingTestCase(unittest.TestCase):

    CHANNEL_NAME = 'channel'
    HTTP_CHANNEL_NAME = 'http_channel'
    TOPIC = 'topic'

    # Use the same ChannelSet for everything
    channel_set = ChannelSet()
    channel_set.mapChannel(Channel(CHANNEL_NAME))
    channel_set.mapChannel(HttpChannel(HTTP_CHANNEL_NAME))

    def setUp(self):
        self.channel_set.connection_manager.reset()
        self.channel_set.subscription_manager.reset()
        self.flex_client_id = 'my_client_id'

    def tearDown(self):
        pass

    def connect(self, channel_name):
        channel = self.channel_set.getChannel(channel_name)
        return channel.connect()

    def testConnect(self):
        connection = self.connect(self.CHANNEL_NAME)

        channel = self.channel_set.getChannel(self.CHANNEL_NAME)
        self.assertTrue(channel.channel_set.connection_manager.getConnectionCount(channel.name) > 0)

        channel = self.channel_set.getChannel(self.HTTP_CHANNEL_NAME)
        self.assertRaises(ChannelError, channel.connect, connection.id)

    def testDisconnect(self):
        connection = self.connect(self.CHANNEL_NAME)
        channel = self.channel_set.getChannel(self.CHANNEL_NAME)

        connection_count = channel.channel_set.connection_manager.getConnectionCount(channel.name)
        id = connection.id
        channel.disconnect(connection)
         
        self.assertEquals(connection_count - 1, channel.channel_set.connection_manager.getConnectionCount(channel.name))
        self.assertRaises(NotConnectedError, self.channel_set.connection_manager.getConnection, id)

    def testSubscribe(self):
        connection = self.connect(self.CHANNEL_NAME)
        self.channel_set.subscription_manager.subscribe(connection, self.flex_client_id, self.TOPIC)

    def testUnSubscribe(self):
        connection = self.connect(self.CHANNEL_NAME)
        self.channel_set.subscription_manager.subscribe(connection, self.flex_client_id, self.TOPIC)
        
        self.channel_set.subscription_manager.unSubscribe(connection, self.flex_client_id, self.TOPIC)

    def testPublish(self):
        connection = self.connect(self.CHANNEL_NAME)
        self.channel_set.subscription_manager.subscribe(connection.id, self.flex_client_id, self.TOPIC)

        self.channel_set.publishObject('test', self.TOPIC)
        msgs = self.channel_set.subscription_manager.pollConnection(connection)
        self.assertEquals(1, len(msgs))

    def testPoll(self):
        connection = self.connect(self.CHANNEL_NAME)
        self.channel_set.subscription_manager.subscribe(connection.id, self.flex_client_id, self.TOPIC)

        # Make sure messages are polled
        self.channel_set.publishObject('test', self.TOPIC)
        msgs = self.channel_set.subscription_manager.pollConnection(connection)
        self.assertEquals(1, len(msgs))

        # Make sure polled messages were deleted
        msgs = self.channel_set.subscription_manager.pollConnection(connection)
        self.assertEquals(0, len(msgs))

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(MessagingTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())
