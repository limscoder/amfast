#include "context.h"

// ------------------------ DECLARATIONS --------------------------------- //
//
// ---- GLOBALS
static PyObject *amfast_mod;
static PyObject *amfast_Error;
static PyObject *amfast_ContextError;

// Idx maps indexes to PyObjects.
static PyObject* Idx_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
    IdxObj *self;

    self = (IdxObj *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->len = 32;
        self->objs = (PyObject**)malloc(sizeof(PyObject*) * (size_t)self->len);
        if (self->objs == NULL) {
            PyErr_SetNone(PyExc_MemoryError);
            self->ob_type->tp_free((PyObject*)self);
            return NULL;
        }
        self->pos = 0;
    }

    return (PyObject *)self;
}

static void Idx_dealloc(IdxObj *self)
{
    int i;
    int len = self->pos;
    for (i = 0; i < len; i++) {
        Py_DECREF(self->objs[i]);
    }

    free(self->objs);

    self->ob_type->tp_free((PyObject*)self);
}

/*
 * Maps a PyObject to the next index.
 * Returns mapped index, or -1 on failure.
 */
int Idx_map(IdxObj *self, PyObject *obj)
{
   // Dynamically expand array if needed.
   int new_len = self->pos;
   int current_len = self->len;

    while (new_len >= current_len) {
        current_len *= 2;
    }

    if (current_len != self->len) {
        self->objs = (PyObject**)realloc(self->objs, sizeof(PyObject*) * (size_t)current_len);
        if (self->objs == NULL) {
            PyErr_SetNone(PyExc_MemoryError);
            return -1;
        }
        self->len = current_len;
    }

    Py_INCREF(obj);
    self->objs[new_len] = obj;
    self->pos = new_len + 1;
    return new_len;
}

/*
 * Python exposed version of Idx_map.
 */
static PyObject* PyIdx_map(IdxObj *self, PyObject *args, PyObject *kwargs)
{
    PyObject *obj;

    if (!PyArg_ParseTuple(args, "O", &obj))
        return NULL;

    int idx = Idx_map(self, obj);

    if (idx == -1)
        return NULL;

    return PyInt_FromLong((long)idx);
}

/*
 * Retrieves an indexed object.
 */
PyObject* Idx_ret(IdxObj *self, int idx)
{
    if (idx > self->pos) {
        PyErr_SetString(amfast_ContextError, "Index is out of range.");
        return NULL;
    }

    PyObject *result = self->objs[idx];
    Py_INCREF(result);
    return result;
}

/*
 * Python exposed version of Idx_ret.
 */
static PyObject* PyIdx_ret(IdxObj *self, PyObject *args, PyObject *kwargs)
{
    int idx;

    if (!PyArg_ParseTuple(args, "i", &idx))
        return NULL;

    return Idx_ret(self, idx);
}

static PyMethodDef Idx_methods[] = {
    {"map", (PyCFunction)PyIdx_map, METH_VARARGS,
     "Map an object to the next index. Returns the index the object was mapped to.\n\n"
     "arguments\n"
     "==========\n"
     " * obj - object, the object to map."},
    {"ret", (PyCFunction)PyIdx_ret, METH_VARARGS,
     "Retrieve an indexed object.\n\n"
     "arguments\n"
     "==========\n"
     " * idx - int, the index of the object to retrieve."},
    {NULL}  /* Sentinel */
};

static PyTypeObject IdxType = {
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "amfast.context.Idx",      /*tp_name*/
    sizeof(IdxObj),            /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)Idx_dealloc,   /*tp_dealloc*/
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
    "Maps objects to index numbers.",           /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    Idx_methods,            /* tp_methods */
    0,                         /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,                         /* tp_init */
    0,                         /* tp_alloc */
    Idx_new,                   /* tp_new */
};

static PyMethodDef context_methods[] = {
    {NULL}  /* Sentinel */
};

#ifndef PyMODINIT_FUNC
#define PyMODINIT_FUNC void
#endif
PyMODINIT_FUNC
initcontext(void)
{
    PyObject* m;

    m = Py_InitModule3("context", context_methods,
        "Tools to manage information relevant to a single run "
        "through the encoder or decoder.");

    // Setup exceptions
    if (!amfast_mod) {
        amfast_mod = PyImport_ImportModule("amfast");
        if(!amfast_mod)
            return;
    }

    amfast_Error = PyObject_GetAttrString(amfast_mod, "AmFastError");
    if (amfast_Error == NULL)
        return;

    amfast_ContextError = PyErr_NewException("amfast.encoder.ContextError",
        amfast_Error, NULL);
    if (amfast_ContextError == NULL)
        return;

    if (PyModule_AddObject(m, "ContextError", amfast_ContextError) == -1)
        return;

    IdxType.tp_new = Idx_new;
    if (PyType_Ready(&IdxType) < 0)
        return;

    Py_INCREF(&IdxType);
    PyModule_AddObject(m, "Idx", (PyObject *)&IdxType);
}
