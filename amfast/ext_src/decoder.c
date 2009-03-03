#include <Python.h>

#ifndef DATETIME_H
#include <datetime.h>
#endif

#include "amf_common.h"

// Use to test for endianness at run time.
const int endian_test = 1;
#define is_bigendian() ((*(char*)&endian_test) == 0)

// ------------------------ DECLARATIONS --------------------------------- //

// ---- GLOBALS
static PyObject *xml_dom_mod;
static PyObject *amfast_mod;
static PyObject *class_def_mod;
static PyObject *amfast_Error;
static PyObject *amfast_DecodeError;
static int big_endian; // Flag == 1 if architecture is big_endian, == 0 if not

// ---- DECODING CONTEXT

/* Context for encoding. */
typedef struct {
    char *buf; // Input buffer
    int pos; // Current position in input buffer
    int buf_len; // Length of the buffer
    int use_array_collections; // Flag == 1 to decode ArrayCollections to lists.
    int use_object_proxies; // Flag == 1 to decode ObjectProxies to dicts.
    int object_proxy_set; // Flag == 1 if an ObjectProxyClassDef has been decoded.
    int array_collection_set; // Flag == 1 if an ArrayCollectionClassDef has been decode.
    PyObject *get_class_def; // PyFunction for getting a ClassDef for an object.
    ObjectContext *string_refs; // Keep track of string references
    ObjectContext *object_refs; // Keep track of object references
    ObjectContext *class_refs; // Keep track of class definitions references
} DecoderContext;

static DecoderContext* _create_decoder_context(PyObject *value);
static int _destroy_decoder_context(DecoderContext *context);

// ---- DECODING

/**
 * deserialize... functions de-reference.
 * decode... functions decode from AMF to Python
 */

static PyObject* decode_int(DecoderContext *context);
static int _decode_int(DecoderContext *context);
static PyObject* decode_double(DecoderContext *context);
static double _decode_double(DecoderContext *context);
static PyObject* deserialize_string(DecoderContext *context);
static PyObject* decode_string(DecoderContext *context);
static PyObject* deserialize_array(DecoderContext *context, int collection);
static int decode_array(DecoderContext *context, PyObject *list_value, int array_len);
static PyObject* decode_reference(DecoderContext *context, ObjectContext *object_context, int bit);
static PyObject* deserialize_xml(DecoderContext *context);
static PyObject* deserialize_byte_array(DecoderContext *context);
static PyObject* deserialize_byte_array(DecoderContext *context);
static PyObject* decode_byte_array(DecoderContext *context);
static PyObject* decode_date(DecoderContext *context);
static PyObject* deserialize_object(DecoderContext *context, int proxy);
static PyObject* deserialize_class_def(DecoderContext *context);
static PyObject* decode_class_def(DecoderContext *context);
static PyObject* decode_proxy_class_def(DecoderContext *context, PyObject *class_alias);
static int decode_typed_object(DecoderContext *context, PyObject *obj_value, PyObject *class_def);
static int decode_externizeable(DecoderContext *context, PyObject *obj_value, PyObject *class_def);
static int _decode_dynamic_dict(DecoderContext *context, PyObject *dict);

static PyObject* decode(PyObject *self, PyObject *args, PyObject *kwargs);
static PyObject* _decode(DecoderContext *context);

// ------------------------ DECODING CONTEXT ------------------------ //

/* Create a new DecoderContext. */
static DecoderContext* _create_decoder_context(PyObject *value)
{
    DecoderContext *context;
    context = (DecoderContext*)malloc(sizeof(DecoderContext));
    if (!context) {
        PyErr_SetNone(PyExc_MemoryError);
        return NULL;
    }

    context->buf = PyString_AsString(value);
    if (!context->buf)
        return NULL;

    context->buf_len = PyString_GET_SIZE(value);

    context->pos = 0;

    context->string_refs = create_object_context(64);
    if (!context->string_refs) {
        PyErr_SetNone(PyExc_MemoryError);
        return NULL;
    }

    context->object_refs = create_object_context(64);
    if (!context->object_refs) {
        PyErr_SetNone(PyExc_MemoryError);
        return NULL;
    }

    context->class_refs = create_object_context(64);
    if (!context->class_refs) {
        PyErr_SetNone(PyExc_MemoryError);
        return NULL;
    }

    context->array_collection_set = 0;
    context->object_proxy_set = 0;

    return context;
}

