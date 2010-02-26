#include <Python.h>
#include <string.h>
#include <time.h>

#include "amf.h"
#include "context.h"

// ------------------------ DECLARATIONS --------------------------------- //

// ---- GLOBALS
static PyObject *xml_dom_mod;
static PyObject *amfast_mod;
static PyObject *context_mod;
static PyObject *class_def_mod;
static PyObject *as_types_mod;
static PyObject *amfast_Error;
static PyObject *amfast_EncodeError;
static int big_endian; // Flag == 1 if architecture is big_endian, == 0 if not

/*
 * Use these functions to serialize Python objects.
 *
 * write... functions that encode including type marker.
 * serialize... functions that encode with reference.
 * encode... functions that encode PyObjects to AMF
 *
 * functions starting with '_' encode a C value.
 */

// COMMON
static int encode_packet(EncoderObj *context, PyObject *value);
static int encode_ushort(EncoderObj *context, unsigned short value);
static int encode_ulong(EncoderObj *context, unsigned int value);
static int _encode_double(EncoderObj *context, double value);
static int encode_float(EncoderObj *context, PyObject *value);
static int encode_string(EncoderObj *context, PyObject *value);
static int encode_date(EncoderObj *context, PyObject *value);
static int check_xml(PyObject *value);
static int check_byte_array(PyObject *value);
static int check_proxy(PyObject *value);
static int check_no_proxy(PyObject *value);
static PyObject* class_def_from_class(EncoderObj *context, PyObject *value);
static PyObject* attributes_from_object(EncoderObj *context, PyObject *value);
static PyObject* static_attr_vals_from_class_def(EncoderObj *context,
    PyObject *class_def, PyObject *value);
static PyObject* dynamic_attrs_from_class_def(EncoderObj *context,
    PyObject *class_def, PyObject *value);

// AMF0
static int encode_bool_AMF0(EncoderObj *context, PyObject *value);
static int encode_int_AMF0(EncoderObj *context, PyObject *value);
static int encode_long_AMF0(EncoderObj *context, PyObject *value);
static int encode_float_AMF0(EncoderObj *context, PyObject *value);
static int write_string_AMF0(EncoderObj *context, PyObject *value);
static int encode_string_AMF0(EncoderObj *context, PyObject *value, int allow_long);
static int write_unicode_AMF0(EncoderObj *context, PyObject *value);
static int encode_unicode_AMF0(EncoderObj *context, PyObject *value, int allow_long);
static int write_reference_AMF0(EncoderObj *context, PyObject *value);
static int write_list_AMF0(EncoderObj *context, PyObject *value, int write_reference);
static int write_dict_AMF0(EncoderObj *context, PyObject *value);
static int encode_dynamic_dict_AMF0(EncoderObj *context, PyObject *value);
static int encode_object_as_string_AMF0(EncoderObj *context, PyObject *value, int allow_long);
static int write_date_AMF0(EncoderObj *context, PyObject *value);
static int encode_class_def_AMF0(EncoderObj *context, PyObject *value);
static int write_object_AMF0(EncoderObj *context, PyObject *value);
static int write_anonymous_object_AMF0(EncoderObj *context, PyObject *value);
static int encode_packet_header_AMF0(EncoderObj *context, PyObject *value);
static int encode_packet_message_AMF0(EncoderObj *context, PyObject *value);
static int write_proxy_AMF0(EncoderObj *context, PyObject *value);
static int encode_AMF0(EncoderObj *context, PyObject *value);

// AMF3
static int encode_long_AMF3(EncoderObj *context, PyObject *value);
static int _encode_int_AMF3(EncoderObj *context, int value);
static int write_int_AMF3(EncoderObj *context, PyObject *value);
static int encode_none_AMF3(EncoderObj *context);
static int encode_bool_AMF3(EncoderObj *context, PyObject *value);
static int serialize_unicode_AMF3(EncoderObj *context, PyObject *value);
static int encode_unicode_AMF3(EncoderObj *context, PyObject *value);
static int serialize_string_AMF3(EncoderObj *context, PyObject *value);
static int serialize_object_as_string_AMF3(EncoderObj *context, PyObject *value);
static int write_list_AMF3(EncoderObj *context, PyObject *value);
static int serialize_list_AMF3(EncoderObj *context, PyObject *value);
static int encode_list_AMF3(EncoderObj *context, PyObject *value);
static int encode_array_collection_header_AMF3(EncoderObj *context);
static int write_dict_AMF3(EncoderObj *context, PyObject *value);
static int serialize_dict_AMF3(EncoderObj *context, PyObject *value);
static int encode_dict_AMF3(EncoderObj *context, PyObject *value);
static int encode_dynamic_dict_AMF3(EncoderObj *context, PyObject *value);
static int encode_object_proxy_header_AMF3(EncoderObj *context);
static int serialize_date_AMF3(EncoderObj *context, PyObject *value);
static int encode_reference_AMF3(EncoderObj *context, RefObj *ref_context, PyObject *value, int bit);
static int write_xml_AMF3(EncoderObj *context, PyObject *value);
static int serialize_xml_AMF3(EncoderObj *context, PyObject *value);
static int serialize_object_AMF3(EncoderObj *context, PyObject *value);
static int encode_object_AMF3(EncoderObj *context, PyObject *value);
static int serialize_class_def_AMF3(EncoderObj *context, PyObject *value);
static int encode_class_def_AMF3(EncoderObj *context, PyObject *value);
static int serialize_byte_array_AMF3(EncoderObj *context, PyObject *value);
static int encode_byte_array_AMF3(EncoderObj *context, PyObject *value);
static int write_proxy_AMF3(EncoderObj *context, PyObject *value);
static int write_no_proxy_AMF3(EncoderObj *context, PyObject *value);
static int encode_AMF3(EncoderObj *context, PyObject *value);

// Python exposed functions
static PyObject* py_encode(PyObject *self, PyObject *args, PyObject *kwargs);
static PyObject* py_encode_packet(PyObject *self, PyObject *args, PyObject *kwargs);

/* Encode a native C double. */
static int _encode_double(EncoderObj *context, double value)
{
   // Put bytes from double into byte array
   union aligned { // use the same memory for d_value and c_value
       double d_value;
       char c_value[8];
   } d_aligned;
   char *char_value = d_aligned.c_value;
   d_aligned.d_value = value;

   // AMF numbers are encoded in big endianness
   if (big_endian) {
       return Encoder_write(context, char_value, 8);
   } else {
       // Flip endianness
       char flipped[8] = {char_value[7], char_value[6], char_value[5], char_value[4], char_value[3], char_value[2], char_value[1], char_value[0]};
       return Encoder_write(context, flipped, 8);
   }
}

/* Encode a PyFloat. */
static int encode_float(EncoderObj *context, PyObject *value)
{
    double n = PyFloat_AsDouble(value);
    return _encode_double(context, n);
}

/* Encode a PyLong. */
static int encode_long_AMF3(EncoderObj *context, PyObject *value)
{
    double n = PyLong_AsDouble(value);
    if (n == -1.0)
        return 0;
    return _encode_double(context, n);
}

/* Encode a native C int. */
static int _encode_int_AMF3(EncoderObj *context, int value)
{
    char tmp[4];
    size_t tmp_size;

    /*
     * Int can be up to 4 bytes long.
     *
     * The first bit of the first 3 bytes
     * is set if another byte follows.
     *
     * The integer value is the last 7 bits from
     * the first 3 bytes and the 8 bits of the last byte
     * (29 bits).
     *
     * The int is negative if the 1st bit of the 29 int is set.
     */
    value &= 0x1fffffff; // Ignore 1st 3 bits of 32 bit int, since we're encoding to 29 bit.
    if (value < 0x80) {
        tmp_size = 1;
        tmp[0] = value;
    } else if (value < 0x4000) {
        tmp_size = 2;
        tmp[0] = (value >> 7 & 0x7f) | 0x80; // Shift bits by 7 to fill 1st byte and set next byte flag
        tmp[1] = value & 0x7f; // Shift bits by 7 to fill 2nd byte, leave next byte flag unset
    } else if (value < 0x200000) {
        tmp_size = 3;
        tmp[0] = (value >> 14 & 0x7f) | 0x80;
        tmp[1] = (value >> 7 & 0x7f) | 0x80;
        tmp[2] = value & 0x7f;
    } else if (value < 0x40000000) {
        tmp_size = 4;
        tmp[0] = (value >> 22 & 0x7f) | 0x80;
        tmp[1] = (value >> 15 & 0x7f) | 0x80;
        tmp[2] = (value >> 8 & 0x7f) | 0x80; // Shift bits by 8, since we can use all bits in the 4th byte
        tmp[3] = (value & 0xff);
    } else {
        PyErr_SetString(amfast_EncodeError, "Int is too big to be encoded by AMF.");
        return 0;        
    }

    return Encoder_write(context, tmp, tmp_size);
}

