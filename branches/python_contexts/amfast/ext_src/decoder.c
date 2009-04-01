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
static PyObject *as_types_mod;
static PyObject *amfast_Error;
static PyObject *amfast_DecodeError;
static int big_endian; // Flag == 1 if architecture is big_endian, == 0 if not

// ---- CONTEXT

typedef struct {
    PyObject *decoder_context; // amfast.context.DecoderContext
    PyObject *i_stream; // Input stream obj
    PyObject *i_read; // Input stream read method
    PyObject *_buf_str; // Current string buffer
    PyObject *class_mapper; // Object that retrieves class defs.
    PyObject *string_refs; // Keep track of string references
    PyObject *obj_refs; // Keep track of obj references
    PyObject *class_refs; // Keep track of class definitions references
    PyObject *map_name; // PyString name of method that maps an obj to an index
    PyObject *ret_name; // PyString name of method that retrieves an obj from an index
    PyObject *apply_name; // PyString name of method that applies attributes to objects
    PyObject *class_def_name; // PyString name of method to retrieve a ClassDef
} Context;

static Context* create_context(PyObject *decoder_context, short init);
static int init_context(Context *context);
static Context* copy_context(Context *context, short amf3);
static const char* read_c_str(Context *context, long length);
static PyObject* read_py_str(Context *context, long length);
static char read_byte(Context *context);
static long tell(Context *context);
static int destroy_context(Context *context);
static int map_idx(Context *context, PyObject *obj_context, PyObject* val);
static PyObject* ret_obj(Context *context, PyObject *obj_context, long idx);

// ---- DECODING

/*
 * deserialize... functions de-reference and decode.
 * decode... functions decode from AMF to Python.
 *
 * functions starting with '_' return a C value.
 */

// COMMON
static unsigned short _decode_ushort(Context *context);
static unsigned int _decode_ulong(Context *context);
static double _decode_double(Context *context);
static PyObject* decode_double(Context *context);
static PyObject* decode_string(Context *context, unsigned int string_size);
static PyObject* decode_date(Context *context);
static PyObject* decode_packet(Context *context);
static PyObject* xml_from_string(PyObject *xml_string);
static PyObject* byte_array_from_string(PyObject *byte_string);
static PyObject* class_def_from_alias(Context *context, PyObject *alias);

// AMF0
static PyObject* decode_AMF0(Context *context);
static PyObject* decode_bool_AMF0(Context *context);
static PyObject* decode_string_AMF0(Context *context);
static PyObject* decode_long_string_AMF0(Context *context);
static PyObject* decode_reference_AMF0(Context *context);
static PyObject* decode_dict_AMF0(Context *context);
static int decode_dynamic_dict_AMF0(Context *context, PyObject *dict);
static PyObject* decode_array_AMF0(Context *context, short map_reference);
static PyObject* decode_date_AMF0(Context *context);
static PyObject* decode_xml_AMF0(Context *context);
static PyObject* decode_typed_obj_AMF0(Context *context);
static PyObject* decode_headers_AMF0(Context *context);
static PyObject* decode_messages_AMF0(Context *context);

// AMF3
static PyObject* decode_reference_AMF3(Context *context, PyObject *obj_context, int val);
static int decode_dynamic_dict_AMF3(Context *context, PyObject *dict);
static PyObject* decode_int_AMF3(Context *context);
static int _decode_int_AMF3(Context *context);
static PyObject* deserialize_string_AMF3(Context *context);
static PyObject* deserialize_array_AMF3(Context *context, int collection);
static int decode_dynamic_array_AMF3(Context *context, PyObject *list_val, int array_len);
static PyObject* deserialize_xml_AMF3(Context *context);
static PyObject* deserialize_byte_array_AMF3(Context *context);
static PyObject* decode_byte_array_AMF3(Context *context, int byte_len);
static PyObject* deserialize_obj_AMF3(Context *context, int proxy);
static PyObject* deserialize_class_def_AMF3(Context *context, int header);
static PyObject* decode_class_def_AMF3(Context *context, int header);
static int decode_typed_obj_AMF3(Context *context, PyObject *obj_val, PyObject *class_def_dict);
//static int decode_externizeable_AMF3(Context *context, PyObject *obj_val, PyObject *class_def);
static PyObject* decode_obj_attrs_AMF3(Context *context, PyObject *class_def_dict);
static int decode_anon_obj_AMF3(Context *context, PyObject *obj_val, PyObject *class_def_dict);
static PyObject* decode_AMF3(Context *context);

// Python EXPOSED FUNCTIONS
static PyObject* decode(PyObject *self, PyObject *args, PyObject *kwargs);

// ------------------------ DECODING CONTEXT ------------------------ //

