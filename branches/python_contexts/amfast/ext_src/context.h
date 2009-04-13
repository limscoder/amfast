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
