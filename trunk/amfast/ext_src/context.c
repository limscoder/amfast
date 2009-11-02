#include <Python.h>
#include "buffer.h"

#define CONTEXT_MODULE
#include "context.h"

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
static int Idx_map(IdxObj *self, PyObject *obj)
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
 * Returns new ref.
 */
static PyObject* Idx_ret(IdxObj *self, int idx)
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
    {"map", (PyCFunction)PyIdx_map, METH_VARARGS | METH_KEYWORDS,
     "Map an object to the next index. Returns the index the object was mapped to.\n\n"
     "arguments\n"
     "==========\n"
     " * obj - object, the object to map."},
    {"ret", (PyCFunction)PyIdx_ret, METH_VARARGS | METH_KEYWORDS,
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
    "Maps objects to AMF reference indexes.",           /* tp_doc */
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

// Ref maps PyObjects indexes.
static PyObject* Ref_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
    RefObj *self;

    self = (RefObj *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->idx = 0;
        self->refs = NULL;
    }

    return (PyObject *)self;
}

static int Ref_init(PyObject *self_raw, PyObject *args, PyObject *kwargs)
{
    RefObj *self = (RefObj*)self_raw;

    self->refs = PyDict_New();
    if (self->refs == NULL)
        return -1;
    
    return 0;
}

static void Ref_dealloc(RefObj *self)
{
    // DECREF all mapped refs
    // They are incremented in Ref_map.
    PyObject *obj, *key, *val;
    Py_ssize_t pos = 0;

    while (PyDict_Next(self->refs, &pos, &key, &val)) {
        obj = (PyObject*) PyLong_AsVoidPtr(key);
        Py_DECREF(obj);
    }

    Py_XDECREF(self->refs);
    self->ob_type->tp_free((PyObject*)self);
}

/*
 * Maps a PyObject to the next index.
 * Returns mapped index, or -1 on failure.
 */
static int Ref_map(RefObj *self, PyObject *obj)
{
    PyObject *key = PyLong_FromVoidPtr((void*)obj);
    if (key == NULL)
        return -1;

    PyObject *val = PyInt_FromLong((long)self->idx);
    if (val == NULL) {
        Py_DECREF(key);
        return -1;
    }

    int result = PyDict_SetItem(self->refs, key, val);
    Py_DECREF(key);
    if (result == -1) {
        Py_DECREF(val);
        return -1;
    }

    Py_DECREF(val); // give ownership to dict

    // Make sure the mapped object doesn't get
    // GC'd before we retrieve it.
    Py_INCREF(obj);

    result = self->idx;
    self->idx++;
    return result;
}

/*
 * Python exposed version of Ref_map.
 */
static PyObject* PyRef_map(RefObj *self, PyObject *args, PyObject *kwargs)
{
    PyObject *obj;

    if (!PyArg_ParseTuple(args, "O", &obj))
        return NULL;

    int result = Ref_map(self, obj);
    if (result == -1) {
        return NULL;
    }

    return PyInt_FromLong((long)result);
}

/*
 * Retrieves an indexed object.
 * Returns index, or -1.
 */
static int Ref_ret(RefObj *self, PyObject *obj)
{
    PyObject *key = PyLong_FromVoidPtr((void*)obj);
    if (key == NULL)
        return -1;

    if (PyDict_Contains(self->refs, key) == 0) {
        Py_DECREF(key);
        return -1;
    }

    PyObject *val = PyDict_GetItem(self->refs, key);
    Py_DECREF(key);
    if (val == NULL)
        return -1;

    long idx = PyInt_AsLong(val);
    return (int)idx;
}

/*
 * Python exposed version of Ref_ret.
 */
static PyObject* PyRef_ret(RefObj *self, PyObject *args, PyObject *kwargs)
{
    PyObject *obj;

    if (!PyArg_ParseTuple(args, "O", &obj))
        return NULL;

    int result = Ref_ret(self, obj);
    return PyInt_FromLong((long)result);
}

