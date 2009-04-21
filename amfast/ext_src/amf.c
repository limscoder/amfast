/* Methods used by both the encoder and the decoder. */

#include <Python.h>

#include "amf.h"

// Get typed value from mapper or function. Returns new reference.
static PyObject* get_typed_val(PyObject *mapper, PyObject *get_func,
    PyObject *attr, PyObject *val)
{

    PyObject *id = PyLong_FromVoidPtr((void*)val);
    if (id == NULL)
        return NULL;

    PyObject *result = PyDict_GetItem(mapper, id);
    if (result == NULL) {
        result = PyObject_CallFunctionObjArgs(get_func, attr, val, NULL);
        if (result == NULL) {
            Py_DECREF(id);
            return NULL;
        }

        if (PyDict_SetItem(mapper, id, result) == -1) {
            Py_DECREF(id);
            Py_DECREF(result);
            return NULL;
        }
    } else {
        Py_INCREF(result);
    }

    Py_DECREF(id);
    return result;
}

// Replace values in a list with their correctly typed version
int type_list(PyObject* class_def, PyObject *mapper, const char *method_name,
    PyObject* name_list, PyObject* val_list)
{
    PyObject *get_func = PyObject_GetAttrString(class_def, method_name);
    if (get_func == NULL)
        return 0;

    Py_ssize_t name_len = PySequence_Size(name_list);
    if (name_len == -1) {
        Py_DECREF(get_func);
        return 0;
    }

    Py_ssize_t val_len = PySequence_Size(val_list);
    if (val_len == -1) {
        Py_DECREF(get_func);
        return 0;
    }

    if (val_len != name_len) {
        Py_DECREF(get_func);
        PyErr_SetString(PyExc_Exception, "Name count does not match value count.");
        return 0;
    }

    int i;
    for (i = 0; i < val_len; i++) {
        PyObject *name = PySequence_GetItem(name_list, i);
        if (name == NULL) {
            Py_DECREF(get_func);
            return 0;
        }

        PyObject *item = PySequence_GetItem(val_list, i);
        if (item == NULL) {
            Py_DECREF(get_func);
            Py_DECREF(name);
            return 0;
        }

        PyObject *typed_item = get_typed_val(mapper, get_func, name, item);
        Py_DECREF(name);
        Py_DECREF(item);
        if (typed_item == NULL) {
            Py_DECREF(get_func);
            return 0;
        }

        int result = PySequence_SetItem(val_list, i, typed_item);
        Py_DECREF(typed_item);
        if (result == -1) {
            Py_DECREF(get_func);
            return 0;
        }
    }

    Py_DECREF(get_func);
    return 1;
}

// Replace values in a dict with their correctly typed version
int type_dict(PyObject* class_def, PyObject *mapper, const char *method_name, PyObject* dict)
{
    PyObject *get_func = PyObject_GetAttrString(class_def, method_name);
    if (get_func == NULL)
        return 0;

    PyObject *key;
    PyObject *val;
    Py_ssize_t idx = 0;

    while (PyDict_Next(dict, &idx, &key, &val)) {
        PyObject *typed_item = get_typed_val(mapper, get_func, key, val);
        if (PyDict_SetItem(dict, key, typed_item) == -1) {
            Py_DECREF(get_func);
            return 0;
        }
    }

    Py_DECREF(get_func);
    return 1;
}
