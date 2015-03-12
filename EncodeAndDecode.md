# Encoder and Decoder #



## Type Map ##
  * How types are mapped between Python and AMF

### Python -> AS3 ###

| Python | AS3 |
|:-------|:----|
| None | null |
| True | true |
| False | false |
| int | int |
| long, float | Number |
| str, unicode | String |
| dict | Object |
| list, tuple | Array |
| xml.dom.minidom.Document | XML, XMLDocument |
| datetime | Date |

### AS3 -> Python ###

| AS3 | Python |
|:----|:-------|
| null | None |
| undefined | None |
| true | True |
| false | False |
| int | int |
| Number | float |
| String | unicode |
| Object, MixedArray | dict |
| Array | list |
| XML, XMLDocument | xml.dom.minidom.Document |
| Date | datetime |


---


## Encoding ##
  * Use the amfast.encoder.Encoder class to encode objects.

### Encoder ###
  * amf3 - bool - True to encode as AMF3.
  * use\_collections - bool - True to encode lists and tuples as ArrayCollections.
  * use\_proxies - bool - True to encode dicts as ObjectProxies.
  * use\_references - bool - True to encode multiply occurring objects by reference.
  * use\_legacy\_xml - bool - True to encode XML as XMLDocument instead of e4x.
  * include\_private - bool - True to encode attributes starting with an underscore.
  * class\_def\_mapper - amfast.class\_def.ClassDefMapper - The object that retrieves ClassDef objects.
  * buffer - file-like-object - Output buffer. Set to None to output to a string.

```
from amfast.encoder import Encoder

# Encode an object to AMF0
encoder = Encoder(amf3=False)
encoded = encoder.encode(obj)

# Encode an object to AMF3
encoder = Encoder(amf3=True)
encoded = encoder.encode(obj)

# Encode an AMF Packet
encoded = encoder.encode_packet(packet_obj)

# If the 'buffer' attribute
# of the encoder is not set,
# the return value of 'encode'
# method is a string.
#
# If the 'buffer' attribute
# is set, the return value is
# the buffer object.
```


---


## Decoding ##
  * Use the amfast.decoder.Decoder class to decode objects.

### Decoder ###
  * amf3 - bool - True to decode as AMF3.
  * class\_def\_mapper - amfast.class\_def.ClassDefMapper - The object that retrieves ClassDef objects.

```
from amfast.decoder import Decoder

# Decode an object from AMF0
decoder = Decoder(amf3=False)
obj = decoder.decode(encoded)

# Decode an object from AMF3
decoder = Decoder(amf3=True)
obj = decoder.decode(encoded)

# Decode an AMF Packet
packet_obj = decoder.decode_packet(encoded)
```


---


## Custom Type Maps ##

  * AmFast supports user-defined object types.
  * Use a amfast.class\_def.ClassDef object to define how custom objects are serialized/deserialized.
  * Use a ClassDefMapper to map amfast.class\_def.ClassDef to an object alias.

```
from amfast import class_def

# ClassDefMapper objects keep track of ClassDefs
class_mapper = class_def.ClassDefMapper()

# Map a custom class with static attributes
class_mapper.mapClass(class_def.ClassDef(MyCustomClass, 'class.alias', ('tuple', 'of', 'static', 'attribute', 'names')))

# Object attributes can be automatically converted
# to/from a specific type with the
# encode_types and decode_types attributes.
#
# encode_types and decode_types are dictionaries where
# the keys are the names of the attributes to convert,
# and the values are functions that will perform the conversion.
mapped_class = class_def.ClassDef(MyCustomClass, 'class.alias'....
mapped_class.encode_types = {'attribute_to_convert_to_int_before_encoding': int}
mapped_class.decode_types = {'attribute_to_convert_to_int_after_decoding': int}

# Map a custom class with dynamic attributes
class_mapper.mapClass(class_def.DynamicClassDef(MyCustomClass, 'class.alias', ()))

# Map a custom class implementing IExternalizable
# ExternClassDef must be sub-classed, and the
# methods readExternal and writeExternal must be implemented.
class_mapper.mapClass(class_def.ExternClassDef(MyCustomClass,'class.alias'))

# Map a custom class that is also mapped with SQLAlchemy.
# Attributes mapped with SQLAlchemy will automatically be
# added to the list of static attributes.
class_mapper.mapClass(class_def.sa_class_def.SaClassDef(MyCustomClass, 'class.alias')

# Attach ClassDefMapper to Encoder and Decoder
# objects to use the ClassDefMapper for encoding
# and decoding
encoder.class_def_mapper = class_mapper
decoder.class_def_mapper = class_mapper

# Use custom class mappings with a Channel
channel = channel_set.getChannel('channel_name')
channel.endpoint.encoder.class_def_mapper = class_mapper
channel.endpoint.decoder.class_def_mapper = class_mapper
```