/* Create a new Context. */
static Context* create_context(PyObject *decoder_context, short init)
{
    if (!decoder_context)
        return NULL;

    Context *context;
    context = (Context*)malloc(sizeof(Context));
    if (!context) {
        PyErr_SetNone(PyExc_MemoryError);
        return NULL;
    }

    // Set refs to NULL
    context->decoder_context = NULL;
    context->i_stream = NULL;
    context->i_read = NULL;
    context->_buf_str = NULL;
    context->class_mapper = NULL;
    context->obj_refs = NULL;
    context->string_refs = NULL;
    context->class_refs = NULL;
    context->map_name = NULL;
    context->ret_name = NULL;
    context->apply_name = NULL;
    context->class_def_name = NULL;

    // Set information from DecoderContext
    context->decoder_context = decoder_context;
    context->i_stream = PyObject_GetAttrString(decoder_context, "file_obj");
    if (!context->i_stream) {
        destroy_context(context);
        return NULL;
    }
    context->i_read = PyObject_GetAttrString(context->i_stream, "read");
    if (!context->i_read) {
        destroy_context(context);
        return NULL;
    }

    context->class_mapper = PyObject_GetAttrString(decoder_context, "class_def_mapper");
    if (!context->class_mapper) {
        destroy_context(context);
        return NULL;
    }
    context->obj_refs = PyObject_GetAttrString(decoder_context, "object_context");
    if (!context->obj_refs) {
        destroy_context(context);
        return NULL;
    }

    // Only get these vals if it is an AMF3 decoder.
    PyObject *amf3 = PyObject_GetAttrString(decoder_context, "amf3");
    if (!amf3) {
        destroy_context(context);
        return NULL;
    }

    if (amf3 == Py_True) {
        context->string_refs = PyObject_GetAttrString(decoder_context, "string_context");
        if (!context->string_refs) {
            destroy_context(context);
            return NULL;
        }
        context->class_refs = PyObject_GetAttrString(decoder_context, "class_context");
        if (!context->class_refs) {
            destroy_context(context);
            return NULL;
        }
    }
    Py_DECREF(amf3);

    if (init) {
        if (!init_context(context)) {
            destroy_context(context);
            return NULL;
        }
    }

    return context;
}

/* Add optional information to a context. */
static int init_context(Context *context)
{
    context->map_name = PyString_InternFromString("mapObject");
    if (!context->map_name)
        return 0;

    context->ret_name = PyString_InternFromString("getObject");
    if (!context->ret_name)
        return 0;

    context->apply_name = PyString_InternFromString("applyAttrVals");
    if (!context->apply_name) 
        return 0;

    context->class_def_name = PyString_InternFromString("getClassDefByAlias");
    if (!context->class_def_name)
        return 0;

    return 1;
}

/*
 * Creates a new context with the same stream and options,
 * but with new reference counts.
 */
static Context* copy_context(Context *context, short amf3)
{
    PyObject *copy = PyObject_GetAttrString(context->decoder_context, "copy");
    if (!copy)
        return NULL;

    PyObject *py_amf3;
    if (amf3) {
        py_amf3 = Py_True;
    } else {
        py_amf3 = Py_False;
    }

    PyObject *decoder_context = PyObject_CallMethodObjArgs(copy, py_amf3, NULL);
    Py_DECREF(copy);
    if (!decoder_context)
        return NULL;

    Context *new_context = create_context(decoder_context, 0);
    if (!new_context)
        return NULL;

    // Copy init properties over
    // instead of re-creating
    new_context->map_name = context->map_name;
    Py_INCREF(new_context->map_name);
    new_context->ret_name = context->ret_name;
    Py_INCREF(new_context->ret_name);
    new_context->apply_name = context->apply_name;
    Py_INCREF(new_context->apply_name);
    new_context->class_def_name = context->class_def_name;
    Py_INCREF(new_context->class_def_name);

    return new_context;
}

/* De-allocate a Context. */
static int destroy_context(Context *context)
{
    // Set refs to NULL
    Py_XDECREF(context->decoder_context);
    Py_XDECREF(context->i_stream);
    Py_XDECREF(context->i_read);
    Py_XDECREF(context->_buf_str);
    Py_XDECREF(context->class_mapper);
    Py_XDECREF(context->obj_refs);
    Py_XDECREF(context->string_refs);
    Py_XDECREF(context->class_refs);
    Py_XDECREF(context->map_name);
    Py_XDECREF(context->ret_name);
    Py_XDECREF(context->apply_name);
    Py_XDECREF(context->class_def_name);

    free(context);
    return 1;
}

/* Map a val to an index. */
static int map_idx(Context *context, PyObject *obj_context, PyObject *val)
{
    PyObject *result = PyObject_CallMethodObjArgs(obj_context, context->map_name, val, NULL);
    if (!result)
        return 0;

    Py_DECREF(result);
    return 1;
}

/* Retrieve and indexed value. */
static PyObject* ret_obj(Context *context, PyObject *obj_context, long idx)
{
    PyObject *py_idx = PyInt_FromLong(idx);
    PyObject *result = PyObject_CallMethodObjArgs(obj_context, context->ret_name, py_idx, NULL);
    Py_DECREF(py_idx);
    return result;
}

