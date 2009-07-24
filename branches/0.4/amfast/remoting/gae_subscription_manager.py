from google.appengine.ext import db

from gae_connection_manager import Subscription
from subscription_manager import SubscriptionManager

class GaeSubscriptionManager(SubscriptionManager):
    """Stores subscriptions in Google DataStore."""

    def subscribe(self, connection_id, topic, sub_topic=None, selector=None):
        pass

    def unSubscribe(self, connection_id, topic, sub_topic=None):
        pass

    def getSubscribers(self, topic, sub_topic=None):
        """Iterate through all subscribers of a topic."""

        topic = self.getTopicKey(topic, sub_topic)
        query = Subscription.all()
        query.filter('topic = ', topic)
        connection_ids = {}
        for subscription in query:
            if subscription.connection_id in connection_ids:
                continue

            connection_ids[subscription.connection_id] = True
            yield subscription.connection_id
