// doxoade/tools/vulcan/native/mercury_core.c
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

static PyObject* mercury_load_hbd1(PyObject* self, PyObject* args) {
    const char* path;
    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    FILE* f = fopen(path, "rb");
    if (!f) return PyErr_SetFromErrno(PyExc_FileNotFoundError);

    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);

    uint8_t* data = (uint8_t*)malloc(sz);
    if (!data) { fclose(f); return PyErr_NoMemory(); }
    
    if (fread(data, 1, sz, f) != (size_t)sz) {
        free(data); fclose(f); return PyErr_SetFromErrno(PyExc_IOError);
    }
    fclose(f);

    if (sz < 11 || memcmp(data, "HBD1", 4) != 0) {
        free(data);
        return PyErr_Format(PyExc_ValueError, "Arquivo HBD1 invalido");
    }

    uint16_t tk_count = (uint16_t)(data[5] | (data[6] << 8));
    uint32_t orig_sz = (uint32_t)(data[7] | (data[8]<<8) | (data[9]<<16) | (data[10]<<24));
    size_t off = 11;

    char* dict_strs[256] = {0};
    int dict_lens[256] = {0};

    // Lê os tokens para L1 Cache
    for (int i = 0; i < tk_count; i++) {
        if (off + 2 > (size_t)sz) break;
        uint16_t plen = (uint16_t)(data[off] | (data[off+1] << 8)); off += 2;
        if (off + plen > (size_t)sz) break;
        dict_strs[i] = (char*)malloc(plen);
        memcpy(dict_strs[i], data + off, plen);
        dict_lens[i] = plen;
        off += plen;
    }

    if (off + 4 > (size_t)sz) { free(data); return PyErr_Format(PyExc_ValueError, "Payload truncado"); }
    uint32_t payload_sz = (uint32_t)(data[off] | (data[off+1]<<8) | (data[off+2]<<16) | (data[off+3]<<24));
    off += 4;
    
    char* out = (char*)malloc(orig_sz + 1);
    if (!out) { free(data); return PyErr_NoMemory(); }
    
    // ---------------------------------------------------------
    // LOOP MESTRE: POINTER CHASING (Zero Function Calls)
    // ---------------------------------------------------------
    // O comando 'register' implora ao compilador C (GCC) para 
    // manter essas variáveis DENTRO do chip, sem nunca ir pra RAM.
    register char* dst = out;
    register const uint8_t* src = data + off;
    register const uint8_t* end = src + payload_sz;

    while (src < end) {
        // Pega o byte atual e já avança o ponteiro num único ciclo de clock
        uint8_t c = *src++; 
        
        if (c == 0xFF) {
            if (src < end) {
                uint8_t tid = *src++;
                if (tid < tk_count) {
                    int l = dict_lens[tid];
                    memcpy(dst, dict_strs[tid], l);
                    dst += l;
                }
            }
        } else {
            *dst++ = c;
        }
    }
    // ---------------------------------------------------------

    PyObject* result = PyUnicode_DecodeUTF8(out, dst - out, "strict");

    free(out);
    free(data);
    for(int i = 0; i < 256; i++) { if(dict_strs[i]) free(dict_strs[i]); }

    return result;
}

static PyMethodDef MercuryMethods[] = {
    {"load_hermes_data", mercury_load_hbd1, METH_VARARGS, "HBD1 Pointer Chasing Decoder"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef mercurymodule = {
    PyModuleDef_HEAD_INIT, "mercury_core", "Mercury Data Engine", -1, MercuryMethods
};

PyMODINIT_FUNC PyInit_mercury_core(void) {
    return PyModule_Create(&mercurymodule);
}