import pickle

from google.appengine.ext import db

import amfast
from subscription_manager import Subscription, SubscriptionManager

class GaeSubscription(db.Model, Subscription):
    """A client's subscription to a topic, persisted in a Google Datastore."""

    @classmethod
    def getKeyName(cls, connection_id, client_id, topic):
        return ':'.join((connection_id, client_id, topic))

    connection_id = db.StringProperty(required=True)
    client_id = db.StringProperty(required=True)
    topic = db.StringProperty(required=True)

class GaeMessageBody(db.Model):
    """Flex message body persisted in a Google Datastore."""

    p_message = db.BlobProperty(required=True)

class GaeMessageMetadata(db.Model):
    """Flex message metadata persisted in a Google Datastore."""

    time_to_live = db.FloatProperty(required=True)
    timestamp = db.FloatProperty(required=True)
    topic = db.StringProperty(required=True)
    message_body = db.ReferenceProperty(reference_class=GaeMessageBody, required=True)

class GaeSubscriptionManager(SubscriptionManager):
    """Stores subscriptions in Google DataStore."""

    def reset(self):
        query = GaeSubscription.all(keys_only=True)
        for result in query:
            db.delete(result)

        query = GaeMessageMetadata.all(keys_only=True)
        for result in query:
            db.delete(result)

        query = GaeMessageBody.all(keys_only=True)
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
        db.delete(subscription)

    def deleteConnection(self, connection):
        """Delete connection-subscription information."""

        query = GaeSubscription.all(keys_only=True)
        query.filter('connection_id = ', connection.id)
        db.delete(query)

    def persistMessage(self, msg):
        """Save message object."""

        # Remove connection data,
        # so that it is not pickled
        tmp_connection = getattr(msg, 'connection', None)
        if tmp_connection is not None:
            msg.connection = None

        message_body = GaeMessageBody(p_message=pickle.dumps(msg))
        message_body.put()
       
        message_data = GaeMessageMetadata(timestamp=msg.timestamp,
            time_to_live=float(msg.timeToLive), topic=self.getMessageTopicKey(msg),
            message_body=message_body)
        message_data.put()

        # Restore connection attr.
        if tmp_connection is not None:
            msg.connection = tmp_connection

    def iterConnectionSubscriptions(self, connection):
        """Iterate through all Subscriptions that belong to a specific connection."""

        query = GaeSubscription.all()
        query.filter('connection_id = ', connection.id)
        return query

    def iterSubscribers(self, topic, sub_topic=None):
        """Iterate through all connection ids subscribed to a topic."""

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

        query = GaeMessageMetadata.all()
        query.filter('topic = ', topic)
        query.filter('timestamp > ', cutoff_time)
        query.order('timestamp')
        for message_data in query:
            yield pickle.loads(message_data.message_body.p_message) 

    def deleteExpiredMessages(self, cutoff_time):
        query = GaeMessageMetadata.all(keys_only=True)
        query.filter('timestamp < ', cutoff_time)
        for result in query:
            db.delete(result)