/* De-allocate an DecoderContext. */
static int _destroy_decoder_context(DecoderContext *context)
{
    destroy_object_context(context->string_refs);
    destroy_object_context(context->object_refs);
    destroy_object_context(context->class_refs);

    Py_DECREF(context->get_class_def);

    //free(context->buf);
    free(context);
    return 1;
}

// ------------------------ DECODING --------------------------------- //

/*
 * Deserialize an object.
 *
 * proxy is flag indicating that the object being deserialized is within an ObjectProxy
 */
static PyObject* deserialize_object(DecoderContext *context, int proxy)
{
    // TODO: this is a little hairy, should probably be split up.

    PyObject *obj_value;

    // Check for object reference
    obj_value = decode_reference(context, context->object_refs, 0);
    if (!obj_value)
        return NULL;

    if (obj_value != Py_None) {
        // Ref found

        if (proxy) {
            // Map ObjectProxy idx to ref, since
            // it points to the same object.
            if (!map_next_object_idx(context->object_refs, obj_value)) {
                Py_DECREF(obj_value);
                return NULL;
            }
        }

        return obj_value;
    }
    Py_DECREF(Py_None);

    // Ref not found
    // Create instance based on class def
    PyObject *class_def = deserialize_class_def(context);
    if (!class_def)
        return NULL;

    int obj_type; // 0 = anonymous, 1 == externizeable, 2 == typed
   
    if (class_def == Py_None) {
        // Anonymous object.
        obj_type = 0;
    } else if (PyObject_HasAttrString(class_def, "EXTERNIZEABLE_CLASS_DEF")) {
        // Check for special ArrayCollection and ObjectProxy types
        if (context->use_array_collections && PyObject_HasAttrString(class_def, "ARRAY_COLLECTION_CLASS_DEF")) {
            context->pos++; // Skip Array MarkerType
            Py_DECREF(class_def);
            return deserialize_array(context, 1);
        }

        if (context->use_object_proxies && PyObject_HasAttrString(class_def, "OBJECT_PROXY_CLASS_DEF")) {
            context->pos++; // Skip Object MarkerType
            Py_DECREF(class_def);
            return deserialize_object(context, 1);
        }

        obj_type = 1;
    } else {
        obj_type = 2;
    }

    // Instantiate new object
    if (!obj_type) {
        obj_value = PyDict_New();
    } else {
        // Create obj_value for all typed objects.
        obj_value = PyObject_CallMethod(class_def, "getInstance", NULL);
    }
    
    if (!obj_value) {
        Py_DECREF(class_def);
        return NULL;
    }

    // Reference must be added before children (to allow for recursion).
    if (!map_next_object_idx(context->object_refs, obj_value)) {
        Py_DECREF(class_def);
        Py_DECREF(obj_value);
        return NULL;
    }

    // If this is an ObjectProxy,
    // we need to add another reference,
    // so there is one that
    // points to the object and one that points
    // to the proxy.
    if (proxy) {
        if (!map_next_object_idx(context->object_refs, obj_value)) {
            Py_DECREF(class_def);
            Py_DECREF(obj_value);
            return NULL;
        }
    }

    int return_value;
    if (obj_type == 0) {
        return_value = _decode_dynamic_dict(context, obj_value);
    } else if (obj_type == 1) {
        return_value = decode_externizeable(context, obj_value, class_def);
    } else if (obj_type == 2) {
        return_value = decode_typed_object(context, obj_value, class_def);
    }
    Py_DECREF(class_def);

    if (!return_value) {
        Py_DECREF(obj_value);
        return NULL;
    }

    return obj_value;
}