/* 
 * Returns position in stream.
 */
static long tell(Context *context)
{
    PyObject *pos = PyObject_CallMethod(context->i_stream, "tell", NULL);
    if (!pos)
        return -1;

    long result = PyInt_AsLong(pos);
    Py_DECREF(pos);
    return result;
}

/* 
 * Read a PyString from the context.
 *
 * Returns a borrowed reference.
 */
static PyObject* read_py_str(Context *context, long length)
{
    PyObject *tmp = context->_buf_str;
    PyObject *py_length = PyInt_FromLong(length);
    if (!py_length)
        return NULL;
    context->_buf_str = PyObject_CallFunctionObjArgs(context->i_read, py_length, NULL);
    Py_DECREF(py_length);
    Py_XDECREF(tmp); // Decrement reference to OLD string.
    return context->_buf_str;
}

/* Read a string from the context. */
static const char* read_c_str(Context *context, long length)
{
    PyObject* py_str = read_py_str(context, length);
    if (!py_str)
        return NULL;
    return PyString_AsString(py_str);
}

/* Reads a single byte from the context. */
static char read_byte(Context *context)
{
    const char *str = read_c_str(context, 1);
    return str[0];
}

// ------------------------ DECODING --------------------------------- //

/*
 * Deserialize an obj.
 *
 * proxy is flag indicating that the obj being deserialized is within an ObjectProxy
 */
static PyObject* deserialize_obj_AMF3(Context *context, int proxy)
{
    int header = _decode_int_AMF3(context);

    // Check for obj reference
    PyObject *obj_val = decode_reference_AMF3(context, context->obj_refs, header);
    if (!obj_val)
        return NULL;

    if (obj_val != Py_False) {
        // Ref found
        if (proxy) {
            // Map ObjectProxy idx to ref, since
            // it points to the same obj.
            if (!map_idx(context, context->obj_refs, obj_val)) {
                Py_DECREF(obj_val);
                return NULL;
            }
        }
        return obj_val;
    } else {
        Py_DECREF(Py_False);
    }

    // Ref not found
    // Create instance based on class def
    // class_def_dict ref belongs to the context
    PyObject *class_def_dict = deserialize_class_def_AMF3(context, header);
    if (!class_def_dict)
        return NULL;

    PyObject *class_def = PyDict_GetItemString(class_def_dict, "class_def");
    if (!class_def)
        return NULL;

    int obj_type; // 0 = anonymous, 1 == externizeable, 2 == typed
    if (class_def == Py_None) {
        // Anonymous obj.
        obj_type = 0;
    } else if (PyObject_HasAttrString(class_def, "EXTERNIZEABLE_CLASS_DEF")) {
        // Check for special ArrayCollection and ObjectProxy types
        if (PyObject_HasAttrString(class_def, "ARRAY_COLLECTION_CLASS_DEF")) {
            //TODO
            //context->pos++; // Skip Array MarkerType
            return deserialize_array_AMF3(context, 1);
        }

        if (PyObject_HasAttrString(class_def, "OBJECT_PROXY_CLASS_DEF")) {
            // TODO
            //context->pos++; // Skip Object MarkerType
            return deserialize_obj_AMF3(context, 1);
        }

        obj_type = 1;
    } else {
        obj_type = 2;
    }

    // Instantiate new obj
    if (!obj_type) {
        // Anonymous obj == dict
        obj_val = PyDict_New();
    } else {
        // Create obj_val for all typed objs.
        obj_val = PyObject_CallMethod(class_def, "getInstance", NULL);
    }
    
    if (!obj_val)
        return NULL;

    // Reference must be added before children (to allow for recursion).
    if (!map_idx(context, context->obj_refs, obj_val)) {
        Py_DECREF(obj_val);
        return NULL;
    }

    // If this is an ObjectProxy,
    // we need to add another reference,
    // so there is one that
    // points to the obj and one that points
    // to the proxy.
    if (proxy) {
        if (!map_idx(context, context->obj_refs, obj_val)) {
            Py_DECREF(obj_val);
            return NULL;
        }
    }

    int return_val = 0;
    if (obj_type == 0) {
        return_val = decode_anon_obj_AMF3(context, obj_val, class_def_dict);
    } else if (obj_type == 1) {
        //return_val = decode_externizeable_AMF3(context, obj_val, class_def);
    } else if (obj_type == 2) {
        return_val = decode_typed_obj_AMF3(context, obj_val, class_def_dict);
    }

    if (!return_val) {
        Py_DECREF(obj_val);
        return NULL;
    }

    return obj_val;
}

