/* Functions used by both the encoder and the decoder. */
#include "amf_common.h"

// ---- DECLARATIONS
static int map_object_ref(ObjectContext *context, PyObject *ref);

/* Create a new ObjectContext. */
ObjectContext* create_object_context(size_t size)
{
    ObjectContext *context;
    context = (ObjectContext*)malloc(sizeof(ObjectContext));
    if (!context) {
        PyErr_SetNone(PyExc_MemoryError);
        return NULL;
    }

    context->data_size = size; // Initial array size.
    context->data_len = 0; // Nothing is in the array yet
    context->data = (PyObject**)malloc(sizeof(PyObject*) * context->data_size); // Create array
    if (!context->data) {
        free(context);
        PyErr_SetNone(PyExc_MemoryError);
        return NULL;
    }

    context->references = PyDict_New();
    if (!context->references) {
        free(context->data);
        free(context);
        return NULL;
    }

    return context;
}

/* De-allocate an ObjectContext. */
int destroy_object_context(ObjectContext *context)
{
    // De-Allocate all ObjectRefs
    int i;
    for (i = 0; i < (int)context->data_len; i++) {
        PyObject *ref = context->data[i];
        Py_DECREF(ref); // Don't need obj anymore
    }

    Py_DECREF(context->references);

    if (context->data) {
        free(context->data);
    }
    free(context);
    return 1;
}

/*
 * Maps a PyObject to the next available index.
 *
 * Also adds a reference to the reference dict.
 */
int map_next_object_ref(ObjectContext *context, PyObject *ref)
{
    int idx_int = map_object_ref(context, ref);
    if (idx_int == -1)
        return 0;
  
    // Add a pointer to this object to
    // the reference dict.
    PyObject *key = PyLong_FromVoidPtr(ref);
    if (!key)
        return 0;

    PyObject *idx = PyInt_FromLong((long)idx_int);
    if (!idx) {
        Py_DECREF(key);
        return 0;
    }

    int return_value = PyDict_SetItem(context->references, key, idx);
    Py_DECREF(key);
    Py_DECREF(idx);
    if (return_value == -1)
        return 0;

    return 1;
}

/* Maps an object to the next available index. */
int map_next_object_idx(ObjectContext *context, PyObject *ref)
{
    int idx_int = map_object_ref(context, ref);
    if (idx_int == -1)
        return 0; 

    return 1;
}

/* Returns mapped idx if it exists, otherwise returns -1. */
int get_idx_from_ref(ObjectContext *context, PyObject *ref)
{
    // Retrieve idx from dict
    PyObject *key = PyLong_FromVoidPtr(ref);
    if (!key)
        return 0;

    PyObject *idx = PyDict_GetItem(context->references, key);
    Py_DECREF(key);
    if (!idx)
        return -1;

    long idx_int = PyInt_AsLong(idx);
    return (int)idx_int;
}

/* Returns mapped ref if it exists, otherwise returns NULL. */
PyObject* get_ref_from_idx(ObjectContext *context, int idx)
{
    if (idx >= (int)context->data_len) {
        PyErr_SetString(PyExc_IndexError, "AMF index out of range.");
        return NULL;
    }

    return context->data[idx];
}

/* Maps an reference and an index, DOES NOT CHECK UNIQUENESS!!. */
static int map_object_ref(ObjectContext *context, PyObject *ref)
{
    // Make sure data array is large enough
    const size_t new_len = context->data_len + 1;
    size_t current_size = context->data_size;

    while (new_len > current_size) {
        // array is not large enough.
        // Double its memory, so that we
        // don't need to realloc everytime.
        current_size *= 2;
    }

    if (current_size != context->data_size) {
        context->data_size = current_size;
        context->data = (PyObject**)realloc(context->data, sizeof(PyObject*) * context->data_size);
        if (!context->data) {
            PyErr_SetNone(PyExc_MemoryError);
            return -1;
        }
    }

    context->data[context->data_len] = ref;
    context->data_len += 1;

    // Just to make sure this object is not GCed before we get to it.
    Py_INCREF(ref);

    return context->data_len - 1;
}
