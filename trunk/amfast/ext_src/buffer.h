#ifndef Py_BUFFERMODULE_H
#define Py_BUFFERMODULE_H
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

// Use this string buffer for better performance when
// using string input/outputs.
typedef struct {
    PyObject_HEAD
    PyObject *src_str; // Ptr to source if source string was passed
    char *buf; // C-Buffer
    int len; // Length of current buffer
    int pos; // Current position in buffer
} BufferObj;

// All this nasty stuff is for properly exposing API functions. Ugh

// Number of exposed functions
#define PyBuffer_API_pointers 6

// C Exposed functions
#define Buffer_read_NUM 0
#define Buffer_read_RETURN char*
#define Buffer_read_PROTO (BufferObj *self, int len)

#define Buffer_readPyString_NUM 1
#define Buffer_readPyString_RETURN PyObject*
#define Buffer_readPyString_PROTO (BufferObj *self, int len)

#define Buffer_tell_NUM 2
#define Buffer_tell_RETURN int
#define Buffer_tell_PROTO (BufferObj *self)

#define Buffer_seek_NUM 3
#define Buffer_seek_RETURN int
#define Buffer_seek_PROTO (BufferObj *self, int pos)

#define Buffer_write_NUM 4
#define Buffer_write_RETURN int
#define Buffer_write_PROTO (BufferObj *self, char *str, int len)

#define Buffer_writePyString_NUM 5
#define Buffer_writePyString_RETURN int
#define Buffer_writePyString_PROTO (BufferObj *self, PyObject* py_str)

#ifdef BUFFER_MODULE
/* This section is used when compiling module.c */

static Buffer_read_RETURN Buffer_read Buffer_read_PROTO;
static Buffer_readPyString_RETURN Buffer_readPyString Buffer_readPyString_PROTO;
static Buffer_tell_RETURN Buffer_tell Buffer_tell_PROTO;
static Buffer_seek_RETURN Buffer_seek Buffer_seek_PROTO;
static Buffer_write_RETURN Buffer_write Buffer_write_PROTO;
static Buffer_writePyString_RETURN Buffer_writePyString Buffer_writePyString_PROTO;

#else
/* This section is used in modules that use the module's API */

static void **PyBuffer_API;

#define Buffer_read \
 (*(Buffer_read_RETURN (*)Buffer_read_PROTO) PyBuffer_API[Buffer_read_NUM])

#define Buffer_readPyString \
 (*(Buffer_readPyString_RETURN (*)Buffer_readPyString_PROTO) PyBuffer_API[Buffer_readPyString_NUM])

#define Buffer_tell \
 (*(Buffer_tell_RETURN (*)Buffer_tell_PROTO) PyBuffer_API[Buffer_tell_NUM])

#define Buffer_seek \
 (*(Buffer_seek_RETURN (*)Buffer_seek_PROTO) PyBuffer_API[Buffer_seek_NUM])

#define Buffer_write \
 (*(Buffer_write_RETURN (*)Buffer_write_PROTO) PyBuffer_API[Buffer_write_NUM])

#define Buffer_writePyString \
 (*(Buffer_writePyString_RETURN (*)Buffer_writePyString_PROTO) PyBuffer_API[Buffer_writePyString_NUM])

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