/* Decode an anonymous obj. */
static int decode_anon_obj_AMF3(Context *context, PyObject *obj_val, PyObject *class_def_dict)
{
    PyObject *decoded_attrs = decode_obj_attrs_AMF3(context, class_def_dict);
    if (!decoded_attrs) {
        return 0;
    }

    int return_val = PyDict_Merge(obj_val, decoded_attrs, 1);
    Py_DECREF(decoded_attrs);
    if (return_val == -1)
        return 0;
    return 1;
}

/* Returns a dict with vals from an obj. */
static PyObject* decode_obj_attrs_AMF3(Context *context, PyObject *class_def_dict)
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
        if (!obj) {
            Py_DECREF(decoded_attrs);
            return NULL;
        }

        PyObject *attr_name = PyTuple_GET_ITEM(static_attrs, i);
        if (!attr_name) {
            Py_DECREF(decoded_attrs);
            return NULL;
        }

        int return_val = PyDict_SetItem(decoded_attrs, attr_name, obj);
        Py_DECREF(obj);

        if (return_val == -1) {
            Py_DECREF(decoded_attrs);
            return NULL;
        }
    }

    // Decode dynamic attrs
    PyObject *dynamic = PyDict_GetItemString(class_def_dict, "dynamic");
    if (!dynamic)
        return NULL;

    if (dynamic == Py_True) {
        if (!decode_dynamic_dict_AMF3(context, decoded_attrs)) {
            Py_DECREF(decoded_attrs);
            return NULL;
        }
    }
    return decoded_attrs;
}

/* Decode a typed obj. */
static int decode_typed_obj_AMF3(Context *context, PyObject *obj_val, PyObject *class_def_dict)
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

    PyObject *return_val = PyObject_CallMethodObjArgs(class_def, context->apply_name, obj_val, decoded_attrs, NULL);
    Py_DECREF(decoded_attrs);

    if (!return_val)
        return 0;

    Py_DECREF(return_val); // should be Py_None
    return 1;
}

/* Decode an EXTERNIZEABLE obj. */
/*static int decode_externizeable_AMF3(Context *context, PyObject *obj_val, PyObject *class_def)
{
    PyObject *method_name = PyString_FromString("readByteString");
    if (!method_name)
        return 0;

    // Read bytes
    size_t byte_len = context->buf_len;
    byte_len -= context->pos;
    char char_val[byte_len];
    memcpy(char_val, context->buf + context->pos, byte_len);

    PyObject *byte_array;

    #ifdef Py_BYTEARRAYOBJECT_H
    // ByteArray decoding is only available in 2.6+
    byte_array = PyByteArray_FromStringAndSize(char_val, (Py_ssize_t)byte_len);
    #else
    byte_array = PyString_FromStringAndSize(char_val, (Py_ssize_t)byte_len);
    #endif

    if (!byte_array) {
        Py_DECREF(method_name);
        return 0;
    }

    PyObject *parsed_len = PyObject_CallMethodObjArgs(class_def, method_name, obj_val, byte_array, NULL);
    Py_DECREF(method_name);
    Py_DECREF(byte_array);

    if (!parsed_len)
        return 0;

    context->pos = (int)(PyInt_AsLong(parsed_len) + 1);
    Py_DECREF(parsed_len);
    return 1; 
}*/

/*
 * Deserialize a ClassDef.
 *
 * header argument is the parsed obj header.
 */
static PyObject* deserialize_class_def_AMF3(Context *context, int header)
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
    if (!map_idx(context, context->class_refs, class_def_dict))
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
static PyObject* decode_class_def_AMF3(Context *context, int header)
{
    PyObject *alias = deserialize_string_AMF3(context);
    if (!alias)
        return NULL;

    PyObject *class_def;
    if (PySequence_Size(alias) == 0) {
        // This is an anonymous obj.
        class_def = Py_None;
        Py_INCREF(class_def);
    } else {
        // This is a typed obj.
        class_def = class_def_from_alias(context, alias);
    }
    Py_DECREF(alias);
    if (!class_def) 
        return NULL;

    // Create a dict with class def information
    // specific to this decode context.
    PyObject *class_def_dict = PyDict_New();
    if (!class_def_dict) {
        Py_DECREF(class_def);
        return NULL;
    }

    if (PyDict_SetItemString(class_def_dict, "class_def", class_def)  == -1) {
        Py_DECREF(class_def_dict);
        Py_DECREF(class_def);
        return NULL;
    }

    // Check for or externizeable obj
    int externizeable = PyObject_HasAttrString(class_def, "EXTERNIZEABLE_CLASS_DEF");
    if (externizeable) {
        // There is nothing else we need to do
        // with this ClassDef
        Py_DECREF(class_def); // class_def_dict has reference now.
        return class_def_dict;
    }

    // If the class is externizeable, but the ClassDef isn't,
    // we have a big problem.
    if ((header & 0x07FFFFFF) == EXTERNIZEABLE) {
        // Get alias as C-String for error handling
        PyObject *alias_str = PyObject_GetAttrString(class_def, "alias");
        Py_DECREF(class_def);
        Py_DECREF(class_def_dict);
        if (!alias_str)
            return NULL;
        char *alias_char = PyString_AsString(alias_str);
        Py_DECREF(alias_str);

        char error_str[512];
        sprintf(error_str, "Encoded class '%s' is externizeable, but ClassDef is not.", alias_char);
        PyErr_SetString(amfast_DecodeError, error_str);
        return NULL;
    }
    Py_DECREF(class_def); // class_def_dict has reference now.

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

    // Decode static attrs
    int static_attr_len = header >> 4;

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
    int return_val = PyDict_SetItemString(class_def_dict, "static_attrs", decoded_attrs);
    Py_DECREF(decoded_attrs);
    if (return_val == -1) {
        Py_DECREF(class_def_dict);
        return NULL;
    }

    return class_def_dict;
}

