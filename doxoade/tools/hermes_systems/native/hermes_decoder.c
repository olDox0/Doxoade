// doxoade/tools/hermes_systems/native/hermes_decoder.c
/*
 * Hermes Native Decoder v1.3
 * Decodificador C nativo para arquivos .hermes HBC3 e HBC4
 * Toolchain: w64devkit (MinGW-w64 GCC)
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <marshal.h>

#define BITMAP_SIZE 32
#define TOKEN_MIN 0x80

static inline int has_token(const uint8_t* bitmap, uint8_t c) {
    return (bitmap[c >> 3] >> (c & 7)) & 1;
}

static PyObject* reverse_tokens_c(PyObject* code_obj, PyObject* decoder, const uint8_t* bitmap) {
    PyObject* co_consts = PyObject_GetAttrString(code_obj, "co_consts");
    if (!co_consts) return NULL;

    Py_ssize_t n = PyTuple_Size(co_consts);
    PyObject* new_consts = PyTuple_New(n);
    if (!new_consts) { Py_DECREF(co_consts); return NULL; }

    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject* item = PyTuple_GetItem(co_consts, i);
        PyObject* replaced = NULL;

        if (PyUnicode_Check(item)) {
            Py_ssize_t len;
            const char* s = PyUnicode_AsUTF8AndSize(item, &len);
            if (!s) {
                Py_DECREF(co_consts);
                Py_DECREF(new_consts);
                return NULL;
            }
            
            int needs_rev = 0;
            for (Py_ssize_t k = 0; k < len; k++) {
                uint8_t c = (uint8_t)s[k];
                if (c >= TOKEN_MIN && has_token(bitmap, c)) { needs_rev = 1; break; }
            }
            
            if (!needs_rev) {
                Py_INCREF(item);
                replaced = item;
            } else {
                size_t out_cap = (size_t)len * 8;
                char* out = (char*)malloc(out_cap);
                if (!out) {
                    Py_DECREF(co_consts); Py_DECREF(new_consts); PyErr_NoMemory(); return NULL;
                }
                
                size_t out_pos = 0;
                for (Py_ssize_t k = 0; k < len; k++) {
                    uint8_t c = (uint8_t)s[k];
                    if (c >= TOKEN_MIN && has_token(bitmap, c)) {
                        PyObject* key = PyLong_FromLong(c);
                        PyObject* repl = PyDict_GetItem(decoder, key);
                        Py_DECREF(key);
                        
                        if (repl) {
                            const char* r = PyUnicode_AsUTF8(repl);
                            if (!r) {
                                free(out); Py_DECREF(co_consts); Py_DECREF(new_consts); return NULL;
                            }
                            size_t rl = strlen(r);
                            while (out_pos + rl >= out_cap) {
                                out_cap *= 2;
                                char* new_buf = (char*)realloc(out, out_cap);
                                if (!new_buf) {
                                    free(out); Py_DECREF(co_consts); Py_DECREF(new_consts); PyErr_NoMemory(); return NULL;
                                }
                                out = new_buf;
                            }
                            memcpy(out + out_pos, r, rl);
                            out_pos += rl;
                        } else {
                            if (out_pos + 1 >= out_cap) {
                                out_cap *= 2; out = (char*)realloc(out, out_cap);
                            }
                            out[out_pos++] = c;
                        }
                    } else {
                        if (out_pos + 1 >= out_cap) {
                            out_cap *= 2; out = (char*)realloc(out, out_cap);
                        }
                        out[out_pos++] = c;
                    }
                }
                replaced = PyUnicode_DecodeUTF8(out, out_pos, "strict");
                free(out);
            }
        } else if (PyCode_Check(item)) {
            replaced = reverse_tokens_c(item, decoder, bitmap);
        } else {
            Py_INCREF(item);
            replaced = item;
        }

        if (!replaced) {
            Py_DECREF(co_consts); Py_DECREF(new_consts); return NULL;
        }
        PyTuple_SetItem(new_consts, i, replaced);
    }
    Py_DECREF(co_consts);

    PyObject* meth = PyObject_GetAttrString(code_obj, "replace");
    if (!meth) { Py_DECREF(new_consts); return NULL; }
    
    PyObject* kwargs = PyDict_New();
    if (!kwargs) { Py_DECREF(new_consts); Py_DECREF(meth); return NULL; }
    PyDict_SetItemString(kwargs, "co_consts", new_consts);
    
    PyObject* args = PyTuple_New(0);
    PyObject* res = PyObject_Call(meth, args, kwargs);
    
    Py_DECREF(args); Py_DECREF(kwargs); Py_DECREF(meth); Py_DECREF(new_consts);
    return res;
}

static PyObject* hermes_decode(PyObject* self, PyObject* args) {
    const char* path;
    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    FILE* f = fopen(path, "rb");
    if (!f) { PyErr_SetString(PyExc_FileNotFoundError, path); return NULL; }
    
    fseek(f, 0, SEEK_END);
    long sz_long = ftell(f);
    if (sz_long < 0) { fclose(f); PyErr_SetString(PyExc_IOError, "ftell failed"); return NULL; }
    size_t sz = (size_t)sz_long;
    fseek(f, 0, SEEK_SET);
    
    uint8_t* data = (uint8_t*)malloc(sz);
    if (!data) { fclose(f); PyErr_NoMemory(); return NULL; }
    
    if (fread(data, 1, sz, f) != sz) {
        free(data); fclose(f); PyErr_SetString(PyExc_IOError, "fread failed"); return NULL;
    }
    fclose(f);

    if (sz < 4 + 1 + 2 + BITMAP_SIZE) {
        free(data); PyErr_SetString(PyExc_ValueError, "Invalid file size"); return NULL;
    }

    int is_hbc3 = (memcmp(data, "HBC3", 4) == 0);
    int is_hbc4 = (memcmp(data, "HBC4", 4) == 0);

    if (!is_hbc3 && !is_hbc4) {
        free(data); PyErr_SetString(PyExc_ValueError, "Invalid magic header"); return NULL;
    }

    uint8_t version = data[4];
    if ((is_hbc3 && version != 3) || (is_hbc4 && version != 4)) {
        free(data); PyErr_SetString(PyExc_ValueError, "Unsupported HBC version"); return NULL;
    }
    
    uint16_t tk_count = (uint16_t)(data[5] | (data[6] << 8));
    const uint8_t* bitmap = data + 7;
    
    PyObject* decoder = PyDict_New();
    if (!decoder) { free(data); return NULL; }
    
    size_t off = 7 + BITMAP_SIZE;
    for (uint16_t i = 0; i < tk_count; i++) {
        if (off + 4 > sz) goto truncate_err;
        uint16_t tid = (uint16_t)(data[off] | (data[off+1] << 8)); off += 2;
        uint16_t plen = (uint16_t)(data[off] | (data[off+1] << 8)); off += 2;
        
        if (off + plen > sz) goto truncate_err;
        
        PyObject* k = PyLong_FromLong(tid);
        PyObject* v = PyUnicode_DecodeUTF8((const char*)data + off, plen, "strict");
        if (!k || !v) { Py_XDECREF(k); Py_XDECREF(v); Py_DECREF(decoder); free(data); return NULL; }
        if (PyDict_SetItem(decoder, k, v) < 0) { Py_DECREF(k); Py_DECREF(v); Py_DECREF(decoder); free(data); return NULL; }
        
        Py_DECREF(k); Py_DECREF(v); off += plen;
        continue;
        
    truncate_err:
        Py_DECREF(decoder); free(data); PyErr_SetString(PyExc_ValueError, "Truncated"); return NULL;
    }

    PyObject* code = NULL;

    if (is_hbc4) {
        if (off + 4 > sz) goto truncate_err;
        uint32_t marshalled_size = (uint32_t)(data[off] | (data[off+1]<<8) | (data[off+2]<<16) | (data[off+3]<<24));
        off += 4;

        if (off + marshalled_size > sz) goto truncate_err;

        code = PyMarshal_ReadObjectFromString((char*)data + off, marshalled_size);
        free(data);
        if (!code) { Py_DECREF(decoder); return NULL; }
    } else {
        PyObject* zlib_mod = PyImport_ImportModule("zlib");
        if (!zlib_mod) { Py_DECREF(decoder); free(data); return NULL; }
        PyObject* decompress = PyObject_GetAttrString(zlib_mod, "decompress");
        Py_DECREF(zlib_mod);
        if (!decompress) { Py_DECREF(decoder); free(data); return NULL; }
        
        PyObject* comp_bytes = PyBytes_FromStringAndSize((const char*)data + off, sz - off);
        free(data);
        if (!comp_bytes) { Py_DECREF(decompress); Py_DECREF(decoder); return NULL; }
        
        PyObject* raw = PyObject_CallFunctionObjArgs(decompress, comp_bytes, NULL);
        Py_DECREF(comp_bytes); Py_DECREF(decompress);
        if (!raw) { Py_DECREF(decoder); return NULL; }
        
        char* buf; Py_ssize_t blen;
        if (PyBytes_AsStringAndSize(raw, &buf, &blen) < 0) { Py_DECREF(raw); Py_DECREF(decoder); return NULL; }
        code = PyMarshal_ReadObjectFromString(buf, blen);
        Py_DECREF(raw);
        if (!code) { Py_DECREF(decoder); return NULL; }
    }

    PyObject* res = reverse_tokens_c(code, decoder, bitmap);
    Py_DECREF(code); Py_DECREF(decoder);
    return res;
}

static PyMethodDef HermesMethods[] = {
    {"decode", hermes_decode, METH_VARARGS, "Decodifica HBC3/HBC4"}, {NULL, NULL, 0, NULL}
};

static struct PyModuleDef hermesmodule = {
    PyModuleDef_HEAD_INIT, "hermes_decoder", "Hermes Native Decoder", -1, HermesMethods
};

PyMODINIT_FUNC PyInit_hermes_decoder(void) { return PyModule_Create(&hermesmodule); }