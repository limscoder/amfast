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
static PyObject *remoting_mod;
static PyObject *amfast_Error;
static PyObject *amfast_DecodeError;
static int big_endian; // Flag == 1 if architecture is big_endian, == 0 if not

// ---- DECODING CONTEXT

/* Context for encoding. */
typedef struct {
    PyObject *class_def_mapper; // Object for getting a ClassDef for an object.
    PyObject *get_class_def_method_name; // Name of the method to call to retrieve a class def.
    PyObject *apply_attr_vals_method_name; // Name of the method to call to apply attributes
    ObjectContext *string_refs; // Keep track of string references
    ObjectContext *object_refs; // Keep track of object references
    ObjectContext *class_refs; // Keep track of class definitions references
    char *buf; // Input buffer
    int pos; // Current position in input buffer
    int buf_len; // Length of the buffer
} DecoderContext;

static DecoderContext* _create_decoder_context(int amf3);
static DecoderContext* _copy_decoder_context(DecoderContext *context, int amf3);
static int _destroy_decoder_context(DecoderContext *context);

// ---- DECODING

/**
 * deserialize... functions de-reference.
 * decode... functions decode from AMF to Python
 */

// AMF3
static PyObject* decode_int(DecoderContext *context);
static int _decode_int(DecoderContext *context);
static PyObject* decode_double(DecoderContext *context);
static double _decode_double(DecoderContext *context);
static PyObject* deserialize_string(DecoderContext *context);
static PyObject* decode_string(DecoderContext *context, unsigned int string_size);
static PyObject* deserialize_array(DecoderContext *context, int collection);
static int decode_array(DecoderContext *context, PyObject *list_value, int array_len);
static PyObject* decode_reference(ObjectContext *object_context, int value);
static PyObject* deserialize_xml(DecoderContext *context);
static PyObject* xml_from_string(PyObject *xml_string);
static PyObject* deserialize_byte_array(DecoderContext *context);
static PyObject* deserialize_byte_array(DecoderContext *context);
static PyObject* decode_byte_array(DecoderContext *context, int byte_len);
static PyObject* decode_date(DecoderContext *context);
static PyObject* deserialize_object(DecoderContext *context, int proxy);
static PyObject* deserialize_class_def(DecoderContext *context, int header);
static PyObject* decode_class_def(DecoderContext *context, int header);
static PyObject* class_def_from_alias(DecoderContext *context, PyObject *alias);
static int decode_typed_object(DecoderContext *context, PyObject *obj_value, PyObject *class_def);
static int decode_externizeable(DecoderContext *context, PyObject *obj_value, PyObject *class_def);
static int _decode_dynamic_dict(DecoderContext *context, PyObject *dict);
static PyObject* _decode_packet(DecoderContext *context);

//AMF0
static PyObject* decode_bool_AMF0(DecoderContext *context);
static PyObject* decode_string_AMF0(DecoderContext *context);
static PyObject* decode_reference_AMF0(DecoderContext *context);
static PyObject* decode_dict_AMF0(DecoderContext *context);
static int _decode_dynamic_dict_AMF0(DecoderContext *context, PyObject *dict);
static unsigned short _decode_ushort(DecoderContext *context);
static unsigned int _decode_ulong(DecoderContext *context);
static PyObject* decode_array_AMF0(DecoderContext *context);
static PyObject* decode_long_string_AMF0(DecoderContext *context);
static PyObject* decode_date_AMF0(DecoderContext *context);
static PyObject* decode_xml_AMF0(DecoderContext *context);
static PyObject* decode_typed_object_AMF0(DecoderContext *context);
static PyObject* decode_headers_AMF0(DecoderContext *context);
static PyObject* decode_messages_AMF0(DecoderContext *context);

// Entry functions
static PyObject* decode(PyObject *self, PyObject *args, PyObject *kwargs);
static PyObject* _decode_AMF0(DecoderContext *context);
static PyObject* _decode(DecoderContext *context);

// ------------------------ DECODING CONTEXT ------------------------ //