/* Decode a typed object. */
static int decode_typed_object(DecoderContext *context, PyObject *obj_value, PyObject *class_def)
{
    // Put decoded attributes in this dict
    PyObject *decoded_attrs = PyDict_New();

    // Decode static attrs
    PyObject *static_attrs = PyObject_GetAttrString(class_def, "_decoded_attrs");
    if (!static_attrs) {
        Py_DECREF(decoded_attrs);
        return 0;
    }

    int static_attr_len = PyTuple_GET_SIZE(static_attrs);
    int i;
    for (i = 0; i < static_attr_len; i++) {
        PyObject *obj = _decode(context);
        if (!obj) {
            Py_DECREF(decoded_attrs);
            Py_DECREF(static_attrs);
            return 0;
        }

        PyObject *attr_name = PyTuple_GetItem(static_attrs, i);
        if (!attr_name) {
            Py_DECREF(decoded_attrs);
            Py_DECREF(static_attrs);
            return 0;
        }

        int return_value = PyDict_SetItem(decoded_attrs, attr_name, obj);
        Py_DECREF(obj);

        if (return_value == -1) {
            Py_DECREF(decoded_attrs);
            Py_DECREF(static_attrs);
            return 0;
        }
    }
    Py_DECREF(static_attrs);

    // Decode dynamic attrs
    if (PyObject_HasAttrString(class_def, "DYNAMIC_CLASS_DEF")) {
        if (!_decode_dynamic_dict(context, decoded_attrs)) {
            Py_DECREF(decoded_attrs);
            return 0;
        }
    }

    // apply attributes
    PyObject *method_name = PyString_FromString("applyAttrVals");
    if (!method_name) {
        Py_DECREF(decoded_attrs);
        return 0;
    }

    PyObject *return_value = PyObject_CallMethodObjArgs(class_def, method_name, obj_value, decoded_attrs, NULL);
    Py_DECREF(decoded_attrs);
    Py_DECREF(method_name);

    if (!return_value)
        return 0;

    Py_DECREF(return_value); // should be Py_None
    return 1;
}

/* Decode an EXTERNIZEABLE object. */
static int decode_externizeable(DecoderContext *context, PyObject *obj_value, PyObject *class_def)
{
    PyObject *method_name = PyString_FromString("readByteString");
    if (!method_name)
        return 0;

    // Read bytes
    size_t byte_len = context->buf_len;
    byte_len -= context->pos;
    char char_value[byte_len];
    memcpy(char_value, context->buf + context->pos, byte_len);

    PyObject *byte_array;

    #ifdef Py_BYTEARRAYOBJECT_H
    // ByteArray decoding is only available in 2.6+
    byte_array = PyByteArray_FromStringAndSize(char_value, byte_len);
    #else
    byte_array = PyString_FromStringAndSize(char_value, byte_len);
    #endif

    if (!byte_array) {
        Py_DECREF(method_name);
        return 0;
    }

    PyObject *parsed_len = PyObject_CallMethodObjArgs(class_def, method_name, obj_value, byte_array, NULL);
    Py_DECREF(method_name);
    Py_DECREF(byte_array);

    if (!parsed_len)
        return 0;

    context->pos = PyInt_AsLong(parsed_len) + 1;
    Py_DECREF(parsed_len);
    return 1; 
}

/* Deserialize a ClassDef. */
static PyObject* deserialize_class_def(DecoderContext *context)
{
    PyObject *class_def = decode_reference(context, context->class_refs, 1);
    if (!class_def)
        return NULL;

    if (class_def != Py_None)
        return class_def;
    Py_DECREF(Py_None);

    class_def = decode_class_def(context);
    if (!class_def)
        return 0;

    // Add reference to obj
    if (!map_next_object_idx(context->class_refs, class_def))
        return NULL;

    return class_def;
}

