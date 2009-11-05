#include <Python.h>

#include "amf.h"
#include "context.h"

// ------------------------ DECLARATIONS --------------------------------- //

// ---- GLOBALS
static PyObject *xml_dom_mod;
static PyObject *amfast_mod;
static PyObject *context_mod;
static PyObject *remoting_mod;
static PyObject *as_types_mod;
static PyObject *amfast_Error;
static PyObject *amfast_DecodeError;
static int big_endian; // Flag == 1 if architecture is big_endian, == 0 if not

/*
 * deserialize... functions de-reference and decode.
 * decode... functions decode from AMF to Python.
 *
 * functions starting with '_' return a C value.
 */

// COMMON
static int _decode_ushort(DecoderObj *context, unsigned short *val);
static int _decode_ulong(DecoderObj *context, unsigned int *val);
static int _decode_double(DecoderObj *context, double *val);
static PyObject* decode_double(DecoderObj *context);
static PyObject* decode_string(DecoderObj *context, unsigned int string_size);
static PyObject* decode_date(DecoderObj *context);
static PyObject* decode_packet(DecoderObj *context);
static PyObject* xml_from_string(PyObject *xml_string);
static PyObject* byte_array_from_string(PyObject *byte_string);
static PyObject* class_def_from_alias(DecoderObj *context, PyObject *alias);

// AMF0
static PyObject* decode_AMF0(DecoderObj *context);
static PyObject* decode_bool_AMF0(DecoderObj *context);
static PyObject* decode_string_AMF0(DecoderObj *context);
static PyObject* decode_long_string_AMF0(DecoderObj *context);
static PyObject* decode_reference_AMF0(DecoderObj *context);
static PyObject* decode_dict_AMF0(DecoderObj *context);
static int decode_dynamic_dict_AMF0(DecoderObj *context, PyObject *dict);
static PyObject* decode_array_AMF0(DecoderObj *context, short map_reference);
static PyObject* decode_date_AMF0(DecoderObj *context);
static PyObject* decode_xml_AMF0(DecoderObj *context);
static PyObject* decode_typed_obj_AMF0(DecoderObj *context);
static PyObject* decode_headers_AMF0(DecoderObj *context);
static PyObject* decode_messages_AMF0(DecoderObj *context);

// AMF3
static PyObject* decode_reference_AMF3(DecoderObj *context, PyObject *obj_context, int val);
static int decode_dynamic_dict_AMF3(DecoderObj *context, PyObject *dict);
static PyObject* decode_int_AMF3(DecoderObj *context);
static int _decode_int_AMF3(DecoderObj *context, int *val);
static PyObject* deserialize_string_AMF3(DecoderObj *context);
static PyObject* deserialize_array_AMF3(DecoderObj *context, int collection);
static int decode_dynamic_array_AMF3(DecoderObj *context, PyObject *list_val, int array_len, int dict);
static PyObject* deserialize_xml_AMF3(DecoderObj *context);
static PyObject* deserialize_byte_array_AMF3(DecoderObj *context);
static PyObject* decode_byte_array_AMF3(DecoderObj *context, int byte_len);
static PyObject* deserialize_obj_AMF3(DecoderObj *context, int proxy);
static PyObject* deserialize_class_def_AMF3(DecoderObj *context, int header);
static PyObject* decode_class_def_AMF3(DecoderObj *context, int header);
static int decode_typed_obj_AMF3(DecoderObj *context, PyObject *obj_val, PyObject *class_def_dict);
static int decode_externalizable_AMF3(DecoderObj *context, PyObject *obj_val, PyObject *class_def);
static PyObject* decode_obj_attrs_AMF3(DecoderObj *context, PyObject *class_def_dict);
static int decode_anon_obj_AMF3(DecoderObj *context, PyObject *obj_val, PyObject *class_def_dict);
static PyObject* decode_AMF3(DecoderObj *context);

// Python EXPOSED FUNCTIONS
static PyObject* py_decode(PyObject *self, PyObject *args, PyObject *kwargs);
static PyObject* py_decode_packet(PyObject *self, PyObject *args, PyObject *kwargs);

/*
 * Deserialize an obj.
 *
 * proxy is flag indicating that the obj being deserialized is within an ObjectProxy
 */
static PyObject* deserialize_obj_AMF3(DecoderObj *context, int proxy)
{
    int header;
    int *header_p = &header;
    if(!_decode_int_AMF3(context, header_p))
        return NULL;

    // Check for obj reference
    PyObject *obj_val = decode_reference_AMF3(context, context->obj_refs, header);
    if (obj_val == NULL)
        return NULL;

    if (obj_val != Py_False) {
        // Ref found
        if (proxy) {
            // Map ObjectProxy idx to ref, since
            // it points to the same obj.
            if (Idx_map((IdxObj*)context->obj_refs, obj_val) == -1) {
                Py_DECREF(obj_val);
                return NULL;
            }
        }
        return obj_val;
    } else {
        Py_DECREF(obj_val);
    }

    // Ref not found
    // Create instance based on class def
    // class_def_dict ref belongs to the context
    PyObject *class_def_dict = deserialize_class_def_AMF3(context, header);
    if (class_def_dict == NULL)
        return NULL;

    PyObject *class_def = PyDict_GetItemString(class_def_dict, "class_def");
    if (class_def == NULL)
        return NULL;

    int obj_type; // 0 = anonymous, 1 == externalizable, 2 == typed
    if (class_def == Py_None) {
        // Anonymous obj.
        obj_type = 0;
    } else if (PyObject_HasAttrString(class_def, "EXTERNALIZABLE_CLASS_DEF")) {
        // Check for special Proxy types
        if (PyObject_HasAttrString(class_def, "ARRAY_COLLECTION_CLASS_DEF")) {
            if (Decoder_skipBytes(context, 1) == 0) // Skip array type marker
                return NULL;
            return deserialize_array_AMF3(context, 1);
        }

        if (PyObject_HasAttrString(class_def, "OBJECT_PROXY_CLASS_DEF")) {
            if (Decoder_skipBytes(context, 1) == 0) // Skip object type marker
                return NULL;
            return deserialize_obj_AMF3(context, 1);
        }

        obj_type = 1;
    } else {
        obj_type = 2;
    }

    // Instantiate new obj
    if (obj_type == 0) {
        // Anonymous obj == dict
        obj_val = PyDict_New();
    } else {
        // Create obj_val for all typed objs.
        obj_val = PyObject_CallMethod(class_def, "getInstance", NULL);
    }
    
    if (!obj_val)
        return NULL;

    // Reference must be added before children (to allow for recursion).
    if (Idx_map((IdxObj*)context->obj_refs, obj_val) == -1) {
        Py_DECREF(obj_val);
        return NULL;
    }

    // If this is an ObjectProxy,
    // we need to add another reference,
    // so there is one that
    // points to the obj and one that points
    // to the proxy.
    if (proxy) {
        if (Idx_map((IdxObj*)context->obj_refs, obj_val) == -1) {
            Py_DECREF(obj_val);
            return NULL;
        }
    }

    int result = 0;
    if (obj_type == 0) {
        result = decode_anon_obj_AMF3(context, obj_val, class_def_dict);
    } else if (obj_type == 1) {
        result = decode_externalizable_AMF3(context, obj_val, class_def);
    } else if (obj_type == 2) {
        result = decode_typed_obj_AMF3(context, obj_val, class_def_dict);
    }

    if (result == 0) {
        Py_DECREF(obj_val);
        return NULL;
    }

    return obj_val;
}

