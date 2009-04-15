/*
 * Contexts are used to keep track of data relevant
 * to a single run through the encoder/decoder.
 */
#include <Python.h>

typedef struct {
    PyObject_HEAD
    PyObject **objs;
    int len;
    int pos;
} IdxObj;

int Idx_map(IdxObj *self, PyObject *obj);
PyObject* Idx_ret(IdxObj *self, int idx);

typedef struct {
    PyObject_HEAD;
    PyObject *buf; // Input
    PyObject *_buf_str; // Temporary storage of PyString read from file-like-obj
    PyObject *amf3; // True to decode as AMF3.
    PyObject *class_mapper; // Object that retrieves ClassDef objects.
    PyObject *obj_refs; // IdxObj for objects
    PyObject *string_refs; // IdxObj for strings
    PyObject *class_refs; // IdxObj for ClassDefs
    PyObject *read_name; // PyString name of method to read from file-like-obj
    PyObject *apply_name; // PyString name of method that applies attributes to instances
    PyObject *class_def_name; // PyString name of method to retrieve a ClassDef
    PyObject *extern_name; // PyString name of method to read externalizable objects
    int int_buf; // 1 if we're using an amfast.buffer.Buffer object as the input, 0 if not
} DecoderObj;

int Decoder_check(PyObject *self);
PyObject* Decoder_copy(DecoderObj *self, int amf3);
int Decoder_tell(DecoderObj *self);
PyObject* Decoder_readPyString(DecoderObj *self, int len);
int Decoder_skipBytes(DecoderObj *self, int len);
char* Decoder_readCString(DecoderObj *self, int len);
char Decoder_readByte(DecoderObj *self);

typedef struct {
    PyObject_HEAD
    PyObject *refs;
    int idx;
} RefObj;

int Ref_map(RefObj *self, PyObject *obj);
int Ref_ret(RefObj *self, PyObject *obj);

typedef struct {
    PyObject_HEAD;
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
    PyObject *array_collection_def; // ClassDef for ArrayCollection
    PyObject *object_proxy_def; // ClassDef for ObjectProxy
    PyObject *class_def_name; // Name of method to get class def
    PyObject *write_name; // PyString name of method to write to buffer
    PyObject *extern_name; // PyString name of method to write externalizable objects
    int int_buf; // 1 if we're using an amfast.buffer.Buffer object as the output, 0 if not
} EncoderObj;

int Encoder_check(PyObject *self);
int Encoder_writePyString(EncoderObj *self, PyObject *py_str);
int Encoder_writeCStringLength(EncoderObj *self, char *str, int len);
int Encoder_writeByte(EncoderObj *self, char byte);
int Encoder_tell(EncoderObj *self);
char* Encoder_read(EncoderObj *self);
PyObject* Encoder_copy(EncoderObj *self, int amf3, int new_buf);
