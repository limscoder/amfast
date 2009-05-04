import models
from persistent import Schema

class SAObject(object):
    """Handles common operations for persistent objects."""

    def getClassDefByAlias(self, alias):
        return self.class_def_mapper.getClassDefByAlias(alias)

#---- These operations are performed on a single object. ---#
    def load(self, class_alias, key):
        class_def = self.getClassDefByAlias(class_alias)
        session = Schema().session
        return session.query(class_def.class_).get(key)

    def loadAttr(self, class_alias, key, attr):
        obj = self.load(class_alias, key)
        return getattr(obj, attr)

    def save(self, obj):
        session = Schema().session
        merged_obj = session.merge(obj)
        session.commit()
        return merged_obj

    def saveAttr(self, class_alias, key, attr, val):
        obj = self.load(class_alias, key)
        setattr(obj, attr, val)
        session.commit()
        return getattr(obj, attr)

    def remove(self, class_alias, key):
        class_def = self.getClassDefByAlias(class_alias)
        session = Schema().session
        obj = session.query(class_def.class_).get(key)
        session.delete(obj)
        session.commit()

#---- These operations are performed on multiple objects. ----#
    def loadAll(self, class_alias):
        class_def = self.getClassDefByAlias(class_alias)
        session = Schema().session
        return session.query(class_def.class_).all()

    def saveList(self, objs):
        for obj in objs:
            self.save(obj)
        return objs

    def removeList(self, class_alias, keys):
        for key in keys:
            self.remove(class_alias, key)

    def insertDefaultData(self):
        user = models.User()
        user.first_name = 'Bill'
        user.last_name = 'Lumbergh'
        for label, email in {'personal': 'bill@yahoo.com', 'work': 'bill@initech.com'}.iteritems():
            email_obj = models.Email()
            email_obj.label = label
            email_obj.email = email
            user.emails.append(email_obj)

        for label, number in {'personal': '1-800-555-5555', 'work': '1-555-555-5555'}.iteritems():
            phone_obj = models.PhoneNumber()
            phone_obj.label = label
            phone_obj.number = number
            user.phone_numbers.append(phone_obj)

        session = Schema().session
        session.add(user)
        session.commit()