/* Decode an anonymous obj. */
static int decode_anon_obj_AMF3(DecoderObj *context, PyObject *obj_val, PyObject *class_def_dict)
{
    // We're using merge instead of populating the dict
    // directly, because we have to setup a reference to the 
    // object before decoding it.
    PyObject *decoded_attrs = decode_obj_attrs_AMF3(context, class_def_dict);
    if (!decoded_attrs) {
        return 0;
    }

    int result = PyDict_Merge(obj_val, decoded_attrs, 1);
    Py_DECREF(decoded_attrs);
    if (result == -1)
        return 0;
    return 1;
}

/* Returns a dict with vals from an obj. */
static PyObject* decode_obj_attrs_AMF3(DecoderObj *context, PyObject *class_def_dict)
{
    // Put decoded attributes in this dict
    PyObject *decoded_attrs = PyDict_New();

    // Decode static attrs
    PyObject *static_attrs = PyDict_GetItemString(class_def_dict, "static_attrs");
    if (!static_attrs) {
        Py_DECREF(decoded_attrs);
        return NULL;
    }

    Py_ssize_t static_attr_len = PyTuple_GET_SIZE(static_attrs);
    int i;
    for (i = 0; i < static_attr_len; i++) {
        PyObject *obj = decode_AMF3(context);
        if (obj == NULL) {
            Py_DECREF(decoded_attrs);
            return NULL;
        }

        PyObject *attr_name = PyTuple_GET_ITEM(static_attrs, i); // Borrowed ref
        if (attr_name == NULL) {
            Py_DECREF(obj);
            Py_DECREF(decoded_attrs);
            return NULL;
        }

        int result = PyDict_SetItem(decoded_attrs, attr_name, obj);
        Py_DECREF(obj);

        if (result == -1) {
            Py_DECREF(decoded_attrs);
            return NULL;
        }
    }

    // Decode dynamic attrs
    PyObject *dynamic = PyDict_GetItemString(class_def_dict, "dynamic");
    if (dynamic == NULL)
        return NULL;

    if (dynamic == Py_True) {
        if (decode_dynamic_dict_AMF3(context, decoded_attrs) == 0) {
            Py_DECREF(decoded_attrs);
            return NULL;
        }
    }
    return decoded_attrs;
}

/* Decode a typed obj. */
static int decode_typed_obj_AMF3(DecoderObj *context, PyObject *obj_val, PyObject *class_def_dict)
{
    PyObject *decoded_attrs = decode_obj_attrs_AMF3(context, class_def_dict);
    if (!decoded_attrs) {
        return 0;
    }

    PyObject *class_def = PyDict_GetItemString(class_def_dict, "class_def");
    if (!class_def) {
        Py_DECREF(decoded_attrs);
        return 0;
    }

    int result = type_dict(class_def, context->type_map, decoded_attrs, 1);
    if (result == 0) {
        Py_DECREF(decoded_attrs);
        return 0;
    }

    PyObject *return_val = PyObject_CallMethodObjArgs(class_def, context->apply_name,
        obj_val, decoded_attrs, NULL);
    Py_DECREF(decoded_attrs);

    if (!return_val)
        return 0;

    Py_DECREF(return_val); // should be Py_None
    return 1;
}

/* Decode an EXTERNALIZABLE obj. */
static int decode_externalizable_AMF3(DecoderObj *context, PyObject *obj_val, PyObject *class_def)
{
    PyObject *result = PyObject_CallMethodObjArgs(class_def, context->extern_name,
        obj_val, context, NULL);
    if (result == NULL)
        return 0;

    Py_DECREF(result); // should by Py_None
    return 1;
}

/*
 * Deserialize a ClassDef.
 *
 * header argument is the parsed obj header.
 */
static PyObject* deserialize_class_def_AMF3(DecoderObj *context, int header)
{
    PyObject *class_def_dict = decode_reference_AMF3(context, context->class_refs, header >> 1);
    if (!class_def_dict)
        return NULL;

    if (class_def_dict != Py_False) {
        return class_def_dict;
    } else {
        Py_DECREF(class_def_dict);
    }

    class_def_dict = decode_class_def_AMF3(context, header);
    if (!class_def_dict)
        return NULL;

    // Add reference to obj
    if (Idx_map((IdxObj*)context->class_refs, class_def_dict) == -1)
        return NULL;
    // Give class_def_dict ref to context,
    // because it should be DECREFed when
    // the context is destroyed
    Py_DECREF(class_def_dict);

    return class_def_dict;
}

/*
 * Decode a ClassDef.
 *
 * Header argument is the obj header.
 */
