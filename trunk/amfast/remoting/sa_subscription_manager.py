import time
import cPickle as pickle

import sqlalchemy as sa
from sqlalchemy.sql import func, and_

from subscription_manager import Subscription, SubscriptionManager
import flex_messages as messaging

class SaSubscriptionManager(SubscriptionManager):
    """Manages subscriptions in a database, uses SqlAlchemy to talk to the DB."""

    def __init__(self, engine, metadata, secure=False, ttl=30000):
        SubscriptionManager.__init__(self, secure=secure, ttl=ttl)

        self.engine = engine
        self.metadata = metadata
        self.mapTables()

    def reset(self):
        db = self.getDb()
        db.execute(self.subscriptions.delete())
        db.execute(self.messages.delete())
        db.close()

    def mapTables(self):
        self.subscriptions = sa.Table('subscriptions', self.metadata,
            sa.Column('connection_id', sa.String(36), primary_key=True),
            sa.Column('client_id', sa.String(36), primary_key=True),
            sa.Column('topic', sa.String(128), primary_key=True)
        )

        self.messages = sa.Table('messages', self.metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('topic', sa.String(256), index=True),
            sa.Column('clientId', sa.String(128), nullable=True),
            sa.Column('messageId', sa.String(128), nullable=True),
            sa.Column('correlationId', sa.String(128), nullable=True),
            sa.Column('destination', sa.String(128), nullable=True),
            sa.Column('timestamp', sa.Float(), nullable=True),
            sa.Column('timeToLive', sa.Float(), nullable=True),
            sa.Column('headers', sa.Binary(), nullable=True),
            sa.Column('body', sa.Binary(), nullable=False)
        )

    def createTables(self):
       db = self.getDb()
       self.subscriptions.create(db, checkfirst=True)
       self.messages.create(db, checkfirst=True)
       db.close()

    def getDb(self):
        return self.engine.connect()

    def subscribe(self, connection_id, client_id, topic, sub_topic=None, selector=None):
        """Subscribe a client to a topic.

        arguments
        ==========
         * connection_id - string, id of Flash client that is subscribing.
         * client_id - string, id of messaging client that is subscribing.
         * topic - string, Topic to subscribe to.
         * sub_topic - string, Sub-Topic to subscribe to. Default = None.
        """

        topic = self.getTopicKey(topic, sub_topic)

        ins = self.subscriptions.insert().values(
            connection_id=connection_id,
            client_id=client_id,
            topic=topic
        )

        db = self.getDb()
        db.execute(ins)
        db.close()

    def unSubscribe(self, connection_id, client_id, topic, sub_topic=None):
        """Un-Subscribe a client from a topic.

        arguments
        ==========
         * connection_id - string, id of Flash client that is subscribing.
         * client_id - string, id of messaging client that is subscribing.
         * topic - string, Topic to un-subscribe from.
         * sub_topic - string, Sub-Topic to un-subscribe from. Default = None.
        """

        topic = self.getTopicKey(topic, sub_topic)

        d = self.subscriptions.delete().\
            where(and_(self.subscriptions.c.connection_id==connection_id,
                self.subscriptions.c.client_id==client_id,
                self.subscriptions.c.topic==topic))
        db = self.getDb()
        db.execute(d)
        db.close()

    def deleteConnection(self, connection):
        """Remove all subscriptions for this connection.

        arguments
        ==========
         * connection_id - string, id of Flash client that is subscribing.
        """

        d = self.subscriptions.delete().\
            where(self.subscriptions.c.connection_id==connection.id)
        db = self.getDb()
        db.execute(d)
        db.close()

    def iterSubscribers(self, topic, sub_topic=None):
        """Iterate through Flash client ids subscribed to a specific topic."""

        topic = self.getTopicKey(topic, sub_topic)

        s = sa.select([self.subscriptions.c.connection_id],
            self.subscriptions.c.topic==topic, distinct=True)
        db = self.getDb()
        results = db.execute(s)
        for row in results:
            yield row[self.subscriptions.c.connection_id]

    def iterConnectionSubscriptions(self, connection):
        """Iterate through all Subscriptions that belong to a specific connection."""

        s = sa.select([self.subscriptions.c.connection_id,
            self.subscriptions.c.client_id, self.subscriptions.c.topic],
            self.subscriptions.c.connection_id==connection.id)
        db = self.getDb()
        results = db.execute(s)
        for row in results:
            yield Subscription(row[self.subscriptions.c.connection_id],
                row[self.subscriptions.c.client_id], row[self.subscriptions.c.topic])

    def persistMessage(self, msg):
        """Store a message."""

        if hasattr(msg, 'headers') and (msg.headers is not None):
            enc_headers = pickle.dumps(msg.headers)
        else:
            enc_headers = None

        if hasattr(msg, 'correlationId'):
            correlation_id = msg.correlationId
        else:
            correlation_id = None

        ins = self.messages.insert().values(
            topic=self.getMessageTopicKey(msg),
            clientId=msg.clientId,
            messageId=msg.messageId,
            correlationId=correlation_id,
            destination=msg.destination,
            timestamp=msg.timestamp,
            timeToLive=msg.timeToLive,
            headers=enc_headers,
            body=pickle.dumps(msg.body)
        )

        db = self.getDb()
        db.execute(ins)
        db.close()

    def deleteExpiredMessages(self, cutoff_time):
        """Deletes expired messages."""
        
	d = self.messages.delete().\
            where(self.messages.c.timestamp + self.messages.c.timeToLive < cutoff_time)

        db = self.getDb()
        db.execute(d)
        db.close()

    def pollMessages(self, topic, cutoff_time, current_time):
        """Retrieves all queued messages, and discards expired messages.

        arguments:
        ===========
         * topic - string, Topic to find messages for.
         * cutoff_time - float, epoch time, only messages published
             after this time will be returned.
         * current_time - float, epoch time, used to determine if a
             message is expired.
        """

        # Poll for new messages
        s = sa.select((self.messages,),
                and_(self.messages.c.topic == topic,
                    self.messages.c.timestamp > cutoff_time)).\
            order_by(self.messages.c.timestamp)

        db = self.getDb()
        results = db.execute(s)
        for row in results:
             if row['headers'] is None:
                 headers = None
             else:
                 headers = pickle.loads(str(row['headers']))

             yield messaging.AsyncMessage(body=pickle.loads(str(row['body'])),
                 clientId=row['clientId'], destination=row['destination'],
                 headers=headers, timeToLive=row['timeToLive'],
                 timestamp=row['timestamp'], messageId=row['messageId'])

        db.close()