/* Writes a PyInt. */
static int write_int_AMF3(EncoderObj *context, PyObject *value)
{
    long n = PyInt_AsLong(value);
    if (n < MAX_INT && n > MIN_INT) {
        // Int is in valid AMF3 int range.
        if (Encoder_writeByte(context, INT_TYPE) != 1)
            return 0;
        return _encode_int_AMF3(context, n);
    } else {
        // Int is too big, it must be encoded as a double
        if (Encoder_writeByte(context, DOUBLE_TYPE) != 1)
            return 0;
        return _encode_double(context, (double)n);
    }
}

/* Encode a Py_None. */
static int encode_none_AMF3(EncoderObj *context)
{
    return Encoder_writeByte(context, NULL_TYPE);
}

/* Encode a PyBool. */
static int encode_bool_AMF3(EncoderObj *context, PyObject *value)
{
    if (value == Py_True) {
        return Encoder_writeByte(context, TRUE_TYPE);
    } else {
        return Encoder_writeByte(context, FALSE_TYPE);
    }
}

/* Serialize a PyUnicode. */
static int serialize_unicode_AMF3(EncoderObj *context, PyObject *value)
{
    // Check for empty string
    if (PyUnicode_GET_SIZE(value) == 0) {
        // References are never used for empty strings.
        return Encoder_writeByte(context, EMPTY_STRING_TYPE);
    }

    // Check for idx
    int result = encode_reference_AMF3(context, (RefObj*)context->string_refs, value, 0);
    if (result > -1)
        return result;

    return encode_unicode_AMF3(context, value); 
}

/* Encode a PyUnicode. */
static int encode_unicode_AMF3(EncoderObj *context, PyObject *value)
{
    PyObject *PyString_value = PyUnicode_AsUTF8String(value);
    return encode_string(context, PyString_value);
}

/* Serialize a PyString. */
static int serialize_string_AMF3(EncoderObj *context, PyObject *value)
{
    // Check for empty string
    if (PyString_GET_SIZE(value) == 0) {
        // References are never used for empty strings.
        return Encoder_writeByte(context, EMPTY_STRING_TYPE);
    }

    // Check for idx
    int result = encode_reference_AMF3(context, (RefObj*)context->string_refs, value, 0);
    if (result > -1)
        return result;

    return encode_string(context, value);
}

/* Encode a PyString as UTF8. */
static int encode_string(EncoderObj *context, PyObject *value)
{
    /*
     *  TODO: The following code assumes all strings
     *  are already UTF8 or ASCII.
     *
     *  Should we check to make sure,
     *  or just let the client pick it up?
     */
    char *char_value = PyString_AS_STRING(value);
    Py_ssize_t string_len = PyString_GET_SIZE(value);
    if (!char_value)
        return 0;

    // Add size of string to header
    if (!_encode_int_AMF3(context, ((int)string_len) << 1 | REFERENCE_BIT))
        return 0;

    // Write string.
    return Encoder_write(context, char_value, (int)string_len);
}

/* Encode a PyString or a PyUnicode. */
static int serialize_object_as_string_AMF3(EncoderObj *context, PyObject *value)
{
    if (PyString_Check(value)) {
        return serialize_string_AMF3(context, value);
    } else if (PyUnicode_Check(value)) {
        return serialize_unicode_AMF3(context, value);
    }

    PyObject *str_rep = PyObject_Str(value);
    if (!str_rep)
        return 0;

    int result = serialize_string_AMF3(context, str_rep);
    Py_DECREF(str_rep);
    return result;
}

/* Encode a PyString or a PyUnicode to AMF0. */
static int encode_object_as_string_AMF0(EncoderObj *context, PyObject *value, int allow_long)
{
    if (PyUnicode_Check(value)) {
        return encode_unicode_AMF0(context, value, allow_long);
    } else if (PyString_Check(value)) {
        return encode_string_AMF0(context, value, allow_long);
    }

    PyObject *str_rep = PyObject_Str(value);
    if (!str_rep)
        return 0;

    int result = encode_string_AMF0(context, str_rep, allow_long);
    Py_DECREF(str_rep);
    return result;
}

/* Encode an ArrayCollection header. */
static int encode_array_collection_header_AMF3(EncoderObj *context)
{
    // If ClassDef object has not been created,
    // for ArrayCollection, create it.
    if (!context->array_collection_def) {
        PyObject *method_name = PyString_FromString("getClassDefByAlias");
        if (!method_name)
            return 0;

        PyObject *alias = PyString_FromString("flex.messaging.io.ArrayCollection");
        if (!alias) {
            Py_DECREF(method_name);
            return 0;
        }

        PyObject *class_def = PyObject_CallMethodObjArgs(context->class_mapper, method_name, alias, NULL);
        Py_DECREF(method_name);
        Py_DECREF(alias);

        if (!class_def)
            return 0;

        context->array_collection_def = class_def;
    }

    // Write ArrayCollectionClassDef to buf.
    if (!serialize_class_def_AMF3(context, context->array_collection_def))
        return 0;

    // Add an extra item to the index for the array following the collection
    if (Ref_map((RefObj*)context->obj_refs, Py_None) == -1)
        return 0;

    return 1;
}

/* Writes a PyList or PyTuple. */
static int write_list_AMF3(EncoderObj *context, PyObject *value)
{
    if (context->use_collections == Py_True) {
        return write_proxy_AMF3(context, value);
    }

    // Write type marker
    if (Encoder_writeByte(context, ARRAY_TYPE) != 1)
            return 0;
    
    return serialize_list_AMF3(context, value);
}

/* Writes a proxied object. */
static int write_proxy_AMF3(EncoderObj *context, PyObject *value)
{
    if (!Encoder_writeByte(context, OBJECT_TYPE))
        return 0;

    // Check for idx
    int result = encode_reference_AMF3(context, (RefObj*)context->obj_refs, value, 0);
    if (result > -1) {
        return result;
    }

    PyObject *source;
    if (PyObject_HasAttrString(value, "source")) {
        source = PyObject_GetAttrString(value, "source");
        if (source == NULL)
            return 0;
    } else {
        source = value;
        Py_INCREF(source);
    }

    if (PyList_Check(source) || PyTuple_Check(source)) {
        // Array Collections
        if (!encode_array_collection_header_AMF3(context)) {
            Py_DECREF(source);
            return 0;
        }

        if (!Encoder_writeByte(context, ARRAY_TYPE)) {
            Py_DECREF(source);
            return 0;
        }

        result = encode_list_AMF3(context, source);
        Py_DECREF(source);
        return result;
    }

    // All other proxied objects
    if (!encode_object_proxy_header_AMF3(context)) {
        Py_DECREF(source);
        return 0;
    }

    if (PyDict_Check(source)) {
        if (!Encoder_writeByte(context, OBJECT_TYPE)) {
           Py_DECREF(source);
           return 0;
        }
        result = encode_dict_AMF3(context, source);
    } else {
        result = encode_object_AMF3(context, source);
    }
    Py_DECREF(source);
    return result;
}