static PyObject* decode_class_def_AMF3(DecoderObj *context, int header)
{
    PyObject *alias = deserialize_string_AMF3(context);
    if (!alias)
        return NULL;

    PyObject *class_def = class_def_from_alias(context, alias);
    if (!class_def) {
        Py_DECREF(alias);
        return NULL;
    }

    // Create a dict with class def information
    // specific to this decode context.
    PyObject *class_def_dict = PyDict_New();
    if (!class_def_dict) {
        Py_DECREF(alias);
        Py_DECREF(class_def);
        return NULL;
    }

    if (PyDict_SetItemString(class_def_dict, "class_def", class_def) == -1) {
        Py_DECREF(alias);
        Py_DECREF(class_def);
        Py_DECREF(class_def_dict);
        return NULL;
    }

    if (PyObject_HasAttrString(class_def, "EXTERNALIZABLE_CLASS_DEF") == 1) {
        // There is nothing else we need to do
        // with externalizable ClassDefs
        Py_DECREF(alias);
        Py_DECREF(class_def); // class_def_dict has reference now.
        return class_def_dict;
    }
    Py_DECREF(class_def); // class_def_dict has reference now.

    if ((header & 0x07FFFFFF) == EXTERNALIZABLE) {
        // If the class is externalizable, but the ClassDef isn't,
        // we have a big problem, because we don't know how to read
        // the raw bytes.
        Py_DECREF(class_def_dict);

        Py_DECREF(alias);        
        PyErr_SetString(amfast_DecodeError, "Encoded class is externalizable, but ClassDef is not.");
        return NULL;
    }
    Py_DECREF(alias); // We were only keeping this around to use in the externalizable error message.

    // Set dynamic flag
    if ((header & DYNAMIC) == DYNAMIC) {
        if (PyDict_SetItemString(class_def_dict, "dynamic", Py_True) == -1) {
            Py_DECREF(class_def_dict);
            return NULL;
        }
    } else {
        if (PyDict_SetItemString(class_def_dict, "dynamic", Py_False) == -1) {
            Py_DECREF(class_def_dict);
            return NULL;
        }
    }

    // Decode static attr names
    int static_attr_len = (int)(header >> 4);

    PyObject *decoded_attrs = PyTuple_New(static_attr_len);
    if (!decoded_attrs) {
        Py_DECREF(class_def_dict);
        return NULL;
    }

    int i;
    for (i = 0; i < static_attr_len; i++) {
        PyObject *attr_name = deserialize_string_AMF3(context);
        if (!attr_name) {
            Py_DECREF(class_def_dict);
            Py_DECREF(decoded_attrs);
            return NULL;
        }

        // steals ref to attr_name
        if (PyTuple_SetItem(decoded_attrs, i, attr_name) != 0) {
            Py_DECREF(class_def_dict);
            Py_DECREF(decoded_attrs);
            return NULL;
        }
    }

    // Set decoded attrs onto ClassDef
    int result = PyDict_SetItemString(class_def_dict, "static_attrs", decoded_attrs);
    Py_DECREF(decoded_attrs);
    if (result == -1) {
        Py_DECREF(class_def_dict);
        return NULL;
    }

    return class_def_dict;
}

/* Retrieve a ClassDef from a class alias string. */
static PyObject* class_def_from_alias(DecoderObj *context, PyObject *alias)
{
    // Check for empty string (anonymous obj)
    if (PyUnicode_GET_SIZE(alias) == 0) {
        Py_RETURN_NONE;
    }

    return PyObject_CallMethodObjArgs(context->class_mapper,
        context->class_def_name, alias, NULL);
}

/* Add the dynamic attributes of an encoded obj to a dict. */
static int decode_dynamic_dict_AMF3(DecoderObj *context, PyObject *dict)
{
    while (1) {
        PyObject *key = deserialize_string_AMF3(context);
        if (!key)
            return 0;

        if (PyUnicode_GET_SIZE(key) == 0) {
            // Empty string marks end of name/value pairs
            Py_DECREF(key);
            return 1;
        }

        PyObject *val = decode_AMF3(context);
        if (!val) {
            Py_DECREF(key);
            return 0;
        }

        if (PyDict_SetItem(dict, key, val) != 0) {
            Py_DECREF(key);
            Py_DECREF(val);
            return 0;
        }

        Py_DECREF(key);
        Py_DECREF(val);
    }
}

/*
 * Deserialize an array.
 * collection argument is a flag if this array is an array collection.
 */
static PyObject* deserialize_array_AMF3(DecoderObj *context, int collection)
{
    int header;
    int *header_p = &header;
    if(!_decode_int_AMF3(context, header_p))
        return NULL;

    // Check for reference
    PyObject *list_val = decode_reference_AMF3(context, context->obj_refs, header);
    if (!list_val)
        return NULL;

    if (list_val != Py_False) {
        // Ref found
        if (collection) {
            // Map ArrayCollection idx to ref, since
            // it points to the same list.
            if (Idx_map((IdxObj*)context->obj_refs, list_val) == -1) {
                Py_DECREF(list_val);
                return NULL;
            }
        }
        return list_val;
    } else {
        Py_DECREF(Py_False);
    }

    int array_len = (int)(header >> 1);
    // Can't use array_len to create a list of known
    // length, see ticket #46

    // Determine if array is mixed (associative) or not
    int mixed = 0;
    char *byte_ref = Decoder_readByte(context);
    if (byte_ref == NULL)
        return NULL;
    if (byte_ref[0] == EMPTY_STRING_TYPE) {
        // Dense array
        list_val = PyList_New(0);
    } else {
        if (!Decoder_skipBytes(context, -1))
            return NULL;

        list_val = PyDict_New();
        if (list_val == NULL)
            return NULL;
        
        // Get rest of dict
        if (decode_dynamic_dict_AMF3(context, list_val) == 0) {
            Py_DECREF(list_val);
            return NULL;
        }

        mixed = 1;
    }

    // Reference must be added before children (to allow for recursion).
    if (Idx_map((IdxObj*)context->obj_refs, list_val) == -1) {
        Py_DECREF(list_val);
        return NULL;
    }

    // If this is an ArrayCollection,
    // we need to add another reference,
    // so there is one that
    // points to the array and one that points
    // to the collection.
    if (collection) {
        if (Idx_map((IdxObj*)context->obj_refs, list_val) == -1) {
            Py_DECREF(list_val);
            return NULL;
        }
    }

    // Populate list
    if (decode_dynamic_array_AMF3(context, list_val, array_len, mixed) == 0) {
        Py_DECREF(list_val);
        return NULL;
    }

    return list_val;
}

/* Populate an array with vals from the buffer. */
static int decode_dynamic_array_AMF3(DecoderObj *context, PyObject *list_val, int array_len, int dict)
{
    int i;
    if (dict) {
        // Object is a dict, set item index as key.
        for (i = 0; i < array_len; i++) {
            PyObject *val = decode_AMF3(context);
            if (!val)
                return 0;

            PyObject *key = PyInt_FromLong((long)i);
            if (!key) {
               Py_DECREF(val);
               return 0;
            }

            int result = PyDict_SetItem(list_val, key, val);
            Py_DECREF(val);
            Py_DECREF(key);
            if (result == -1)
                return 0;
        }
    } else {
        // Standard array.
        for (i = 0; i < array_len; i++) {
            PyObject *val = decode_AMF3(context);
            if (!val)
                return 0;

            int result = PyList_Append(list_val, val);
            Py_DECREF(val);
            if (result < 0)
                return 0;
        }
    }

    return 1;
}

