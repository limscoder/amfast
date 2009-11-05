#include <Python.h>

#define BUFFER_MODULE
#include "buffer.h"

// ------------------------ DECLARATIONS --------------------------------- //
//
// ---- GLOBALS
static PyObject *amfast_mod;
static PyObject *amfast_Error;
static PyObject *amfast_BufferError;

static PyObject* Buffer_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
    BufferObj *self;

    self = (BufferObj *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->src_str = NULL;
        self->buf = NULL;
        self->len = 0;
        self->pos = 0;
    }

    return (PyObject *)self;
}

static int Buffer_init(BufferObj *self, PyObject *args, PyObject *kwargs)
{
    static char *kwlist[] = {"source", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|O", kwlist, &self->src_str))
        return -1;

    if (self->src_str != NULL) {
        Py_INCREF(self->src_str);
        self->buf = PyString_AsString(self->src_str);
        self->len = PyString_GET_SIZE(self->src_str);
    } else {
        self->len = 256;
        self->buf = (char*)malloc(sizeof(char*) * (size_t)self->len);
    }

    return 0;
}

static void Buffer_dealloc(BufferObj *self)
{
    Py_XDECREF(self->src_str);
    if (!self->src_str)
        free(self->buf);
    self->ob_type->tp_free((PyObject*)self);
}

/*
 * Returns the current position in the buffer.
 */
static int Buffer_tell(BufferObj *self)
{
    return self->pos;
}

/*
 * Python exposed version of Buffer_tell.
 */
static PyObject* PyBuffer_tell(BufferObj *self)
{
    return PyInt_FromLong((long)Buffer_tell(self));
}

/*
 * Moves to a specific position in the buffer.
 *
 * Returns position or -1 on error.
 */
static int Buffer_seek(BufferObj *self, int pos)
{
    if (pos < 0) {
        PyErr_SetString(amfast_BufferError, "Attempted to seek before start of buffer.");
        return -1;
    }

    if (pos > self->len) {
        PyErr_SetString(amfast_BufferError, "Attempted to seek past end of buffer.");
        return -1;
    }

    self->pos = pos;
    return pos;
}

/*
 * Python exposed version of Buffer_seek.
 */
static PyObject* PyBuffer_seek(BufferObj *self, PyObject *args, PyObject *kwargs)
{
    int pos;

    if (!PyArg_ParseTuple(args, "i", &pos))
        return NULL;

    int new_pos = Buffer_seek(self, pos);
    if (new_pos == -1)
        return NULL;

    return PyInt_FromLong((long)new_pos);
}

/*
 * Returns a pointer to the current buffer position
 * and increments the position by the given length.
 */
static char* Buffer_read(BufferObj *self, int len)
{
    int new_pos = self->pos + len;
    if (new_pos < 0) {
        PyErr_SetString(amfast_BufferError, "Attempted to read before start of buffer.");
        return NULL;
    }

    if (new_pos > self->len) {
        PyErr_SetString(amfast_BufferError, "Attempted to read past end of buffer.");
        return NULL;
    }

    char* result = (char*)(self->buf + self->pos);
    self->pos = new_pos;
    return result;
}

/*
 * Returns a PyString.
 */
static PyObject* Buffer_readPyString(BufferObj *self, int len)
{
    char *str = Buffer_read(self, len);
    if (!str)
       return NULL;

    return PyString_FromStringAndSize(str, (Py_ssize_t)len);
}

/*
 * Python exposed version of Buffer_readPyString.
 */
static PyObject* PyBuffer_readPyString(BufferObj *self, PyObject *args, PyObject *kwargs)
{
    int len;

    if (!PyArg_ParseTuple(args, "i", &len))
        return NULL;

    if (!self->src_str) {
        PyErr_SetString(amfast_BufferError, "Cannot read from write-only buffer.");
        return NULL;
    }

    return Buffer_readPyString(self, len);
}

/*
 * Expand the length of the buffer.
 *
 * len == number of bytes to expand by.
 *
 * Returns size of new buffer, or -1 if failed.
 *
 */
static int Buffer_grow(BufferObj *self, int len)
{
    int new_len = self->pos + len;
    int current_len = self->len;

    while (new_len > current_len) {
        // Buffer is not large enough.
        // Double its memory, so that we don't need to realloc everytime.
        current_len *= 2;
    }

    if (current_len != self->len) {
        self->buf = (char*)realloc(self->buf, sizeof(char*) * (size_t)current_len);
        if (!self->buf) {
            PyErr_SetNone(PyExc_MemoryError);
            return -1;
        }
        self->len = current_len;
    }

    return current_len;
}

/*
 * Write a C string.
 *
 * Returns 1 on success, 0 on failure.
 */
static int Buffer_write(BufferObj *self, char *str, int len)
{
    if (Buffer_grow(self, len) == -1)
        return 0;

    memcpy(self->buf + self->pos, str, (size_t)len);
    self->pos += len;
    return 1;
}

/*
 * Writes a Python string.
 */
static int Buffer_writePyString(BufferObj *self, PyObject* py_str)
{
    char *c_str = PyString_AS_STRING(py_str);
    int len = PyString_GET_SIZE(py_str);

    return Buffer_write(self, c_str, len);
}

/*
 * Python exposed version of Buffer_writePyString.
 */
static PyObject* PyBuffer_writePyString(BufferObj *self, PyObject *args, PyObject *kwargs)
{
    PyObject *py_str;

    if (!PyArg_ParseTuple(args, "O", &py_str))
        return NULL;

    if (self->src_str != NULL) {
        PyErr_SetString(amfast_BufferError, "Cannot write to read-only buffer.");
        return NULL;
    }

    if (PyString_Check(py_str) == 0) {
        PyErr_SetString(amfast_BufferError, "Argument must be a string.");
        return NULL;
    }

    int result = Buffer_writePyString(self, py_str);
    if (result == 0)
        return NULL;

    Py_RETURN_NONE;
}

/*
 * Gets Python string for entire buffer.
 */
static PyObject* PyBuffer_getPyString(BufferObj *self, PyObject *args, PyObject *kwargs)
{
    if (!self->src_str) {
        return PyString_FromStringAndSize(self->buf, (Py_ssize_t)self->pos);
    } else {
        Py_XINCREF(self->src_str);
        return self->src_str;
    }
}

static PyMethodDef Buffer_methods[] = {
    {"read", (PyCFunction)PyBuffer_readPyString, METH_VARARGS | METH_KEYWORDS,
     "Read from buffer. Returns a string.\n\n"
     "arguments\n"
     "==========\n"
     " * len - int, length to read from buffer."},
    {"getvalue", (PyCFunction)PyBuffer_getPyString, METH_VARARGS | METH_KEYWORDS,
     "Gets a string value.\n"},
    {"tell", (PyCFunction)PyBuffer_tell, METH_NOARGS,
     "Returns the current position in the buffer.\n\n"},
    {"seek", (PyCFunction)PyBuffer_seek, METH_VARARGS  | METH_KEYWORDS,
     "Moves to a specified position in the buffer.\n\n"
     "arguments\n"
     "==========\n"
     " * pos - int, position to move to in the buffer."},
    {"write", (PyCFunction)PyBuffer_writePyString, METH_VARARGS | METH_KEYWORDS,
     "Writes a string to the buffer.\n\n"
     "arguments\n"
     "==========\n"
     " * str - str, string to write to the buffer."},
    {NULL}  /* Sentinel */
};

static PyTypeObject BufferType = {
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "amfast.buffer.Buffer",    /*tp_name*/
    sizeof(BufferObj),         /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)Buffer_dealloc,                         /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    0,                         /*tp_repr*/
    0,                         /*tp_as_number*/
    0,                         /*tp_as_sequence*/
    0,                         /*tp_as_mapping*/
    0,                         /*tp_hash */
    0,                         /*tp_call*/
    0,                         /*tp_str*/
    0,                         /*tp_getattro*/
    0,                         /*tp_setattro*/
    0,                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT,        /*tp_flags*/
    "A buffer used to encode and decode AMF strings.",           /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    Buffer_methods,            /* tp_methods */
    0,                         /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)Buffer_init,      /* tp_init */
    0,                         /* tp_alloc */
    Buffer_new,                 /* tp_new */
};