/* Write an object without a proxy in AMF3. */
static int write_no_proxy_AMF3(EncoderObj *context, PyObject *value)
{
    PyObject *source;
    if (PyObject_HasAttrString(value, "source")) {
        source = PyObject_GetAttrString(value, "source");
        if (source == NULL)
            return 0;
    } else {
        source = value;
        Py_INCREF(source);
    }

    int result;
    if (PyList_Check(source) || PyTuple_Check(source)) {
        if (!Encoder_writeByte(context, ARRAY_TYPE)) {
           Py_DECREF(source);
           return 0;
        }

        result = serialize_list_AMF3(context, source);
    } else if (PyDict_Check(source)) {
        if (!Encoder_writeByte(context, OBJECT_TYPE)) {
           Py_DECREF(source);
           return 0;
        }

        result = serialize_dict_AMF3(context, source);
    } else {
        result = encode_AMF3(context, source);
    }

    Py_DECREF(source);
    return result;
}

/* Write a proxied object to AMF0. */
static int write_proxy_AMF0(EncoderObj *context, PyObject *value)
{
    PyObject *source = PyObject_GetAttrString(value, "source");
    if (source == NULL)
        return 0;

    int result = encode_AMF0(context, source);
    Py_DECREF(source);
    return result;
}

/* Serializes a PyList or PyTuple. */
static int serialize_list_AMF3(EncoderObj *context, PyObject *value)
{
    // Check for idx
    int result = encode_reference_AMF3(context, (RefObj*)context->obj_refs, value, 0);
    if (result > -1)
        return result;

    return encode_list_AMF3(context, value);
}

/* Encode a PyList or PyTuple. */
static int encode_list_AMF3(EncoderObj *context, PyObject *value)
{
    // Add size of list to header
    Py_ssize_t value_len = PySequence_Size(value);
    if (value_len < 0)
        return 0;

    if (!_encode_int_AMF3(context, ((int)value_len) << 1 | REFERENCE_BIT))
        return 0;

    // We're never writing associative array items
    if (!Encoder_writeByte(context, NULL_TYPE))
        return 0;

    // Encode each value in the list
    int i;
    for (i = 0; i < value_len; i++) {
        // GetItem increments ref count 
        PyObject *list_item = PySequence_GetItem(value, i);
        if (!list_item)
            return 0;

        int result = encode_AMF3(context, list_item);
        Py_DECREF(list_item);
        if (!result)
            return 0;
    }

    return 1;
}

/* Encode an ObjectProxy header. */
static int encode_object_proxy_header_AMF3(EncoderObj *context)
{
    // If ClassDef object has not been created
    // for ObjectProxy, create it.
    if (!context->object_proxy_def) {
        PyObject *method_name = PyString_FromString("getClassDefByAlias");
        if (!method_name) 
            return 0;

        PyObject *alias = PyString_FromString("flex.messaging.io.ObjectProxy");
        if (!alias) {
            Py_DECREF(method_name);
            return 0;
        }

        PyObject *class_def = PyObject_CallMethodObjArgs(context->class_mapper, method_name, alias, NULL);
        Py_DECREF(method_name);
        Py_DECREF(alias);

        if (!class_def)
            return 0;

        context->object_proxy_def = class_def;
    }

    // Encode object proxy class def.
    if (!serialize_class_def_AMF3(context, context->object_proxy_def))
         return 0;

    // Add an extra item to the index for the object following the proxy
    if (Ref_map((RefObj*)context->obj_refs, Py_None) == -1)
        return 0;

    return 1;
}

/* Write a PyDict. */
static int write_dict_AMF3(EncoderObj *context, PyObject *value)
{
    if (context->use_proxies == Py_True) {
        return write_proxy_AMF3(context, value);
    }

    if (!Encoder_writeByte(context, OBJECT_TYPE))
       return 0;

    return serialize_dict_AMF3(context, value);
}

/* Serialize a PyDict. */
static int serialize_dict_AMF3(EncoderObj *context, PyObject *value)
{
    // Check for idx
    int result = encode_reference_AMF3(context, (RefObj*)context->obj_refs, value, 0);
    if (result > -1) {
        return result;
    }

    return encode_dict_AMF3(context, value);
}

/* Encode a dict. */
static int encode_dict_AMF3(EncoderObj *context, PyObject *value)
{
    if (!serialize_class_def_AMF3(context, Py_None)) {
        return 0;
    }

    return encode_dynamic_dict_AMF3(context, value);
}

/* Encode the key/value pairs of a dict. */
static int encode_dynamic_dict_AMF3(EncoderObj *context, PyObject *value)
{
    PyObject *key;
    PyObject *val;
    Py_ssize_t idx = 0;

    while (PyDict_Next(value, &idx, &key, &val)) {
        if (!serialize_object_as_string_AMF3(context, key))
            return 0;

        if (!encode_AMF3(context, val)) {
            return 0;
        }
    }

    // Terminate key/value pairs with empty string
    if (!Encoder_writeByte(context, EMPTY_STRING_TYPE))
        return 0; 

    return 1;
}

/* Serialize a PyDate. */
static int serialize_date_AMF3(EncoderObj *context, PyObject *value)
{
    // Check for idx
    int result = encode_reference_AMF3(context, (RefObj*)context->obj_refs, value, 0);
    if (result > -1)
        return result;

    return encode_date(context, value);
}

/* Encode a PyDate. */
static int encode_date(EncoderObj *context, PyObject *value)
{
    // Reference header
    if (!_encode_int_AMF3(context, REFERENCE_BIT))
        return 0;

    // Call python function to get datetime
    PyObject *epoch_func = PyObject_GetAttrString(amfast_mod, "epoch_from_date");
    if (!epoch_func)
        return 0;

    PyObject *epoch_time = PyObject_CallFunctionObjArgs(epoch_func, value, NULL);
    Py_DECREF(epoch_func);
    if (!epoch_time)
        return 0;

    double micro_time = PyLong_AsDouble(epoch_time);
    Py_DECREF(epoch_time);

    return _encode_double(context, micro_time);
}

/* 
 * Encode a referenced value.
 *
 * bit argument specifies which bit to is the reference bit (0 = low bit)
 *
 * Returns -1 if reference was not found,
 * 1 if reference was found
 * 0 if error.
 */
static int encode_reference_AMF3(EncoderObj *context, RefObj *ref_context,
    PyObject *value, int bit)
{
    if (ref_context == NULL) {
        PyErr_SetString(amfast_EncodeError, "Reference indexer is NULL.");
        return 0;
    }

    // Using references is an option set in the context
    if (context->use_refs == Py_True) {
        int idx = Ref_ret(ref_context, value);
        if (idx > -1) {
            if (idx < MAX_INT) {// Max reference count
                if (!_encode_int_AMF3(context, (idx << (bit + 1)) | (0x00 + bit)))
                   return 0;
               return 1;
           }
        }
    }

    // Object is not indexed, add index
    if (Ref_map(ref_context, value) == -1)
        return 0;

    return -1;
}

/*
 * Encode an AMF0 Reference.
 *
 * Returns -1 if reference was not found,
 * 1 if reference was found
 * 0 if error.
 */
static int write_reference_AMF0(EncoderObj *context, PyObject *value)
{
    // Using references is an option set in the context
    if (context->use_refs == Py_True) {
        int idx = Ref_ret((RefObj*)context->obj_refs, value);
        if (idx > -1) {
            if (idx < MAX_USHORT) {
                if (!Encoder_writeByte(context, REF_AMF0))
                    return 0;

                if (!encode_ushort(context, (unsigned short)idx))
                    return 0;

                return 1;
            }
        }
    }

    // Object is not indexed, add index
    if (Ref_map((RefObj*)context->obj_refs, value) == -1)
        return 0;

    return -1;
}