/* Deserialize date. */
static PyObject* deserialize_date(DecoderObj *context)
{
    int header;
    int *header_p = &header;
    if(!_decode_int_AMF3(context, header_p))
        return NULL;

    // Check for reference
    PyObject *date_val = decode_reference_AMF3(context, context->obj_refs, header);
    if (!date_val)
        return NULL;

    if (date_val != Py_False) {
        return date_val;
    } else {
        Py_DECREF(Py_False);
    }

    date_val = decode_date(context);
    if (!date_val)
        return NULL;

    // Add reference
    if (Idx_map((IdxObj*)context->obj_refs, date_val) == -1) {
        Py_DECREF(date_val);
        return NULL;
    }

    return date_val;
}

/* Decode a date. */
static PyObject* decode_date(DecoderObj *context)
{
    double epoch_millisecs;
    double *epoch_p = &epoch_millisecs;
    if(!_decode_double(context, epoch_p))
        return NULL;

    PyObject *epoch_float = PyFloat_FromDouble(epoch_millisecs / 1000);
    if (!epoch_float)
        return NULL;

    PyObject *func = PyObject_GetAttrString(amfast_mod, "date_from_epoch");
    if (!func) {
        Py_DECREF(epoch_float);
        return NULL;
    }

    PyObject *date_time = PyObject_CallFunctionObjArgs(func, epoch_float, NULL);
    Py_DECREF(func);
    Py_DECREF(epoch_float);
    return date_time;
}

/* Deserialize a byte array. */
static PyObject* deserialize_byte_array_AMF3(DecoderObj *context)
{
    int header;
    int *header_p = &header;
    if(!_decode_int_AMF3(context, header_p))
        return NULL;

    // Check for reference
    PyObject *byte_array_val = decode_reference_AMF3(context, context->obj_refs, header);
    if (!byte_array_val)
        return NULL;

    if (byte_array_val != Py_False) {
        return byte_array_val;
    } else {
        Py_DECREF(Py_False);
    }

    byte_array_val = decode_byte_array_AMF3(context, header >> 1);
    if (!byte_array_val)
        return NULL;
    
    // Add reference
    if (Idx_map((IdxObj*)context->obj_refs, byte_array_val) == -1) {
        Py_DECREF(byte_array_val);
        return NULL;
    }

    return byte_array_val;
}

/* Decode a byte array. */
static PyObject* decode_byte_array_AMF3(DecoderObj *context, int byte_len)
{
    PyObject *byte_array_val;
    PyObject *str_val = Decoder_readPyString(context, (long)byte_len);
    if (!str_val)
        return NULL;

    byte_array_val = byte_array_from_string(str_val);

    return byte_array_val;
}

/* Deserialize an XML Doc. */
static PyObject* deserialize_xml_AMF3(DecoderObj *context)
{
    int header;
    int *header_p = &header;
    if(!_decode_int_AMF3(context, header_p))
        return NULL;

    // Check for reference
    PyObject *xml_val = decode_reference_AMF3(context, context->obj_refs, header);
    if (!xml_val)
        return NULL;

    if (xml_val != Py_False) {
        return xml_val;
    } else {
        Py_DECREF(Py_False);
    }

    // No reference found
    PyObject *unicode_val = decode_string(context, header >> 1);
    if (!unicode_val)
        return NULL;

    xml_val = xml_from_string(unicode_val);
    Py_DECREF(unicode_val);
    if (!xml_val)
        return NULL;

    // Add reference
    if (Idx_map((IdxObj*)context->obj_refs, xml_val) == -1) {
        Py_DECREF(xml_val);
        return NULL;
    }

    return xml_val;
}

/* Create an XML val from a string. */
static PyObject* xml_from_string(PyObject *xml_string)
{
    PyObject *func = PyObject_GetAttrString(xml_dom_mod, "parseString");
    if (!func)
        return NULL;

    PyObject *xml_obj = PyObject_CallFunctionObjArgs(func, xml_string, NULL);
    Py_DECREF(func);
    return xml_obj;
}

/* Create an AsByteArray from a string. */
static PyObject* byte_array_from_string(PyObject *byte_string)
{
    PyObject *class_ = PyObject_GetAttrString(as_types_mod, "AsByteArray");
    if (!class_)
        return NULL;

    PyObject *obj = PyObject_CallFunctionObjArgs(class_, byte_string, NULL);
    Py_DECREF(class_);
    return obj;
}

/* Deserialize a string. */
static PyObject* deserialize_string_AMF3(DecoderObj *context)
{
    int header;
    int *header_p = &header;
    if(!_decode_int_AMF3(context, header_p))
        return NULL;

    // Check for null string
    if (header == EMPTY_STRING_TYPE) {
        return PyUnicode_Decode(NULL, 0, "UTF8", NULL);
    }

    // Check for reference
    PyObject *unicode_val = decode_reference_AMF3(context, context->string_refs, header);
    if (!unicode_val)
        return NULL;

    if (unicode_val != Py_False) {
        return unicode_val;
    } else {
        Py_DECREF(Py_False);
    }

    // No reference found
    unicode_val = decode_string(context, header >> 1);
    if (!unicode_val)
        return NULL;

    // Add reference
    if (Idx_map((IdxObj*)context->string_refs, unicode_val) == -1) {
        Py_DECREF(unicode_val);
        return NULL;
    }

    return unicode_val;
}

/* Decode a string. */
static PyObject* decode_string(DecoderObj *context, unsigned int string_size)
{
    const char *str = Decoder_read(context, (long)string_size);
    if (!str)
        return NULL;
    PyObject *unicode_val = PyUnicode_DecodeUTF8(str, (Py_ssize_t)string_size, NULL);
    if (!unicode_val)
        return NULL;

    return unicode_val;
}

/*
 * Checks a decoded int for the presence of a reference
 *
 * Returns PyObject if obj reference was found.
 * returns PyFalse if obj reference was not found.
 * returns NULL if call failed.
 */
