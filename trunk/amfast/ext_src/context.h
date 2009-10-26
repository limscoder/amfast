#ifndef Py_CONTEXTMODULE_H
#define Py_CONTEXTMODULE_H
#ifdef __cplusplus
extern "C" {
#endif

// For 2.4 support
#if PY_VERSION_HEX < 0x02050000
#ifndef PY_SSIZE_T_MAX
typedef int Py_ssize_t;
#define PY_SSIZE_T_MAX INT_MAX
#define PY_SSIZE_T_MIN INT_MIN
#endif
#endif

/*
 * Contexts are used to keep track of data relevant
 * to a single run through the encoder/decoder.
 */
typedef struct {
    PyObject_HEAD
    PyObject **objs;
    int len;
    int pos;
} IdxObj;

// Number of exposed functions
#define PyIdx_API_pointers 2

// C Exposed functions
#define Idx_map_NUM 0
#define Idx_map_RETURN int
#define Idx_map_PROTO (IdxObj *self, PyObject *obj)

#define Idx_ret_NUM 1
#define Idx_ret_RETURN PyObject*
#define Idx_ret_PROTO (IdxObj *self, int idx)

#ifdef CONTEXT_MODULE
/* This section is used when compiling module.c */

static Idx_map_RETURN Idx_map Idx_map_PROTO;
static Idx_ret_RETURN Idx_ret Idx_ret_PROTO;

#else
/* This section is used in modules that use the module's API */

static void **PyIdx_API;

#define Idx_map \
 (*(Idx_map_RETURN (*)Idx_map_PROTO) PyIdx_API[Idx_map_NUM])

#define Idx_ret \
 (*(Idx_ret_RETURN (*)Idx_ret_PROTO) PyIdx_API[Idx_ret_NUM])

#endif

typedef struct {
    PyObject_HEAD
    PyObject *buf; // Input
    PyObject *_buf_str; // Temporary storage of PyString read from file-like-obj
    PyObject *amf3; // True to decode as AMF3.
    PyObject *class_mapper; // Object that retrieves ClassDef objects.
    PyObject *obj_refs; // IdxObj for objects
    PyObject *string_refs; // IdxObj for strings
    PyObject *class_refs; // IdxObj for ClassDefs
    PyObject *type_map; // Maps objects to different types
    PyObject *read_name; // PyString name of method to read from file-like-obj
    PyObject *apply_name; // PyString name of method that applies attributes to instances
    PyObject *class_def_name; // PyString name of method to retrieve a ClassDef
    PyObject *extern_name; // PyString name of method to read externalizable objects
    int int_buf; // 1 if we're using an amfast.buffer.Buffer object as the input, 0 if not
} DecoderObj;

// Number of exposed functions
#define PyDecoder_API_pointers 7

// C Exposed functions
#define Decoder_check_NUM 0
#define Decoder_check_RETURN int
#define Decoder_check_PROTO (PyObject *self)

#define Decoder_copy_NUM 1
#define Decoder_copy_RETURN PyObject*
#define Decoder_copy_PROTO (DecoderObj *self, int amf3)

#define Decoder_tell_NUM 2
#define Decoder_tell_RETURN int
#define Decoder_tell_PROTO (DecoderObj *self)

#define Decoder_readPyString_NUM 3
#define Decoder_readPyString_RETURN PyObject*
#define Decoder_readPyString_PROTO (DecoderObj *self, int amf3)

#define Decoder_skipBytes_NUM 4
#define Decoder_skipBytes_RETURN int
#define Decoder_skipBytes_PROTO (DecoderObj *self, int len)

#define Decoder_read_NUM 5
#define Decoder_read_RETURN char*
#define Decoder_read_PROTO (DecoderObj *self, int amf3)

#define Decoder_readByte_NUM 6
#define Decoder_readByte_RETURN char*
#define Decoder_readByte_PROTO (DecoderObj *self)

#ifdef CONTEXT_MODULE
/* This section is used when compiling module.c */

static Decoder_check_RETURN Decoder_check Decoder_check_PROTO;
static Decoder_copy_RETURN Decoder_copy Decoder_copy_PROTO;
static Decoder_tell_RETURN Decoder_tell Decoder_tell_PROTO;
static Decoder_readPyString_RETURN Decoder_readPyString Decoder_readPyString_PROTO;
static Decoder_skipBytes_RETURN Decoder_skipBytes Decoder_skipBytes_PROTO;
static Decoder_read_RETURN Decoder_read Decoder_read_PROTO;
static Decoder_readByte_RETURN Decoder_readByte Decoder_readByte_PROTO;

#else
/* This section is used in modules that use the module's API */

static void **PyDecoder_API;

#define Decoder_check \
 (*(Decoder_check_RETURN (*)Decoder_check_PROTO) PyDecoder_API[Decoder_check_NUM])

#define Decoder_copy \
 (*(Decoder_copy_RETURN (*)Decoder_copy_PROTO) PyDecoder_API[Decoder_copy_NUM])

#define Decoder_tell \
 (*(Decoder_tell_RETURN (*)Decoder_tell_PROTO) PyDecoder_API[Decoder_tell_NUM])

#define Decoder_readPyString \
 (*(Decoder_readPyString_RETURN (*)Decoder_readPyString_PROTO) PyDecoder_API[Decoder_readPyString_NUM])

#define Decoder_skipBytes \
 (*(Decoder_skipBytes_RETURN (*)Decoder_skipBytes_PROTO) PyDecoder_API[Decoder_skipBytes_NUM])

#define Decoder_read \
 (*(Decoder_read_RETURN (*)Decoder_read_PROTO) PyDecoder_API[Decoder_read_NUM])

#define Decoder_readByte \
 (*(Decoder_readByte_RETURN (*)Decoder_readByte_PROTO) PyDecoder_API[Decoder_readByte_NUM])

#endif

typedef struct {
    PyObject_HEAD
    PyObject *refs;
    int idx;
} RefObj;

// Number of exposed functions
#define PyRef_API_pointers 2

// C Exposed functions
#define Ref_map_NUM 0
#define Ref_map_RETURN int
#define Ref_map_PROTO (RefObj *self, PyObject *obj)

#define Ref_ret_NUM 1
#define Ref_ret_RETURN int
#define Ref_ret_PROTO (RefObj *self, PyObject *obj)

#ifdef CONTEXT_MODULE
/* This section is used when compiling module.c */

static Ref_map_RETURN Ref_map Ref_map_PROTO;
static Ref_ret_RETURN Ref_ret Ref_ret_PROTO;

#else
/* This section is used in modules that use the module's API */

static void **PyRef_API;

#define Ref_map \
 (*(Ref_map_RETURN (*)Ref_map_PROTO) PyRef_API[Ref_map_NUM])

#define Ref_ret \
 (*(Ref_ret_RETURN (*)Ref_ret_PROTO) PyRef_API[Ref_ret_NUM])

#endif

typedef struct {
    PyObject_HEAD
    PyObject *buf; // Input
    PyObject *amf3; // True to encode as AMF3.
    PyObject *use_collections; // True to encode lists and tuples as ArrayCollections.
    PyObject *use_proxies; // True to encode dicts as ObjectProxies
    PyObject *use_refs; // True to encode objects as references.
    PyObject *use_legacy_xml; // True to encode XML as XMLDocument instead of e4x
    PyObject *include_private; // True to encode attributes starting with '_' - Default = False
    PyObject *class_mapper; // Object that retrieves ClassDef objects.
    PyObject *obj_refs; // IdxObj for objects
    PyObject *string_refs; // IdxObj for strings
    PyObject *class_refs; // IdxObj for ClassDefs
    PyObject *type_map; // Maps objects to different types
    PyObject *array_collection_def; // ClassDef for ArrayCollection
    PyObject *object_proxy_def; // ClassDef for ObjectProxy
    PyObject *class_def_name; // Name of method to get class def
    PyObject *write_name; // PyString name of method to write to buffer
    PyObject *extern_name; // PyString name of method to write externalizable objects
    int int_buf; // 1 if we're using an amfast.buffer.Buffer object as the output, 0 if not
} EncoderObj;

// Number of exposed functions
#define PyEncoder_API_pointers 8

// C Exposed functions
#define Encoder_check_NUM 0
#define Encoder_check_RETURN int
#define Encoder_check_PROTO (PyObject *self)

#define Encoder_writePyString_NUM 1
#define Encoder_writePyString_RETURN int
#define Encoder_writePyString_PROTO (EncoderObj *self, PyObject *py_str)

#define Encoder_write_NUM 2
#define Encoder_write_RETURN int
#define Encoder_write_PROTO (EncoderObj *self, char *str, int len)

#define Encoder_writeByte_NUM 3
#define Encoder_writeByte_RETURN int
#define Encoder_writeByte_PROTO (EncoderObj *self, char byte)

#define Encoder_tell_NUM 4
#define Encoder_tell_RETURN int
#define Encoder_tell_PROTO (EncoderObj *self)

#define Encoder_read_NUM 5
#define Encoder_read_RETURN char*
#define Encoder_read_PROTO (EncoderObj *self)

#define Encoder_copy_NUM 6
#define Encoder_copy_RETURN PyObject*
#define Encoder_copy_PROTO (EncoderObj *self, int amf3, int new_buf)

#define Encoder_getReturnVal_NUM 7
#define Encoder_getReturnVal_RETURN PyObject*
#define Encoder_getReturnVal_PROTO (EncoderObj *self)


#ifdef CONTEXT_MODULE
/* This section is used when compiling module.c */

static Encoder_check_RETURN Encoder_check Encoder_check_PROTO;
static Encoder_writePyString_RETURN Encoder_writePyString Encoder_writePyString_PROTO;
static Encoder_write_RETURN Encoder_write Encoder_write_PROTO;
static Encoder_writeByte_RETURN Encoder_writeByte Encoder_writeByte_PROTO;
static Encoder_tell_RETURN Encoder_tell Encoder_tell_PROTO;
static Encoder_read_RETURN Encoder_read Encoder_read_PROTO;
static Encoder_copy_RETURN Encoder_copy Encoder_copy_PROTO;
static Encoder_getReturnVal_RETURN Encoder_getReturnVal Encoder_getReturnVal_PROTO;

#else
/* This section is used in modules that use the module's API */

static void **PyEncoder_API;

#define Encoder_check \
 (*(Encoder_check_RETURN (*)Encoder_check_PROTO) PyEncoder_API[Encoder_check_NUM])

#define Encoder_writePyString \
 (*(Encoder_writePyString_RETURN (*)Encoder_writePyString_PROTO) PyEncoder_API[Encoder_writePyString_NUM])

#define Encoder_write \
 (*(Encoder_write_RETURN (*)Encoder_write_PROTO) PyEncoder_API[Encoder_write_NUM])

#define Encoder_writeByte \
 (*(Encoder_writeByte_RETURN (*)Encoder_writeByte_PROTO) PyEncoder_API[Encoder_writeByte_NUM])

#define Encoder_tell \
 (*(Encoder_tell_RETURN (*)Encoder_tell_PROTO) PyEncoder_API[Encoder_tell_NUM])

#define Encoder_read \
 (*(Encoder_read_RETURN (*)Encoder_read_PROTO) PyEncoder_API[Encoder_read_NUM])

#define Encoder_copy \
 (*(Encoder_copy_RETURN (*)Encoder_copy_PROTO) PyEncoder_API[Encoder_copy_NUM])

#define Encoder_getReturnVal \
 (*(Encoder_getReturnVal_RETURN (*)Encoder_getReturnVal_PROTO) PyEncoder_API[Encoder_getReturnVal_NUM])

#endif

#ifndef CONTEXT_MODULE
static PyObject* import_context_mod(void)
{
    PyObject *m = PyImport_ImportModule("amfast.context");
    if (m == NULL)
        return NULL;

    PyObject *idx_c_api = PyObject_GetAttrString(m, "_IDX_C_API");
    if (idx_c_api == NULL)
         return NULL;
    if (!PyCObject_Check(idx_c_api))
        return NULL;

    PyIdx_API = (void **)PyCObject_AsVoidPtr(idx_c_api);
    Py_DECREF(idx_c_api);

    PyObject *decoder_c_api = PyObject_GetAttrString(m, "_DECODER_C_API");
    if (decoder_c_api == NULL)
         return NULL;
    if (!PyCObject_Check(decoder_c_api))
        return NULL;

    PyDecoder_API = (void **)PyCObject_AsVoidPtr(decoder_c_api);
    Py_DECREF(decoder_c_api);

    PyObject *ref_c_api = PyObject_GetAttrString(m, "_REF_C_API");
    if (ref_c_api == NULL)
         return NULL;
    if (!PyCObject_Check(ref_c_api))
        return NULL;

    PyRef_API = (void **)PyCObject_AsVoidPtr(ref_c_api);
    Py_DECREF(ref_c_api);

    PyObject *encoder_c_api = PyObject_GetAttrString(m, "_ENCODER_C_API");
    if (encoder_c_api == NULL)
         return NULL;
    if (!PyCObject_Check(encoder_c_api))
        return NULL;

    PyEncoder_API = (void **)PyCObject_AsVoidPtr(encoder_c_api);
    Py_DECREF(encoder_c_api);

    return m;
}
#endif

#ifdef __cplusplus
}
#endif

#endif /* !defined(Py_MODULE_H) */
