import time
import unittest

from amfast.remoting.subscription_manager import MemorySubscriptionManager
import amfast.remoting.flex_messages as messaging

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

    def makeMessage(self, topic=None, sub_topic=None):
        if topic is None:
            topic = self.topic

        if sub_topic is None:
            sub_topic = self.sub_topic

        msg = messaging.AsyncMessage(body='tester', clientId=None,
            destination=topic,
            headers={messaging.AsyncMessage.SUBTOPIC_HEADER: sub_topic},
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

    def testPollIgnoresDifferentTopics(self):
        cutoff_time = time.time() * 1000

        self.manager.subscribe(self.connection_id, self.client_id,
            self.topic, self.sub_topic)

        self.manager.publishMessage(self.makeMessage())
        self.manager.publishMessage(self.makeMessage('different', 'topic'))

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
        """TODO: re-write this test.

        Expired messages now are cleaned
        in different ways depending on the
        subscription manager."""
        pass  
        #cutoff_time = time.time() * 1000

        #self.manager.subscribe(self.connection_id, self.client_id,
        #    self.topic, self.sub_topic)

        #msg = self.makeMessage()
        #msg.timeToLive = 0.00001
        #self.manager.publishMessage(msg)
        #current_time = time.time() * 1000

        #msgs = self.manager.pollMessages(self.manager.getTopicKey(self.topic, self.sub_topic),
        #    cutoff_time, current_time)

        #count = 0
        #for msg in msgs:
        #    count += 1
        #self.assertEquals(0, count)

class MemoryTestCase(SubscriptionTestCase):

    def setUp(self):
        self.manager = MemorySubscriptionManager()
        SubscriptionTestCase.setUp(self)

class GaeTestCase(SubscriptionTestCase):

    def setUp(self):
        from amfast.remoting.gae_subscription_manager import GaeSubscriptionManager
        self.manager = GaeSubscriptionManager()
        SubscriptionTestCase.setUp(self)

class MemcacheTestCase(SubscriptionTestCase):

    def setUp(self):
        from amfast.remoting.memcache_subscription_manager import MemcacheSubscriptionManager
        self.manager = MemcacheSubscriptionManager()
        SubscriptionTestCase.setUp(self)

class SaTestCase(SubscriptionTestCase):

    def setUp(self):
        import sqlalchemy as sa
        from amfast.remoting.sa_subscription_manager import SaSubscriptionManager
        engine = sa.create_engine('sqlite:///sa_test_case.db', echo=False)
        metadata = sa.MetaData()

        self.manager = SaSubscriptionManager(engine, metadata)
        self.manager.createTables()
        SubscriptionTestCase.setUp(self)


def suite():
    tests = [
        unittest.TestLoader().loadTestsFromTestCase(MemoryTestCase)
    ]

    print "\n---- Optional Subscription Tests ----"
    try:
        from amfast.remoting.gae_subscription_manager import GaeSubscriptionManager
    except Exception:
        # Skip if we're not in Gae environment.
        print "Skipping GAE test."
    else:
        print "Running GAE test."
        tests.append(unittest.TestLoader().loadTestsFromTestCase(GaeTestCase))

    try:
        import sqlalchemy as sa
        from amfast.remoting.sa_subscription_manager import SaSubscriptionManager
    except Exception:
        # Skip if SQLAlchemy is not installed.
        print "Skipping SA test."
    else:
        print "Running SA test."
        tests.append(unittest.TestLoader().loadTestsFromTestCase(SaTestCase))

    try:
        from amfast.remoting.memcache_subscription_manager import MemcacheSubscriptionManager

        # Check connection
        manager = MemcacheSubscriptionManager()
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