static PyObject* decode_reference_AMF3(DecoderObj *context, PyObject *obj_context, int val)
{
    // Check for index reference
    if ((val & REFERENCE_BIT) == 0) {
        return Idx_ret((IdxObj*)obj_context, val >> 1);
    }

    Py_RETURN_FALSE;
}

/* Decode a double to a native C double.
 * Pass in reference, so we can detect an buffer error.
 */
static int _decode_double(DecoderObj *context, double *val)
{
    const char *bytes = Decoder_read(context, 8);
    if (!bytes)
        return 0;

    // Put bytes from byte array into double
    union aligned {
        double d_val;
        char c_val[8];
    } d;

    if (big_endian) {
        memcpy(d.c_val, bytes, 8);
    } else {
        // Flip endianness
        d.c_val[0] = bytes[7];
        d.c_val[1] = bytes[6];
        d.c_val[2] = bytes[5];
        d.c_val[3] = bytes[4];
        d.c_val[4] = bytes[3];
        d.c_val[5] = bytes[2];
        d.c_val[6] = bytes[1];
        d.c_val[7] = bytes[0];
    }

    *val = d.d_val;
    return 1;
}

/* Decode a native C unsigned short. */
static int _decode_ushort(DecoderObj *context, unsigned short *val)
{
    const char *bytes = Decoder_read(context, 2);
    if (!bytes)
        return 0;

    // Put bytes from byte array into short
    union aligned {
        unsigned short s_val;
        char c_val[2];
    } s;

    if (big_endian) {
        memcpy(s.c_val, bytes, 2);
    } else {
        // Flip endianness
        s.c_val[0] = bytes[1];
        s.c_val[1] = bytes[0];
    }

    *val = s.s_val;
    return 1;
}

/* Decode a native C unsigned int. */
static int _decode_ulong(DecoderObj *context, unsigned int *val)
{
    const char *bytes = Decoder_read(context, 4);
    if (!bytes)
        return 0;

    // Put bytes from byte array into short
    union aligned {
        unsigned int i_val;
        char c_val[4];
    } i;

    if (big_endian) {
        memcpy(i.c_val, bytes, 4);
    } else {
        // Flip endianness
        i.c_val[0] = bytes[3];
        i.c_val[1] = bytes[2];
        i.c_val[2] = bytes[1];
        i.c_val[3] = bytes[0];
    }

    *val = i.i_val;
    return 1;
}

/* Decode a double to a PyFloat. */
static PyObject* decode_double(DecoderObj *context)
{
    double number;
    double *number_p = &number;
    if(!_decode_double(context, number_p))
        return NULL;
    return PyFloat_FromDouble(number);
}

/* Decode an int to a native C int. */
static int _decode_int_AMF3(DecoderObj *context, int *val)
{
    int result = 0;
    int byte_cnt = 0;
    char *byte_ref = Decoder_readByte(context);
    if (!byte_ref)
        return 0;
    char byte = byte_ref[0];

    // If 0x80 is set, int includes the next byte, up to 4 total bytes
    while ((byte & 0x80) && (byte_cnt < 3)) {
        result <<= 7;
        result |= byte & 0x7F;
        byte_ref = Decoder_readByte(context);
        if (!byte_ref)
            return 0;
        byte = byte_ref[0];
        byte_cnt++;
    }

    // shift bits in last byte
    if (byte_cnt < 3) {
        result <<= 7; // shift by 7, since the 1st bit is reserved for next byte flag
        result |= byte & 0x7F;
    } else {
        result <<= 8; // shift by 8, since no further bytes are possible and 1st bit is not used for flag.
        result |= byte & 0xff;
    }

    // Move sign bit, since we're converting 29bit->32bit
    if (result & 0x10000000) {
        result -= 0x20000000;
    }

    *val = result;
    return 1;
}

/* Decode an int to a PyInt. */
static PyObject* decode_int_AMF3(DecoderObj *context)
{
    int header;
    int *header_p = &header;
    if(!_decode_int_AMF3(context, header_p))
        return NULL;

    return PyInt_FromLong((long)header); 
}

/* Decode an AMF0 Boolean. */
static PyObject* decode_bool_AMF0(DecoderObj *context)
{
    PyObject *boolean;
    const char *byte_ref = Decoder_readByte(context);
    if (!byte_ref)
        return NULL;
    const char byte = byte_ref[0];

    if (byte == TRUE_AMF0) {
        boolean = Py_True;
    } else {
        boolean = Py_False;
    }

    Py_INCREF(boolean);
    return boolean;
}

/* Decode an AMF0 String. */
static PyObject* decode_string_AMF0(DecoderObj *context)
{
    unsigned short string_size;
    unsigned short *string_size_p = &string_size;
    if (!_decode_ushort(context, string_size_p))
        return NULL;
    return decode_string(context, (unsigned int)string_size); 
}

/* Decode a long AMF0 String. */
static PyObject* decode_long_string_AMF0(DecoderObj *context)
{
    unsigned int string_size;
    unsigned int *string_size_p = &string_size;
    if(!_decode_ulong(context, string_size_p))
        return NULL; 
    return decode_string(context, string_size);
}

/* Decode an AMF0 Reference. */
static PyObject* decode_reference_AMF0(DecoderObj *context)
{
    unsigned short idx;
    unsigned short *idx_p = &idx;
    if(!_decode_ushort(context, idx_p))
        return NULL;
    return Idx_ret((IdxObj*)context->obj_refs, (int)idx);
}

/* Decode an AMF0 dict. */
static PyObject* decode_dict_AMF0(DecoderObj *context)
{
    PyObject *obj_val = PyDict_New();
    if (!obj_val)
        return NULL;

    // Add obj to reference
    if (Idx_map((IdxObj*)context->obj_refs, obj_val) == -1) {
        Py_DECREF(obj_val);
        return NULL;
    }

    if (decode_dynamic_dict_AMF0(context, obj_val) == 0) {
        Py_DECREF(obj_val);
        return NULL;
    }

    return obj_val;
}

/* Decode an dynamic AMF0 dict. */
static int decode_dynamic_dict_AMF0(DecoderObj *context, PyObject *dict)
{
    while (1) {
        PyObject *key = decode_string_AMF0(context);
        if (key == NULL)
            return 0;

        if (PyUnicode_GET_SIZE(key) == 0) {
            // Empty string indicates end of array.
            Py_DECREF(key);
            return Decoder_skipBytes(context, 1); // Skip end marker
        }

        PyObject *val = decode_AMF0(context);
        if (val == NULL) {
            Py_DECREF(key);
            return 0;
        }

        if (PyDict_SetItem(dict, key, val) != 0) {
            Py_DECREF(key);
            Py_DECREF(val);
            return 0;
        }
    }
}