/* Serializes a PyByteArray or a PyString. */
static int serialize_byte_array_AMF3(EncoderObj *context, PyObject *value)
{
    // Check for idx
    int result = encode_reference_AMF3(context, (RefObj*)context->obj_refs, value, 0);
    if (result > -1)
        return result;

    // Length prefix
    Py_ssize_t value_len;
    
    #ifdef Py_BYTEARRAYOBJECT_H
    // ByteArray encoding is only available in 2.6+
    if (PyByteArray_Check(value)) {
        value_len = PyByteArray_GET_SIZE(value);

        if (!_encode_int_AMF3(context, ((int)value_len) << 1 | REFERENCE_BIT)) {
            return 0;
        }

        return encode_byte_array_AMF3(context, value);
    }
    #endif
    PyObject *byte_string;
    if (check_byte_array(value)) {
        byte_string = PyObject_GetAttrString(value, "bytes");
        if (!byte_string)
            return 0;
        value_len = PyString_GET_SIZE(byte_string);
        if (value_len < 0) {
            Py_DECREF(byte_string);
            return 0;
        }
    } else {
        PyErr_SetString(amfast_EncodeError, "Cannot encode non AsByteArray as byte array.");
        return 0;
    }

    if (!_encode_int_AMF3(context, ((int)value_len) << 1 | REFERENCE_BIT)) {
        Py_DECREF(byte_string);
        return 0;
    }

    result = encode_byte_array_AMF3(context, byte_string);
    Py_DECREF(byte_string);
    return result; 
}

/* Encodes a PyByteArray or a PyString. */
static int encode_byte_array_AMF3(EncoderObj *context, PyObject *value)
{
    Py_ssize_t value_len;
    char *byte_value;
    
    if (PyString_CheckExact(value)) {
        value_len = PyString_GET_SIZE(value);
        byte_value = PyString_AS_STRING(value);
    }
    #ifdef Py_BYTEARRAYOBJECT_H
    // ByteArray encoding is only available in 2.6+
    else if (PyByteArray_Check(value)) {
        value_len = PyByteArray_GET_SIZE(value);
        byte_value = PyByteArray_AS_STRING(value);
    }
    #endif
    else {
        PyErr_SetString(amfast_EncodeError, "Cannot encode non ByteArray/String as byte array.");
        return 0;
    }
    
    if (!byte_value)
        return 0;

    return Encoder_write(context, byte_value, (int)value_len);
}

/* Writes an xml.dom.Document object. */
static int write_xml_AMF3(EncoderObj *context, PyObject *value)
{
    int byte_marker;

    if (context->use_legacy_xml == Py_True) {
        byte_marker = XML_DOC_TYPE;
    } else {
        byte_marker = XML_TYPE;
    }

    if (!Encoder_writeByte(context, byte_marker))
        return 0;

    return serialize_xml_AMF3(context, value);
}

/* Serializes an xml.dom.Document object. */
static int serialize_xml_AMF3(EncoderObj *context, PyObject *value)
{
    // Check for idx
    int result = encode_reference_AMF3(context, (RefObj*)context->obj_refs, value, 0);
    if (result > -1)
        return result;

    PyObject *unicode_value = PyObject_CallMethod(value, "toxml", NULL);
    if (unicode_value == NULL)
        return 0;

    result = encode_unicode_AMF3(context, unicode_value);
    Py_DECREF(unicode_value);
    return result;
}

/* Returns 1 if a PyObject is a xml.dom.Document object. */
static int check_xml(PyObject *value)
{
    if (!PyObject_HasAttrString(value, "toxml"))
        return 0;
    if (!PyObject_HasAttrString(value, "toprettyxml"))
        return 0;

    return 1;
}

/* Returns 1 if a PyObject is a amfast.class_def.as_types.AsByteArray object. */
static int check_byte_array(PyObject *value)
{
    return PyObject_HasAttrString(value, "AS_BYTE_ARRAY");
}

/* Returns 1 if a PyObject is an AsProxy. */
static int check_proxy(PyObject *value)
{
    return PyObject_HasAttrString(value, "AS_PROXY");
}

/* Returns 1 if a PyObject is an AsNoProxy. */
static int check_no_proxy(PyObject *value)
{
    return PyObject_HasAttrString(value, "AS_NO_PROXY");
}

/* Serialize a Python object. */
static int serialize_object_AMF3(EncoderObj *context, PyObject *value)
{
    // Check for idx
    int result = encode_reference_AMF3(context, (RefObj*)context->obj_refs, value, 0);
    if (result > -1)
        return result;

    return encode_object_AMF3(context, value);
}

/* Encode a Python object. */
static int encode_object_AMF3(EncoderObj *context, PyObject *value)
{
    PyObject *class_def = class_def_from_class(context, value);
    if (!class_def)
        return 0;

    if (class_def == Py_None) {
        // No ClassDef was found, encode as an anonymous object
        Py_DECREF(class_def);

        PyObject *dict = attributes_from_object(context, value);
        if (!dict)
            return 0;

        int result = encode_dict_AMF3(context, dict);
        Py_DECREF(dict);
        return result;
    }

    // Class has a ClassDef
    // encode class definition
    if (!serialize_class_def_AMF3(context, class_def)) {
        Py_DECREF(class_def);
        return 0;
    }

    if (PyObject_HasAttrString(class_def, "EXTERNALIZABLE_CLASS_DEF")) {
        // Let custom Python function handle the encoding
        // of Externalizeable objects.
        PyObject *result = PyObject_CallMethodObjArgs(class_def,
            context->extern_name, value, (PyObject*)context, NULL);
        Py_DECREF(class_def);
        if (result == NULL)
            return 0;

        Py_DECREF(result);
        return 1;
    }

    // Encode static attrs
    PyObject *static_attrs = static_attr_vals_from_class_def(context, class_def, value);
    if (!static_attrs) {
        Py_DECREF(class_def);
        return 0;
    }

    Py_ssize_t static_attr_len = PySequence_Size(static_attrs);
    if (static_attr_len == -1) {
        Py_DECREF(class_def);
        Py_DECREF(static_attrs);
        return 0;
    }

    int i;
    for (i = 0; i < static_attr_len; i++) {
        PyObject *static_attr = PySequence_GetItem(static_attrs, i);
        if (!static_attr) {
            Py_DECREF(static_attrs);
            Py_DECREF(class_def);
            return 0;
        }

        int result = encode_AMF3(context, static_attr);
        Py_DECREF(static_attr);
        if (!result) {
            Py_DECREF(static_attrs);
            Py_DECREF(class_def);
            return 0;
        }
    }
    Py_DECREF(static_attrs);

    // Encode dynamic attrs
    if (PyObject_HasAttrString(class_def, "DYNAMIC_CLASS_DEF")) {
        PyObject *dynamic_attrs = dynamic_attrs_from_class_def(context, class_def, value);
        if (!dynamic_attrs) {
            Py_DECREF(class_def);
            return 0;
        }

        int result = encode_dynamic_dict_AMF3(context, dynamic_attrs);
        Py_DECREF(dynamic_attrs);
        if (!result) {
            Py_DECREF(class_def);
            return 0;
        }
    }

    Py_DECREF(class_def);
    return 1;
}

/* Serialize a class definition. */
static int serialize_class_def_AMF3(EncoderObj *context, PyObject *value)
{
    // Check for idx
    int result = encode_reference_AMF3(context, (RefObj*)context->class_refs, value, 1);
    if (result > -1)
        return result;

    return encode_class_def_AMF3(context, value);
}