static PyMethodDef Ref_methods[] = {
    {"map", (PyCFunction)PyRef_map, METH_VARARGS | METH_KEYWORDS,
     "Map an object to the next index. Returns the index the object was mapped to.\n\n"
     "arguments\n"
     "==========\n"
     " * obj - object, the object to map."},
    {"ret", (PyCFunction)PyRef_ret, METH_VARARGS | METH_KEYWORDS,
     "Retrieve the index of a mapped object.\n\n"
     "arguments\n"
     "==========\n"
     " * obj - object, the object to retrieve an index for."},
    {NULL}  /* Sentinel */
};

static PyTypeObject RefType = {
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "amfast.context.Ref",      /*tp_name*/
    sizeof(RefObj),            /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)Ref_dealloc,   /*tp_dealloc*/
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
    Ref_methods,            /* tp_methods */
    0,                         /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    Ref_init,                  /* tp_init */
    0,                         /* tp_alloc */
    Ref_new,                   /* tp_new */
};


// Keeps track of information relevant to a single run through the decoder.
static PyObject* Decoder_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
    DecoderObj *self;

    self = (DecoderObj *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->buf = NULL;
        self->_buf_str = NULL;
        self->amf3 = NULL;
        self->class_mapper = NULL;
        self->obj_refs = NULL;
        self->string_refs = NULL;
        self->class_refs = NULL;
        self->type_map = NULL;
        self->read_name = NULL;
        self->apply_name = NULL;
        self->class_def_name = NULL;
        self->extern_name = NULL;
        self->int_buf = 0;
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

    PyObject *ref = PyObject_CallObject(idx_class, NULL);
    if (ref == NULL) {
        Py_DECREF(idx_class);
        return -1;
    }
    self->obj_refs = ref;

    if (self->amf3 == Py_True) {
        ref = PyObject_CallObject(idx_class, NULL);
        if (ref == NULL) {
            Py_DECREF(idx_class);
            return -1;
        }
        self->string_refs = ref;

        ref = PyObject_CallObject(idx_class, NULL);
        if (ref == NULL) {
            Py_DECREF(idx_class);
            return -1;
        }
        self->class_refs = ref;
    }
    Py_DECREF(idx_class);

    return 0;
}

static int Decoder_init(PyObject *self_raw, PyObject *args, PyObject *kwargs)
{
    DecoderObj *self = (DecoderObj*)self_raw;

    static char *kwlist[] = {"buffer", "class_def_mapper", "amf3", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|OO", kwlist,
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
    } else {
        Py_INCREF(self->buf);
    }

    if (self->class_mapper == NULL) {
        // Create anon class mapper
        PyObject *mapper_class = PyObject_GetAttrString(class_def_mod, "ClassDefMapper");
        if (mapper_class == NULL)
            return -1;

        PyObject *mapper = PyObject_CallObject(mapper_class, NULL);
        Py_DECREF(mapper_class);
        if (mapper == NULL)
            return -1;
        self->class_mapper = mapper;
    } else {
        Py_INCREF(self->class_mapper);
    }

    if (self->amf3 == NULL)
        self->amf3 = Py_False;
    Py_INCREF(self->amf3);

    // Init object reference indexes.
    if (Decoder_initIdx(self) == -1)
        return -1;

    if (self->type_map == NULL) {
        self->type_map = PyDict_New();
        if (self->type_map == NULL)
            return -1;
    }

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
    Py_XDECREF(self->amf3);
    Py_XDECREF(self->class_mapper);
    Py_XDECREF(self->obj_refs);
    Py_XDECREF(self->string_refs);
    Py_XDECREF(self->class_refs);
    Py_XDECREF(self->type_map);
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
static PyObject* Decoder_copy(DecoderObj *self, int amf3)
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
    Py_XINCREF(new_decoder->buf);
    new_decoder->class_mapper = self->class_mapper;
    Py_XINCREF(new_decoder->class_mapper);
    new_decoder->read_name = self->read_name;
    Py_XINCREF(new_decoder->read_name);
    new_decoder->apply_name = self->apply_name;
    Py_XINCREF(new_decoder->apply_name);
    new_decoder->class_def_name = self->class_def_name;
    Py_XINCREF(new_decoder->class_def_name);
    new_decoder->extern_name = self->extern_name;
    Py_XINCREF(new_decoder->extern_name);
    new_decoder->type_map = self->type_map;
    Py_XINCREF(new_decoder->type_map);
    new_decoder->int_buf = self->int_buf;
    if (amf3 == 1) {
        new_decoder->amf3 = Py_True;
    } else {
        new_decoder->amf3 = Py_False;
    }
    Py_XINCREF(new_decoder->amf3);

    // Reset indexes
    if (Decoder_initIdx(new_decoder) == -1) {
        Py_DECREF(new_decoder);
        return NULL;
    }

    return (PyObject*)new_decoder;
}