/*
 * Decode an AMF0 array.
 *
 * If the map_reference property is not 0, a reference for this list
 * is added to the context. If the array being decoded is the body
 * of a NetConnection message, map_reference should be 0.
 *
 */
static PyObject* decode_array_AMF0(DecoderObj *context, short map_reference)
{
    unsigned int array_len;
    unsigned int *array_len_p = &array_len;
    if(!_decode_ulong(context, array_len_p))
        return NULL;

    // Can't use array_len to create list
    // of known length. See ticket #46.

    PyObject *list_val = PyList_New(0);
    if (!list_val)
        return NULL;

    if (map_reference) {
        // Reference must be added before children (to allow for recursion).
        if (Idx_map((IdxObj*)context->obj_refs, list_val) == -1) {
            Py_DECREF(list_val);
            return NULL;
        }
    }

    // Add each item to the list
    unsigned int i;
    for (i = 0; i < array_len; i++) {
        PyObject *val = decode_AMF0(context);
        if (!val) {
            Py_DECREF(list_val);
            return NULL;
        }

        int result = PyList_Append(list_val, val);
        Py_DECREF(val);
        if (result < 0)
            return NULL;
    }

    return list_val;
}

/* Decode an AMF0 Date. */
static PyObject* decode_date_AMF0(DecoderObj *context)
{
    // TODO: use timezone val to adjust datetime
    PyObject *date_val = decode_date(context);
    unsigned short tz;
    unsigned short *tz_p = &tz;
    if(!_decode_ushort(context, tz_p)) // timezone val.
        return NULL;

    // Add date to reference count
    if (Idx_map((IdxObj*)context->obj_refs, date_val) == -1) {
        Py_DECREF(date_val);
        return NULL;
    }

    return date_val;
}

/* Decode an AMF0 XML-Doc. */
static PyObject* decode_xml_AMF0(DecoderObj *context)
{
    PyObject *xml_string = decode_long_string_AMF0(context);
    if (!xml_string)
        return NULL;
    PyObject *xml_obj = xml_from_string(xml_string);
    Py_DECREF(xml_string);
    if (!xml_obj)
        return NULL;
        
    return xml_obj;
}

/* Decode AMF0 typed obj. */
static PyObject* decode_typed_obj_AMF0(DecoderObj *context)
{
    PyObject *alias = decode_string_AMF0(context);
    if (!alias)
        return NULL;

    PyObject *class_def = class_def_from_alias(context, alias);
    Py_DECREF(alias);
    if (!class_def)
        return NULL;

    // Anonymous obj.
    if (class_def == Py_None) {
        Py_DECREF(class_def);
        return decode_dict_AMF0(context);
    }

    PyObject *obj_val = PyObject_CallMethod(class_def, "getInstance", NULL);
    if (!obj_val) {
        Py_DECREF(class_def);
        return NULL;
    }

    // Reference must be added before children (to allow for recursion).
    if (Idx_map((IdxObj*)context->obj_refs, obj_val) == -1) {
        Py_DECREF(class_def);
        Py_DECREF(obj_val);
        return NULL;
    }

    // Put decoded attributes in this dict
    PyObject *decoded_attrs = PyDict_New();
    if (decoded_attrs == NULL) {
        Py_DECREF(class_def);
        Py_DECREF(obj_val);
        return NULL;
    }

    if (decode_dynamic_dict_AMF0(context, decoded_attrs) == 0) {
        Py_DECREF(class_def);
        Py_DECREF(obj_val);
        Py_DECREF(decoded_attrs);
        return NULL;
    }

    int type_result = type_dict(class_def, context->type_map, decoded_attrs, 1);
    if (type_result == 0) {
        Py_DECREF(class_def);
        Py_DECREF(obj_val);
        Py_DECREF(decoded_attrs);
        return NULL;
    }

    PyObject *result = PyObject_CallMethodObjArgs(class_def,
        context->apply_name, obj_val, decoded_attrs, NULL);
    Py_DECREF(class_def);
    Py_DECREF(decoded_attrs);

    if (result == NULL) {
        Py_DECREF(obj_val);
        return NULL;
    }

    Py_DECREF(result); // should be Py_None
    return obj_val;
}

/* Decode an AMF0 NetConnection packet. */
static PyObject* decode_packet(DecoderObj *context)
{
    PyObject *packet_class = PyObject_GetAttrString(remoting_mod, "Packet");
    if (!packet_class)
        return NULL;

    // Set client type
    PyObject *client_type;
    unsigned short version;
    unsigned short *version_p = &version;
    if(!_decode_ushort(context, version_p))
        return NULL;

    switch (version) {
        case FLASH_8:
            client_type = PyObject_GetAttrString(packet_class, "FLASH_8"); 
            break;
        case FLASH_COM:
            client_type = PyObject_GetAttrString(packet_class, "FLASH_COM");
            break;
        case FLASH_9:
            client_type = PyObject_GetAttrString(packet_class, "FLASH_9");
            break;
        default:
            PyErr_SetString(amfast_DecodeError, "Unknown client type.");
            Py_DECREF(packet_class);
            return NULL;
    }

    if (!client_type) {
        Py_DECREF(packet_class);
        return NULL;
    }

    PyObject *headers = decode_headers_AMF0(context);
    if (!headers) {
        Py_DECREF(packet_class);
        Py_DECREF(client_type);
        return NULL;
    }

    PyObject *messages = decode_messages_AMF0(context);
    if (!messages) {
        Py_DECREF(packet_class);
        Py_DECREF(client_type);
        Py_DECREF(headers);
        return NULL;
    }

    PyObject *packet = PyObject_CallFunctionObjArgs(packet_class, client_type, headers, messages, NULL);
    Py_DECREF(packet_class);
    Py_DECREF(client_type);
    Py_DECREF(headers);
    Py_DECREF(messages);

    return packet;
}