/* Encode a class definition. */
static int encode_class_def_AMF3(EncoderObj *context, PyObject *value)
{
    if (value == Py_None) {
        // Encode as anonymous object
        if (!Encoder_writeByte(context, DYNAMIC))
            return 0;

        // Anonymous object alias is an empty string
        if (!Encoder_writeByte(context, EMPTY_STRING_TYPE))
            return 0;
        return 1;
    }

    // Encode class type
    if (!PyObject_HasAttrString(value, "CLASS_DEF")) {
        PyErr_SetString(amfast_EncodeError, "Invalid class definition object.");
        return 0;
    }

    // Determine header type
    int header;
    if (PyObject_HasAttrString(value, "EXTERNALIZABLE_CLASS_DEF")) {
        header = EXTERNALIZABLE;
    } else if (PyObject_HasAttrString(value, "DYNAMIC_CLASS_DEF")) {
        header = DYNAMIC;
    } else {
        header = STATIC;
    }

    PyObject *class_alias = PyObject_GetAttrString(value, "alias");
    if (!class_alias)
       return 0;

    // Don't need to encode static attrs of externalizeable.
    if (header == EXTERNALIZABLE) {
       if (!_encode_int_AMF3(context, header)) {
           Py_DECREF(class_alias);
           return 0;
       }
       
       int result = serialize_object_as_string_AMF3(context, class_alias);
       Py_DECREF(class_alias);
       return result;
    }

    // Encode number of static attrs in header.
    PyObject *static_attrs = PyObject_GetAttrString(value, "static_attrs");
    if (!static_attrs) {
       Py_DECREF(class_alias);
       return 0;
    }

    Py_ssize_t static_attr_len = PySequence_Size(static_attrs);
    if (static_attr_len == -1) {
       Py_DECREF(class_alias);
       Py_DECREF(static_attrs);
       return 0;
    }

    if (static_attr_len > (MAX_INT >> 4)) {
       Py_DECREF(class_alias);
       Py_DECREF(static_attrs);
       PyErr_SetString(amfast_EncodeError, "ClassDef has too many attributes.");
       return 0;
    }
    header |= ((int)static_attr_len) << 4;

    if (!_encode_int_AMF3(context, header)) {
       Py_DECREF(class_alias);
       Py_DECREF(static_attrs);
       return 0;
    }

    int result = serialize_object_as_string_AMF3(context, class_alias);
    Py_DECREF(class_alias);
    if (!result) {
       Py_DECREF(static_attrs);
       return 0;
    }

    // Encode static attr names
    int i;
    for (i = 0; i < static_attr_len; i++) {
        PyObject *attr_name = PySequence_GetItem(static_attrs, i);
        if (!attr_name) {
            Py_DECREF(static_attrs);
            return 0;
        }
        
        int result = serialize_object_as_string_AMF3(context, attr_name);
        Py_DECREF(attr_name);
        if (!result)
            return 0;
    }

    Py_DECREF(static_attrs);
    return 1;
}

/* Encode a Python boolean in AMF0. */
static int encode_bool_AMF0(EncoderObj *context, PyObject *value)
{
    int result;
    if (value == Py_True) {
        result = Encoder_writeByte(context, TRUE_AMF0);
    } else {
        result = Encoder_writeByte(context, FALSE_AMF0);
    }

    return result;
}

/* Encode a PyInt in AMF0. */
static int encode_int_AMF0(EncoderObj *context, PyObject *value)
{
    long long_val = PyInt_AsLong(value);
    PyObject *py_long_val = PyLong_FromLong(long_val);
    if (!py_long_val)
        return 0;

    int result = encode_long_AMF0(context, py_long_val);
    Py_DECREF(py_long_val);
    return result;
}

/* Encode a PyLong in AMF0. */
static int encode_long_AMF0(EncoderObj *context, PyObject *value)
{
    return _encode_double(context, PyLong_AsDouble(value));
}

/* Encode a PyFloat in AMF0. */
static int encode_float_AMF0(EncoderObj *context, PyObject *value)
{
    return _encode_double(context, PyFloat_AsDouble(value));
}

/* Encode a native C unsigned short. */
static int encode_ushort(EncoderObj *context, unsigned short value)
{
   // Put bytes from short into byte array
   union aligned { // use the same memory for d_value and c_value
       unsigned short d_value;
       char c_value[2];
   } d;
   char *char_value = d.c_value;
   d.d_value = value;

   // AMF numbers are encoded in big endianness
   if (big_endian) {
       return Encoder_write(context, char_value, 2);
   } else {
       // Flip endianness
       char flipped[2] = {char_value[1], char_value[0]};
       return Encoder_write(context, flipped, 2);
   }
}

/* Encode a native C unsigned int. */
static int encode_ulong(EncoderObj *context, unsigned int value)
{
   // Put bytes from long into byte array
   union aligned { // use the same memory for d_value and c_value
       unsigned int d_value;
       char c_value[4];
   } d;
   char *char_value = d.c_value;
   d.d_value = value;

   // AMF numbers are encoded in big endianness
   if (big_endian) {
       return Encoder_write(context, char_value, 4);
   } else {
       // Flip endianness
       char flipped[4] = {char_value[3], char_value[2], char_value[1], char_value[0]};
       return Encoder_write(context, flipped, 4);
   }
}

/* Write a PyString. */
static int write_string_AMF0(EncoderObj *context, PyObject *value)
{
    PyObject *unicode_value = PyUnicode_FromObject(value);
    if (!unicode_value)
        return 0;

    int result = write_unicode_AMF0(context, unicode_value);
    Py_DECREF(unicode_value);
    return result;
}

/* Write a PyUnicode in AMF0. */
static int write_unicode_AMF0(EncoderObj *context, PyObject *value)
{
    Py_ssize_t string_len = PyUnicode_GET_SIZE(value);

    if (string_len > 65536) {
        if (!Encoder_writeByte(context, LONG_STRING_AMF0))
            return 0;
        return encode_unicode_AMF0(context, value, 1);
    }

    if (!Encoder_writeByte(context, STRING_AMF0))
        return 0;

    return encode_unicode_AMF0(context, value, 0);
}

/*
 * Encode a PyUnicode in AMF0.
 *
 * allow_long
 * 1 = allow long values
 * 0 = don't allow long values
 * -1 = force long value
 */
static int encode_unicode_AMF0(EncoderObj *context, PyObject *value, int allow_long)
{
    PyObject *PyString_value = PyUnicode_AsUTF8String(value);
    if (!PyString_value)
        return 0;

    int result = encode_string_AMF0(context, PyString_value, allow_long);
    Py_DECREF(PyString_value);
    return result;
}

/*
 * Encode a PyString in AMF0.
 *
 * allow_long
 * 1 = allow long values
 * 0 = don't allow long values
 * -1 = force long value
 */
static int encode_string_AMF0(EncoderObj *context, PyObject *value, int allow_long)
{
    char *char_value = PyString_AS_STRING(value);
    Py_ssize_t string_len = PyString_GET_SIZE(value);
    if (!char_value)
        return 0;

    if (string_len > MAX_USHORT && allow_long == 0) {
        PyErr_SetString(amfast_EncodeError, "Long string not allowed.");
        return 0;
    } else if (string_len > MAX_USHORT || allow_long == -1) {
        if (!encode_ulong(context, (unsigned int)string_len))
            return 0;
    } else {
        if (!encode_ushort(context, (unsigned short)string_len))
            return 0;
    }

    return Encoder_write(context, char_value, (int)string_len);
}

/* Write a PyList to AMF0. */
static int write_list_AMF0(EncoderObj *context, PyObject *value, int write_reference)
{
    if (write_reference) {
        int result = write_reference_AMF0(context, value);
        if (result == 0 || result == 1) {
            return result;
        }
    }

    // No reference
    if (!Encoder_writeByte(context, ARRAY_AMF0))
        return 0;

    Py_ssize_t array_len = PySequence_Size(value);
    if (array_len < 0)
        return 0;

    if (!encode_ulong(context, (unsigned int)array_len))
        return 0;

    int i;
    for (i = 0; i < array_len; i++) {
        // Increment ref count in case 
        // list is modified by someone else.
        PyObject *list_item = PySequence_GetItem(value, (Py_ssize_t)i);
        if (!list_item)
            return 0;

        int result = encode_AMF0(context, list_item);
        Py_DECREF(list_item);
        if (!result)
            return 0;
    }

    return 1;
}

/* Write a PyDict to AMF0. */
static int write_dict_AMF0(EncoderObj *context, PyObject *value)
{
    int result = write_reference_AMF0(context, value);
    if (result == 0 || result == 1) {
        return result;
    }

    // No reference
    if (!Encoder_writeByte(context, OBJECT_AMF0))
        return 0;

    return encode_dynamic_dict_AMF0(context, value);
}

/* Write the contents of a Dict to AMF0. */
static int encode_dynamic_dict_AMF0(EncoderObj *context, PyObject *value)
{
    PyObject *key;
    PyObject *val;
    Py_ssize_t idx = 0;

    while (PyDict_Next(value, &idx, &key, &val)) {
        if (!encode_object_as_string_AMF0(context, key, 0))
            return 0;

        if (!encode_AMF0(context, val)) {
            return 0;
        }
    }

    // Terminate key/value pairs.
    char terminator[3] = {0x00, 0x00, 0x09};
    if (Encoder_write(context, terminator, 3) == 0)
        return 0;

    return 1;
}

