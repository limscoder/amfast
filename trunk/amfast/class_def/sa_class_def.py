"""ClassDef for dealing with classes mapped with SQLAlchemy."""

from amfast import class_def
from amfast.class_def.as_types import AsNoProxy

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

    The class must be mapped with SQLAlchemy BEFORE calling ClassDefMapper.map_class().
    """
    KEY_ATTR = 'sa_key' # sa instance key
    LAZY_ATTR = 'sa_lazy' # list of lazy attribute names

    # Set to True to always encode
    # KEY_ATTR and LAZY_ATTR as Array objects.
    no_proxy_sa_attrs = True

    def __init__(self, class_, alias=None, static_attrs=None, amf3=None,
        encode_types=None, decode_types=None):
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
        self.unmapped_attrs = static_attrs

        self.mapped_attrs = []
        for prop in self.mapper.iterate_properties:
            self.mapped_attrs.append(prop.key)

        # Check for duplicates
        for attr in self.mapped_attrs:
            if attr in self.unmapped_attrs:
                raise class_def.ClassDefError("Mapped attributes cannot be listed in the static_attrs argument.")

        combined_attrs = [self.KEY_ATTR, self.LAZY_ATTR]
        combined_attrs.extend(self.mapped_attrs)
        combined_attrs.extend(self.unmapped_attrs)

        class_def.ClassDef.__init__(self, class_, alias=alias,
            static_attrs=combined_attrs, amf3=amf3, encode_types=encode_types,
            decode_types=decode_types)

    def getStaticAttrVals(self, obj):
        # Set key and lazy
        lazy_attrs = []
        
        if self.__class__.no_proxy_sa_attrs is True:
            vals = [AsNoProxy(self.mapper.primary_key_from_instance(obj)), AsNoProxy(lazy_attrs)]
        else:
            vals = [self.mapper.primary_key_from_instance(obj), lazy_attrs]

        # Set mapped values
        attr_count = len(self.mapped_attrs)
        for i in xrange(0, attr_count):
            attr = self.mapped_attrs[i]
 
            # Look at __dict__ directly,
            # otherwise SA will touch the attr.
            if attr in obj.__dict__:
                vals.append(getattr(obj, attr))
            else:
                # This attr is lazy
                vals.append(None)
                lazy_attrs.append(attr)

        # Set un-mapped values
        vals.extend([getattr(obj, attr, None) for attr in self.unmapped_attrs])

        return vals

    def getInstance(self):
        return self.mapper.class_manager.new_instance()

    def applyAttrVals(self, obj, vals):
        # Delete lazy-loaded attrs from vals
        if self.LAZY_ATTR in vals:
            lazy_attrs = vals[self.LAZY_ATTR]
            if lazy_attrs is not None:
                for lazy_attr in lazy_attrs:
                    if lazy_attr in vals:
                        del vals[lazy_attr]
            del vals[self.LAZY_ATTR]

        class_def.ClassDef.applyAttrVals(self, obj, vals)
