import time
import pickle

from google.appengine.ext import db

from connection import Connection
from connection_manager import ConnectionManager, NotConnectedError
from subscription_manager import SubscriptionManager
import flex_messages as messaging

class Subscription(db.Model):
    """A client's subscription to a topic, persisted in a Google Datastore."""

    connection_id = db.StringProperty(required=True)
    client_id = db.StringProperty(required=True)
    topic = db.StringProperty(required=True)
    message_keys = db.ListProperty(db.Key, required=True)

class GaeMessage(db.Model):
    """A Flex message, persisted in a Google Datastore."""

    p_message = db.BlobProperty(required=True)

class GaeConnection(db.Model, Connection):
    """A connection that is persisted in a Google Datastore."""

    _id = db.StringProperty(required=True)
    _channel_name = db.StringProperty(required=True)
    _timeout = db.IntegerProperty(required=True)
    _connected = db.BooleanProperty(required=True)
    _last_active = db.FloatProperty(required=True)
    _authenticated = db.BooleanProperty(required=True)
    _flex_user = db.StringProperty(required=False)

class GaeConnectionManager(ConnectionManager):
    """Manages connections stored by Google DataStore."""

    # Prefix id with this string to make a key_name
    KEY = 'K'

    def __init__(self, connection_class=GaeConnection, connection_params=None):
        ConnectionManager.__init__(self, connection_class=connection_class,
            connection_params=connection_params)

    def getKeyName(self, id):
        return self.KEY + id

    def getIdFromKey(self, key_name):
        return key_name.replace(self.KEY, '', 1)

    def getSubscriptionKey(self, connection_id, client_id, topic):
        return self.KEY.join(('', connection_id, client_id, topic))

    def loadConnection(self, connection_id):
        connection = GaeConnection.get_by_key_name(self.getKeyName(connection_id))
        
        if connection is None:
            raise NotConnectedError("Connection '%s' is not connected." % connection_id)

        connection._manager = self
        return connection
        
    def createConnection(self, channel, connection_id=None):
        if connection_id is None:
            connection_id = self.generateId()

        defaults = {
            'key_name': self.getKeyName(connection_id),
            '_id': connection_id,
            '_channel_name': channel.name,
            '_timeout': 1800,
            '_connected': True,
            '_last_active': time.time(),
            '_authenticated': False
        }

        defaults.update(self.connection_params)

        connection = self.connection_class(**defaults)
        connection._manager = self
        connection.put()
        return connection

    def deleteConnection(self, connection):
        connection.delete()
        ConnectionManager.deleteConnection(self, connection)

    def getConnectionIds(self):
        query = GaeConnection.all(keys_only=True)
        for key in query:
            yield self.getIdFromKey(key.name())

    def touchConnection(self, connection):
        connection._last_active = time.time()
        connection.put()

    def subscribeConnection(self, connection, client_id, topic, sub_topic=None):
        """Add a subscription to a topic."""

        topic = SubscriptionManager.getTopicKey(topic, sub_topic)
        key_name = self.getSubscriptionKey(connection.id, client_id, topic)
        subscription = Subscription(key_name=key_name,
            connection_id=connection.id, client_id=client_id,
            topic=topic, message_keys=[])
        subscription.put()

    def unSubscribeConnection(self, connection, client_id, topic, sub_topic=None):
        """Remove a subscription from a topic."""
        topic = SubscriptionManager.getTopicKey(topic, sub_topic)
        key_name = self.getSubscriptionKey(connection.id, client_id, topic)
        subscription = Subscription.get_by_key_name(key_name)

        if subscription is not None:
            subscription.delete()

    def getSubscribedTopics(self, connection):
        """Returns a list of topics that the connection is subscribed to."""

        query = Subscription.all()
        query.filter('connection_id = ', connection.id)
        topics = {}
        for subscription in query:
            if subscription.topic in topics:
                continue

            topics[subscription.topic] = True
            yield subscription.topic

    def getSubscribedClients(self, connection, topic, sub_topic=None):
        topic = SubscriptionManager.getTopicKey(topic, sub_topic)

        query = Subscription.all()
        query.filter('connection_id = ', connection.id)
        query.filter('topic = ', topic)
        for subscription in query:
            yield subscription.topic

    def publishToConnection(self, connection, msg):
        """Publish a message to a connection."""

        topic = msg.destination
        if hasattr(msg, 'headers') and \
            msg.headers is not None and \
            messaging.AsyncMessage.SUBTOPIC_HEADER in msg.headers:
            sub_topic = msg.headers[messaging.AsyncMessage.SUBTOPIC_HEADER]
        else:
            sub_topic = None

        topic = SubscriptionManager.getTopicKey(topic, sub_topic)

        # TODO: This is ugly!!
        # Make sure message has already been inserted into the DB.
        key_name = self.getKeyName(msg.messageId)
        message = GaeMessage.get_by_key_name(key_name)
        if message is None:
            # Message needs to be inserted 1st.
            p_message = pickle.dumps(msg)
            message = GaeMessage(p_message=p_message)
            message.put()
        message_key = message.key()

        query = Subscription.all()
        query.filter('connection_id = ', connection.id)
        query.filter('topic = ', topic)
        for subscription in query:
            subscription.message_keys.append(message_key)
        subscription.put()

    def pollConnection(self, connection):
        """Returns a list of messages, and clears message qeue."""
        polled_messages = []

        query = Subscription.all()
        query.filter('connection_id = ', connection.id)
        for subscription in query:
            for message_key in subscription.message_keys:
                message = GaeMessage.get(message_key)
                polled_messages.append(connection.personalizeMessage(
                    subscription.client_id, pickle.loads(message.p_message)))
            subscription.message_keys = []
            subscription.put()

        return polled_messages

    def authenticateConnection(self, connection, user):
        connection._authenticated = True
        connection._flex_user = user
        connection.put()

    def unAuthenticateConnection(self, connection):
        connection._authenticated = False
        connection._flex_user = None
        connection.put()

    def getConnectionSessionAttr(self, connection, name):
        return connection._session[name]

    def setConnectionSessionAttr(self, connection, name, val):
        connection._session[name] = val

    def delSessionAttr(self, connection, name):
        del connection._session[name]
