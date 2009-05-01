import sqlalchemy as sa

import models

class Schema(object):
    """Describes the schema and mappers used by the SQLAlchemy example."""
    engine = sa.create_engine('sqlite:///sqlalchemy_example.db', echo=False)

    def _get_session(self):
        return sa.orm.scoped_session(sa.orm.sessionmaker(bind=self.engine))
    session = property(_get_session)

    def createSchema(self):
        metadata = sa.MetaData()

        metadata = sa.MetaData()
        self.users_table = sa.Table('users_table', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('first_name', sa.String(50)),
            sa.Column('last_name', sa.String(50)))

        self.phone_numbers_table = sa.Table('phone_numbers_table', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('user_id', sa.Integer, sa.ForeignKey('users_table.id')),
            sa.Column('label', sa.String(50)),
            sa.Column('number', sa.String(50)))

        self.emails_table = sa.Table('emails_table', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('user_id', sa.Integer, sa.ForeignKey('users_table.id')),
            sa.Column('label', sa.String(50)),
            sa.Column('email', sa.String(50)))

        metadata.create_all(self.engine)

    def createMappers(self):
        sa.orm.clear_mappers()

        sa.orm.mapper(models.User, self.users_table, properties={
            'emails': sa.orm.relation(models.Email, lazy=False),
            'phone_numbers': sa.orm.relation(models.PhoneNumber, lazy=True)})
        sa.orm.mapper(models.Email, self.emails_table)
        sa.orm.mapper(models.PhoneNumber, self.phone_numbers_table)