/* Decode a ClassDef. */
static PyObject* decode_class_def(DecoderContext *context)
{
    int header = _decode_int(context);
    PyObject *class_alias = deserialize_string(context);
    if (!class_alias)
        return NULL;
    
    // Check for empty string (anonymous object)
    if (PyUnicode_GET_SIZE(class_alias) == 0) {
        Py_DECREF(class_alias);
        Py_RETURN_NONE;
    }

    // Check for Proxy Class
    if ((header & 0x07FFFFFF) == EXTERNIZEABLE) {
        PyObject *proxy_class_def = decode_proxy_class_def(context, class_alias);
        if (!proxy_class_def) {
            return NULL;
        } else if(proxy_class_def != Py_None) {
            Py_DECREF(class_alias);
            return proxy_class_def;
        } else {
            Py_DECREF(proxy_class_def);
        }
    }

    // Get ClassDef object from map.
    PyObject *class_def = PyObject_CallFunctionObjArgs(context->get_class_def, class_alias, NULL);
    Py_DECREF(class_alias);

    // Check for an externizeable class def.
    if (((header & 0x07FFFFFF) == EXTERNIZEABLE) && PyObject_HasAttrString(class_def, "EXTERNIZEABLE_CLASS_DEF")) {
        // Externizeable
        return(class_def);
    } else if (((header & 0x07FFFFFF) != EXTERNIZEABLE) && PyObject_HasAttrString(class_def, "EXTERNIZEABLE_CLASS_DEF")) {
        Py_DECREF(class_def);
        PyErr_SetString(amfast_DecodeError, "ClassDef is externizeable, but encoded class is not.");
        return NULL;
    } else if (((header & 0x07FFFFFF) == EXTERNIZEABLE) && (!PyObject_HasAttrString(class_def, "EXTERNIZEABLE_CLASS_DEF"))) {
        Py_DECREF(class_def);
        PyErr_SetString(amfast_DecodeError, "Encoded class is externizeable, but ClassDef is not.");
        return NULL;
    }

    // Raise exception if number of encoded static attrs
    // does not match number of static attrs defined in Class
    PyObject *static_attrs = PyObject_GetAttrString(class_def, "static_attrs");
    if (!static_attrs) {
        Py_DECREF(class_def);
        return NULL;
    }

    if (!PyTuple_Check(static_attrs)) {
       Py_DECREF(static_attrs);
       Py_DECREF(class_def);
       PyErr_SetString(amfast_DecodeError, "ClassDef.static_attrs must be a tuple.");
       return NULL;
    }

    int static_attr_len = PyTuple_GET_SIZE(static_attrs);
    Py_DECREF(static_attrs);

    // Raise exception if ClassDef is dynamic,
    // but encoding is static
    if (PyObject_HasAttrString(class_def, "DYNAMIC_CLASS_DEF") && (!((header & DYNAMIC) == DYNAMIC))) {
        Py_DECREF(class_def);
        PyErr_SetString(amfast_DecodeError, "Encoded class is static, but ClassDef is dynamic.");
        return NULL;
    } else if ((header & DYNAMIC) == DYNAMIC && (!PyObject_HasAttrString(class_def, "DYNAMIC_CLASS_DEF"))) {
        Py_DECREF(class_def);
        PyErr_SetString(amfast_DecodeError, "Encoded class is dynamic, but ClassDef is not.");
        return NULL;
    }

    // Get static attr name from encoding
    // since attrs may be in a different order
    // and we need to move context->pos
    PyObject *decoded_attrs = PyTuple_New(static_attr_len);
    if (!decoded_attrs) {
        Py_DECREF(class_def);
        return NULL;
    }

    int i;
    for (i = 0; i < static_attr_len; i++) {
        PyObject *attr_name = deserialize_string(context);
        if (!attr_name) {
            Py_DECREF(class_def);
            Py_DECREF(decoded_attrs);
            return NULL;
        }

        // steals ref to attr_name
        if (PyTuple_SetItem(decoded_attrs, i, attr_name) != 0) {
            Py_DECREF(class_def);
            Py_DECREF(decoded_attrs);
            return NULL;
        }
    }

    // Set decoded attrs onto ClassDef
    int return_value = PyObject_SetAttrString(class_def, "_decoded_attrs", decoded_attrs);
    Py_DECREF(decoded_attrs);
    if (return_value == -1) {
        Py_DECREF(class_def);
        return NULL;
    }

    return class_def;
}