static PyMethodDef buffer_methods[] = {
    {NULL}  /* Sentinel */
};

#ifndef PyMODINIT_FUNC
#define PyMODINIT_FUNC void
#endif
PyMODINIT_FUNC
initbuffer(void) 
{
    PyObject *m = Py_InitModule3("buffer", buffer_methods,
        "Tools for encoding and decoding AMF strings.");

    // Import modules
    if (!amfast_mod) {
        amfast_mod = PyImport_ImportModule("amfast");
        if(!amfast_mod)
            return;
    }

    // Setup exceptions
    amfast_Error = PyObject_GetAttrString(amfast_mod, "AmFastError");
    if (!amfast_Error)
        return;

    amfast_BufferError = PyErr_NewException("amfast.encoder.BufferError", amfast_Error, NULL);
    if (!amfast_BufferError)
        return;

    if (PyModule_AddObject(m, "BufferError", amfast_BufferError) == -1)
        return;

    // Setup types
    BufferType.tp_new = Buffer_new;
    if (PyType_Ready(&BufferType) < 0)
        return;

    Py_INCREF(&BufferType);
    PyModule_AddObject(m, "Buffer", (PyObject *)&BufferType);

    // Export Buffer C API
    static void *PyBuffer_API[PyBuffer_API_pointers];

    PyBuffer_API[Buffer_read_NUM] = (void*)Buffer_read;
    PyBuffer_API[Buffer_readPyString_NUM] = (void*)Buffer_readPyString;
    PyBuffer_API[Buffer_tell_NUM] = (void*)Buffer_tell;
    PyBuffer_API[Buffer_seek_NUM] = (void*)Buffer_seek;
    PyBuffer_API[Buffer_write_NUM] = (void*)Buffer_write;
    PyBuffer_API[Buffer_writePyString_NUM] = (void*)Buffer_writePyString;

    PyObject *c_api = PyCObject_FromVoidPtr((void*)PyBuffer_API, NULL);
    if (c_api != NULL)
        PyModule_AddObject(m, "_C_API", c_api);
}
