#ifndef Py_BUFFERMODULE_H
#define Py_BUFFERMODULE_H
#ifdef __cplusplus
extern "C" {
#endif

// Use this string buffer for better performance when using string input/outputs.
typedef struct {
    PyObject_HEAD
    PyObject *src_str; // Ptr to source if source string was passed
    char *buf; // C-Buffer
    int len; // Length of current buffer
    int pos; // Current position in buffer
} BufferObj;

//char* Buffer_read(BufferObj *self, int len);
PyObject* Buffer_readPyString(BufferObj *self, int len);
int Buffer_tell(BufferObj *self);
int Buffer_seek(BufferObj *self, int pos);
int Buffer_writeCStringLength(BufferObj *self, char *str, int len);
int Buffer_writePyString(BufferObj *self, PyObject* py_str);

// All this nasty stuff is for properly exposing API functions.

// Number of exposed functions
#define PyBuffer_API_pointers 1

// C Exposed functions
#define Buffer_read_NUM 0
#define Buffer_read_RETURN char*
#define Buffer_read_PROTO (BufferObj *self, int len)

#ifdef BUFFER_MODULE
/* This section is used when compiling module.c */

static Buffer_read_RETURN Buffer_read Buffer_read_PROTO;

#else
/* This section is used in modules that use the module's API */

static void **PyBuffer_API;

#define Buffer_read \
 (*(Buffer_read_RETURN (*)Buffer_read_PROTO) PyBuffer_API[Buffer_read_NUM])

static PyObject* import_buffer_mod(void)
{
    PyObject *m = PyImport_ImportModule("amfast.buffer");
    if (m == NULL)
        return NULL;

    PyObject *c_api = PyObject_GetAttrString(m, "_C_API");
    if (c_api == NULL)
         return NULL;
    if (!PyCObject_Check(c_api))
        return NULL;

    PyBuffer_API = (void **)PyCObject_AsVoidPtr(c_api);
    Py_DECREF(c_api);
    return m;
}

#endif

#ifdef __cplusplus
}
#endif

#endif /* !defined(Py_MODULE_H) */


