// Use this string buffer for better performance when using string input/outputs.
#include <Python.h>

typedef struct {
    PyObject_HEAD
    PyObject *src_str; // Ptr to source if source string was passed
    char *buf; // C-Buffer
    int len; // Length of current buffer
    int pos; // Current position in buffer
} BufferObj;

char* Buffer_read(BufferObj *self, int len);
PyObject* Buffer_readPyString(BufferObj *self, int len);
int Buffer_tell(BufferObj *self);
int Buffer_seek(BufferObj *self, int pos);
int Buffer_writeCStringLength(BufferObj *self, char *str, int len);
int Buffer_writePyString(BufferObj *self, PyObject* py_str);