/* Retrieve a ClassDef from a class alias string. */
static PyObject* class_def_from_alias(Context *context, PyObject *alias)
{
    // Check for empty string (anonymous obj)
    if (PyUnicode_GET_SIZE(alias) == 0) {
        Py_RETURN_NONE;
    }

    PyObject *return_val = PyObject_CallMethodObjArgs(context->class_mapper, context->class_def_name, alias, NULL);

    // Raise exception if class is not mapped.
    if (return_val == Py_None) {
        PyObject *error_title = PyString_FromString("Class alias not mapped: ");
        PyObject *error_str = PyUnicode_Concat(error_title, alias);
        PyErr_SetObject(amfast_DecodeError, error_str);
        Py_DECREF(error_title);
        Py_DECREF(error_str);
        Py_DECREF(return_val);
        return NULL;
    }

    return return_val;
}

/* Add the dynamic attributes of an encoded obj to a dict. */
static int decode_dynamic_dict_AMF3(Context *context, PyObject *dict)
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
static PyObject* deserialize_array_AMF3(Context *context, int collection)
{
    int header = _decode_int_AMF3(context);

    // Check for reference
    PyObject *list_val = decode_reference_AMF3(context, context->obj_refs, header);
    if (!list_val)
        return NULL;

    if (list_val != Py_False) {
        // Ref found
        if (collection) {
            // Map ArrayCollection idx to ref, since
            // it points to the same list.
            if (!map_idx(context, context->obj_refs, list_val)) {
                Py_DECREF(list_val);
                return NULL;
            }
        }
        return list_val;
    } else {
        Py_DECREF(Py_False);
    }

    // Create list of correct length
    int array_len = header >> 1;
    /*
     * TODO
    if (context->buf[context->pos] == EMPTY_STRING_TYPE) {
        // Regular array
        list_val = PyList_New(array_len);
    } else {
        // Associative array
        list_val = PyDict_New();
    }
    if (!list_val)
        return NULL;
    */
    return NULL;

    // Reference must be added before children (to allow for recursion).
    if (!map_idx(context, context->obj_refs, list_val)) {
        Py_DECREF(list_val);
        return NULL;
    }

    // If this is an ArrayCollection,
    // we need to add another reference,
    // so there is one that
    // points to the array and one that points
    // to the collection.
    if (collection) {
        if (!map_idx(context, context->obj_refs, list_val)) {
            Py_DECREF(list_val);
            return NULL;
        }
    }

    // Populate list
    if (!decode_dynamic_array_AMF3(context, list_val, array_len)) {
        Py_DECREF(list_val);
        return NULL;
    }

    return list_val;
}

/* Populate an array with vals from the buffer. */
static int decode_dynamic_array_AMF3(Context *context, PyObject *list_val, int array_len)
{
    int assoc = 0;
    /*
     * TODO
    if (context->buf[context->pos] == EMPTY_STRING_TYPE) {
        // Regular array.
        assoc = 0;
        context->pos++;
    } else {
        if (!decode_dynamic_dict_AMF3(context, list_val))
            return 0;
        assoc = 1;
    }*/

    // Add each item to the list
    int i;
    if (assoc) {
        for (i = 0; i < array_len; i++) {
            PyObject *val = decode_AMF3(context);
            if (!val)
                return 0;

            PyObject *key = PyInt_FromLong((long)i);
            if (!key) {
               Py_DECREF(val);
               return 0;
            }

            int return_val = PyDict_SetItem(list_val, key, val);
            Py_DECREF(val);
            Py_DECREF(key);
            if (return_val == -1)
                return 0;
        }
    } else {
        for (i = 0; i < array_len; i++) {
            PyObject *val = decode_AMF3(context);
            if (!val)
                return 0;
            PyList_SET_ITEM(list_val, i, val);
        }
    }

    return 1;
}

/* Deserialize date. */
static PyObject* deserialize_date(Context *context)
{
    int header = _decode_int_AMF3(context);

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
    if (!map_idx(context, context->obj_refs, date_val)) {
        Py_DECREF(date_val);
        return NULL;
    }

    return date_val;
}

