/* Things used by both the encoder and the decoder. */

// Python date handling API
#ifndef DATETIME_H
#include <datetime.h>
#endif

// Use to test for endianness at run time.
#define is_bigendian() ((*(char*)&endian_test) == 0)

// ---- AMF3

// Valid AMF3 integer range
#define MIN_INT -268435457
#define MAX_INT 268435456

// Reference bit
#define REFERENCE_BIT 0x01

// Empty string
#define EMPTY_STRING_TYPE 0x01

// Object Headers
#define STATIC 0x03
#define DYNAMIC 0x0B
#define EXTERNALIZABLE 0x07

// Type markers
#define UNDEFINED_TYPE 0x00
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

// ---- AMF0

// Valid AMF0 integer types
#define MAX_USHORT 65535

// Client types defined in AMF remoting message
#define FLASH_8 0x00
#define FLASH_COM 0x01
#define FLASH_9 0x03

// AMF0 Types
#define NUMBER_AMF0 0x00
#define BOOL_AMF0 0x01
#define FALSE_AMF0 0x00
#define TRUE_AMF0 0x01
#define STRING_AMF0 0x02
#define OBJECT_AMF0 0x03
#define MOVIE_AMF0 0x04
#define NULL_AMF0 0x05
#define UNDEFINED_AMF0 0x06
#define REF_AMF0 0x07
#define MIXED_ARRAY_AMF0 0x08
#define OBJECT_END_AMF0 0x09
#define ARRAY_AMF0 0x0A
#define DATE_AMF0 0x0B
#define LONG_STRING_AMF0 0x0C
#define UNSUPPORTED_AMF0 0x0D
#define RECORDSET_AMF0 0x0E
#define XML_DOC_AMF0 0x0F
#define TYPED_OBJ_AMF0 0x10
#define AMF3_AMF0 0x11

// For 2.4 support
#if PY_VERSION_HEX < 0x02050000
#ifndef PY_SSIZE_T_MAX
typedef int Py_ssize_t;
#define PY_SSIZE_T_MAX INT_MAX
#define PY_SSIZE_T_MIN INT_MIN
#endif
#endif

// Functions
int type_list(PyObject* class_def, PyObject *mapper,
    PyObject* name_list, PyObject* val_list, int type);
int type_dict(PyObject* class_def, PyObject *mapper, PyObject* dict, int type);
