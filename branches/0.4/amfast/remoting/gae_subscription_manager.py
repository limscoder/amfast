import pickle

from google.appengine.ext import db

import amfast
from subscription_manager import Subscription, SubscriptionManager

class GaeSubscription(db.Model, Subscription):
    """A client's subscription to a topic, persisted in a Google Datastore."""

    # Prefix id with this string to make a key_name
    KEY = 'K'

    @classmethod
    def getKeyName(cls, connection_id, client_id, topic):
        return cls.KEY.join(('', connection_id, client_id, topic))

    connection_id = db.StringProperty(required=True)
    client_id = db.StringProperty(required=True)
    topic = db.StringProperty(required=True)

class GaeMessage(db.Model):
    """A Flex message, persisted in a Google Datastore."""

    p_message = db.BlobProperty(required=True)

class GaeSubscriptionManager(SubscriptionManager):
    """Stores subscriptions in Google DataStore."""

    def reset(self):
        query = GaeSubscription.all(keys_only=True)
        for result in query:
            db.delete(result)

        query = GaeMessage.all(keys_only=True)
        for result in query:
            db.delete(result)

    def subscribe(self, connection_id, client_id, topic, sub_topic=None, selector=None):
        """Add a subscription to a topic."""

        topic = SubscriptionManager.getTopicKey(topic, sub_topic)
        key_name = GaeSubscription.getKeyName(connection_id, client_id, topic)
        subscription = GaeSubscription(key_name=key_name,
            connection_id=connection_id, client_id=client_id, topic=topic)
        subscription.put()

    def unSubscribe(self, connection_id, client_id, topic, sub_topic=None):
        """Remove a subscription from a topic."""
        topic = SubscriptionManager.getTopicKey(topic, sub_topic)
        key_name = GaeSubscription.getKeyName(connection_id, client_id, topic)

        subscription = GaeSubscription.get_by_key_name(key_name)
        if subscription is not None:
            subscription.delete()

    def deleteConnection(self, connection):
        query = GaeSubscription.all()
        query.filter('connection_id = ', connection.id)
        db.delete(query)

    def persistMessage(self, msg):
        # Remove connection data,
        # so that it is not pickled
        tmp_connection = getattr(msg, 'connection', None)
        if tmp_connection is not None:
            msg.connection = None
       
        message = GaeMessage(p_message=pickle.dumps(msg))
        message.put()

        # Restore connection attr.
        if tmp_connection is not None:
            msg.connection = tmp_connection

    def iterConnectionSubscriptions(self, connection):
        """Iterate through all Subscriptions that belong to a specific connection."""

        query = GaeSubscription.all()
        query.filter('connection_id = ', connection.id)
        return query

    def iterSubscribers(self, topic, sub_topic=None):
        topic = SubscriptionManager.getTopicKey(topic, sub_topic)

        connection_ids = {} # Keep track of unique IDs.

        query = GaeSubscription.all()
        query.filter('topic = ', topic)
        for subscription in query:
            if subscription.connection_id in connection_ids:
                continue
            
            connection_ids[subscription.connection_id] = True
            yield subscription.connection_id

    def pollMessages(self, topic, cutoff_time, current_time):
        """Retrieves all qeued messages, and discards expired messages.

        arguments:
        ===========
         * topic - string, Topic to find messages for.
         * cutoff_time - float, epoch time, only messages published
             after this time will be returned.
         * current_time - float, epoch time, used to determine if a
             message is expired.
        """

        remove_msgs = []

        query = GaeMessage.all()
        for message in query:
            msg = pickle.loads(message.p_message)
            if current_time > (msg.timestamp + msg.timeToLive):
                # Remove expired message
                remove_msgs.append(message)
            else:
                if msg.timestamp > cutoff_time:
                    yield msg

        for message in remove_msgs:
            message.delete()