/* Return a Proxy ClassDef or Py_None if Proxy is not found. */
static PyObject* decode_proxy_class_def(DecoderContext *context, PyObject *class_alias)
{
    if (context->use_array_collections && (!context->array_collection_set)) {
        PyObject *class_def = PyObject_GetAttrString(class_def_mod, "_ArrayCollectionClassDef");
        if (!class_def)
            return NULL;

        PyObject *proxy_alias = PyObject_GetAttrString(class_def, "PROXY_ALIAS");
        if (!proxy_alias) {
            Py_DECREF(class_def);
            return NULL;
        }
        
        int return_value = PyUnicode_Compare(proxy_alias, class_alias);
        Py_DECREF(proxy_alias);
        if (return_value == 0) {
             PyObject *class_def_obj = PyObject_CallFunctionObjArgs(class_def, NULL);
             Py_DECREF(class_def);
             context->array_collection_set = 1;
             return class_def_obj;
        }
    }

    if (context->use_object_proxies && (!context->object_proxy_set)) {
        PyObject *class_def = PyObject_GetAttrString(class_def_mod, "_ObjectProxyClassDef");
        if (!class_def)
            return NULL;

        PyObject *proxy_alias = PyObject_GetAttrString(class_def, "PROXY_ALIAS");
        if (!proxy_alias) {
            Py_DECREF(class_def);
            return NULL;
        }

        int return_value = PyUnicode_Compare(proxy_alias, class_alias);
        Py_DECREF(proxy_alias);
        if (return_value == 0) {
             PyObject *class_def_obj = PyObject_CallFunctionObjArgs(class_def, NULL);
             Py_DECREF(class_def);
             context->object_proxy_set = 1;
             return class_def_obj;
        }
    }

    Py_RETURN_NONE;
}

