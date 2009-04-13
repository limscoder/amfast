#include "context.h"
#include "buffer.h"

#include "structmember.h"

// ------------------------ DECLARATIONS --------------------------------- //
//
// ---- GLOBALS
static PyObject *amfast_mod;
static PyObject *context_mod;
static PyObject *buffer_mod;
static PyObject *class_def_mod;
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
    if (idx >= self->pos) {
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

// Keeps track of information relevant to a single run through the decoder.
static PyObject* Decoder_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
    DecoderObj *self;

    self = (DecoderObj *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->buf = NULL;
        self->_buf_str = NULL;
        self->class_mapper = NULL;
        self->obj_refs = NULL;
        self->string_refs = NULL;
        self->class_refs = NULL;
        self->read_name = NULL;
        self->apply_name = NULL;
        self->class_def_name = NULL;
        self->extern_name = NULL;
        self->int_buf = 0;
        self->amf3 = 0;
    }

    return (PyObject *)self;
}

/*
 * Initialize Idx objects.
 */
static int Decoder_initIdx(DecoderObj *self)
{
    PyObject *idx_class = PyObject_GetAttrString(context_mod, "Idx");
    if (idx_class == NULL)
        return -1;

    PyObject *ref = PyObject_CallFunctionObjArgs(idx_class, NULL);
    if (ref == NULL) {
        Py_DECREF(idx_class);
        return -1;
    }
    self->obj_refs = ref;

    if (self->amf3 == 1) {
        ref = PyObject_CallFunctionObjArgs(idx_class, NULL);
        if (ref == NULL) {
            Py_DECREF(idx_class);
            return -1;
        }
        self->string_refs = ref;

        ref = PyObject_CallFunctionObjArgs(idx_class, NULL);
        if (ref == NULL) {
            Py_DECREF(idx_class);
            return -1;
        }
        self->class_refs = ref;
    }
    Py_DECREF(idx_class);

    return 0;
}

static int Decoder_init(DecoderObj *self, PyObject *args, PyObject *kwargs)
{
    static char *kwlist[] = {"buffer", "class_def_mapper", "amf3", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|Oi", kwlist,
        &self->buf, &self->class_mapper, &self->amf3))
        return -1;

    if (PyString_Check(self->buf) == 1) {
        // If input is a string, create our own buffer object.
        PyObject *buf_class = PyObject_GetAttrString(buffer_mod, "Buffer");
        if (buf_class == NULL)
            return -1;

        PyObject *buf = PyObject_CallFunctionObjArgs(buf_class, self->buf, NULL);
        Py_DECREF(buf_class);
        if (buf == NULL)
            return -1;
        self->buf = buf;
        self->int_buf = 1;
    }

    if (self->class_mapper == NULL) {
        // Create anon class mapper
        PyObject *mapper_class = PyObject_GetAttrString(class_def_mod, "ClassDefMapper");
        if (mapper_class == NULL)
            return -1;

        PyObject *mapper = PyObject_CallFunctionObjArgs(mapper_class, NULL);
        Py_DECREF(mapper_class);
        if (mapper == NULL)
            return -1;
        self->class_mapper = mapper;
    }

    // Init object reference indexes.
    if (Decoder_initIdx(self) == -1)
        return -1;

    if (self->int_buf == 0) {
        if (self->read_name == NULL) {
            self->read_name = PyString_InternFromString("read");
            if (self->read_name == NULL)
                return -1;
        }
    }

    if (self->apply_name == NULL) {
        self->apply_name = PyString_InternFromString("applyAttrVals");
        if (self->apply_name == NULL)
            return -1;
    }
 
    if (self->class_def_name == NULL) {
        self->class_def_name = PyString_InternFromString("getClassDefByAlias");
        if (self->class_def_name == NULL)
            return -1;
    }

    if (self->extern_name == NULL) {
        self->extern_name = PyString_InternFromString("readExternal");
        if (self->extern_name == NULL)
            return -1;
    }

    return 0;
}