/* Decode AMF0 packet headers. */
static PyObject* decode_headers_AMF0(DecoderObj *context)
{
    unsigned short header_count;
    unsigned short *header_count_p = &header_count;
    if(!_decode_ushort(context, header_count_p))
        return NULL;

    PyObject *header_list = PyList_New(header_count);
    if (!header_list)
        return NULL;

    int i;
    for (i = 0; i < header_count; i++) {

        PyObject *header_name = decode_string_AMF0(context);
        if (!header_name) {
            Py_DECREF(header_list);
            return NULL;
        }

        PyObject *required = decode_bool_AMF0(context);
        if (!required) {
            Py_DECREF(header_list);
            Py_DECREF(header_name);
            return NULL;
        }

        // Read byte length, but don't do anything with it.
        unsigned int byte_len;
        unsigned int *byte_len_p = &byte_len;
        if(!_decode_ulong(context, byte_len_p))
            return NULL;

        // We need a new context for each header
        DecoderObj *new_context = (DecoderObj*)Decoder_copy(context, 0);
        if (!new_context) {
            Py_DECREF(header_list);
            Py_DECREF(header_name);
            Py_DECREF(required);
            return NULL;
        }

        PyObject *header_obj = decode_AMF0(new_context);
        Py_XDECREF(new_context);
        if (!header_obj) {
            Py_DECREF(header_list);
            Py_DECREF(header_name);
            Py_DECREF(required);
            return NULL;
        }

        // Create header obj
        PyObject *header_class = PyObject_GetAttrString(remoting_mod, "Header");
        if (!header_class) {
            Py_DECREF(header_list);
            Py_DECREF(header_name);
            Py_DECREF(required);
            return NULL;
        }

        PyObject *header = PyObject_CallFunctionObjArgs(header_class, header_name, required, header_obj, NULL);
        Py_DECREF(header_class);
        Py_DECREF(header_name);
        Py_DECREF(required);
        Py_DECREF(header_obj);
        if (!header) {
            Py_DECREF(header_list);
            return NULL;
        }

        // Steals reference to header
        PyList_SET_ITEM(header_list, i, header);
    }

    return header_list;
}

/* Decode AMF0 packet messages. */
static PyObject* decode_messages_AMF0(DecoderObj *context)
{
    unsigned short message_count;
    unsigned short *message_count_p = &message_count;
    if(!_decode_ushort(context, message_count_p))
        return NULL;

    PyObject *message_list = PyList_New(message_count);
    if (!message_list)
        return NULL;

    int i;
    for (i = 0; i < message_count; i++) {
        PyObject *target = decode_string_AMF0(context);
        if (!target) {
            Py_DECREF(message_list);
            return NULL;
        }

        PyObject *response = decode_string_AMF0(context);
        if (!response) {
            Py_DECREF(message_list);
            Py_DECREF(target);
            return NULL;
        }

        // Read byte length, but don't do anything with it.
        unsigned int byte_len;
        unsigned int *byte_len_p = &byte_len;
        if(!_decode_ulong(context, byte_len_p))
            return NULL;

        // We need a new context for each message
        // so that reference indexes are reset
        DecoderObj *new_context = (DecoderObj*)Decoder_copy(context, 0);
        if (!new_context) {
            Py_DECREF(message_list);
            Py_DECREF(target);
            Py_DECREF(response);
            return NULL;
        }

        PyObject *message_obj;
        if (PyUnicode_GET_SIZE(response) > 0) {
            // If this is a list of arguments for a RPC,
            // then the list of arguments should not be
            // added to the reference count!
            
            // Skip Array Type Marker
            if (Decoder_skipBytes(new_context, 1) == 0) {
                Py_DECREF(message_list);
                Py_DECREF(target);
                Py_DECREF(response);
            }

            message_obj = decode_array_AMF0(new_context, 0);
        } else {
            message_obj = decode_AMF0(new_context);
        }
        Py_XDECREF(new_context);

        if (!message_obj) {
            Py_DECREF(message_list);
            Py_DECREF(target);
            Py_DECREF(response);
            return NULL;
        }

        // Create message obj
        PyObject *message_class = PyObject_GetAttrString(remoting_mod, "Message");
        if (!message_class) {
            Py_DECREF(message_list);
            Py_DECREF(target);
            Py_DECREF(response);
            Py_DECREF(message_obj);
            return NULL;
        }

        PyObject *message = PyObject_CallFunctionObjArgs(message_class, target, response, message_obj, NULL);
        Py_DECREF(message_class);
        Py_DECREF(target);
        Py_DECREF(response);
        Py_DECREF(message_obj);
        if (!message) {
            Py_DECREF(message_list);
            return NULL;
        }

        // Steals reference
        PyList_SET_ITEM(message_list, i, message);
    }

    return message_list;
}

/* Decode individual AMF0 objs from buffer. */
static PyObject* decode_AMF0(DecoderObj *context)
{
    const char *byte_ref = Decoder_readByte(context);
    if (!byte_ref)
        return NULL;
    const char byte = byte_ref[0];

    switch(byte) {
        case NUMBER_AMF0:
            return decode_double(context);
        case BOOL_AMF0:
            return decode_bool_AMF0(context);
        case STRING_AMF0:
            return decode_string_AMF0(context);
        case OBJECT_AMF0:
            return decode_dict_AMF0(context);
        case MOVIE_AMF0:
            break;
        case NULL_AMF0:
            Py_RETURN_NONE;
        case UNDEFINED_AMF0:
            Py_RETURN_NONE;
        case REF_AMF0:
            return decode_reference_AMF0(context);
        case MIXED_ARRAY_AMF0:
            if (Decoder_skipBytes(context, 4) == 0) // Skip encoded max index
                return NULL;
            return decode_dict_AMF0(context);
        case OBJECT_END_AMF0:
            break;
        case ARRAY_AMF0:
            return decode_array_AMF0(context, 1);
        case DATE_AMF0:
            return decode_date_AMF0(context);
        case LONG_STRING_AMF0:
            return decode_long_string_AMF0(context);
        case UNSUPPORTED_AMF0:
            break;
        case RECORDSET_AMF0:
            break;
        case XML_DOC_AMF0:
            return decode_xml_AMF0(context);
        case TYPED_OBJ_AMF0:
            return decode_typed_obj_AMF0(context);
        case AMF3_AMF0:
            {
                DecoderObj *new_context = (DecoderObj*)Decoder_copy(context, 1);
                PyObject *result = decode_AMF3(new_context);
                Py_XDECREF(new_context);
                return result;
            }
        default:
            break;
    }

    char error_str[100];
    sprintf(error_str, "Unknown AMF0 type marker byte: '%X' at position: %d", byte, Decoder_tell(context) - 1);
    PyErr_SetString(amfast_DecodeError, error_str);
    return NULL;
}

