"""ClassDef for dealing with classes mapped with SQLAlchemy."""

from amfast import class_def

# Import from different places depending on which 
# version of SA is being used.
try:
    from sqlalchemy.orm import class_mapper, object_mapper
except ImportError:
    from sqlalchemy.orm.util import class_mapper, object_mapper

# Exception is different depending on which
# version of SA is being used.
UnmappedInstanceError = None
try:
    class_mapper(dict)
except Exception, e:
    UnmappedInstanceError = e.__class__

class SaClassDef(class_def.ClassDef):
    """Defines how objects with a class mapped by SQLAlchemy should be serialized and de-serialized.

    Mapped attributes are considered static.
    Dynamic attributes are ignored.

    The class must be mapped with SQLAlchemy BEFORE calling class_def.map_class.
    """
    KEY_ATTR = 'sa_key' # sa key
    LAZY_ATTR = 'sa_lazy' # list of lazy attribute names

    def __init__(self, class_, alias=None, static_attrs=None, amf3=None):
        """Static attributes are inferred from the class mapper,
        so static_attrs needs to be passed only if there are additional
        un-mapped attributes that need to be considered static."""

        try:
            self.mapper = class_mapper(class_)
            self.mapper.compile()
        except UnmappedInstanceError:
            raise class_def.ClassDefError("Class does not have a SA mapper associated with it.")

        if static_attrs is None:
            static_attrs = ()

        combined_attrs = [self.KEY_ATTR, self.LAZY_ATTR]
        combined_attrs.extend(static_attrs)
        for prop in self.mapper.iterate_properties:
            if not prop.key in combined_attrs:
                combined_attrs.append(prop.key)

        class_def.ClassDef.__init__(self, class_, alias, tuple(combined_attrs), amf3)

    def getStaticAttrVals(self, obj):
        lazy_attrs = []
        vals = [self.mapper.primary_key_from_instance(obj), lazy_attrs]

        attr_count = len(self.static_attrs)
        for i in xrange(2, attr_count):
            attr = self.static_attrs[i]
 
            # Look at __dict__ directly,
            # otherwise SA will touch the attr
            # TODO: what about attrs defined in __slots__??
            if attr in obj.__dict__:
                vals.append(getattr(obj, attr))
            else:
                # This object is lazy
                vals.append(None)
                lazy_attrs.append(attr)

        return vals

    def getInstance(self):
        return self.mapper.class_manager.new_instance()

    def applyAttrVals(self, obj, vals):
        # Delete lazy-loaded attrs from vals
        if self.LAZY_ATTR in vals:
            for lazy_attr in vals[self.LAZY_ATTR]:
                if lazy_attr in vals:
                    del vals[lazy_attr]
            del vals[self.LAZY_ATTR]
            
        if self.KEY_ATTR in vals:
            del vals[self.KEY_ATTR]

        class_def.ClassDef.applyAttrVals(self, obj, vals)
