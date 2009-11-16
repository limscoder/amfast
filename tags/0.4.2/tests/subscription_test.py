import time
import unittest

from amfast.remoting.subscription_manager import MemorySubscriptionManager
import amfast.remoting.flex_messages as messaging

try:
    from amfast.remoting.gae_subscription_manager import GaeSubscriptionManager
except ImportError:
    # Only import when running from GAE environment.
    pass

try:
    from amfast.remoting.memcache_subscription_manager import MemcacheSubscriptionManager
except ImportError:
    pass

try:
    import sqlalchemy as sa
    from amfast.remoting.sa_subscription_manager import SaSubscriptionManager
except ImportError:
    pass

class SubscriptionTestCase(unittest.TestCase):

    class Connection(object):
        def __init__(self, **kwargs):
            for key, val in kwargs.iteritems():
                setattr(self, key, val)

    def setUp(self):
        self.manager.reset()

        self.connection_id = '95e714de-bd15-48f9-b496-8b2c5cb1af78'
        self.client_id = '95e714de-bd15-48f9-b496-8b2c5cb1af60'
        self.topic = 'test'
        self.sub_topic = 'tester'

    def makeMessage(self):
        msg = messaging.AsyncMessage(body='tester', clientId=None,
            destination=self.topic,
            headers={messaging.AsyncMessage.SUBTOPIC_HEADER: self.sub_topic},
            timeToLive=30000, timestamp=time.time() * 1000, messageId=self.client_id)
        return msg

    def testSubscribe(self):
        self.manager.subscribe(self.connection_id, self.client_id,
            self.topic, self.sub_topic)

        for connection_id in self.manager.iterSubscribers(self.topic, self.sub_topic):
            self.assertEquals(self.connection_id, connection_id)

        self.manager.unSubscribe(self.connection_id, self.client_id,
            self.topic, self.sub_topic)

        count = 0
        for subscription in self.manager.iterSubscribers(self.topic, self.sub_topic):
            count += 1
        self.assertEquals(0, count)

    def testReset(self):
        self.manager.subscribe(self.connection_id, self.client_id,
            self.topic, self.sub_topic)

        self.manager.reset()

        count = 0
        for subscription in self.manager.iterSubscribers(self.topic, self.sub_topic):
            count += 1
        self.assertEquals(0, count)

    def testDeleteConnection(self):
        self.manager.subscribe(self.connection_id, self.client_id,
            self.topic, self.sub_topic)

        count = 0
        for subscription in self.manager.iterSubscribers(self.topic, self.sub_topic):
            count += 1
        self.assertEquals(1, count)

        connection = self.Connection(id=self.connection_id)
        self.manager.deleteConnection(connection)

        count = 0
        for subscription in self.manager.iterSubscribers(self.topic, self.sub_topic):
            count += 1
        self.assertEquals(0, count)

    def testPublishAndPoll(self):
        cutoff_time = time.time() * 1000

        self.manager.subscribe(self.connection_id, self.client_id,
            self.topic, self.sub_topic)

        self.manager.publishMessage(self.makeMessage())

        msgs = self.manager.pollMessages(self.manager.getTopicKey(self.topic, self.sub_topic),
            cutoff_time, cutoff_time)

        count = 0
        for msg in msgs:
            count += 1
        self.assertEquals(1, count)

    def testOldMessages(self):
        current_time = time.time() * 1000

        self.manager.subscribe(self.connection_id, self.client_id,
            self.topic, self.sub_topic)

        self.manager.publishMessage(self.makeMessage())
        cutoff_time = time.time() * 1000

        msgs = self.manager.pollMessages(self.manager.getTopicKey(self.topic, self.sub_topic),
            cutoff_time, current_time)

        count = 0
        for msg in msgs:
            count += 1
        self.assertEquals(0, count)

    def testExpiredMessages(self):
        cutoff_time = time.time() * 1000

        self.manager.subscribe(self.connection_id, self.client_id,
            self.topic, self.sub_topic)

        msg = self.makeMessage()
        msg.timeToLive = 0.00001
        self.manager.publishMessage(msg)
        current_time = time.time() * 1000

        msgs = self.manager.pollMessages(self.manager.getTopicKey(self.topic, self.sub_topic),
            cutoff_time, current_time)

        count = 0
        for msg in msgs:
            count += 1
        self.assertEquals(0, count)

class MemoryTestCase(SubscriptionTestCase):

    def setUp(self):
        self.manager = MemorySubscriptionManager()
        SubscriptionTestCase.setUp(self)

class GaeTestCase(SubscriptionTestCase):

    def setUp(self):
        self.manager = GaeSubscriptionManager()
        SubscriptionTestCase.setUp(self)

class MemcacheTestCase(SubscriptionTestCase):

    def setUp(self):
        self.manager = MemcacheSubscriptionManager()
        SubscriptionTestCase.setUp(self)

class SaTestCase(SubscriptionTestCase):

    def setUp(self):
        engine = sa.create_engine('sqlite:///sa_test_case.db', echo=False)
        metadata = sa.MetaData()

        self.manager = SaSubscriptionManager(engine, metadata)
        self.manager.createTables()
        SubscriptionTestCase.setUp(self)


def suite():
    return unittest.TestSuite((
        unittest.TestLoader().loadTestsFromTestCase(MemoryTestCase),
        unittest.TestLoader().loadTestsFromTestCase(SaTestCase)
    ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(suite())   
