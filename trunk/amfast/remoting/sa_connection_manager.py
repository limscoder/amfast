import time
import cPickle as pickle

import sqlalchemy as sa
from sqlalchemy.sql import func, and_

from connection import Connection
from connection_manager import NotConnectedError, ConnectionManager, SessionAttrError

class SaConnectionManager(ConnectionManager):
    """Manages connections in a database, uses SqlAlchemy to talk to the DB."""

    def __init__(self, engine, metadata, connection_class=Connection, connection_params=None):
        ConnectionManager.__init__(self, connection_class=connection_class,
            connection_params=connection_params)

        self.engine = engine
        self.metadata = metadata
        self.mapTables()

    def reset(self):
        db = self.getDb()
        db.execute(self.session_attrs.delete())
        db.execute(self.connections.delete())
        db.close()

    def mapTables(self):
        self.connections = sa.Table('connections', self.metadata,
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('channel_name', sa.String(128), nullable=False),
            sa.Column('timeout', sa.Float(), nullable=False),
            sa.Column('connected', sa.Boolean(), nullable=False),
            sa.Column('last_active', sa.Float(), nullable=False),
            sa.Column('last_polled', sa.Float(), nullable=False, default=0.0),
            sa.Column('authenticated', sa.Boolean(), nullable=False, default=False),
            sa.Column('flex_user', sa.String(128), nullable=True),
            sa.Column('notify_func_id', sa.Integer(), nullable=True)
        )

        self.session_attrs = sa.Table('session_attrs', self.metadata,
            sa.Column('connection_id', sa.String(36),
                sa.ForeignKey('connections.id'),
                primary_key=True, index=True),
            sa.Column('name', sa.String(128), primary_key=True),
            sa.Column('value', sa.Binary(), nullable=False)
        )

    def createTables(self):
       db = self.getDb()
       self.connections.create(db, checkfirst=True)
       self.session_attrs.create(db, checkfirst=True)
       db.close()

    def getDb(self):
        return self.engine.connect()

    def loadConnection(self, connection_id):
        s = sa.select([self.connections.c.channel_name, self.connections.c.timeout],
            self.connections.c.id==connection_id)
        db = self.getDb()
        result = db.execute(s)
        row = result.fetchone()
        db.close()

        if row is None:
            raise NotConnectedError("Connection '%s' is not connected." % connection_id)
        
        return self.connection_class(self, row[self.connections.c.channel_name],
            connection_id, row[self.connections.c.timeout])

    def initConnection(self, connection, channel):
        ins = self.connections.insert().values(
            id=connection.id,
            channel_name=connection.channel_name,
            timeout=connection.timeout,
            connected=True,
            last_active=time.time() * 1000,
            last_polled=0.0,
            authenticated=False,
        )

        db = self.getDb()
        db.execute(ins)
        db.close()

    def getConnectionCount(self, channel_name):
        s = sa.select([sa.sql.func.count(self.connections.c.id)])
        db = self.getDb()
        result = db.execute(s)
        row = result.fetchone()
        db.close()

        return row[0]

    def iterConnectionIds(self):
        s = sa.select([self.connections.c.id])
        db = self.getDb()
        result = db.execute(s)
        for row in result:
            yield row[self.connections.c.id]
        db.close()

    # --- proxies for connection properties --- #

    def getConnected(self, connection):
        s = sa.select([self.connections.c.connected], self.connections.c.id==connection.id)
        db = self.getDb()
        result = db.execute(s)
        row =result.fetchone()
        db.close()

        if row is None:
            return False

        return row[self.connections.c.connected]

    def getLastActive(self, connection):
        s = sa.select([self.connections.c.last_active], self.connections.c.id==connection.id)
        db = self.getDb()
        result = db.execute(s)
        row = result.fetchone()
        db.close()

        return row[self.connections.c.last_active]

    def getLastPolled(self, connection):
        s = sa.select([self.connections.c.last_polled], self.connections.c.id==connection.id)
        db = self.getDb()
        result = db.execute(s)
        row = result.fetchone()
        db.close()

        return row[self.connections.c.last_polled]

    def getAuthenticated(self, connection):
        s = sa.select([self.connections.c.authenticated], self.connections.c.id==connection.id)
        db = self.getDb()
        result = db.execute(s)
        row = result.fetchone()
        db.close()

        return row[self.connections.c.authenticated]

    def getFlexUser(self, connection):
        s = sa.select([self.connections.c.flex_user], self.connections.c.id==connection.id)
        db = self.getDb()
        result = db.execute(s)
        row = result.fetchone()
        db.close()

        return row[self.connections.c.flex_user]

    def getNotifyFunc(self, connection):
        s = sa.select([self.connections.c.notify_func_id], self.connections.c.id==connection.id)
        db = self.getDb()
        result = db.execute(s)
        row = result.fetchone()
        db.close()

        if row is None:
            return None

        notify_func_id = notify_func_id = row[self.connections.c.notify_func_id]
        if notify_func_id is None:
            return None

        return connection._getNotifyFuncById(notify_func_id)

    # --- proxies for connection methods --- #

    def deleteConnection(self, connection):
        d = self.connections.delete().\
            where(self.connections.c.id==connection.id)
        db = self.getDb()
        db.execute(d)
        db.close()

        ConnectionManager.deleteConnection(self, connection)

    def connectConnection(self, connection):
        u = self.connections.update().\
            where(self.connections.c.id==connection.id).\
            values(connected=True)
        db = self.getDb()
        db.execute(u)
        db.close()

    def disconnectConnection(self, connection):
        u = self.connections.update().\
            where(self.connections.c.id==connection.id).\
            values(connected=False)
        db = self.getDb()
        db.execute(u)
        db.close()

    def touchConnection(self, connection):
        u = self.connections.update().\
            where(self.connections.c.id==connection.id).\
            values(last_active=time.time() * 1000)
        db = self.getDb()
        db.execute(u)
        db.close()

    def touchPolled(self, connection):
        u = self.connections.update().\
            where(self.connections.c.id==connection.id).\
            values(last_polled=time.time() * 1000)
        db = self.getDb()
        db.execute(u)
        db.close()

    def authenticateConnection(self, connection, user):
        u = self.connections.update().\
            where(self.connections.c.id==connection.id).\
            values(authenticated=True, flex_user=user)
        db = self.getDb()
        db.execute(u)
        db.close()

    def unAuthenticateConnection(self, connection):
        u = self.connections.update().\
            where(self.connections.c.id==connection.id).\
            values(authenticated=False, flex_user=None)
        db = self.getDb()
        db.execute(u)
        db.close()

    def setNotifyFunc(self, connection, func):
        u = self.connections.update().\
            where(self.connections.c.id==connection.id).\
            values(notify_func_id=connection._setNotifyFunc(func))
        db = self.getDb()
        db.execute(u)
        db.close()

    def unSetNotifyFunc(self, connection):
        s = sa.select([self.connections.c.notify_func_id], self.connections.c.id==connection.id)
        db = self.getDb()
        result = db.execute(s)
        row = result.fetchone()

        if row is None:
            return

        connection._delNotifyFunc(row[self.connections.c.notify_func_id])

        u = self.connections.update().\
            where(self.connections.c.id==connection.id).\
            values(notify_func_id=None)
        db.execute(u)
        db.close()

    def getConnectionSessionAttr(self, connection, name):
        s = sa.select([self.session_attrs.c.value],
            and_(self.session_attrs.c.connection_id==connection.id,
                self.session_attrs.c.name==name))
        db = self.getDb()
        result = db.execute(s)
        row = result.fetchone()
        db.close()

        if row is None:
            raise SessionAttrError("Attribute '%s' not found." % name)

        return pickle.loads(str(row[self.session_attrs.c.value]))

    def setConnectionSessionAttr(self, connection, name, val):
        s = sa.select([self.session_attrs.c.connection_id],
            and_(self.session_attrs.c.connection_id==connection.id,
                self.session_attrs.c.name==name))
        db = self.getDb()
        result = db.execute(s)
        row = result.fetchone()
        
        if row is None: 
            statement = self.session_attrs.insert().values(
                connection_id=connection.id,
                name=name, value=pickle.dumps(val))
        else:
            statement = self.connections.update().\
                where(and_(self.session_attrs.c.connection_id==connection.id,
                    self.session_attrs.c.name==name)).\
                values(value=pickle.dumps(val))

        db.execute(statement)
        db.close()

    def delConnectionSessionAttr(self, connection, name):
        d = self.session_attrs.delete().\
            where(and_(self.session_attrs.c.connection_id==connection.id,
                self.session_attrs.c.name==name))

        db = self.getDb()
        db.execute(d)
        db.close()
