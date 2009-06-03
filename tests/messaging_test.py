import threading
import unittest
import time
import random

from amfast.remoting.channel import ChannelSet, Channel, HttpChannel, NotConnectedError, ChannelError

class MessagingTestCase(unittest.TestCase):

    CHANNEL_NAME = 'channel'
    HTTP_CHANNEL_NAME = 'http_channel'
    TOPIC = 'topic'

    # Use the same ChannelSet for everything
    channel_set = ChannelSet()
    channel_set.mapChannel(Channel(CHANNEL_NAME))
    channel_set.mapChannel(HttpChannel(HTTP_CHANNEL_NAME))

    def tearDown(self):
        for connection in self.channel_set._connections.values():
            connection.disconnect()

    def connect(self, channel_name):
        client_id = self.channel_set.generateId()
        channel = self.channel_set.getChannel(channel_name)
        return channel.connect(client_id)

    def testConnect(self):
        connection = self.connect(self.CHANNEL_NAME)
        self.assertTrue(connection.channel.connection_count > 0)
        self.assertEquals(id(connection), id(self.channel_set.getConnection(connection.flex_client_id)))

        channel = self.channel_set.getChannel(self.HTTP_CHANNEL_NAME)
        self.assertRaises(ChannelError, channel.connect, connection.flex_client_id)

    def testDisconnect(self):
        connection = self.connect(self.CHANNEL_NAME)
        connection.disconnect()

        self.assertEquals(0, connection.channel.connection_count)
        self.assertRaises(NotConnectedError, self.channel_set.getConnection, connection.flex_client_id)

    def testSubscribe(self):
        connection = self.connect(self.CHANNEL_NAME)
        self.channel_set.message_agent.subscribe(connection, connection.flex_client_id, self.TOPIC)

        # Make sure subscription is listed in connection
        client_subscriptions = connection._subscriptions.get(connection.flex_client_id)
        self.assertTrue(client_subscriptions.has_key(self.TOPIC))

        # Make sure subscription is listed in message_agent
        client_ids = self.channel_set.message_agent._topics[self.TOPIC]
        self.assertTrue(client_ids.has_key(connection.flex_client_id))

    def testUnSubscribe(self):
        connection = self.connect(self.CHANNEL_NAME)
        self.channel_set.message_agent.subscribe(connection, connection.flex_client_id, self.TOPIC)
        
        self.channel_set.message_agent.unsubscribe(connection, connection.flex_client_id, self.TOPIC)

        # Make sure subscription is listed in connection
        self.assertFalse(connection._subscriptions.has_key(connection.flex_client_id))

        # Make sure subscription is listed in message_agent
        self.assertFalse(self.channel_set.message_agent._topics.has_key(self.TOPIC))

    def testPublish(self):
        connection = self.connect(self.CHANNEL_NAME)
        self.channel_set.message_agent.subscribe(connection, connection.flex_client_id, self.TOPIC)

        self.channel_set.message_agent.publish('test', self.TOPIC)
        self.assertEquals(1, len(connection._messages))

    def testPoll(self):
        connection = self.connect(self.CHANNEL_NAME)
        self.channel_set.message_agent.subscribe(connection, connection.flex_client_id, self.TOPIC)

        self.channel_set.message_agent.publish('test', self.TOPIC)
        msgs = connection.poll()
        self.assertEquals(1, len(msgs))
        self.assertEquals(0, len(connection._messages))

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(MessagingTestCase)

if __name__ == "__main__":
    unittest.TextTestRunner().run(suite())