/* Create a new DecoderContext. */
static DecoderContext* _create_decoder_context(int amf3)
{
    DecoderContext *context;
    context = (DecoderContext*)malloc(sizeof(DecoderContext));
    if (!context) {
        PyErr_SetNone(PyExc_MemoryError);
        return NULL;
    }

    // Set python pointers to NULL
    context->buf = NULL;
    context->class_def_mapper = NULL;
    context->get_class_def_method_name = NULL;
    context->apply_attr_vals_method_name = NULL;

    if (amf3) {
        context->string_refs = create_object_context(64);
        if (!context->string_refs) {
            free(context);
            return NULL;
        }
    } else {
        context->string_refs = NULL;
    }

    // Always create object refs.
    context->object_refs = create_object_context(64);
    if (!context->object_refs) {
        if (context->string_refs) {
            destroy_object_context(context->string_refs);
        }
        free(context);
        return NULL;
    }

    if (amf3) {
        context->class_refs = create_object_context(64);
        if (!context->class_refs) {
            if (context->string_refs) {
                destroy_object_context(context->string_refs);
            }
            if (context->object_refs) {
                destroy_object_context(context->object_refs);
            }

            free(context);
            return NULL;
        }
    } else {
        context->class_refs = NULL;
    }

    context->buf_len = 0;
    context->pos = 0;

    return context;
}

/*
 *Creates a new context, and copies over the existing values.
 *
 * Use this when you need to reset reference counts.
 */
static DecoderContext* _copy_decoder_context(DecoderContext *context, int amf3)
{
    DecoderContext *new_context = _create_decoder_context(amf3);
    if (!new_context)
        return NULL;

    new_context->buf = context->buf;
    new_context->buf_len = context->buf_len;
    new_context->pos = context->pos;

    new_context->class_def_mapper = context->class_def_mapper;
    if (new_context->class_def_mapper)
        Py_INCREF(new_context->class_def_mapper);

    new_context->get_class_def_method_name  = context->get_class_def_method_name;
    if (new_context->get_class_def_method_name)
        Py_INCREF(new_context->get_class_def_method_name);

    new_context->apply_attr_vals_method_name = context->apply_attr_vals_method_name;
    if (new_context->apply_attr_vals_method_name)
        Py_INCREF(new_context->apply_attr_vals_method_name);

    return new_context;
}