/* Encode a Date object to AMF0 .*/
static int write_date_AMF0(EncoderObj *context, PyObject *value)
{
    // Dates can use references
    /*int wrote_ref = write_reference_AMF0(context, value);
    if (wrote_ref == 0 || wrote_ref == 1) {
        return wrote_ref;
    }*/

    if (!Encoder_writeByte(context, DATE_AMF0))
        return 0;
 
    // Call python function to get datetime
    PyObject *epoch_func = PyObject_GetAttrString(amfast_mod, "epoch_from_date");
    if (!epoch_func)
        return 0;

    PyObject *epoch_time = PyObject_CallFunctionObjArgs(epoch_func, value, NULL);
    Py_DECREF(epoch_func);
    if (!epoch_time)
        return 0;

    double micro_time = PyLong_AsDouble(epoch_time);
    Py_DECREF(epoch_time);

    if (!_encode_double(context, micro_time))
        return 0;
    
    // UTC time zone
    return encode_ushort(context, 0);
}

/* Write an XML object in AMF0. */
static int write_xml_AMF0(EncoderObj *context, PyObject *value)
{
    if (!Encoder_writeByte(context, XML_DOC_AMF0))
        return 0;

    PyObject *unicode_value = PyObject_CallMethod(value, "toxml", NULL);
    if (!unicode_value)
        return 0;

    int result = encode_unicode_AMF0(context, unicode_value, -1);
    Py_DECREF(unicode_value);
    return result;
}

/* Get an object's class def. */
static PyObject* class_def_from_class(EncoderObj *context, PyObject *value)
{
    // Use object's class to get ClassDef
    PyObject *class_ = PyObject_GetAttrString(value, "__class__");
    if (!class_)
        return NULL;

    PyObject *class_def = PyObject_CallMethodObjArgs(context->class_mapper, context->class_def_name,
        class_, NULL);
    Py_DECREF(class_);
    return class_def;
}

/* Write an anonymous object in AMF0. */
static int write_anonymous_object_AMF0(EncoderObj *context, PyObject *value)
{
    if (!Encoder_writeByte(context, OBJECT_AMF0))
        return 0;

    PyObject *dict = attributes_from_object(context, value);
    if (!dict)
        return 0;

    int result = encode_dynamic_dict_AMF0(context, dict);
    Py_DECREF(dict);
    return result;
}

/* Get attributes from an anonymous object as a dict. */
static PyObject* attributes_from_object(EncoderObj *context, PyObject *value)
{
    PyObject *attr_func = PyObject_GetAttrString(class_def_mod, "get_dynamic_attr_vals");
    if (!attr_func)
        return NULL;

    PyObject *dict = PyObject_CallFunctionObjArgs(attr_func, value, Py_None, context->include_private, NULL);
    Py_DECREF(attr_func);
    if (!dict)
        return NULL;

    return dict;
}

/* Encode a ClassDef in AMF0. */
static int encode_class_def_AMF0(EncoderObj *context, PyObject *value)
{
    PyObject *alias = PyObject_GetAttrString(value, "alias");
    if (!alias)
        return 0;

    int result = encode_object_as_string_AMF0(context, alias, 0);
    Py_DECREF(alias);
    return result;
}

/* Get static attrs. */
static PyObject* static_attr_vals_from_class_def(EncoderObj *context, PyObject *class_def, PyObject *value)
{
    PyObject *method_name = PyString_FromString("getStaticAttrVals");
    if (!method_name)
        return NULL;

    PyObject *static_attrs = PyObject_CallMethodObjArgs(class_def, method_name, value, NULL);
    Py_DECREF(method_name);
    if (!static_attrs)
        return NULL;

    if (!PySequence_Check(static_attrs)) {
        PyErr_SetString(amfast_EncodeError, "ClassDef.getStaticAttrVals must return a sequence.");
        Py_DECREF(static_attrs);
        return NULL;
    }

    PyObject *static_names = PyObject_GetAttrString(class_def, "static_attrs");
    int result = type_list(class_def, context->type_map, static_names, static_attrs, 0);
    Py_DECREF(static_names);
    if (result == 0) {
        Py_DECREF(static_attrs);
        return NULL;
    }

    return static_attrs;
}

/* Get dynamic attrs. */
static PyObject* dynamic_attrs_from_class_def(EncoderObj *context, PyObject *class_def, PyObject *value)
{
    PyObject *get_func = PyObject_GetAttrString(class_def, "getDynamicAttrVals");
    if (!get_func)
        return NULL;

    PyObject *dynamic_attrs = PyObject_CallFunctionObjArgs(get_func, value, context->include_private, NULL);
    Py_DECREF(get_func);
    if (!dynamic_attrs)
        return NULL;

    if (!PyDict_Check(dynamic_attrs)) {
        PyErr_SetString(amfast_EncodeError, "ClassDef.getDynamicAttrVals must return a dict.");
        Py_DECREF(dynamic_attrs);
        return NULL;
    }

    if (type_dict(class_def, context->type_map, dynamic_attrs, 0) == 0) {
        Py_DECREF(dynamic_attrs);
        return NULL;
    }

    return dynamic_attrs;
}

/* Write a Python object in AMF0. */
static int write_object_AMF0(EncoderObj *context, PyObject *value)
{
    int wrote_ref = write_reference_AMF0(context, value);
    if (wrote_ref == 0 || wrote_ref == 1) {
        return wrote_ref;
    }

    PyObject *class_def = class_def_from_class(context, value);
    if (!class_def)
        return 0;

    if (class_def == Py_None) {
        Py_DECREF(class_def);
        return write_anonymous_object_AMF0(context, value);
    }

    // Check for AMF3 object
    PyObject *amf3 = PyObject_GetAttrString(class_def, "amf3");
    if (amf3 == Py_True) {
        // Encode this object in AMF3
        Py_DECREF(amf3);
        Py_DECREF(class_def);
        if (Encoder_writeByte(context, AMF3_AMF0) == 0)
            return 0;

        // Create new context for AMF3 encode
        EncoderObj *new_context = (EncoderObj*)Encoder_copy(context, 1, 0);
        if (new_context == NULL)
            return 0;

        int result = encode_AMF3(new_context, value);
        Py_DECREF(new_context);
        return result;
    } else {
        Py_DECREF(amf3);
    }

    // Write marker byte
    if (!Encoder_writeByte(context, TYPED_OBJ_AMF0)) {
        Py_DECREF(class_def);
        return 0;
    }

    // Class has a ClassDef
    // encode class definition
    if (!encode_class_def_AMF0(context, class_def)) {
        Py_DECREF(class_def);
        return 0;
    }

    // Get all attributes to encode
    PyObject *attrs = PyDict_New();
    if (!attrs) {
        Py_DECREF(class_def);
        return 0;
    }

    // Get static attrs
    PyObject *static_attrs = static_attr_vals_from_class_def(context, class_def, value);
    if (!static_attrs) {
        Py_DECREF(class_def);
        Py_DECREF(attrs);
        return 0;
    }

    // Get static attr names
    PyObject *static_attr_names = PyObject_GetAttrString(class_def, "static_attrs");
    if (!static_attr_names) {
        Py_DECREF(class_def);
        Py_DECREF(attrs);
        Py_DECREF(static_attrs);
        return 0;
    }

    Py_ssize_t static_attr_len = PySequence_Size(static_attrs);
    if (static_attr_len == -1) {
        Py_DECREF(class_def);
        Py_DECREF(attrs);
        Py_DECREF(static_attrs);
        return 0;
    }

    int i;
    for (i = 0; i < static_attr_len; i++) {
        PyObject *static_attr_name = PySequence_GetItem(static_attr_names, i);
        if (!static_attr_name) {
            Py_DECREF(class_def);
            Py_DECREF(attrs);
            Py_DECREF(static_attrs);
            return 0;
        }

        PyObject *static_attr = PySequence_GetItem(static_attrs, i);
        if (!static_attr) {
            Py_DECREF(class_def);
            Py_DECREF(attrs);
            Py_DECREF(static_attrs);
            Py_DECREF(static_attr_name);
            return 0;
        }

        int result = PyDict_SetItem(attrs, static_attr_name, static_attr);
        Py_DECREF(static_attr_name);
        Py_DECREF(static_attr);
        if (result == -1) {
            Py_DECREF(class_def);
            Py_DECREF(attrs);
            Py_DECREF(static_attrs);
            return 0;
        }
    }
    Py_DECREF(static_attrs);
    Py_DECREF(static_attr_names);

    // Get dynamic attrs
    if (PyObject_HasAttrString(class_def, "DYNAMIC_CLASS_DEF")) {
        PyObject *dynamic_attrs = dynamic_attrs_from_class_def(context, class_def, value);
        if (!dynamic_attrs) {
            Py_DECREF(class_def);
            Py_DECREF(attrs);
            return 0;
        }

        int result = PyDict_Merge(attrs, dynamic_attrs, 0);
        Py_DECREF(dynamic_attrs);
        if (result == -1) {
            Py_DECREF(class_def);
            Py_DECREF(attrs);
            return 0;
        }
    }
    Py_DECREF(class_def);

    int result = encode_dynamic_dict_AMF0(context, attrs);
    Py_DECREF(attrs);
    return result;
}

