import pickle
import random
import time

from google.appengine.ext import db

from connection import Connection, ConnectionError
from connection_manager import ConnectionManager, NotConnectedError, SessionAttrError

class GaeConnection(Connection):
    """A connection stored in Google Datastore."""

    def __init__(self, *args, **kwargs):
        Connection.__init__(self, *args, **kwargs)
        self.model = None

class GaeConnectionLastActive(db.Model):
    value = db.FloatProperty(required=True)

class GaeConnectionConnected(db.Model):
    value = db.BooleanProperty(required=True)

class GaeConnectionLastPolled(db.Model):
    value = db.FloatProperty(required=True)

class GaeConnectionAuthentication(db.Model):
    authenticated = db.BooleanProperty(required=True)
    flex_user = db.StringProperty(required=False)

class GaeConnectionSession(db.Model):
    value = db.BlobProperty(required=True)

class GaeConnectionModel(db.Model):
    """Connection data that is stored in a Google Datastore."""

    # These values never change
    channel_name = db.StringProperty(required=True)
    timeout = db.IntegerProperty(required=True)

    # Every changeable property is it's own model,
    # So we can update each property
    # without affecting any other.

    # Referenced properties.
    last_active = db.ReferenceProperty(reference_class=GaeConnectionLastActive, required=True)
    connected = db.ReferenceProperty(reference_class=GaeConnectionConnected, required=True)
    last_polled = db.ReferenceProperty(reference_class=GaeConnectionLastPolled, required=True)
    authentication = db.ReferenceProperty(reference_class=GaeConnectionAuthentication, required=False)
    session = db.ReferenceProperty(reference_class=GaeConnectionSession, required=False)

class GaeChannelModel(db.Model):
    """Channel data that is stored in a Google Datastore."""

    # Shard counter into multiple entities to avoid conflicts.
    NUM_SHARDS = 20

    name = db.StringProperty(required=True)
    count = db.IntegerProperty(required=True)

