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
    PyObject *class_mapper; // Object that retrieves ClassDef objects.
    PyObject *obj_refs; // IdxObj for objects
    PyObject *string_refs; // IdxObj for strings
    PyObject *class_refs; // IdxObj for ClassDefs
    PyObject *read_name; // PyString name of method to read from file-like-obj
    PyObject *apply_name; // PyString name of method that applies attributes to instances
    PyObject *class_def_name; // PyString name of method to retrieve a ClassDef
    PyObject *extern_name; // PyString name of method to read externalizable objects
    int int_buf; // 1 if we're using an amfast.buffer.Buffer object as the input, 0 if not
    int amf3; // 1 to encode objects using AMF3, 0 to encode objects using AMF0
} DecoderObj;

PyObject* Decoder_copy(DecoderObj *self, int amf3);
int Decoder_tell(DecoderObj *self);
PyObject* Decoder_readPyString(DecoderObj *self, int len);
int Decoder_skipBytes(DecoderObj *self, int len);
char* Decoder_readCString(DecoderObj *self, int len);
char Decoder_readByte(DecoderObj *self);