/* Encode an AMF packet. */
static int encode_packet(EncoderObj *context, PyObject *value)
{
    // write flash client_type
    PyObject *client_type = PyObject_GetAttrString(value, "client_type");
    if (!client_type)
        return 0;

    short amf_client_type = (short) PyInt_AsLong(client_type);
    Py_DECREF(client_type); 
    if (amf_client_type < 0)
        return 0;

    if (!encode_ushort(context, (unsigned short)amf_client_type))
        return 0;

    // write headers
    PyObject *headers = PyObject_GetAttrString(value, "headers");
    if (!headers)
        return 0;

    Py_ssize_t header_count = 0;
    if (PySequence_Check(headers)) {
        header_count = PySequence_Size(headers);
        if (header_count == -1) {
            Py_DECREF(headers);
            return 0;
        }
    }

    if (!encode_ushort(context, (unsigned short)header_count)) {
        Py_DECREF(headers);
        return 0;
    }

    int i;
    for (i = 0; i < header_count; i++) {
        PyObject *header = PySequence_GetItem(headers, i);
        if (!header) {
            Py_DECREF(headers);
            return 0;
        }

        int wrote_header = encode_packet_header_AMF0(context, header);
        Py_DECREF(header);
        if (!wrote_header) {
            Py_DECREF(headers);
            return 0;
        }
    }
    Py_DECREF(headers);

    // write messages
    PyObject *messages = PyObject_GetAttrString(value, "messages");
    if (!messages)
        return 0;

    Py_ssize_t message_count = PySequence_Size(messages);
    if (message_count == -1) {
        Py_DECREF(messages);
        return 0;
    }
    if (!encode_ushort(context, (unsigned short)message_count)) {
        Py_DECREF(messages);
        return 0;
    }

    for (i = 0; i < message_count; i++) {
        PyObject *message = PySequence_GetItem(messages, i);
        if (!message) {
            Py_DECREF(messages);
            return 0;
        }

        int wrote_message = encode_packet_message_AMF0(context, message);
        Py_DECREF(message);
        if (!wrote_message) {
            Py_DECREF(messages);
            return 0;
        }
    }
    Py_DECREF(messages);
    return 1;
}

/* Encode a Packet header in AMF0. */
static int encode_packet_header_AMF0(EncoderObj *context, PyObject *value)
{
    PyObject *header_name = PyObject_GetAttrString(value, "name");
    if (!header_name)
        return 0;

    int result = encode_object_as_string_AMF0(context, header_name, 0);
    Py_DECREF(header_name);
    if (!result)
        return 0;

    PyObject *required = PyObject_GetAttrString(value, "required");
    if (!required)
        return 0;

    result = encode_bool_AMF0(context, required);
    Py_DECREF(required);
    if (!result)
        return 0;

    PyObject *body = PyObject_GetAttrString(value, "value");
    if (!body)
        return 0;

    // Encode header value with a new context, so references are reset
    EncoderObj *new_context = (EncoderObj*)Encoder_copy(context, 0, 1);
    if (!new_context) {
        Py_DECREF(body);
        return 0;
    }

    result = encode_AMF0(new_context, body);
    Py_DECREF(body);
    if (!result) {
        Py_DECREF(new_context);
        return 0;
    }

    int new_len = Encoder_tell(new_context);
    char *new_buf = Encoder_read(new_context); // Don't decref new_context until we've used new_buf
    if (new_buf == NULL) {
        Py_DECREF(new_context);
        return 0;
    }

    if (!encode_ulong(context, (unsigned int)new_len)) {
        Py_DECREF(new_context);
        return 0;
    }

    result = Encoder_write(context, new_buf, new_len);
    Py_DECREF(new_context);
    return result;
}

/* Encode a Packet message in AMF0. */
static int encode_packet_message_AMF0(EncoderObj *context, PyObject *value)
{
    PyObject *target = PyObject_GetAttrString(value, "target");
    if (!target)
        return 0;

    int result = encode_object_as_string_AMF0(context, target, 0);
    Py_DECREF(target);
    if (!result)
        return 0;

    PyObject *response = PyObject_GetAttrString(value, "response");
    if (!response)
        return 0;

    result = encode_object_as_string_AMF0(context, response, 0);
    if (!result) {
        Py_DECREF(response);
        return 0;
    }

    PyObject *body = PyObject_GetAttrString(value, "body");
    if (!body) {
        Py_DECREF(response);
        return 0;
    }

    // Encode message body with a new context, so references are reset
    EncoderObj *new_context;
    if (PySequence_Size(response) > 0 && (PyList_Check(body) || PyTuple_Check(body))) {
        // We're encoding a request,
        // Don't count argument list 
        // in reference count.

        // Always use AMF0 context!
        new_context = (EncoderObj*)Encoder_copy(context, 0, 1);
        result = write_list_AMF0(new_context, body, 0);
    } else {
        if (context->amf3 == Py_True) {
            new_context = (EncoderObj*)Encoder_copy(context, 1, 1);
            if (!Encoder_writeByte(new_context, AMF3_AMF0))
                return 0;
            result = encode_AMF3(new_context, body);
        } else {
            new_context = (EncoderObj*)Encoder_copy(context, 0, 1);
            result = encode_AMF0(new_context, body);
        }
    }
    Py_DECREF(response);
    Py_DECREF(body);

    if (!result) {
        Py_DECREF(new_context);
        return 0;
    }

    int new_len = Encoder_tell(new_context);
    char *new_buf = Encoder_read(new_context); // Don't decref new_context until we've used new_buf
    if (new_buf == NULL) {
        Py_DECREF(new_context);
        return 0;
    }

    if (!encode_ulong(context, (unsigned int)new_len)) {
        Py_DECREF(new_context);
        return 0;
    }

    result = Encoder_write(context, new_buf, new_len);
    Py_DECREF(new_context);
    return result;
}