/* Decode a date. */
static PyObject* decode_date(Context *context)
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
static PyObject* deserialize_byte_array_AMF3(Context *context)
{
    int header = _decode_int_AMF3(context);

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
    if (!map_idx(context, context->obj_refs, byte_array_val)) {
        Py_DECREF(byte_array_val);
        return NULL;
    }

    return byte_array_val;
}

/* Decode a byte array. */
static PyObject* decode_byte_array_AMF3(Context *context, int byte_len)
{
    PyObject *byte_array_val;
    PyObject *str_val = read_py_str(context, (long)byte_len);
    if (!str_val)
        return NULL;

    #ifdef Py_BYTEARRAYOBJECT_H
    byte_array_val = PyByteArray_FromObject(str_val);
    #else
    byte_array_val = byte_array_from_string(str_val);
    #endif

    return byte_array_val;
}

/* Deserialize an XML Doc. */
static PyObject* deserialize_xml_AMF3(Context *context)
{
    int header = _decode_int_AMF3(context);

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
    if (!map_idx(context, context->obj_refs, xml_val)) {
        Py_DECREF(xml_val);
        return NULL;
    }

    return xml_val;
}

/* Create an XML val from a string. */
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

/* Create an AsByteArray from a string. */
static PyObject* byte_array_from_string(PyObject *byte_string)
{
    if (!as_types_mod) {
        // Import amfast.class_def.as_types
        as_types_mod = PyImport_ImportModule("amfast.class_def.as_types");
        if (!as_types_mod)
            return NULL;
    }

    PyObject *class_ = PyObject_GetAttrString(as_types_mod, "AsByteArray");
    if (!class_)
        return NULL;

    PyObject *obj = PyObject_CallFunctionObjArgs(class_, byte_string, NULL);
    Py_DECREF(class_);
    return obj;
}