static void Decoder_dealloc(DecoderObj *self)
{
    Py_XDECREF(self->buf);
    Py_XDECREF(self->_buf_str);
    Py_XDECREF(self->class_mapper);
    Py_XDECREF(self->obj_refs);
    Py_XDECREF(self->string_refs);
    Py_XDECREF(self->class_refs);
    Py_XDECREF(self->read_name);
    Py_XDECREF(self->apply_name);
    Py_XDECREF(self->class_def_name);
    Py_XDECREF(self->extern_name);
    self->ob_type->tp_free((PyObject*)self);
}

/*
 * Copy a Decoder with all the same settings, but
 * reset the index references.
 */
PyObject* Decoder_copy(DecoderObj *self, int amf3)
{
    PyObject *decoder_class = PyObject_GetAttrString(context_mod, "DecoderContext");
    if (decoder_class == NULL)
        return NULL;

    PyObject *decoder_new = PyObject_GetAttrString(decoder_class, "__new__");
    if (decoder_new == NULL) {
        Py_DECREF(decoder_class);
        return NULL;
    }

    DecoderObj *new_decoder = (DecoderObj*)PyObject_CallFunctionObjArgs(decoder_new, decoder_class, NULL);
    Py_DECREF(decoder_class);
    Py_DECREF(decoder_new);
    if (new_decoder == NULL)
        return NULL;

    // Copy values from original
    new_decoder->buf = self->buf;
    new_decoder->class_mapper = self->class_mapper;
    new_decoder->read_name = self->read_name;
    new_decoder->apply_name = self->apply_name;
    new_decoder->class_def_name = self->class_def_name;
    new_decoder->extern_name = self->extern_name;
    new_decoder->int_buf = self->int_buf;
    new_decoder->amf3 = amf3;

    // Reset indexes
    if (Decoder_initIdx(new_decoder) == -1) {
        Py_DECREF(new_decoder);
        return NULL;
    }

    return (PyObject*)new_decoder;
}

/* 
 * Returns position in stream.
 */
int Decoder_tell(DecoderObj *self)
{
    if (self->int_buf == 1) {
        return Buffer_tell((BufferObj*)self->buf);
    }

    PyObject *pos = PyObject_CallMethod(self->buf, "tell", NULL);
    if (!pos)
        return -1;

    int result = (int)PyInt_AsLong(pos);
    Py_DECREF(pos);
    return result;
}

/* 
 * Read a PyString from the context.
 *
 * Returns a borrowed reference.
 */
PyObject* Decoder_readPyString(DecoderObj *self, int len)
{
    if (self->int_buf) {
       return Buffer_readPyString((BufferObj*)self->buf, len); 
    }

    PyObject *tmp = self->_buf_str;
    PyObject *py_len = PyInt_FromLong((long)len);
    if (!py_len)
        return NULL;
    self->_buf_str = PyObject_CallMethodObjArgs(self->buf, self->read_name, py_len, NULL);
    Py_DECREF(py_len);
    Py_XDECREF(tmp); // Decrement reference to OLD string.
    return self->_buf_str;
}

/*
 * Python exposed version of Decoder_readPyString
 */
static PyObject* PyDecoder_readPyString(DecoderObj *self, PyObject *args, PyObject *kwargs)
{
    int len;

    if (!PyArg_ParseTuple(args, "i", &len))
        return NULL;

    return Decoder_readPyString(self, len);
}

/*
 * Moves the position in the stream forward without
 * returning a string. Can be more efficient than
 * Decoder_readPyString.
 */
int Decoder_skipBytes(DecoderObj *self, int len)
{
    if (self->int_buf) {
        int pos = Buffer_tell(self->buf);
        pos += len;
        int result = Buffer_seek(self->buf, pos);
        if (result == -1) {
            return 0;
        }
        return 1;
    }

    PyObject *py_len = PyInt_FromLong((long)len);
    if (!py_len)
        return 0;
    PyObject *str = PyObject_CallMethodObjArgs(self->buf, self->read_name, py_len, NULL);
    Py_DECREF(py_len);
    if (str == NULL)
        return 0;

    Py_DECREF(str);
    return 1;
}

/*
 * Read a C string from the buffer.
 */