class GaeConnectionManager(ConnectionManager):
    """Manages connections stored by Google DataStore.

    attributes
    =============
     * touch_time - int, minimum time in milliseconds between writes to 'last_active' field.
    """

    def __init__(self, connection_class=GaeConnection, connection_params=None, touch_time=10000):
        ConnectionManager.__init__(self, connection_class=connection_class,
            connection_params=connection_params)

        # Reduces number of writes to 'last_active' field.
        self.touch_time = touch_time

    def reset(self):
        query = GaeConnectionModel.all(keys_only=True)
        for result in query:
            db.delete(result)

        query = GaeConnectionLastActive.all(keys_only=True)
        for result in query:
            db.delete(result)

        query = GaeConnectionConnected.all(keys_only=True)
        for result in query:
            db.delete(result)

        query = GaeConnectionLastPolled.all(keys_only=True)
        for result in query:
            db.delete(result)

        query = GaeConnectionAuthentication.all(keys_only=True)
        for result in query:
            db.delete(result)

        query = GaeConnectionSession.all(keys_only=True)
        for result in query:
            db.delete(result)

        query = GaeChannelModel.all(keys_only=True)
        for result in query:
            db.delete(result)

    def _getChannelShardName(self, channel_name):
        index = random.randint(0, GaeChannelModel.NUM_SHARDS - 1)
        return ":".join((channel_name, str(index)))

    def _incrementChannelCount(self, channel_name):
        shard_name = self._getChannelShardName(channel_name)
        counter = GaeChannelModel.get_by_key_name(shard_name)
        if counter is None:
            counter = GaeChannelModel(key_name=shard_name,
                name=channel_name, count=0)
        counter.count += 1
        counter.put()

    def _decrementChannelCount(self, channel_name):
        shard_name = self._getChannelShardName(channel_name)
        counter = GaeChannelModel.get_by_key_name(shard_name)
        if counter is None:
            counter = GaeChannelModel(key_name=shard_name,
                name=channel_name, count=0)
        counter.count -= 1
        counter.put()

    def getConnectionCount(self, channel_name):
        query = GaeChannelModel.all()
        query.filter('name = ', channel_name)
        total = 0
        for result in query:
            total += result.count
        return total
 
    def loadConnection(self, connection_id):
        connection_model = GaeConnectionModel.get_by_key_name(connection_id)
        
        if connection_model is None:
            raise NotConnectedError("Connection '%s' is not connected." % connection_id)

        connection = self.connection_class(self, connection_model.channel_name,
            connection_id, timeout=connection_model.timeout)
        connection.model = connection_model
        return connection

    def initConnection(self, connection, channel):
        last_active = GaeConnectionLastActive(key_name=connection.id,
            value=(time.time() * 1000))
        last_active.put()

        connected = GaeConnectionConnected(key_name=connection.id, value=True)
        connected.put()

        last_polled = GaeConnectionLastPolled(key_name=connection.id, value=0.0)
        last_polled.put()

        params = {
            'key_name': connection.id,
            'channel_name': connection.channel_name,
            'timeout': connection.timeout,
            'connected': connected,
            'last_active': last_active,
            'last_polled': last_polled
        }

        connection_model = GaeConnectionModel(**params)
        connection_model.put()

        db.run_in_transaction(self._incrementChannelCount,
            connection.channel_name)

        connection.model = connection_model

    def iterConnectionIds(self):
        query = GaeConnectionModel.all(keys_only=True)
        for key in query:
            yield key.name()

    # --- proxies for connection properties --- #

    def getConnected(self, connection):
        if connection.model is None:
            return False
        else:
            return connection.model.connected.value

    def getLastActive(self, connection):
        return connection.model.last_active.value

    def getLastPolled(self, connection):
        return connection.model.last_polled.value

    def getAuthenticated(self, connection):
        if connection.model.authentication is None:
            return False
       
        return connection.model.authentication.authenticated

    def getFlexUser(self, connection):
        if connection.model.authentication is None:
            return None

        return connection.model.authentication.flex_user

    def getNotifyFunc(self, connection):
        return None

    # --- proxies for connection methods --- #

    def deleteConnection(self, connection):
        # Delete referenced properties 1st
        db.delete(GaeConnectionModel.last_active.get_value_for_datastore(connection.model))
        db.delete(GaeConnectionModel.connected.get_value_for_datastore(connection.model))
        db.delete(GaeConnectionModel.last_polled.get_value_for_datastore(connection.model))

        # Optional referenced properties
        authentication_key = GaeConnectionModel.authentication.get_value_for_datastore(connection.model)
        if authentication_key is not None:
            db.delete(authentication_key)

        session_key = GaeConnectionModel.session.get_value_for_datastore(connection.model)
        if session_key is not None:
            db.delete(session_key)

        # Delete connection
        connection.model.delete()
        connection.model = None
        ConnectionManager.deleteConnection(self, connection)

        db.run_in_transaction(self._decrementChannelCount, connection.channel_name)

    def connectConnection(self, connection):
        if connection.model is not None:
            connected = GaeConnectionConnected(key_name=connection.id, value=True)
            connected.put()
            connection.model.connected = connected

    def disconnectConnection(self, connection):
        if connection.model is not None:
            connected = GaeConnectionConnected(key_name=connection.id, value=False)
            connected.put()
            connection.model.connected = connected

    def touchConnection(self, connection):
        if connection.model is not None:
            now = time.time() * 1000
            diff = now - connection.model.last_active.value
            connection.model.last_active.value = now
            if diff > self.touch_time:
                # last_active value is only written periodically
                # to save time writing to data_store.
                connection.model.last_active.put()

    def touchPolled(self, connection):
        self.softTouchPolled(connection);
        if connection.model is not None:
            connection.model.last_polled.put()

    def softTouchPolled(self, connection):
        if connection.model is not None:
            connection.model.last_polled.value = time.time() * 1000

    def authenticateConnection(self, connection, user):
        if connection.model is not None:
            if connection.model.authentication is None:
                authentication = GaeConnectionAuthentication(
                    key_name=connection.id, authenticated=True, flex_user=user)
                authentication.put()
                connection.model.authentication = authentication
                connection.model.put()
            else:
                connection.model.authentication.authenticated = True
                connection.model.authentication.flex_user = user
                connection.model.authentication.authenticated.put()

    def unAuthenticateConnection(self, connection):
        if connection.model is not None:
            if connection.model.authentication is not None:
                connection.model.authentication.authenticated = False
                connection.model.authentication.flex_user = None
                connection.model.authentication.put()

    def initSession(self, connection):
        if connection.model is not None:
            if connection.model.session is None or \
                connection.model.session.value is None:
                connection._session = {}
            else:
                connection._session = pickle.loads(connection.model.session.value)

    def saveSession(self, connection):
        if connection.model is not None:
            value = pickle.dumps(connection._session)
            if connection.model.session is None:
                session = GaeConnectionSession(key_name=connection.id, value=value)
                session.put()
                connection.model.session = session
                connection.model.put()
            else:
                connection.model.session.value = value
                connection.model.session.put()

    def getConnectionSessionAttr(self, connection, name):
        self.initSession(connection)
        try:
            return connection._session[name]
        except KeyError:
            raise SessionAttrError("Attribute '%s' not found." % name)

    def setConnectionSessionAttr(self, connection, name, val):
        self.initSession(connection)
        connection._session[name] = val
        self.saveSession(connection)

    def delConnectionSessionAttr(self, connection, name):
        self.initSession(connection)
        try:
            del connection._session[name]
            self.saveSession(connection)
        except KeyError:
            pass