/* Decode individual AMF3 objs from buffer. */
static PyObject* decode_AMF3(DecoderObj *context)
{
    const char *byte_ref = Decoder_readByte(context);
    if (!byte_ref)
        return NULL;
    const char byte = byte_ref[0];

    switch(byte) {
        case UNDEFINED_TYPE:
            Py_RETURN_NONE;
        case NULL_TYPE:
            Py_RETURN_NONE;
        case FALSE_TYPE:
            Py_RETURN_FALSE;
        case TRUE_TYPE:
            Py_RETURN_TRUE;
        case INT_TYPE:
            return decode_int_AMF3(context);
        case DOUBLE_TYPE:
            return decode_double(context);
        case STRING_TYPE:
            return deserialize_string_AMF3(context);
        case XML_DOC_TYPE:
            return deserialize_xml_AMF3(context);
        case DATE_TYPE:
            return deserialize_date(context);
        case ARRAY_TYPE:
            return deserialize_array_AMF3(context, 0);
        case OBJECT_TYPE:
            return deserialize_obj_AMF3(context, 0);
        case XML_TYPE:
           return deserialize_xml_AMF3(context);
        case BYTE_ARRAY_TYPE:
            return deserialize_byte_array_AMF3(context);
        case AMF3_AMF0:
            return decode_AMF3(context);
        default:
            break;
    }

    char error_str[100];
    sprintf(error_str, "Unknown AMF3 type marker byte: '%X' at position: %d", byte, Decoder_tell(context) - 1);
    PyErr_SetString(amfast_DecodeError, error_str);
    return NULL;
}

// ---- Python EXPOSED FUNCTIONS

/* Decode an AMF stream to a Python obj. */
static PyObject* py_decode(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *context;
    DecoderObj *dec_context;

    if (!PyArg_ParseTuple(args, "O", &context))
        return NULL;

    // If input is a string, create a context object.
    if (PyString_Check(context) == 1) {
        PyObject *cls = PyObject_GetAttrString(context_mod, "DecoderContext");
        if (cls == NULL)
            return NULL;

        dec_context = (DecoderObj*)PyObject_CallFunctionObjArgs(cls, context, NULL);
        Py_DECREF(cls);
        if (dec_context == NULL)
            return NULL;
    } else if (Decoder_check(context) == 1) {
        dec_context = (DecoderObj*)context;
        Py_INCREF(dec_context);
    } else {
        PyErr_SetString(amfast_DecodeError, "Argument must be a string or type amfast.context.DecoderContext");
        return NULL;
    }

    PyObject *result;
    if (dec_context->amf3 == Py_True) {
        result = decode_AMF3(dec_context);
    } else {
        result = decode_AMF0(dec_context);
    }

    Py_DECREF(dec_context);
    return result;
}

/* Decode an AMF Packet from a stream. */
static PyObject* py_decode_packet(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *context;
    DecoderObj *dec_context;

    if (!PyArg_ParseTuple(args, "O", &context))
        return NULL;

    // If input is a string, create a context object.
    if (PyString_Check(context) == 1) {
        PyObject *cls = PyObject_GetAttrString(context_mod, "DecoderContext");
        if (cls == NULL)
            return NULL;

        dec_context = (DecoderObj*)PyObject_CallFunctionObjArgs(cls, context, NULL);
        Py_DECREF(cls);
        if (dec_context == NULL)
            return NULL;
    } else if (Decoder_check(context) == 1) {
        dec_context = (DecoderObj*)context;
        Py_INCREF(dec_context);
    } else {
        PyErr_SetString(amfast_DecodeError, "Argument must be a string or type amfast.context.DecoderContext");
        return NULL;
    }

    PyObject *result = decode_packet(dec_context);
    Py_DECREF(dec_context);
    return result;
}

// ---- Module init

/* Expose functions as Python module functions. */
static PyMethodDef decode_methods[] = {
    {"decode", (PyCFunction)py_decode, METH_VARARGS | METH_KEYWORDS,
    "Description:\n"
    "=============\n"
    "Decode an AMF stream to Python objs.\n\n"
    "Useage:\n"
    "===========\n"
    "py_obj = decode(context)\n\n"
    "arguments:\n"
    "============\n"
    " * context - amfast.context.DecoderContext, Holds options valid for a single decode session.\n"},
    {"decode_packet", (PyCFunction)py_decode_packet, METH_VARARGS | METH_KEYWORDS,
    "Description:\n"
    "=============\n"
    "Decode an AMF packet stream.\n\n"
    "Useage:\n"
    "=========\n"
    "py_obj = decode_packet(context)\n\n"
    "arguments:\n"
    "===========\n"
    " * context - amfast.context.DecoderContext, Holds options valid for a single decode session.\n"},
    {NULL, NULL, 0, NULL}   /* sentinel */
};

PyMODINIT_FUNC
initdecode(void)
{
    PyObject *m;

    // Create module
    m = Py_InitModule3("decode", decode_methods,
        "Tools for decoding AMF streams.");
    if (m == NULL)
        return;

    // import all required external modules
    if (!amfast_mod) {
        amfast_mod = PyImport_ImportModule("amfast");
        if(!amfast_mod)
            return;
    }

    if (!remoting_mod) {
        remoting_mod = PyImport_ImportModule("amfast.remoting");
        if (!remoting_mod)
            return;
    }

    if (context_mod == NULL) {
        context_mod = import_context_mod();
        if (context_mod == NULL)
            return;
    }

    if (!xml_dom_mod) {
        xml_dom_mod = PyImport_ImportModule("xml.dom.minidom");
        if (!xml_dom_mod)
            return;
    }

    if (!as_types_mod) {
        as_types_mod = PyImport_ImportModule("amfast.class_def.as_types");
        if (!as_types_mod)
            return;
    }

    // Setup exceptions
    amfast_Error = PyObject_GetAttrString(amfast_mod, "AmFastError");
    if (amfast_Error == NULL) {
        return;
    }

    amfast_DecodeError = PyErr_NewException("amfast.decode.DecodeError", amfast_Error, NULL);
    if (amfast_DecodeError == NULL) {
        return;
    }

    Py_INCREF(amfast_DecodeError);
    if (PyModule_AddObject(m, "DecodeError", amfast_DecodeError) == -1) {
        return;
    }

    // Determine endianness of architecture
    const int endian_test = 1;
    if (is_bigendian()) {
        big_endian = 1;
    } else {
        big_endian = 0;
    }

    // Setup date time API
    PyDateTime_IMPORT;
}