char* Decoder_readCString(DecoderObj *self, int len)
{
    if (self->int_buf) {
        return Buffer_read(self->buf, len); 
    }

    PyObject* py_str = Decoder_readPyString(self, len);
    if (!py_str)
        return NULL;
    return PyString_AsString(py_str);
}

/* Reads a single byte from the context. */
char Decoder_readByte(DecoderObj *self)
{
    char *str = Decoder_readCString(self, 1);
    return str[0];
}

/*
 * Python exposed version of Decoder_copy.
 */
static PyObject* PyDecoder_copy(DecoderObj *self, PyObject *args, PyObject *kwargs)
{
    int amf3 = self->amf3;

    static char *kwlist[] = {"amf3", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|i", kwlist, &amf3))
        return NULL;

    return Decoder_copy(self, amf3);
}

static PyMethodDef Decoder_methods[] = {
    {"copy", (PyCFunction)PyDecoder_copy, METH_VARARGS,
     "Copy the decoder context. Settings are preserved, but index counts are reset.\n\n"
     "arguments\n"
     "==========\n"
     " * amf3 - bool, True to encode as AMF3."},
    {"read", (PyCFunction)PyDecoder_readPyString, METH_VARARGS,
     "Reads from the buffer.\n\n"
     "arguments\n"
     "==========\n"
     " * len - int, Number of bytes to read."},
    {NULL}  /* Sentinel */
};

static PyMemberDef Decoder_members[] = {
    {"buffer", T_OBJECT_EX, offsetof(DecoderObj, buf), 0,
     "The object being encoded."},
    {"class_def_mapper", T_OBJECT_EX, offsetof(DecoderObj, class_mapper), 0,
     "The object the retrieves ClassDef objects."},
    {"obj_refs", T_OBJECT_EX, offsetof(DecoderObj, obj_refs), 0,
     "Object references."},
    {"string_refs", T_OBJECT_EX, offsetof(DecoderObj, string_refs), 0,
     "String references."},
    {"class_refs", T_OBJECT_EX, offsetof(DecoderObj, class_refs), 0,
     "ClassDef references."},
    {NULL}  /* Sentinel */
};

static PyTypeObject DecoderType = {
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "amfast.context.DecoderContext",      /*tp_name*/
    sizeof(DecoderObj),            /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)Decoder_dealloc,   /*tp_dealloc*/
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
    "Decoder context.",           /* tp_doc */
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    0,                         /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    Decoder_methods,           /* tp_methods */
    Decoder_members,           /* tp_members */ 
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    Decoder_init,              /* tp_init */
    0,                         /* tp_alloc */
    Decoder_new,               /* tp_new */
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
    context_mod = Py_InitModule3("context", context_methods,
        "Tools to manage information relevant to a single run "
        "through the encoder or decoder.");

    // Import modules
    if (!amfast_mod) {
        amfast_mod = PyImport_ImportModule("amfast");
        if(!amfast_mod)
            return;
    }

    if (!buffer_mod) {
        buffer_mod = PyImport_ImportModule("amfast.buffer");
        if (!buffer_mod)
            return;
    }

    if (!class_def_mod) {
        class_def_mod = PyImport_ImportModule("amfast.class_def");
        if (!class_def_mod)
            return;
    }

    // Setup exceptions
    amfast_Error = PyObject_GetAttrString(amfast_mod, "AmFastError");
    if (amfast_Error == NULL)
        return;

    amfast_ContextError = PyErr_NewException("amfast.encoder.ContextError",
        amfast_Error, NULL);
    if (amfast_ContextError == NULL)
        return;

    if (PyModule_AddObject(context_mod, "ContextError", amfast_ContextError) == -1)
        return;

    IdxType.tp_new = Idx_new;
    if (PyType_Ready(&IdxType) < 0)
        return;

    Py_INCREF(&IdxType);
    PyModule_AddObject(context_mod, "Idx", (PyObject *)&IdxType);

    DecoderType.tp_new = Decoder_new;
    if (PyType_Ready(&DecoderType) < 0)
        return;

    Py_INCREF(&DecoderType);
    PyModule_AddObject(context_mod, "DecoderContext", (PyObject *)&DecoderType);
}