/*
 * Returns 1 if object is a DecoderContext.
 */
static int Decoder_check(PyObject *self)
{
    if (!PyObject_HasAttrString(self, "class_def_mapper")) {
        return 0;
    }

    if (PyObject_HasAttrString(self, "use_collections")) {
        return 0;
    }

    return 1;
}

/* 
 * Returns position in stream.
 */
static int Decoder_tell(DecoderObj *self)
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
static PyObject* Decoder_readPyString(DecoderObj *self, int len)
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

    PyObject *result = Decoder_readPyString(self, len);
    Py_XINCREF(result);
    return result;
}

/*
 * Moves the position in the stream forward without
 * returning a string. Can be more efficient than
 * Decoder_readPyString.
 */
static int Decoder_skipBytes(DecoderObj *self, int len)
{
    if (self->int_buf) {
        int pos = Buffer_tell((BufferObj*)self->buf);
        pos += len;
        int result = Buffer_seek((BufferObj*)self->buf, pos);
        if (result == -1)
            return 0;
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
static char* Decoder_read(DecoderObj *self, int len)
{
    if (self->int_buf) {
        return Buffer_read((BufferObj*)self->buf, len); 
    }

    PyObject* py_str = Decoder_readPyString(self, len);
    if (!py_str)
        return NULL;
    return PyString_AsString(py_str);
}

/* Reads a single byte from the context. */
static char* Decoder_readByte(DecoderObj *self)
{
    return Decoder_read(self, 1);
}

/*
 * Python exposed version of Decoder_copy.
 */
static PyObject* PyDecoder_copy(DecoderObj *self, PyObject *args, PyObject *kwargs)
{
    int amf3 = 0;
    if (self->amf3 == Py_True)
       amf3 = 1;

    static char *kwlist[] = {"amf3", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|i", kwlist, &amf3))
        return NULL;

    return Decoder_copy(self, amf3);
}

static PyMethodDef Decoder_methods[] = {
    {"copy", (PyCFunction)PyDecoder_copy, METH_VARARGS | METH_KEYWORDS,
     "Copy the decoder context. Settings are preserved, but index counts are reset.\n\n"
     "arguments\n"
     "==========\n"
     " * amf3 - bool, True to decode as AMF3."},
    {"read", (PyCFunction)PyDecoder_readPyString, METH_VARARGS | METH_KEYWORDS,
     "Reads from the buffer.\n\n"
     "arguments\n"
     "==========\n"
     " * len - int, Number of bytes to read."},
    {NULL}  /* Sentinel */
};

static PyMemberDef Decoder_members[] = {
    {"buffer", T_OBJECT_EX, offsetof(DecoderObj, buf), 0,
     "file-like-obj - The object being encoded."},
    {"amf3", T_OBJECT_EX, offsetof(DecoderObj, amf3), 0,
     "obj - True to decode as AMF3."},
    {"class_def_mapper", T_OBJECT_EX, offsetof(DecoderObj, class_mapper), 0,
     "amfast.class_def.ClassDefMapper - Retrieves ClassDef objects."},
    {"obj_refs", T_OBJECT_EX, offsetof(DecoderObj, obj_refs), 0,
     "amfast.context.Idx - Object references."},
    {"string_refs", T_OBJECT_EX, offsetof(DecoderObj, string_refs), 0,
     "amfast.context.Idx - String references."},
    {"class_refs", T_OBJECT_EX, offsetof(DecoderObj, class_refs), 0,
     "amfast.context.Idx - ClassDef references."},
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
    "DecoderContext\n"
    "================\n"
    " * amf3 - bool - True to decode as AMF3 format. Default = False\n"
    " * class_def_mapper - amfast.class_def.ClassDefMapper - \n"
    "    Retrieves ClassDef objects.\n"
    " * buffer - file-like-obj - The object being encoded.\n"
    " * obj_refs - amfast.context.Idx - Object references.\n"
    " * string_refs - amfast.context.Idx - String references.\n"
    " * class_refs - amfast.context.Idx - ClassDef references.\n", /* tp_doc */
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

// Keeps track of information relevant to a single run through the encoder.
static PyObject* Encoder_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
    EncoderObj *self;

    self = (EncoderObj *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->buf = NULL;
        self->amf3 = NULL;
        self->use_collections = NULL;
        self->use_proxies = NULL;
        self->use_refs = NULL;
        self->use_legacy_xml = NULL;
        self->include_private = NULL;
        self->class_mapper = NULL;
        self->obj_refs = NULL;
        self->string_refs = NULL;
        self->class_refs = NULL;
        self->type_map = NULL;
        self->array_collection_def = NULL;
        self->object_proxy_def = NULL;
        self->class_def_name = NULL;
        self->write_name = NULL;
        self->extern_name = NULL;
        self->int_buf = 0;
    }

    return (PyObject *)self;
}

/*
 * Initialize Ref objects.
 */
static int Encoder_initRef(EncoderObj *self)
{
    PyObject *ref_class = PyObject_GetAttrString(context_mod, "Ref");
    if (ref_class == NULL)
        return -1;

    PyObject *ref = PyObject_CallObject(ref_class, NULL);
    if (ref == NULL) {
        Py_DECREF(ref_class);
        return -1;
    }
    self->obj_refs = ref;

    if (self->amf3 == Py_True) {
        ref = PyObject_CallObject(ref_class, NULL);
        if (ref == NULL) {
            Py_DECREF(ref_class);
            return -1;
        }
        self->string_refs = ref;

        ref = PyObject_CallObject(ref_class, NULL);
        if (ref == NULL) {
            Py_DECREF(ref_class);
            return -1;
        }
        self->class_refs = ref;
    }
    Py_DECREF(ref_class);

    return 0;
}

static int Encoder_init(PyObject *self_raw, PyObject *args, PyObject *kwargs)
{
    EncoderObj *self = (EncoderObj*)self_raw;

    static char *kwlist[] = {"buffer", "class_def_mapper", "amf3", "use_collections",
        "use_proxies", "use_references", "use_legacy_xml", "include_private", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|OOOOOOOO", kwlist,
        &self->buf, &self->class_mapper, &self->amf3, &self->use_collections,
        &self->use_proxies, &self->use_refs, &self->use_legacy_xml, &self->include_private))
        return -1;

    if (self->buf == NULL) {
        // If output buffer is null, create our own buffer object.
        PyObject *buf_class = PyObject_GetAttrString(buffer_mod, "Buffer");
        if (buf_class == NULL)
            return -1;

        PyObject *buf = PyObject_CallObject(buf_class, NULL);
        Py_DECREF(buf_class);
        if (buf == NULL)
            return -1;
        self->buf = buf;
        self->int_buf = 1;
    } else {
        Py_INCREF(self->buf);
    }

    if (self->amf3 == NULL)
        self->amf3 = Py_False;
    Py_INCREF(self->amf3);

    if (self->use_collections == NULL)
        self->use_collections = Py_False;
    Py_INCREF(self->use_collections);

    if (self->use_proxies == NULL)
        self->use_proxies = Py_False;
    Py_INCREF(self->use_proxies);

    if (self->use_refs == NULL)
        self->use_refs = Py_True;
    Py_INCREF(self->use_refs);

    if (self->use_legacy_xml == NULL)
        self->use_legacy_xml = Py_False;
    Py_INCREF(self->use_legacy_xml);

    if (self->include_private == NULL)
        self->include_private = Py_False;
    Py_INCREF(self->include_private);

    if (self->class_mapper == NULL) {
        // Create anon class mapper
        PyObject *mapper_class = PyObject_GetAttrString(class_def_mod, "ClassDefMapper");
        if (mapper_class == NULL)
            return -1;

        PyObject *mapper = PyObject_CallObject(mapper_class, NULL);
        Py_DECREF(mapper_class);
        if (mapper == NULL)
            return -1;
        self->class_mapper = mapper;
    } else {
        Py_INCREF(self->class_mapper);
    }

    // Init object reference indexes.
    if (Encoder_initRef(self) == -1)
        return -1;

    if (self->type_map == NULL) {
        self->type_map = PyDict_New();
        if (self->type_map == NULL)
            return -1;
    }

    if (self->write_name == NULL) {
        self->write_name = PyString_InternFromString("write");
        if (self->write_name == NULL)
            return -1;
    }

    if (self->class_def_name == NULL) {
        self->class_def_name = PyString_InternFromString("getClassDefByClass");
        if (self->class_def_name == NULL)
            return -1;
    }

    if (self->extern_name == NULL) {
        self->extern_name = PyString_InternFromString("writeExternal");
        if (self->extern_name == NULL)
            return -1;
    }

    return 0;
}

static void Encoder_dealloc(EncoderObj *self)
{
    Py_XDECREF(self->buf);
    Py_XDECREF(self->amf3);
    Py_XDECREF(self->use_collections);
    Py_XDECREF(self->use_proxies);
    Py_XDECREF(self->use_refs);
    Py_XDECREF(self->use_legacy_xml);
    Py_XDECREF(self->include_private);
    Py_XDECREF(self->class_mapper);
    Py_XDECREF(self->obj_refs);
    Py_XDECREF(self->string_refs);
    Py_XDECREF(self->class_refs);
    Py_XDECREF(self->type_map);
    Py_XDECREF(self->array_collection_def);
    Py_XDECREF(self->object_proxy_def);
    Py_XDECREF(self->class_def_name);
    Py_XDECREF(self->write_name);
    Py_XDECREF(self->extern_name);
    self->ob_type->tp_free((PyObject*)self);
}

/*
 * Copy an Encoder with all the same settings, but
 * reset the index references.
 */
static PyObject* Encoder_copy(EncoderObj *self, int amf3, int new_buf)
{
    PyObject *encoder_class = PyObject_GetAttrString(context_mod, "EncoderContext");
    if (encoder_class == NULL)
        return NULL;

    PyObject *encoder_new = PyObject_GetAttrString(encoder_class, "__new__");
    if (encoder_new == NULL) {
        Py_DECREF(encoder_class);
        return NULL;
    }

    EncoderObj *new_encoder = (EncoderObj*)PyObject_CallFunctionObjArgs(encoder_new, encoder_class, NULL);
    Py_DECREF(encoder_class);
    Py_DECREF(encoder_new);
    if (new_encoder == NULL)
        return NULL;

    if (new_buf == 1) {
        // Create a new buffer object.
        PyObject *buf_class = PyObject_GetAttrString(buffer_mod, "Buffer");
        if (buf_class == NULL)
            return NULL;

        PyObject *buf = PyObject_CallObject(buf_class, NULL);
        Py_DECREF(buf_class);
        if (buf == NULL)
            return NULL;
        new_encoder->buf = buf;
        new_encoder->int_buf = 1;
    } else {
        new_encoder->buf = self->buf;
        Py_XINCREF(new_encoder->buf);
        new_encoder->int_buf = self->int_buf;
    }

    // Copy values from original
    new_encoder->use_collections = self->use_collections;
    Py_XINCREF(new_encoder->use_collections);
    new_encoder->use_proxies = self->use_proxies;
    Py_XINCREF(new_encoder->use_proxies);
    new_encoder->use_refs = self->use_refs;
    Py_XINCREF(new_encoder->use_refs);
    new_encoder->use_legacy_xml = self->use_legacy_xml;
    Py_XINCREF(new_encoder->use_legacy_xml);
    new_encoder->include_private = self->include_private;
    Py_XINCREF(new_encoder->include_private);
    new_encoder->class_mapper = self->class_mapper;
    Py_XINCREF(new_encoder->class_mapper);
    new_encoder->array_collection_def = self->array_collection_def;
    Py_XINCREF(new_encoder->array_collection_def);
    new_encoder->object_proxy_def = self->object_proxy_def;
    Py_XINCREF(new_encoder->object_proxy_def);
    new_encoder->class_def_name = self->class_def_name;
    Py_XINCREF(new_encoder->class_def_name);
    new_encoder->write_name = self->write_name;
    Py_XINCREF(new_encoder->write_name);
    new_encoder->extern_name = self->extern_name;
    Py_XINCREF(new_encoder->extern_name);
    new_encoder->type_map = self->type_map;
    Py_XINCREF(new_encoder->type_map);
    if (amf3 == 1) {
        new_encoder->amf3 = Py_True;
    } else {
        new_encoder->amf3 = Py_False;
    }
    Py_XINCREF(new_encoder->amf3);

    // Reset indexes
    if (Encoder_initRef(new_encoder) == -1) {
        Py_DECREF(new_encoder);
        return NULL;
    }

    return (PyObject*)new_encoder;
}

/*
 * Returns 1 if object is a EncoderContext.
 */
static int Encoder_check(PyObject *self)
{
    if (!PyObject_HasAttrString(self, "class_def_mapper")) {
        return 0;
    }

    if (!PyObject_HasAttrString(self, "use_collections")) {
        return 0;
    }

    return 1;
}

/* 
 * Returns position in stream.
 */
static int Encoder_tell(EncoderObj *self)
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
 * Returns the current string.
 */
static char* Encoder_read(EncoderObj *self)
{
    if (self->int_buf == 1) {
        BufferObj *buf = (BufferObj*)self->buf;
        return buf->buf;
    }

    PyErr_SetString(amfast_ContextError, "Can't read from unknown buffer type.");
    return NULL;
}

/*
 * Python exposed version of Encoder_copy.
 */
static PyObject* PyEncoder_copy(EncoderObj *self, PyObject *args, PyObject *kwargs)
{
    int amf3 = 0;
    if (self->amf3 == Py_True)
        amf3 = 1;
    int new_buf = 0;

    static char *kwlist[] = {"amf3", "new_buf", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|ii", kwlist, &amf3, &new_buf))
        return NULL;

    return Encoder_copy(self, amf3, new_buf);
}

/*
 * Writes a PyString to the buffer.
 */
static int Encoder_writePyString(EncoderObj *self, PyObject *py_str)
{
    if (self->int_buf == 1) {
        return Buffer_writePyString((BufferObj*)self->buf, py_str);
    }

    PyObject *result = PyObject_CallMethodObjArgs(self->buf, self->write_name, py_str, NULL);
    if (result == NULL)
        return 0;

    Py_DECREF(result);
    return 1;
}

/*
 * Python exposed version of Encoder_writePyString.
 */
static PyObject* PyEncoder_writePyString(EncoderObj *self, PyObject *args, PyObject *kwargs)
{
    PyObject *obj;

    if (!PyArg_ParseTuple(args, "O", &obj))
        return NULL;

    int result = Encoder_writePyString(self, obj);
    if (result == 0)
        return NULL;

    Py_RETURN_NONE;
}

/*
 * Writes a CString to the buffer.
 */
static int Encoder_write(EncoderObj *self, char *str, int len)
{
    if (self->int_buf == 1) {
        return Buffer_write((BufferObj*)self->buf, str, len);
    }

    PyObject *py_str = PyString_FromStringAndSize(str, (Py_ssize_t)len);
    if (py_str == NULL)
        return 0;

    int result = Encoder_writePyString(self, py_str);
    Py_DECREF(py_str);
    return result;
}

/*
 * Writes a byte to the buffer.
 */
static int Encoder_writeByte(EncoderObj *self, char byte)
{
    char bytes[1];
    bytes[0] = byte;

    return Encoder_write(self, bytes, 1);
}

/*
 * Gets value to return when encoding is completed.
 */
static PyObject* Encoder_getReturnVal(EncoderObj *self)
{
    if (self->int_buf == 1) {
        return PyObject_CallMethod(self->buf, "getvalue", NULL); 
    } else {
        Py_INCREF(self->buf);
        return self->buf;
    }
}

static PyMethodDef Encoder_methods[] = {
    {"copy", (PyCFunction)PyEncoder_copy, METH_VARARGS | METH_KEYWORDS,
     "Copy the encoder context. Settings are preserved, but index counts are reset.\n\n"
     "arguments\n"
     "==========\n"
     " * amf3 - bool, True to encode as AMF3."
     " * new_buf - bool, True to encode to a new Buffer object."},
    {"write", (PyCFunction)PyEncoder_writePyString, METH_VARARGS | METH_KEYWORDS,
     "Writes a string to the buffer.\n\n"
     "arguments\n"
     "==========\n"
     " * str - str, string to write."},
    {NULL}  /* Sentinel */
};

static PyMemberDef Encoder_members[] = {
    {"buffer", T_OBJECT_EX, offsetof(EncoderObj, buf), 0,
     "file-like-object - the output."},
    {"amf3", T_OBJECT_EX, offsetof(EncoderObj, amf3), 0,
     "bool - True to encode as AMF3."},
    {"include_private", T_OBJECT_EX, offsetof(EncoderObj, use_collections), 0,
     "bool - True to encode attributes starting with '_'."},
    {"use_collections", T_OBJECT_EX, offsetof(EncoderObj, use_collections), 0,
     "bool - True to encode lists and tuples as ArrayCollections."},
    {"use_proxies", T_OBJECT_EX, offsetof(EncoderObj, use_proxies), 0,
     "bool - True to encode dicts as ObjectProxies."},
    {"use_references", T_OBJECT_EX, offsetof(EncoderObj, use_refs), 0,
     "bool - True to encode multiple occuring objects as references."},
    {"use_legacy_xml", T_OBJECT_EX, offsetof(EncoderObj, use_legacy_xml), 0,
     "bool - True to XML as XMLDocument instead of e4x."},
    {"class_def_mapper", T_OBJECT_EX, offsetof(EncoderObj, class_mapper), 0,
     "amfast.class_def.ClassDefMapper - The object the retrieves ClassDef objects."},
    {"obj_refs", T_OBJECT_EX, offsetof(EncoderObj, obj_refs), 0,
     "amfast.context.Ref - Object references."},
    {"string_refs", T_OBJECT_EX, offsetof(EncoderObj, string_refs), 0,
     "amfast.context.Ref - String references."},
    {"class_refs", T_OBJECT_EX, offsetof(EncoderObj, class_refs), 0,
     "amfast.context.Ref - ClassDef references."},
    {NULL}  /* Sentinel */
};

static PyTypeObject EncoderType = {
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "amfast.context.EncoderContext",      /*tp_name*/
    sizeof(EncoderObj),            /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)Encoder_dealloc,   /*tp_dealloc*/
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
    "EncoderContext\n"
    "===============\n"
    " * buffer - file-like-object - The output.\n"
    " * amf3 - bool - True to encode as AMF3.\n"
    " * use_collections - bool - True to encode lists and tuples as ArrayCollections.\n"
    " * use_proxies - bool - True to encode dicts as ObjectProxies.\n"
    " * use_references - bool - True to encode multiple occuring objects as references.\n"
    " * use_legacy_xml - bool - True to XML as XMLDocument instead of e4x.\n"
    " * include_private - bool - True to encode attributes starting with '_'.\n"
    " * class_def_mapper - amfast.class_def.ClassDefMapper - Retrieves ClassDef objects.\n"
    " * obj_refs - amfast.context.Ref - Object references.\n"
    " * string_refs - amfast.context.Ref - String references.\n"
    " * class_refs - amfast.context.Ref - ClassDef references.\n", /* tp_doc */
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    0,                         /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    Encoder_methods,           /* tp_methods */
    Encoder_members,           /* tp_members */ 
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    Encoder_init,              /* tp_init */
    0,                         /* tp_alloc */
    Encoder_new,               /* tp_new */
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
        "Tools for managing encode/decode sessions.");

    if (context_mod == NULL)
        return;

    // Import modules
    if (!amfast_mod) {
        amfast_mod = PyImport_ImportModule("amfast");
        if(!amfast_mod)
            return;
    }

    buffer_mod = import_buffer_mod();
    if (buffer_mod == NULL)
        return;

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

    // Idx
    IdxType.tp_new = Idx_new;
    if (PyType_Ready(&IdxType) < 0)
        return;

    Py_INCREF(&IdxType);
    PyModule_AddObject(context_mod, "Idx", (PyObject *)&IdxType);

    // Idx C API
    static void *PyIdx_API[PyIdx_API_pointers];

    PyIdx_API[Idx_map_NUM] = (void*)Idx_map;
    PyIdx_API[Idx_ret_NUM] = (void*)Idx_ret;

    PyObject *idx_c_api = PyCObject_FromVoidPtr((void*)PyIdx_API, NULL);
    if (idx_c_api != NULL)
        PyModule_AddObject(context_mod, "_IDX_C_API", idx_c_api);

    // Decoder
    DecoderType.tp_new = Decoder_new;
    if (PyType_Ready(&DecoderType) < 0)
        return;

    Py_INCREF(&DecoderType);
    PyModule_AddObject(context_mod, "DecoderContext", (PyObject *)&DecoderType);

    // Decoder C API
    static void *PyDecoder_API[PyDecoder_API_pointers];

    PyDecoder_API[Decoder_check_NUM] = (void*)Decoder_check;
    PyDecoder_API[Decoder_copy_NUM] = (void*)Decoder_copy;
    PyDecoder_API[Decoder_tell_NUM] = (void*)Decoder_tell;
    PyDecoder_API[Decoder_readPyString_NUM] = (void*)Decoder_readPyString;
    PyDecoder_API[Decoder_skipBytes_NUM] = (void*)Decoder_skipBytes;
    PyDecoder_API[Decoder_read_NUM] = (void*)Decoder_read;
    PyDecoder_API[Decoder_readByte_NUM] = (void*)Decoder_readByte;

    PyObject *decoder_c_api = PyCObject_FromVoidPtr((void*)PyDecoder_API, NULL);
    if (decoder_c_api != NULL)
        PyModule_AddObject(context_mod, "_DECODER_C_API", decoder_c_api);

    // Ref
    RefType.tp_new = Ref_new;
    if (PyType_Ready(&RefType) < 0)
        return;

    Py_INCREF(&RefType);
    PyModule_AddObject(context_mod, "Ref", (PyObject *)&RefType);

    // Ref C API
    static void *PyRef_API[PyRef_API_pointers];

    PyRef_API[Ref_map_NUM] = (void*)Ref_map;
    PyRef_API[Ref_ret_NUM] = (void*)Ref_ret;

    PyObject *ref_c_api = PyCObject_FromVoidPtr((void*)PyRef_API, NULL);
    if (ref_c_api != NULL)
        PyModule_AddObject(context_mod, "_REF_C_API", ref_c_api);

    // Encoder
    EncoderType.tp_new = Encoder_new;
    if (PyType_Ready(&EncoderType) < 0)
        return;

    Py_INCREF(&EncoderType);
    PyModule_AddObject(context_mod, "EncoderContext", (PyObject *)&EncoderType);

    // Encoder C API
    static void *PyEncoder_API[PyEncoder_API_pointers];

    PyEncoder_API[Encoder_check_NUM] = (void*)Encoder_check;
    PyEncoder_API[Encoder_writePyString_NUM] = (void*)Encoder_writePyString;
    PyEncoder_API[Encoder_write_NUM] = (void*)Encoder_write;
    PyEncoder_API[Encoder_writeByte_NUM] = (void*)Encoder_writeByte;
    PyEncoder_API[Encoder_tell_NUM] = (void*)Encoder_tell;
    PyEncoder_API[Encoder_read_NUM] = (void*)Encoder_read;
    PyEncoder_API[Encoder_copy_NUM] = (void*)Encoder_copy;
    PyEncoder_API[Encoder_getReturnVal_NUM] = (void*)Encoder_getReturnVal;

    PyObject *encoder_c_api = PyCObject_FromVoidPtr((void*)PyEncoder_API, NULL);
    if (encoder_c_api != NULL)
        PyModule_AddObject(context_mod, "_ENCODER_C_API", encoder_c_api);
}