/* De-allocate an DecoderContext. */
static int _destroy_decoder_context(DecoderContext *context)
{
    if (context->string_refs) {
        destroy_object_context(context->string_refs);
    }

    if (context->object_refs) {
        destroy_object_context(context->object_refs);
    }

    if (context->class_refs) {
        destroy_object_context(context->class_refs);
    }

    if (context->class_def_mapper) {
        Py_DECREF(context->class_def_mapper);
    }

    if (context->get_class_def_method_name) {
        Py_DECREF(context->get_class_def_method_name);
    }

    if (context->apply_attr_vals_method_name) {
        Py_DECREF(context->apply_attr_vals_method_name);
    }

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
    int header = _decode_int(context);

    // Check for object reference
    PyObject *obj_value = decode_reference(context->object_refs, header);
    if (!obj_value)
        return NULL;

    if (obj_value != Py_False) {
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
    } else {
        Py_DECREF(Py_False);
    }

    // Ref not found
    // Create instance based on class def
    PyObject *class_def = deserialize_class_def(context, header);
    if (!class_def)
        return NULL;

    int obj_type; // 0 = anonymous, 1 == externizeable, 2 == typed
    if (class_def == Py_None) {
        // Anonymous object.
        obj_type = 0;
    } else if (PyObject_HasAttrString(class_def, "EXTERNIZEABLE_CLASS_DEF")) {
        // Check for special ArrayCollection and ObjectProxy types
        if (PyObject_HasAttrString(class_def, "ARRAY_COLLECTION_CLASS_DEF")) {
            context->pos++; // Skip Array MarkerType
            Py_DECREF(class_def);
            return deserialize_array(context, 1);
        }

        if (PyObject_HasAttrString(class_def, "OBJECT_PROXY_CLASS_DEF")) {
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

    int return_value = 0;
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

    Py_ssize_t static_attr_len = PyTuple_GET_SIZE(static_attrs);
    int i;
    for (i = 0; i < static_attr_len; i++) {
        PyObject *obj = _decode(context);
        if (!obj) {
            Py_DECREF(decoded_attrs);
            Py_DECREF(static_attrs);
            return 0;
        }

        PyObject *attr_name = PyTuple_GET_ITEM(static_attrs, i);
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
    if (!context->apply_attr_vals_method_name) {
        context->apply_attr_vals_method_name = PyString_FromString("applyAttrVals");
        if (!context->apply_attr_vals_method_name) {
            Py_DECREF(decoded_attrs);
            return 0;
        }
    }

    PyObject *return_value = PyObject_CallMethodObjArgs(class_def, context->apply_attr_vals_method_name, obj_value, decoded_attrs, NULL);
    Py_DECREF(decoded_attrs);

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
    byte_array = PyByteArray_FromStringAndSize(char_value, (Py_ssize_t)byte_len);
    #else
    byte_array = PyString_FromStringAndSize(char_value, (Py_ssize_t)byte_len);
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

    context->pos = (int)(PyInt_AsLong(parsed_len) + 1);
    Py_DECREF(parsed_len);
    return 1; 
}

/*
 * Deserialize a ClassDef.
 *
 * header argument is the parsed object header.
 */
static PyObject* deserialize_class_def(DecoderContext *context, int header)
{
    PyObject *class_def = decode_reference(context->class_refs, header >> 1);
    if (!class_def)
        return NULL;

    if (class_def != Py_False) {
        return class_def;
    } else {
        Py_DECREF(Py_False);
    }

    class_def = decode_class_def(context, header);
    if (!class_def)
        return 0;

    // Add reference to obj
    if (!map_next_object_idx(context->class_refs, class_def))
        return NULL;

    return class_def;
}

/*
 * Decode a ClassDef.
 *
 * header argument is parsed the object header.
 */
static PyObject* decode_class_def(DecoderContext *context, int header)
{
    PyObject *alias = deserialize_string(context);
    if (!alias)
        return NULL;

    // Get alias as C-String for error handling
    PyObject *alias_str = PyUnicode_AsASCIIString(alias);
    if (!alias_str) {
        Py_DECREF(alias);
        return NULL;
    }
    char *alias_char = PyString_AsString(alias_str);

    PyObject *class_def = class_def_from_alias(context, alias);
    Py_DECREF(alias);
    if (!class_def) 
        return NULL;

    // Check for an externizeable class def.
    if(PyObject_HasAttrString(class_def, "EXTERNIZEABLE_CLASS_DEF")) {
        return(class_def);
    }
 
    if ((header & 0x07FFFFFF) == EXTERNIZEABLE) {
        Py_DECREF(class_def);
        char error_str[512];
        sprintf(error_str, "Encoded class '%s' is externizeable, but ClassDef is not.", alias_char);
        PyErr_SetString(amfast_DecodeError, error_str);
        return NULL;
    }

    // Check for anonymous object
    if (class_def == Py_None)
        return class_def;

    // Raise exception if ClassDef is dynamic,
    // but encoding is static
    if (PyObject_HasAttrString(class_def, "DYNAMIC_CLASS_DEF") && (!((header & DYNAMIC) == DYNAMIC))) {
        Py_DECREF(class_def);
        char error_str[512];
        sprintf(error_str, "Encoded class '%s' is static, but ClassDef is dynamic.", alias_char);
        PyErr_SetString(amfast_DecodeError, error_str);
        return NULL;
    } else if ((header & DYNAMIC) == DYNAMIC && (!PyObject_HasAttrString(class_def, "DYNAMIC_CLASS_DEF"))) {
        Py_DECREF(class_def);
        char error_str[512];
        sprintf(error_str, "Encoded class '%s' is dynamic, but ClassDef is static.", alias_char);
        PyErr_SetString(amfast_DecodeError, error_str);
        return NULL;
    }

    // Decode static attrs
    int static_attr_len = header >> 4;

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

/* Retrieve a ClassDef from a class alias string. */
static PyObject* class_def_from_alias(DecoderContext *context, PyObject *alias)
{
    // Check for empty string (anonymous object)
    if (PyUnicode_GET_SIZE(alias) == 0) {
        Py_RETURN_NONE;
    }

    // Get ClassDef object from map.
    // Create method name, if it does not exist already.
    if (!context->get_class_def_method_name) {
        context->get_class_def_method_name = PyString_FromString("getClassDefByAlias");
        if (!context->get_class_def_method_name)
            return NULL;
    }

    PyObject *return_value = PyObject_CallMethodObjArgs(context->class_def_mapper, context->get_class_def_method_name, alias, NULL);

    // Raise exception if class is not mapped.
    if (return_value == Py_None) {
        PyObject *error_title = PyString_FromString("Class alias not mapped: ");
        PyObject *error_str = PyUnicode_Concat(error_title, alias);
        PyErr_SetObject(amfast_DecodeError, error_str);
        Py_DECREF(error_title);
        Py_DECREF(error_str);
        Py_DECREF(return_value);
        return NULL;
    }

    return return_value;
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

        Py_DECREF(key);
        Py_DECREF(val);
    }
}

/*
 * Deserialize an array.
 * collection argument is a flag if this array is an array collection.
 */
static PyObject* deserialize_array(DecoderContext *context, int collection)
{
    int header = _decode_int(context);

    // Check for reference
    PyObject *list_value = decode_reference(context->object_refs, header);
    if (!list_value)
        return NULL;

    if (list_value != Py_False) {
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
    } else {
        Py_DECREF(Py_False);
    }

    // Create list of correct length
    int array_len = header >> 1;
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
    int header = _decode_int(context);

    // Check for reference
    PyObject *date_value = decode_reference(context->object_refs, header);
    if (!date_value)
        return NULL;

    if (date_value != Py_False) {
        return date_value;
    } else {
        Py_DECREF(Py_False);
    }

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
    double epoch_millisecs = _decode_double(context);
    PyObject *epoch_float = PyFloat_FromDouble(epoch_millisecs / 1000);
    if (!epoch_float)
        return NULL;

    if (!amfast_mod) {
        amfast_mod = PyImport_ImportModule("amfast");
        if(!amfast_mod) {
            return NULL;
        }
    }

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
    int header = _decode_int(context);

    // Check for reference
    PyObject *byte_array_value = decode_reference(context->object_refs, header);
    if (!byte_array_value)
        return NULL;

    if (byte_array_value != Py_False) {
        return byte_array_value;
    } else {
        Py_DECREF(Py_False);
    }

    byte_array_value = decode_byte_array(context, header >> 1);
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
static PyObject* decode_byte_array(DecoderContext *context, int byte_len)
{
    PyObject *byte_array_value;
    char char_value[byte_len];

    memcpy(char_value, context->buf + context->pos, byte_len);

    #ifdef Py_BYTEARRAYOBJECT_H
    // ByteArray decoding is only available in 2.6+
    byte_array_value = PyByteArray_FromStringAndSize(char_value, (Py_ssize_t)byte_len);
    #else
    byte_array_value = PyString_FromStringAndSize(char_value, (Py_ssize_t)byte_len);
    #endif

    if (!byte_array_value)
        return NULL;

    context->pos += byte_len;

    return byte_array_value;
}

/* Deserialize an XML Doc. */
static PyObject* deserialize_xml(DecoderContext *context)
{
    int header = _decode_int(context);

    // Check for reference
    PyObject *xml_value = decode_reference(context->object_refs, header);
    if (!xml_value)
        return NULL;

    if (xml_value != Py_False) {
        return xml_value;
    } else {
        Py_DECREF(Py_False);
    }

    // No reference found
    PyObject *unicode_value = decode_string(context, header >> 1);
    if (!unicode_value)
        return NULL;

    xml_value = xml_from_string(unicode_value);
    Py_DECREF(unicode_value);
    if (!xml_value)
        return NULL;

    // Add reference
    if (!map_next_object_idx(context->object_refs, xml_value)) {
        Py_DECREF(xml_value);
        return NULL;
    }

    return xml_value;
}

/* Create an XML value from a string. */
static PyObject* xml_from_string(PyObject *xml_string)
{
    if (!xml_dom_mod) {
        // Import xml.dom
        xml_dom_mod = PyImport_ImportModule("xml.dom.minidom");
        if (!xml_dom_mod)
            return NULL;
    }

    PyObject *func = PyObject_GetAttrString(xml_dom_mod, "parseString");
    if (!func)
        return NULL;

    PyObject *xml_obj = PyObject_CallFunctionObjArgs(func, xml_string, NULL);
    Py_DECREF(func);
    return xml_obj;
}

/* Deserialize a string. */
static PyObject* deserialize_string(DecoderContext *context)
{
    int header = _decode_int(context);

    // Check for null string
    if (header == EMPTY_STRING_TYPE) {
        PyObject *empty_string = PyString_FromStringAndSize(NULL, 0);
        PyObject *return_value = PyUnicode_FromObject(empty_string);
        Py_DECREF(empty_string);
        return return_value;
    }

    // Check for reference
    PyObject *unicode_value = decode_reference(context->string_refs, header);
    if (!unicode_value)
        return NULL;

    if (unicode_value != Py_False) {
        return unicode_value;
    } else {
        Py_DECREF(Py_False);
    }

    // No reference found
    unicode_value = decode_string(context, header >> 1);
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
static PyObject* decode_string(DecoderContext *context, unsigned int string_size)
{
    PyObject *unicode_value = PyUnicode_DecodeUTF8(context->buf + context->pos, string_size, NULL);
    if (!unicode_value)
        return NULL;

    context->pos += string_size;
    return unicode_value;
}

/*
 * Checks a decoded int for the presence of a reference
 *
 * Returns PyObject if object reference was found.
 * returns PyFalse if object reference was not found.
 * returns NULL if call failed.
 */
static PyObject* decode_reference(ObjectContext *object_context, int value)
{
    // Check for index reference
    if ((value & REFERENCE_BIT) == 0) {
        int idx = value >> 1;

        PyObject *ref = get_ref_from_idx(object_context, idx);
        if (!ref)
            return NULL;

        Py_INCREF(ref); // This reference is getting put somewhere, so we need to increase the ref count.
        return ref;
    }

    Py_RETURN_FALSE;
}

/* Decode a double to a native C double. */
static double _decode_double(DecoderContext *context)
{
    // Put bytes from byte array into double
    union aligned {
        double d_value;
        char c_value[8];
    } d;

    if (big_endian) {
        memcpy(d.c_value, context->buf + context->pos, 8);
    } else {
        // Flip endianness
        d.c_value[0] = context->buf[context->pos + 7];
        d.c_value[1] = context->buf[context->pos + 6],
        d.c_value[2] = context->buf[context->pos + 5],
        d.c_value[3] = context->buf[context->pos + 4],
        d.c_value[4] = context->buf[context->pos + 3],
        d.c_value[5] = context->buf[context->pos + 2],
        d.c_value[6] = context->buf[context->pos + 1],
        d.c_value[7] = context->buf[context->pos];
    }
    context->pos += 8;

    return d.d_value;
}

/* Decode a native C unsigned short. */
static unsigned short _decode_ushort(DecoderContext *context)
{
    // Put bytes from byte array into short
    union aligned {
        unsigned short s_value;
        char c_value[2];
    } s;

    if (big_endian) {
        memcpy(s.c_value, context->buf + context->pos, 2);
    } else {
        // Flip endianness
        s.c_value[0] = context->buf[context->pos + 1];
        s.c_value[1] = context->buf[context->pos];
    }
    context->pos += 2;

    return s.s_value;
}

/* Decode a native C unsigned int. */
static unsigned int _decode_ulong(DecoderContext *context)
{
    // Put bytes from byte array into short
    union aligned {
        unsigned int i_value;
        char c_value[4];
    } i;

    if (big_endian) {
        memcpy(i.c_value, context->buf + context->pos, 4);
    } else {
        // Flip endianness
        i.c_value[0] = context->buf[context->pos + 3];
        i.c_value[1] = context->buf[context->pos + 2];
        i.c_value[2] = context->buf[context->pos + 1];
        i.c_value[3] = context->buf[context->pos];
    }
    context->pos += 4;

    return i.i_value;
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
    return PyInt_FromLong((long)_decode_int(context)); 
}

/* Decode an AMF0 Boolean. */
static PyObject* decode_bool_AMF0(DecoderContext *context)
{
    PyObject *boolean;
    if (context->buf[context->pos] == TRUE_AMF0) {
        boolean = Py_True;
    } else {
        boolean = Py_False;
    }

    Py_INCREF(boolean);
    context->pos++;
    return boolean;
}

/* Decode an AMF0 String. */
static PyObject* decode_string_AMF0(DecoderContext *context)
{
   unsigned short string_size = _decode_ushort(context);
   return decode_string(context, (unsigned int)string_size); 
}

/* Decode a long AMF0 String. */
static PyObject* decode_long_string_AMF0(DecoderContext *context)
{
   unsigned int string_size = _decode_ulong(context);
   return decode_string(context, string_size);
}

/* Decode an AMF0 Reference. */
static PyObject* decode_reference_AMF0(DecoderContext *context)
{
    unsigned short idx = _decode_ushort(context);
    return get_ref_from_idx(context->object_refs, (int)idx);
}

/* Decode an AMF0 dict. */
static PyObject* decode_dict_AMF0(DecoderContext *context)
{
    PyObject *obj_value = PyDict_New();
    if (!obj_value)
        return NULL;

    // Add object to reference
    if (!map_next_object_idx(context->object_refs, obj_value)) {
        Py_DECREF(obj_value);
        return NULL;
    }

    if (!_decode_dynamic_dict_AMF0(context, obj_value)) {
        Py_DECREF(obj_value);
        return NULL;
    }

    return obj_value;
}

/* Decode an dynamic AMF0 dict. */
static int _decode_dynamic_dict_AMF0(DecoderContext *context, PyObject *dict)
{
    while (1) {
        PyObject *key = decode_string_AMF0(context);
        if (!key)
            return 0;

        if (context->buf[context->pos] == OBJECT_END_AMF0) {
            context->pos++;
            return 1;
        }

        PyObject *val = _decode_AMF0(context);
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

/* Decode an AMF0 array. */
static PyObject* decode_array_AMF0(DecoderContext *context)
{
    int array_len = _decode_ulong(context);

    PyObject *list_value = PyList_New(array_len);
    if (!list_value)
        return NULL;

    // Reference must be added before children (to allow for recursion).
    if (!map_next_object_idx(context->object_refs, list_value)) {
        Py_DECREF(list_value);
        return NULL;
    }

    // Add each item to the list
    int i;
    for (i = 0; i < array_len; i++) {
        PyObject *value = _decode_AMF0(context);
        if (!value) {
            Py_DECREF(list_value);
            return NULL;
        }
        PyList_SET_ITEM(list_value, i, value);
    }

    return list_value;
}

/* Decode an AMF0 Date. */
static PyObject* decode_date_AMF0(DecoderContext *context)
{
    // TODO: use timezone value to adjust datetime
    PyObject *date_value = decode_date(context);
    int tz = _decode_ushort(context); // timezone value.
    return date_value;
}

/* Decode an AMF0 XML-Doc. */
static PyObject* decode_xml_AMF0(DecoderContext *context)
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

/* Decode AMF0 typed object. */
static PyObject* decode_typed_object_AMF0(DecoderContext *context)
{
    PyObject *alias = decode_string_AMF0(context);
    if (!alias)
        return NULL;

    PyObject *class_def = class_def_from_alias(context, alias);
    Py_DECREF(alias);
    if (!class_def)
        return NULL;

    // Anonymous object.
    if (class_def == Py_None) {
        Py_DECREF(class_def);
        return decode_dict_AMF0(context);
    }

    PyObject *obj_value = PyObject_CallMethod(class_def, "getInstance", NULL);
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

    // Put decoded attributes in this dict
    PyObject *decoded_attrs = PyDict_New();
    if (!decoded_attrs) {
        Py_DECREF(class_def);
        Py_DECREF(obj_value);
        return NULL;
    }

    if (!_decode_dynamic_dict_AMF0(context, decoded_attrs)) {
        Py_DECREF(class_def);
        Py_DECREF(obj_value);
        Py_DECREF(decoded_attrs);
        return NULL;
    }

    // apply attributes
    if (!context->apply_attr_vals_method_name) {
        context->apply_attr_vals_method_name = PyString_FromString("applyAttrVals");
        if (!context->apply_attr_vals_method_name) {
            Py_DECREF(class_def);
            Py_DECREF(obj_value);
            Py_DECREF(decoded_attrs);
            return NULL;
        }
    }

    PyObject *return_value = PyObject_CallMethodObjArgs(class_def, context->apply_attr_vals_method_name, obj_value, decoded_attrs, NULL);
    Py_DECREF(class_def);
    Py_DECREF(decoded_attrs);

    if (!return_value) {
        Py_DECREF(obj_value);
        return NULL;
    }

    Py_DECREF(return_value); // should be Py_None
    return obj_value;
}

/* Decode an AMF0 NetConnection packet. */
static PyObject* _decode_packet(DecoderContext *context)
{
    if (!remoting_mod) {
        remoting_mod = PyImport_ImportModule("amfast.remoting");
        if(!remoting_mod)
            return NULL;
    }

    PyObject *packet_class = PyObject_GetAttrString(remoting_mod, "Packet");
    if (!packet_class)
        return NULL;

    // Set client type
    PyObject *client_type;
    unsigned short amf_version = _decode_ushort(context);
    if (amf_version == FLASH_8) {
        client_type = PyObject_GetAttrString(packet_class, "FLASH_8"); 
    } else if (amf_version == FLASH_COM) {
        client_type = PyObject_GetAttrString(packet_class, "FLASH_COM");
    } else if (amf_version == FLASH_9) {
        client_type = PyObject_GetAttrString(packet_class, "FLASH_9");
    } else {
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
static PyObject* decode_headers_AMF0(DecoderContext *context)
{
    unsigned short header_count = _decode_ushort(context);
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

        int byte_len = _decode_ulong(context); // Byte length of header.

        // We need a new context for each header
        DecoderContext *new_context = _copy_decoder_context(context, 0);
        if (!new_context) {
            Py_DECREF(header_list);
            Py_DECREF(header_name);
            Py_DECREF(required);
            return NULL;
        }

        PyObject *header_obj = _decode_AMF0(new_context);
        context->pos = new_context->pos;

        if (!_destroy_decoder_context(new_context)) {
            Py_DECREF(header_list);
            Py_DECREF(header_name);
            Py_DECREF(required);
            Py_XDECREF(header_obj);
            return NULL;
        }

        if (!header_obj) {
            Py_DECREF(header_list);
            Py_DECREF(header_name);
            Py_DECREF(required);
            return NULL;
        }

        // Create header object
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
static PyObject* decode_messages_AMF0(DecoderContext *context)
{
    unsigned short message_count = _decode_ushort(context);
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

        int byte_len = _decode_ulong(context); // Message byte length

        // We need a new context for each message
        DecoderContext *new_context = _copy_decoder_context(context, 0);
        if (!new_context) {
            Py_DECREF(message_list);
            Py_DECREF(target);
            Py_DECREF(response);
            return NULL;
        }

        PyObject *message_obj = message_obj = _decode_AMF0(new_context);
        context->pos = new_context->pos;

        if (!_destroy_decoder_context(new_context)) {
            Py_DECREF(message_list);
            Py_DECREF(target);
            Py_DECREF(response);
            Py_XDECREF(message_obj);
            return NULL;
        }

        if (!message_obj) {
            Py_DECREF(message_list);
            Py_DECREF(target);
            Py_DECREF(response);
            return NULL;
        }

        // Create message object
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

/* Decode individual AMF0 objects from buffer. */
static PyObject* _decode_AMF0(DecoderContext *context)
{
    if (context->pos > context->buf_len) {
        PyErr_SetString(amfast_DecodeError, "Parsed past end of buffer.");
        return NULL;
    }

    char byte = context->buf[context->pos];

    if (byte == AMF3_AMF0) {
        // AMF3 item requires new reference counts.
        DecoderContext *new_context = _copy_decoder_context(context, 1);
        new_context->pos++;
        PyObject *return_value = _decode(new_context);
        context->pos = new_context->pos;
        _destroy_decoder_context(new_context);
        return return_value;
    } else if (byte == NUMBER_AMF0) {
        context->pos++;
        return decode_double(context);
    } else if (byte == BOOL_AMF0) {
        context->pos++;
        return decode_bool_AMF0(context);
    } else if (byte == STRING_AMF0) {
        context->pos++;
        return decode_string_AMF0(context);
    } else if (byte == NULL_AMF0) {
        context->pos++;
        Py_RETURN_NONE;
    } else if (byte == UNDEFINED_AMF0) {
        context->pos++;
        Py_RETURN_NONE;
    } else if (byte == REF_AMF0) {
        context->pos++;
        return decode_reference_AMF0(context);
    } else if (byte == OBJECT_AMF0) {
        context->pos++;
        return decode_dict_AMF0(context);
    } else if (byte == MIXED_ARRAY_AMF0) {
        context->pos++;
        context->pos += 4; // skip encoded max index
        return decode_dict_AMF0(context);
    } else if (byte == ARRAY_AMF0) {
        context->pos++;
        return decode_array_AMF0(context);
    } else if (byte == LONG_STRING_AMF0) {
        context->pos++;
        return decode_long_string_AMF0(context);
    } else if (byte == DATE_AMF0) {
        context->pos++;
        return decode_date_AMF0(context);
    } else if (byte == XML_DOC_AMF0) {
        context->pos++;
        return decode_xml_AMF0(context);
    } else if (byte == TYPED_OBJ_AMF0) {
        context->pos++;
        return decode_typed_object_AMF0(context);
    }

    char error_str[100];
    sprintf(error_str, "Unknown AMF0 type marker byte: '%X' at position: %d", byte, context->pos);
    PyErr_SetString(amfast_DecodeError, error_str);
    return NULL;
}

/* Decode individual AMF3 objects from buffer. */
static PyObject* _decode(DecoderContext *context)
{
    if (context->pos > context->buf_len) {
        PyErr_SetString(amfast_DecodeError, "Parsed past end of buffer.");
        return NULL;
    }

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

    char error_str[100];
    sprintf(error_str, "Unknown AMF3 type marker byte: '%X' at position: %d", byte, context->pos);
    PyErr_SetString(amfast_DecodeError, error_str);
    return NULL;
}

/* Decode an AMF buffer to Python object. */
static PyObject* decode(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *value;
    PyObject *class_def_mapper = Py_None;
    Py_INCREF(class_def_mapper);
    int packet = 0;
    int amf3 = 0;

    static char *kwlist[] = {"value", "packet", "amf3", "class_def_mapper", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|iiO", kwlist,
        &value, &packet, &amf3, &class_def_mapper))
        return NULL;

    DecoderContext *context = _create_decoder_context(amf3);
    if (!context) {
        Py_DECREF(class_def_mapper);
        return NULL;
    }

    context->buf_len = (int)PyString_GET_SIZE(value);
    context->buf = PyString_AsString(value);
    if (!context->buf) {
        Py_DECREF(class_def_mapper);
        _destroy_decoder_context(context);
        return NULL;
    }

    // Set defaults
    if (class_def_mapper != Py_None) {
        // Use user supplied ClassDefMapper.
        context->class_def_mapper = class_def_mapper;
        Py_INCREF(context->class_def_mapper);
        Py_DECREF(Py_None);
    } else {
        // Create anonymous ClassDefMapper
        Py_DECREF(Py_None);
        if (!class_def_mod) {
            class_def_mod = PyImport_ImportModule("amfast.class_def");
            if(!class_def_mod) {
                _destroy_decoder_context(context);
                return NULL;
            }
        }

        PyObject *class_def = PyObject_GetAttrString(class_def_mod, "ClassDefMapper");
        if (!class_def) {
            _destroy_decoder_context(context);
            return NULL;
        }

        context->class_def_mapper = PyObject_CallFunctionObjArgs(class_def, NULL);
        Py_DECREF(class_def);
        if (!context->class_def_mapper) {
            _destroy_decoder_context(context);
            return NULL;
        }
    }

    PyObject *return_value;
    if (packet) {
        return_value = _decode_packet(context);
    } else if (amf3) {
        return_value = _decode(context);
    } else {
        return_value = _decode_AMF0(context);
    }

    _destroy_decoder_context(context);
    return return_value;
}

/* Expose functions as Python module functions. */
static PyMethodDef decoder_methods[] = {
    {"decode", (PyCFunction)decode, METH_VARARGS | METH_KEYWORDS,
    "Description:\n"
    "=============\n"
    "Decode an AMF stream to Python objects.\n\n"
    "Useage:\n"
    "===========\n"
    "py_obj = decode(value, **kwargs)\n\n"
    "Optional keyword arguments:\n"
    "============================\n"
    " * packet - bool - True to decode as an AMF NetConnection packet (decode a remoting call). - Default = False\n"
    " * amf3 - bool - True to decode as AMF3 format. - Default = False\n"
    " * class_def_mapper - ClassDefMapper - object that retrieves ClassDef objects used for customizing \n"
    "    de-serialization of objects - Default = None (all objects are anonymous)\n"},
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

    // Determine endianness of architecture
    if (is_bigendian()) {
        big_endian = 1;
    } else {
        big_endian = 0;
    }

    // Setup date time API
    PyDateTime_IMPORT;
}
