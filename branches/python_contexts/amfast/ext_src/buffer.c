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
    }

    return 0;
}

static void Buffer_dealloc(BufferObj *self)
{
    Py_XDECREF(self->src_str);
    if (self->src_str == NULL)
        free(self->buf);
    self->ob_type->tp_free((PyObject*)self);
}

/*
 * Returns a pointer to the current buffer position
 * and increments the position by the given length.
 */
char* Buffer_read(BufferObj *self, int len)
{
    if (self->src_str == NULL) {
        PyErr_SetString(amfast_BufferError, "Cannot read from write-only buffer.");
        return NULL;
    }

    if ((self->pos + len) > self->len) {
        PyErr_SetString(amfast_BufferError, "Attempted to read past end of buffer.");
        return NULL;
    }

    char* result = (char*)(self->buf + self->pos);
    self->pos += len;
    return result;
}

/*
 * Returns a PyString.
 */
PyObject* Buffer_read_PyString(BufferObj *self, int len)
{
    char *str = Buffer_read(self, len);
    if (str == NULL)
       return NULL;

    return PyString_FromStringAndSize(str, (Py_ssize_t)len);
}

/*
 * Python exposed version of Buffer_read_PyString.
 */
static PyObject* PyBuffer_read(BufferObj *self, PyObject *args, PyObject *kwargs)
{
    int len;

    if (!PyArg_ParseTuple(args, "i", &len))
        return NULL;

    return Buffer_read_PyString(self, len);
}

static PyMethodDef Buffer_methods[] = {
    {"read", (PyCFunction)PyBuffer_read, METH_VARARGS,
     "Read from buffer. Returns a string.\n\n"
     "arguments\n"
     "==========\n"
     " * len - int, length to read from buffer."},
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
    PyObject* m;

    m = Py_InitModule3("buffer", buffer_methods,
        "Tools for encoding and decoding AMF strings.");

    // Setup exceptions
    if (!amfast_mod) {
        amfast_mod = PyImport_ImportModule("amfast");
        if(!amfast_mod)
            return;
    }

    amfast_Error = PyObject_GetAttrString(amfast_mod, "AmFastError");
    if (amfast_Error == NULL)
        return;

    amfast_BufferError = PyErr_NewException("amfast.encoder.BufferError", amfast_Error, NULL);
    if (amfast_BufferError == NULL)
        return;

    if (PyModule_AddObject(m, "BufferError", amfast_BufferError) == -1)
        return;

    BufferType.tp_new = Buffer_new;
    if (PyType_Ready(&BufferType) < 0)
        return;

    Py_INCREF(&BufferType);
    PyModule_AddObject(m, "Buffer", (PyObject *)&BufferType);
}
