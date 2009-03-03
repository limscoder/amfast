/* Things used by both the encoder and the decoder. */
#include <Python.h>

// Valid integer range
#define MIN_INT -268435457
#define MAX_INT 268435456

// Reference bit
#define REFERENCE_BIT 0x01

// Empty string
#define EMPTY_STRING_TYPE 0x01

// Object Headers
#define STATIC 0x03
#define DYNAMIC 0x0B
#define EXTERNIZEABLE 0x07

// Type markers
#define NULL_TYPE 0x01
#define FALSE_TYPE 0x02
#define TRUE_TYPE 0x03
#define INT_TYPE 0x04
#define DOUBLE_TYPE 0x05
#define STRING_TYPE 0x06
#define XML_DOC_TYPE 0x07
#define DATE_TYPE 0x08
#define ARRAY_TYPE 0x09
#define OBJECT_TYPE 0x0A
#define XML_TYPE 0x0B
#define BYTE_ARRAY_TYPE 0x0C

/* A dynamic array of ObjectRefs. */
typedef struct {
    PyObject **data;
    size_t data_len;
    size_t data_size;
    PyObject *references; // Map pointers to indexes
} ObjectContext;

ObjectContext* create_object_context(size_t size);
int destroy_object_context(ObjectContext *context);
int map_next_object_ref(ObjectContext *context, PyObject *ref);
int map_next_object_idx(ObjectContext *context, PyObject *ref);
PyObject* get_ref_from_idx(ObjectContext *context, int idx);
int get_idx_from_ref(ObjectContext *context, PyObject *ref);