/* Add the dynamic attributes of an encoded object to a dict. */
static int _decode_dynamic_dict(DecoderContext *context, PyObject *dict)
{
    while (1) {
        if (context->buf[context->pos] == EMPTY_STRING_TYPE) {
            context->pos++;
            return 1;
        }
        PyObject *key = deserialize_string(context);
        if (!key)
            return 0;

        PyObject *val = _decode(context);
        if (!val) {
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
 * Deserialize an array.
 * collection argument is a flag if this array is an array collection.
 */
static PyObject* deserialize_array(DecoderContext *context, int collection)
{
    PyObject *list_value;

    // Check for reference
    list_value = decode_reference(context, context->object_refs, 0);
    if (!list_value)
        return NULL;

    if (list_value != Py_None) {
        // Ref found

        if (collection) {
            // Map ArrayCollection idx to ref, since
            // it points to the same list.
            if (!map_next_object_idx(context->object_refs, list_value)) {
                Py_DECREF(list_value);
                return NULL;
            }
        }
        return list_value;
    }
    Py_DECREF(Py_None);

    // Create list of correct length
    int array_len = _decode_int(context) >> 1;
    list_value = PyList_New(array_len);
    if (!list_value)
        return NULL;

    // Reference must be added before children (to allow for recursion).
    if (!map_next_object_idx(context->object_refs, list_value)) {
        Py_DECREF(list_value);
        return NULL;
    }

    // If this is an ArrayCollection,
    // we need to add another reference,
    // so there is one that
    // points to the array and one that points
    // to the collection.
    if (collection) {
        if (!map_next_object_idx(context->object_refs, list_value)) {
            Py_DECREF(list_value);
            return NULL;
        }
    }

    // Populate list
    if (!decode_array(context, list_value, array_len)) {
        Py_DECREF(list_value);
        return NULL;
    }

    return list_value;
}

/* Populate an array with values from the buffer. */
static int decode_array(DecoderContext *context, PyObject *list_value, int array_len)
{
    // Skip associative part of array (terminated with empty string).
    int go = 1;
    while (go) {
        if (context->buf[context->pos] == EMPTY_STRING_TYPE)
            go = 0;
        context->pos++;
    }

    // Add each item to the list
    int i;
    for (i = 0; i < array_len; i++) {
        PyObject *value = _decode(context);
        if (!value)
            return 0;
        PyList_SET_ITEM(list_value, i, value);
    }

    return 1;
}

/* Deserialize date. */
static PyObject* deserialize_date(DecoderContext *context)
{
    PyObject *date_value;

    // Check for reference
    date_value = decode_reference(context, context->object_refs, 0);
    if (!date_value)
        return NULL;

    if (date_value != Py_None)
        return date_value;
    Py_DECREF(Py_None);

    date_value = decode_date(context);
    if (!date_value)
        return NULL;

    // Add reference
    if (!map_next_object_idx(context->object_refs, date_value)) {
        Py_DECREF(date_value);
        return NULL;
    }

    return date_value;
}

/* Decode a date. */
static PyObject* decode_date(DecoderContext *context)
{
    // Skip reference bit
    // it is only used as a reference,
    // not as a combined ref or int, like the others.
    context->pos++;

    double epoch_millisecs = _decode_double(context);
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
static PyObject* deserialize_byte_array(DecoderContext *context)
{
    PyObject *byte_array_value;

    // Check for reference
    byte_array_value = decode_reference(context, context->object_refs, 0);
    if (!byte_array_value)
        return NULL;

    if (byte_array_value != Py_None)
        return byte_array_value;

    Py_DECREF(Py_None);

    byte_array_value = decode_byte_array(context);
    if (!byte_array_value)
        return NULL;
    
    // Add reference
    if (!map_next_object_idx(context->object_refs, byte_array_value)) {
        Py_DECREF(byte_array_value);
        return NULL;
    }

    return byte_array_value;
}

/* Decode a byte array. */
static PyObject* decode_byte_array(DecoderContext *context)
{
    PyObject *byte_array_value;

    int byte_len = _decode_int(context) >> 1;
    char char_value[byte_len];

    memcpy(char_value, context->buf + context->pos, byte_len);

    #ifdef Py_BYTEARRAYOBJECT_H
    // ByteArray decoding is only available in 2.6+
    byte_array_value = PyByteArray_FromStringAndSize(char_value, byte_len);
    #else
    byte_array_value = PyString_FromStringAndSize(char_value, byte_len);
    #endif

    if (!byte_array_value)
        return NULL;

    context->pos += byte_len;

    return byte_array_value;
}

/* Deserialize an XML Doc. */
static PyObject* deserialize_xml(DecoderContext *context)
{
    PyObject *unicode_value;
    PyObject *xml_value;

    // Check for reference
    xml_value = decode_reference(context, context->object_refs, 0);
    if (!xml_value)
        return NULL;

    if (xml_value != Py_None)
        return xml_value;
    Py_DECREF(Py_None);

    // No reference found
    unicode_value = decode_string(context);
    if (!unicode_value)
        return NULL;

    if (!xml_dom_mod) {
        // Import xml.dom
        xml_dom_mod = PyImport_ImportModule("xml.dom.minidom");
        if (!xml_dom_mod) {
            Py_DECREF(unicode_value);
            return NULL;
        }
    }

    PyObject *func = PyObject_GetAttrString(xml_dom_mod, "parseString");
    if (!func) {
        Py_DECREF(unicode_value);
        return NULL;
    }

    xml_value = PyObject_CallFunctionObjArgs(func, unicode_value, NULL);
    Py_DECREF(unicode_value);
    Py_DECREF(func);
    if (!xml_value)
        return NULL;

    // Add reference
    if (!map_next_object_idx(context->object_refs, xml_value)) {
        Py_DECREF(xml_value);
        return NULL;
    }

    return xml_value;
}

/* Deserialize a string. */
static PyObject* deserialize_string(DecoderContext *context)
{
    PyObject *unicode_value;

    // Check for null string
    if (context->buf[context->pos] == EMPTY_STRING_TYPE) {
        context->pos++;
        return PyString_FromStringAndSize(NULL, 0);
    }

    // Check for reference
    unicode_value = decode_reference(context, context->string_refs, 0);
    if (!unicode_value)
        return NULL;

    if (unicode_value != Py_None)
        return unicode_value;
    Py_DECREF(Py_None);

    // No reference found
    unicode_value = decode_string(context);
    if (!unicode_value)
        return NULL;

    // Add reference
    if (!map_next_object_idx(context->string_refs, unicode_value)) {
        Py_DECREF(unicode_value);
        return NULL;
    }

    return unicode_value;
}

/* Decode a string. */
static PyObject* decode_string(DecoderContext *context)
{
    int string_len = _decode_int(context) >> 1;
    PyObject *unicode_value = PyUnicode_DecodeUTF8(context->buf + context->pos, string_len, NULL);
    if (!unicode_value)
        return NULL;

    context->pos += string_len;
    return unicode_value;
}

/*
 * Decode a reference to an object.
 *
 * bit argument specifies which bit to check for the reference (0 = low bit)
 *
 * Returns PyObject if object reference was found.
 * returns PyNone if object reference was not found.
 * returns NULL if call failed.
 */
static PyObject* decode_reference(DecoderContext *context, ObjectContext *object_context, int bit)
{
    // Check for index reference
    if (((context->buf[context->pos] >> bit) & REFERENCE_BIT) == 0) {
        int idx = _decode_int(context) >> (bit + 1);

        PyObject *value = get_ref_from_idx(object_context, idx);
        if (!value)
            return NULL;

        Py_INCREF(value); // This reference is getting put somewhere, so we need to increase the ref count.
        return value;
    }

    Py_RETURN_NONE;
}

/* Decode a double to a native C double. */
static double _decode_double(DecoderContext *context)
{
    // Put bytes from byte array into double
    union aligned {
        double d_value;
        char c_value[8];
    } d;
    char *char_value = d.c_value;

    if (big_endian) {
        memcpy(char_value, context->buf + context->pos, 8);
    } else {
        // Flip endianness
        char_value[0] = context->buf[context->pos + 7];
        char_value[1] = context->buf[context->pos + 6],
        char_value[2] = context->buf[context->pos + 5],
        char_value[3] = context->buf[context->pos + 4],
        char_value[4] = context->buf[context->pos + 3],
        char_value[5] = context->buf[context->pos + 2],
        char_value[6] = context->buf[context->pos + 1],
        char_value[7] = context->buf[context->pos];
    }
    context->pos += 8;

    return d.d_value;
}

/* Decode a double to a PyFloat. */
static PyObject* decode_double(DecoderContext *context)
{
    return PyFloat_FromDouble(_decode_double(context));
}

/* Decode an int to a native C int. */
static int _decode_int(DecoderContext *context)
{
    int result = 0;
    int byte_cnt = 0;

    // If 0x80 is set, int includes the next byte, up to 4 total bytes
    while ((context->buf[context->pos] & 0x80) && (byte_cnt < 3)) {
        result <<= 7;
        result |= context->buf[context->pos] & 0x7F;
        context->pos++;
        byte_cnt++;
    }

    // shift bits in last byte
    if (byte_cnt < 3) {
        result <<= 7; // shift by 7, since the 1st bit is reserved for next byte flag
        result |= context->buf[context->pos] & 0x7F;
    } else {
        result <<= 8; // shift by 8, since no further bytes are possible and 1st bit is not used for flag.
        result |= context->buf[context->pos] & 0xff;
    }

    // Move sign bit, since we're converting 29bit->32bit
    if (result & 0x10000000) {
        result -= 0x20000000;
    }

    context->pos++;
    return result;
}

/* Decode an int to a PyInt. */
static PyObject* decode_int(DecoderContext *context)
{
    return PyInt_FromLong(_decode_int(context)); 
}

/* Decode individual objects from buffer. */
static PyObject* _decode(DecoderContext *context)
{
    char byte = context->buf[context->pos];

    if (byte == NULL_TYPE) {
        context->pos++;
        Py_RETURN_NONE;
    } else if (byte == FALSE_TYPE) {
        context->pos++;
        Py_RETURN_FALSE;
    } else if (byte == TRUE_TYPE) {
        context->pos++;
        Py_RETURN_TRUE;
    } else if (byte == INT_TYPE) {
        context->pos++;
        return decode_int(context);
    } else if (byte == STRING_TYPE) {
        context->pos++;
        return deserialize_string(context);
    } else if (byte == DOUBLE_TYPE) {
        context->pos++;
        return decode_double(context);
    } else if (byte == ARRAY_TYPE) {
        context->pos++;
        return deserialize_array(context, 0);
    } else if (byte == OBJECT_TYPE) {
        context->pos++;
        return deserialize_object(context, 0);
    } else if (byte == BYTE_ARRAY_TYPE) {
        context->pos++;
        return deserialize_byte_array(context);
    } else if ((byte == XML_TYPE) || (byte == XML_DOC_TYPE)) {
        context->pos++;
        return deserialize_xml(context);
    } else if (byte == DATE_TYPE) {
        context->pos++;
        return deserialize_date(context);
    }

    char error_str[40];
    sprintf(error_str, "Unknown type marker byte: '%X' at position: %d", byte, context->pos);
    PyErr_SetString(amfast_DecodeError, error_str);
    return NULL;
}

/* Decode an AMF buffer to Python objects. */
static PyObject* decode(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *value;
    PyObject *get_class_def = Py_None;
    int use_array_collections = 0;
    int use_object_proxies = 0;

    static char *kwlist[] = {"value", "use_array_collections", "use_object_proxies",
        "get_class_def", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|iiO", kwlist,
        &value, &use_array_collections, &use_object_proxies, &get_class_def))
        return NULL;

    DecoderContext *context = _create_decoder_context(value);
    if (!context)
        return NULL;

    // Set defaults
    context->use_array_collections = use_array_collections;
    context->use_object_proxies = use_object_proxies;
    if (get_class_def != Py_None) {
        // User supplied function
        context->get_class_def = get_class_def;
        Py_INCREF(context->get_class_def);
    } else {
        if (!class_def_mod) {
            class_def_mod = PyImport_ImportModule("amfast.class_def");
            if(!class_def_mod)
                return NULL;
        }

        context->get_class_def = PyObject_GetAttrString(class_def_mod, "get_class_def_by_alias");
        if (!context->get_class_def)
            return NULL;
    }

    PyObject *return_value = _decode(context);
    _destroy_decoder_context(context);
    return return_value;
}

/* Expose functions as Python module functions. */
static PyMethodDef decoder_methods[] = {
    {"decode", (PyCFunction)decode, METH_VARARGS | METH_KEYWORDS,
    "Description:\n"
    "=============\n"
    "Decode an AMF3 stream to Python objects.\n\n"
    "Useage:\n"
    "===========\n"
    "py_obj = decode(value, **kwargs)\n\n"
    "Optional keyword arguments:\n"
    "============================\n"
    " * use_array_collections - bool - True to decode ArrayCollections to lists. - Default = False\n"
    " * use_object_proxies - bool - True to decode ObjectProxies to dicts. - Default = False\n"
    " * get_class_def - function - Function that retrieves a ClassDef object used for customizing \n"
    "    de-serialization of objects - Default = amfast.class_def.get_class_def_by_alias\n"
    "    Custom functions must have the signature: class_def = function(alias), where alias\n"
    "    is the class alias of the object being decoded and class_def is a ClassDef instance, \n"
    "    or None if no ClassDef was found.\n"},
    {NULL, NULL, 0, NULL}   /* sentinel */
};

PyMODINIT_FUNC
initdecoder(void)
{
    PyObject *module;

    module = Py_InitModule("decoder", decoder_methods);
    if (module == NULL)
        return;

    // Setup exceptions
    if (!amfast_mod) {
        amfast_mod = PyImport_ImportModule("amfast");
        if(!amfast_mod) {
            return;
        }
    }

    amfast_Error = PyObject_GetAttrString(amfast_mod, "AmFastError");
    if (amfast_Error == NULL) {
        return;
    }

    amfast_DecodeError = PyErr_NewException("amfast.decoder.DecodeError", amfast_Error, NULL);
    if (amfast_DecodeError == NULL) {
        return;
    }

    Py_INCREF(amfast_DecodeError);
    if (PyModule_AddObject(module, "DecodeError", amfast_DecodeError) == -1) {
        return;
    }

    // Include class def module
    if (!class_def_mod) {
        class_def_mod = PyImport_ImportModule("amfast.class_def");
        if(!class_def_mod) {
            return;
        }
    }

    // Determine endianness of architecture
    if (is_bigendian()) {
        big_endian = 1;
    } else {
        big_endian = 0;
    }

    // Setup date time API
    PyDateTime_IMPORT;
}