/* Encoding function map for AMF0. */
static int encode_AMF0(EncoderObj *context, PyObject *value)
{
    // Determine object type
    if (value == Py_None) {
        return Encoder_writeByte(context, NULL_AMF0);
    } else if (PyBool_Check(value)) {
        if (!Encoder_writeByte(context, BOOL_AMF0))
            return 0;
        return encode_bool_AMF0(context, value);
    } else if (PyInt_Check(value)) {
        if (!Encoder_writeByte(context, NUMBER_AMF0))
            return 0;
        return encode_int_AMF0(context, value);
    } else if (PyLong_Check(value)) {
        if (!Encoder_writeByte(context, NUMBER_AMF0))
            return 0;
        return encode_long_AMF0(context, value);
    } else if (PyFloat_Check(value)) {
        if (!Encoder_writeByte(context, NUMBER_AMF0))
            return 0;
        return encode_float_AMF0(context, value);
    } else if (PyString_Check(value)) {
        return write_string_AMF0(context, value);
    } else if (PyUnicode_Check(value)) {
        return write_unicode_AMF0(context, value);
    } else if (PyList_Check(value) || PyTuple_Check(value)) {
        return write_list_AMF0(context, value, 1);
    } else if (PyDict_Check(value)) {
        return write_dict_AMF0(context, value);
    } else if (PyDateTime_Check(value) || PyDate_Check(value)) {
       return write_date_AMF0(context, value);
    } else if (check_xml(value)) {
        return write_xml_AMF0(context, value);
    } else if (check_byte_array(value)) {
        // Force switch to AMF3
        if (Encoder_writeByte(context, AMF3_AMF0) == 0)
            return 0;

        // Create new context for AMF3 encode
        EncoderObj *new_context = (EncoderObj*)Encoder_copy(context, 1, 0);
        if (new_context == NULL)
            return 0;

        int result = encode_AMF3(new_context, value);
        Py_DECREF(new_context);
        return result;
    } else if (check_proxy(value)) {
        return write_proxy_AMF0(context, value);
    } else if (check_no_proxy(value)) {
        return write_proxy_AMF0(context, value);
    }

    return write_object_AMF0(context, value);
}

/* Encoding function map. */
static int encode_AMF3(EncoderObj *context, PyObject *value)
{
    // Determine object type
    if (value == Py_None) {
        return encode_none_AMF3(context);
    } else if (PyBool_Check(value)) {
        return encode_bool_AMF3(context, value);
    } else if (PyInt_Check(value)) {
        return write_int_AMF3(context, value);
    } else if (PyString_Check(value)) {
        if (!Encoder_writeByte(context, STRING_TYPE))
            return 0;
        return serialize_string_AMF3(context, value);
    } else if (PyUnicode_Check(value)) {
        if (!Encoder_writeByte(context, STRING_TYPE))
            return 0;
        return serialize_unicode_AMF3(context, value);
    } else if (PyFloat_Check(value)) {
        if (!Encoder_writeByte(context, DOUBLE_TYPE))
            return 0;
        return encode_float(context, value);
    } else if (PyLong_Check(value)) {
        if (!Encoder_writeByte(context, DOUBLE_TYPE))
            return 0;
        return encode_long_AMF3(context, value);
    } else if (PyList_Check(value) || PyTuple_Check(value)) {
        return write_list_AMF3(context, value);
    } else if (PyDict_Check(value)) {
        return write_dict_AMF3(context, value);
    } else if (PyDateTime_Check(value) || PyDate_Check(value)) {
        if (!Encoder_writeByte(context, DATE_TYPE))
            return 0;
        return serialize_date_AMF3(context, value);
    } else if (check_xml(value)) {
        return write_xml_AMF3(context, value);
    } else if (check_byte_array(value)) {
        if (!Encoder_writeByte(context, BYTE_ARRAY_TYPE))
            return 0;
        return serialize_byte_array_AMF3(context, value);
    } else if (check_proxy(value)) {
        return write_proxy_AMF3(context, value);
    } else if (check_no_proxy(value)) {
        return write_no_proxy_AMF3(context, value);
    }

    #ifdef Py_BYTEARRAYOBJECT_H
    // ByteArray encoding is only available in 2.6+
    else if (PyByteArray_Check(value)) {
        if (!Encoder_writeByte(context, BYTE_ARRAY_TYPE))
            return 0;
        return serialize_byte_array_AMF3(context, value);
    } 
    #endif

    // Custom object
    if (!Encoder_writeByte(context, OBJECT_TYPE))
            return 0;

    return serialize_object_AMF3(context, value);
}

/* Encode a Python object in AMF. */
static PyObject* py_encode(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *value = NULL;
    PyObject *context = NULL;

    static char *kwlist[] = {"value", "context", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|O", kwlist, &value, &context))
        return NULL;

    // Create default context.
    if (context == NULL) {
        PyObject *cls = PyObject_GetAttrString(context_mod, "EncoderContext");
        if (cls == NULL)
            return NULL;

        context = PyObject_CallObject(cls, NULL);
        Py_DECREF(cls);
        if (context == NULL)
            return NULL;
    } else {
        Py_INCREF(context);
    }

    if (Encoder_check(context) != 1) {
        PyErr_SetString(amfast_EncodeError, "Argument must be of type amfast.context.EncoderContext");
        Py_DECREF(context);
        return NULL;
    }
    EncoderObj *enc_context = (EncoderObj*)context;

    int result;
    if (enc_context->amf3 == Py_True) {
        result = encode_AMF3(enc_context, value);
    } else {
        result = encode_AMF0(enc_context, value);
    }

    if (result == 0) {
        Py_DECREF(context);
        return NULL;
    }

    PyObject *return_val = Encoder_getReturnVal(enc_context);
    Py_DECREF(context);
    return return_val;
}

/* Encode an AMF Packet object in AMF. */
static PyObject* py_encode_packet(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *value = NULL;
    PyObject *context = NULL;

    static char *kwlist[] = {"value", "context", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|O", kwlist, &value, &context))
        return NULL;

    // Create default context.
    if (context == NULL) {
        PyObject *cls = PyObject_GetAttrString(context_mod, "EncoderContext");
        if (cls == NULL)
            return NULL;

        context = PyObject_CallObject(cls, NULL);
        Py_DECREF(cls);
        if (context == NULL)
            return NULL;
    } else {
        Py_INCREF(context);
    }

    if (Encoder_check(context) != 1) {
        PyErr_SetString(amfast_EncodeError, "Argument must be of type amfast.context.EncoderContext");
        Py_DECREF(context);
        return NULL;
    }
    EncoderObj *enc_context = (EncoderObj*)context;

    int result = encode_packet(enc_context, value);
    if (result == 0) {
        Py_DECREF(context);
        return NULL;
    }

    PyObject *return_val = Encoder_getReturnVal(enc_context);
    Py_DECREF(context);
    return return_val;
}

/* Expose functions as Python module functions. */
static PyMethodDef encode_methods[] = {
    {"encode", (PyCFunction)py_encode, METH_VARARGS | METH_KEYWORDS,
    "Description:\n"
    "=============\n"
    "Encode a Python object in AMF format.\n\n"
    "Useage:\n"
    "===========\n"
    "buffer = encode(value, context)\n\n"
    "arguments:\n"
    "===========\n"
    " * value = object, Object to encode.\n"
    " * contest - amfast.context.EncoderObj, Holds options valid for a single encode session.\n"},
    {"encode_packet", (PyCFunction)py_encode_packet, METH_VARARGS | METH_KEYWORDS,
    "Description:\n"
    "=============\n"
    "Encode an AMF packet.\n\n"
    "Useage:\n"
    "===========\n"
    "buffer = encode(packet, context)\n\n"
    "arguments:\n"
    "===========\n"
    " * packet - amfast.remoting.Packet, The AMF packet to encode.\n"
    " * contest - amfast.context.EncoderObj, Holds options valid for a single encode session.\n"},

    {NULL, NULL, 0, NULL}   /* sentinel */
};

PyMODINIT_FUNC
initencode(void)
{
    PyObject *m;

    m = Py_InitModule("encode", encode_methods);
    if (m == NULL)
        return;

    // Setup exceptions
    if (!amfast_mod) {
        amfast_mod = PyImport_ImportModule("amfast");
        if(!amfast_mod) {
            return;
        }
    }

    context_mod = import_context_mod();
    if (context_mod == NULL)
        return;

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

    if (!class_def_mod) {
        class_def_mod = PyImport_ImportModule("amfast.class_def");
        if(!class_def_mod) {
            return;
        }
    }

    amfast_Error = PyObject_GetAttrString(amfast_mod, "AmFastError");
    if (amfast_Error == NULL) {
        return;
    }

    amfast_EncodeError = PyErr_NewException("amfast.encode.EncodeError", amfast_Error, NULL);
    if (amfast_EncodeError == NULL) {
        return;
    }

    if (PyModule_AddObject(m, "EncodeError", amfast_EncodeError) == -1) {
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