/* Deserialize a string. */
static PyObject* deserialize_string_AMF3(Context *context)
{
    int header = _decode_int_AMF3(context);

    // Check for null string
    if (header == EMPTY_STRING_TYPE) {
        PyObject *empty_string = PyString_FromStringAndSize(NULL, 0);
        PyObject *return_val = PyUnicode_FromObject(empty_string);
        Py_DECREF(empty_string);
        return return_val;
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
    if (!map_idx(context, context->string_refs, unicode_val)) {
        Py_DECREF(unicode_val);
        return NULL;
    }

    return unicode_val;
}

/* Decode a string. */
static PyObject* decode_string(Context *context, unsigned int string_size)
{
    const char *str = read_c_str(context, (long)string_size);
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
static PyObject* decode_reference_AMF3(Context *context, PyObject *obj_context, int val)
{
    // Check for index reference
    if ((val & REFERENCE_BIT) == 0) {
        int idx = val >> 1;
        PyObject *ref = ret_obj(context, obj_context, (long)idx);
        if (!ref)
            return NULL;

        Py_INCREF(ref); // This reference is getting put somewhere, so we need to increase the ref count.
        return ref;
    }

    Py_RETURN_FALSE;
}

/* Decode a double to a native C double. */
static double _decode_double(Context *context)
{
    const char *bytes = read_c_str(context, 8);

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

    return d.d_val;
}

/* Decode a native C unsigned short. */
static unsigned short _decode_ushort(Context *context)
{
    const char *bytes = read_c_str(context, 2);

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

    return s.s_val;
}

/* Decode a native C unsigned int. */
static unsigned int _decode_ulong(Context *context)
{
    const char *bytes = read_c_str(context, 4);

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

    return i.i_val;
}

/* Decode a double to a PyFloat. */
static PyObject* decode_double(Context *context)
{
    return PyFloat_FromDouble(_decode_double(context));
}

/* Decode an int to a native C int. */
static int _decode_int_AMF3(Context *context)
{
    int result = 0;
    int byte_cnt = 0;
    char byte = read_byte(context);

    // If 0x80 is set, int includes the next byte, up to 4 total bytes
    while ((byte & 0x80) && (byte_cnt < 3)) {
        result <<= 7;
        result |= byte & 0x7F;
        byte = read_byte(context);
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

    return result;
}

/* Decode an int to a PyInt. */
static PyObject* decode_int_AMF3(Context *context)
{
    return PyInt_FromLong((long)_decode_int_AMF3(context)); 
}

/* Decode an AMF0 Boolean. */
static PyObject* decode_bool_AMF0(Context *context)
{
    PyObject *boolean;
    char byte = read_byte(context);

    if (byte == TRUE_AMF0) {
        boolean = Py_True;
    } else {
        boolean = Py_False;
    }

    Py_INCREF(boolean);
    return boolean;
}

/* Decode an AMF0 String. */
static PyObject* decode_string_AMF0(Context *context)
{
   unsigned short string_size = _decode_ushort(context);
   return decode_string(context, (unsigned int)string_size); 
}

/* Decode a long AMF0 String. */
static PyObject* decode_long_string_AMF0(Context *context)
{
   unsigned int string_size = _decode_ulong(context);
   return decode_string(context, string_size);
}

/* Decode an AMF0 Reference. */
static PyObject* decode_reference_AMF0(Context *context)
{
    unsigned short idx = _decode_ushort(context);
    PyObject *ref = ret_obj(context, context->obj_refs, (long)idx);

    if (!ref)
        return NULL;

    Py_INCREF(ref); // This reference is getting put somewhere, so we need to increase the ref count.
    return ref;
}

/* Decode an AMF0 dict. */
static PyObject* decode_dict_AMF0(Context *context)
{
    PyObject *obj_val = PyDict_New();
    if (!obj_val)
        return NULL;

    // Add obj to reference
    if (!map_idx(context, context->obj_refs, obj_val)) {
        Py_DECREF(obj_val);
        return NULL;
    }

    if (!decode_dynamic_dict_AMF0(context, obj_val)) {
        Py_DECREF(obj_val);
        return NULL;
    }

    return obj_val;
}

/* Decode an dynamic AMF0 dict. */
static int decode_dynamic_dict_AMF0(Context *context, PyObject *dict)
{
    while (1) {
        PyObject *key = decode_string_AMF0(context);
        if (!key)
            return 0;

        if (PyUnicode_GET_SIZE(key) == 0) {
            // End of array.
            PyObject *str = read_py_str(context, 1); // Skip end marker
            return 1;
        }

        PyObject *val = decode_AMF0(context);
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
 * Decode an AMF0 array.
 *
 * If the map_reference property is not 0, a reference for this list
 * is added to the context. If the array being decoded is the body
 * of a NetConnection message, map_reference should be 0.
 *
 */
static PyObject* decode_array_AMF0(Context *context, short map_reference)
{
    unsigned int array_len = _decode_ulong(context);

    PyObject *list_val = PyList_New(array_len);
    if (!list_val)
        return NULL;

    if (map_reference) {
        // Reference must be added before children (to allow for recursion).
        if (!map_idx(context, context->obj_refs, list_val)) {
            Py_DECREF(list_val);
            return NULL;
        }
    }

    // Add each item to the list
    int i;
    for (i = 0; i < array_len; i++) {
        PyObject *val = decode_AMF0(context);
        if (!val) {
            Py_DECREF(list_val);
            return NULL;
        }
        PyList_SET_ITEM(list_val, i, val);
    }

    return list_val;
}

/* Decode an AMF0 Date. */
static PyObject* decode_date_AMF0(Context *context)
{
    // TODO: use timezone val to adjust datetime
    PyObject *date_val = decode_date(context);
    int tz = _decode_ushort(context); // timezone val.

    // Add date to reference count
    if (!map_idx(context, context->obj_refs, date_val)) {
        Py_DECREF(date_val);
        return NULL;
    }

    return date_val;
}

/* Decode an AMF0 XML-Doc. */
static PyObject* decode_xml_AMF0(Context *context)
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
static PyObject* decode_typed_obj_AMF0(Context *context)
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
    if (!map_idx(context, context->obj_refs, obj_val)) {
        Py_DECREF(class_def);
        Py_DECREF(obj_val);
        return NULL;
    }

    // Put decoded attributes in this dict
    PyObject *decoded_attrs = PyDict_New();
    if (!decoded_attrs) {
        Py_DECREF(class_def);
        Py_DECREF(obj_val);
        return NULL;
    }

    if (!decode_dynamic_dict_AMF0(context, decoded_attrs)) {
        Py_DECREF(class_def);
        Py_DECREF(obj_val);
        Py_DECREF(decoded_attrs);
        return NULL;
    }

    PyObject *return_val = PyObject_CallMethodObjArgs(class_def, context->apply_name, obj_val, decoded_attrs, NULL);
    Py_DECREF(class_def);
    Py_DECREF(decoded_attrs);

    if (!return_val) {
        Py_DECREF(obj_val);
        return NULL;
    }

    Py_DECREF(return_val); // should be Py_None
    return obj_val;
}

/* Decode an AMF0 NetConnection packet. */
static PyObject* decode_packet(Context *context)
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
static PyObject* decode_headers_AMF0(Context *context)
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

        unsigned int byte_len = _decode_ulong(context); // Byte length of header.

        // We need a new context for each header
        Context *new_context = copy_context(context, 0);
        if (!new_context) {
            Py_DECREF(header_list);
            Py_DECREF(header_name);
            Py_DECREF(required);
            return NULL;
        }

        PyObject *header_obj = decode_AMF0(new_context);

        if (!destroy_context(new_context)) {
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
static PyObject* decode_messages_AMF0(Context *context)
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

        unsigned int byte_len = _decode_ulong(context); // Message byte length

        // We need a new context for each message
        Context *new_context = copy_context(context, 0);
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
            PyObject *str = read_py_str(new_context, 1); // Skip array marker
            message_obj = decode_array_AMF0(new_context, 0);
        } else {
            message_obj = decode_AMF0(new_context);
        }

        if (!destroy_context(new_context)) {
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
static PyObject* decode_AMF0(Context *context)
{
    const char byte = read_byte(context);

    if (byte == AMF3_AMF0) {
        // AMF3 item requires new reference counts.
        Context *new_context = copy_context(context, 1);
        PyObject *return_val = decode_AMF3(new_context);
        if (!destroy_context(new_context)) {
            return_val = NULL;
        }
        return return_val;
    } else if (byte == NUMBER_AMF0) {
        return decode_double(context);
    } else if (byte == BOOL_AMF0) {
        return decode_bool_AMF0(context);
    } else if (byte == STRING_AMF0) {
        return decode_string_AMF0(context);
    } else if (byte == NULL_AMF0) {
        Py_RETURN_NONE;
    } else if (byte == UNDEFINED_AMF0) {
        Py_RETURN_NONE;
    } else if (byte == REF_AMF0) {
        return decode_reference_AMF0(context);
    } else if (byte == OBJECT_AMF0) {
        return decode_dict_AMF0(context);
    } else if (byte == MIXED_ARRAY_AMF0) {
        PyObject *str = read_py_str(context, 4);// skip encoded max index
        return decode_dict_AMF0(context);
    } else if (byte == ARRAY_AMF0) {
        return decode_array_AMF0(context, 1);
    } else if (byte == LONG_STRING_AMF0) {
        return decode_long_string_AMF0(context);
    } else if (byte == DATE_AMF0) {
        return decode_date_AMF0(context);
    } else if (byte == XML_DOC_AMF0) {
        return decode_xml_AMF0(context);
    } else if (byte == TYPED_OBJ_AMF0) {
        return decode_typed_obj_AMF0(context);
    }

    char error_str[100];
    sprintf(error_str, "Unknown AMF0 type marker byte: '%X' at position: %ld", byte, tell(context) - 1);
    PyErr_SetString(amfast_DecodeError, error_str);
    return NULL;
}

/* Decode individual AMF3 objs from buffer. */
static PyObject* decode_AMF3(Context *context)
{
    const char byte = read_byte(context);

    if (byte == UNDEFINED_TYPE) {
        Py_RETURN_NONE;
    } else if (byte == NULL_TYPE) {
        Py_RETURN_NONE;
    } else if (byte == FALSE_TYPE) {
        Py_RETURN_FALSE;
    } else if (byte == TRUE_TYPE) {
        Py_RETURN_TRUE;
    } else if (byte == INT_TYPE) {
        return decode_int_AMF3(context);
    } else if (byte == STRING_TYPE) {
        return deserialize_string_AMF3(context);
    } else if (byte == DOUBLE_TYPE) {
        return decode_double(context);
    } else if (byte == ARRAY_TYPE) {
        return deserialize_array_AMF3(context, 0);
    } else if (byte == OBJECT_TYPE) {
        return deserialize_obj_AMF3(context, 0);
    } else if (byte == BYTE_ARRAY_TYPE) {
        return deserialize_byte_array_AMF3(context);
    } else if ((byte == XML_TYPE) || (byte == XML_DOC_TYPE)) {
        return deserialize_xml_AMF3(context);
    } else if (byte == DATE_TYPE) {
        return deserialize_date(context);
    }

    char error_str[100];
    sprintf(error_str, "Unknown AMF3 type marker byte: '%X' at position: %ld", byte, tell(context) - 1);
    PyErr_SetString(amfast_DecodeError, error_str);
    return NULL;
}

// ---- Python EXPOSED FUNCTIONS

/* Decode an AMF stream to a Python obj. */
static PyObject* decode(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *decoder_context;

    if (!PyArg_ParseTuple(args, "O", &decoder_context))
        return NULL;

    Context *context = create_context(decoder_context, 1);
    if (!context)
        return NULL;

    PyObject *amf3 = PyObject_GetAttrString(context->decoder_context, "amf3");
    if (!amf3)
        return NULL;

    PyObject *result;
    if (amf3 == Py_True) {
        result = decode_AMF3(context);
    } else {
        result = decode_AMF0(context);
    }
    Py_DECREF(amf3);

    destroy_context(context);
    return result;
}

// ---- Module init

/* Expose functions as Python module functions. */
static PyMethodDef decoder_methods[] = {
    {"decode", (PyCFunction)decode, METH_VARARGS | METH_KEYWORDS,
    "Description:\n"
    "=============\n"
    "Decode an AMF stream to Python objs.\n\n"
    "Useage:\n"
    "===========\n"
    "py_obj = decode(context)\n\n"
    "arguments:\n"
    "============================\n"
    " * context - amfast.context.DecoderContext, Holds options valid for a single decode.\n"},
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
