// doxoade/tools/hermes_systems/native/hermes_hbc6_patches.c
#include <Python.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <emmintrin.h>  // SSE2
#include "hermes_hbc6_patches.h"

#define MACRO_OPCODE 0xC0
#define READ_U16(p) ((uint16_t)((p)[0] | ((p)[1] << 8)))
#define READ_U32(p) ((uint32_t)((p)[0] | ((p)[1] << 8) | ((p)[2] << 16) | ((p)[3] << 24)))

// ═══════════════════════════════════════════════════════════════════
// LOG CONDICIONAL (Unificado com o resto do sistema)
// ═══════════════════════════════════════════════════════════════════
static int g_verbose = -1;
#define HBC6_LOG(fmt, ...) do { \
    if (g_verbose == -1) g_verbose = (getenv("HERMES_VERBOSE") != NULL); \
    if (g_verbose) fprintf(stderr, "[HERMES-C:HBC6] " fmt "\n", ##__VA_ARGS__); \
} while(0)

// ═══════════════════════════════════════════════════════════════════
// STRINGS INTERNADAS (Elimina hash de string no loop DFS)
// ═══════════════════════════════════════════════════════════════════
static PyObject* g_str_co_consts = NULL;
static PyObject* g_str_co_code = NULL;
static PyObject* g_str_replace = NULL;

static void init_interned_strings(void) {
    if (!g_str_co_consts) {
        g_str_co_consts = PyUnicode_InternFromString("co_consts");
        g_str_co_code = PyUnicode_InternFromString("co_code");
        g_str_replace = PyUnicode_InternFromString("replace");
    }
}

// ═══════════════════════════════════════════════════════════════════
// MICRO-TIMERS (RDTSC)
// ═══════════════════════════════════════════════════════════════════
static inline uint64_t _rdtsc() {
#if defined(x86_64) || defined(_M_X64) || defined(__i386) || defined(_M_IX86)
    uint32_t lo, hi;
    __asm__ volatile ("rdtsc" : "=a" (lo), "=d" (hi));
    return ((uint64_t)hi << 32) | lo;
#else
    return 0;
#endif
}

// ═══════════════════════════════════════════════════════════════════
// BUFFER POOL GLOBAL (Zero-Allocation)
// ═══════════════════════════════════════════════════════════════════
#define BUFFER_POOL_SIZE (4 * 1024 * 1024)  // 4MB pool
static uint8_t* g_buffer_pool = NULL;
static size_t g_pool_used = 0;

static uint8_t* get_buffer(size_t needed) {
    if (!g_buffer_pool) {
        g_buffer_pool = (uint8_t*)malloc(BUFFER_POOL_SIZE);
        if (!g_buffer_pool) return NULL;
    }
    if (g_pool_used + needed > BUFFER_POOL_SIZE) {
        g_pool_used = 0;  // Reset circular buffer
    }
    uint8_t* ptr = g_buffer_pool + g_pool_used;
    g_pool_used += needed;
    return ptr;
}

// ═══════════════════════════════════════════════════════════════════
// SIMD SCANNER (SSE2 - Busca 16 bytes por vez)
// ═══════════════════════════════════════════════════════════════════
static inline int has_macro_opcodes_simd(const uint8_t* data, size_t len) {
    __m128i target = _mm_set1_epi8((char)MACRO_OPCODE);
    size_t i = 0;
    for (; i + 16 <= len; i += 16) {
        __m128i chunk = _mm_loadu_si128((const __m128i*)(data + i));
        if (_mm_movemask_epi8(_mm_cmpeq_epi8(chunk, target)) != 0) return 1;
    }
    for (; i < len; i++) {
        if (data[i] == MACRO_OPCODE) return 1;
    }
    return 0;
}

// ═══════════════════════════════════════════════════════════════════
// EXPANSÃO OTIMIZADA (Single-Pass com Prefetch)
// ═══════════════════════════════════════════════════════════════════
static PyObject* expand_bytecode_inplace(PyObject* co_code_bytes, HBC6_MacroDict* dict) {
    uint64_t t0 = _rdtsc();
    Py_ssize_t orig_len = PyBytes_Size(co_code_bytes);
    const uint8_t* src = (const uint8_t*)PyBytes_AsString(co_code_bytes);
    
    if (!has_macro_opcodes_simd(src, orig_len)) {
        Py_INCREF(co_code_bytes);
        return co_code_bytes;
    }
    
    uint64_t t1 = _rdtsc();
    size_t max_len = orig_len * 2;
    uint8_t* dst = get_buffer(max_len);
    if (!dst) {
        dst = (uint8_t*)malloc(max_len);
        if (!dst) return PyErr_NoMemory();
    }
    
    uint64_t t2 = _rdtsc();
    size_t i = 0, j = 0;
    while (i < orig_len) {
        if (i + 64 < orig_len) __builtin_prefetch(src + i + 64, 0, 1);
        if (src[i] == MACRO_OPCODE && (i + 1) < orig_len) {
            uint8_t token_idx = src[i+1];
            if (token_idx < dict->count && dict->defs[token_idx].opcodes != NULL) {
                HBC6_MacroDef* def = &dict->defs[token_idx];
                if (j + def->len > max_len) {
                    max_len *= 2;
                    uint8_t* new_dst = (uint8_t*)malloc(max_len);
                    memcpy(new_dst, dst, j);
                    dst = new_dst;
                }
                memcpy(dst + j, def->opcodes, def->len);
                j += def->len;
                i += 2;
                continue;
            }
        }
        dst[j++] = src[i++];
    }
    
    uint64_t t3 = _rdtsc();
    PyObject* new_bytes = PyBytes_FromStringAndSize((char*)dst, j);
    uint64_t t4 = _rdtsc();
    
    if (g_verbose) {
        fprintf(stderr, "[HERMES-C:PROF] expand_bytecode breakdown:\n");
        fprintf(stderr, "  SIMD scan         : %llu cycles\n", (unsigned long long)(t1 - t0));
        fprintf(stderr, "  Buffer alloc      : %llu cycles\n", (unsigned long long)(t2 - t1));
        fprintf(stderr, "  Expansion loop    : %llu cycles\n", (unsigned long long)(t3 - t2));
        fprintf(stderr, "  PyObject create   : %llu cycles\n", (unsigned long long)(t4 - t3));
    }
    return new_bytes;
}

// ═══════════════════════════════════════════════════════════════════
// WALKER DFS OTIMIZADO (Com Early Exit e Strings Internadas)
// ═══════════════════════════════════════════════════════════════════
static PyObject* apply_expansion_recursive(PyObject* code_obj, HBC6Context* ctx, int* dfs_idx) {
    if (!PyCode_Check(code_obj)) {
        Py_INCREF(code_obj);
        return code_obj;
    }
    
    int my_idx = (*dfs_idx)++;
    int has_patches = 0;
    for (uint32_t i = 0; i < ctx->patch_count; i++) {
        if (ctx->patches[i].co_index == my_idx) {
            has_patches = 1;
            break;
        }
    }
    
    PyObject* final_obj = code_obj;
    Py_INCREF(final_obj);
    
    if (has_patches) {
        PyObject* co_code = PyObject_GetAttr(code_obj, g_str_co_code);
        if (co_code && PyBytes_Check(co_code)) {
            Py_ssize_t len = PyBytes_Size(co_code);
            const uint8_t* data = (const uint8_t*)PyBytes_AsString(co_code);
            if (has_macro_opcodes_simd(data, len)) {
                PyObject* expanded = expand_bytecode_inplace(co_code, &ctx->macro_dict);
                if (expanded && expanded != co_code) {
                    PyObject* kwargs = PyDict_New();
                    PyDict_SetItem(kwargs, g_str_co_code, expanded);
                    PyObject* args = PyTuple_New(0);
                    PyObject* meth = PyObject_GetAttr(code_obj, g_str_replace);
                    PyObject* new_obj = PyObject_Call(meth, args, kwargs);
                    Py_DECREF(meth); Py_DECREF(args); Py_DECREF(kwargs); Py_DECREF(expanded);
                    if (new_obj) {
                        Py_DECREF(final_obj);
                        final_obj = new_obj;
                    }
                } else if (expanded) {
                    Py_DECREF(expanded);
                }
            }
        }
        Py_XDECREF(co_code);
    }
    
    PyObject* co_consts = PyObject_GetAttr(final_obj, g_str_co_consts);
    if (co_consts && PyTuple_Check(co_consts)) {
        Py_ssize_t n = PyTuple_Size(co_consts);
        PyObject* new_consts = PyTuple_New(n);
        int changed = 0;
        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject* item = PyTuple_GetItem(co_consts, i);
            if (PyCode_Check(item)) {
                PyObject* patched_child = apply_expansion_recursive(item, ctx, dfs_idx);
                if (patched_child != item) changed = 1;
                PyTuple_SetItem(new_consts, i, patched_child);
            } else {
                Py_INCREF(item);
                PyTuple_SetItem(new_consts, i, item);
            }
        }
        if (changed) {
            PyObject* kwargs = PyDict_New();
            PyDict_SetItem(kwargs, g_str_co_consts, new_consts);
            PyObject* args = PyTuple_New(0);
            PyObject* meth = PyObject_GetAttr(final_obj, g_str_replace);
            PyObject* updated_obj = PyObject_Call(meth, args, kwargs);
            Py_DECREF(meth); Py_DECREF(args); Py_DECREF(kwargs);
            if (updated_obj) {
                Py_DECREF(final_obj);
                final_obj = updated_obj;
            }
        }
        Py_DECREF(new_consts);
    }
    Py_XDECREF(co_consts);
    return final_obj;
}

// ═══════════════════════════════════════════════════════════════════
// API PÚBLICA
// ═══════════════════════════════════════════════════════════════════
PyObject* hermes_apply_hbc6_expansion(PyObject* code_obj, HBC6Context* ctx) {
    init_interned_strings();
    if (ctx->patch_count == 0) {
        Py_INCREF(code_obj);
        return code_obj;
    }
    HBC6_LOG("=== STARTING HBC6 PATCH ENGINE (SIMD + Pool) ===");
    HBC6_LOG("Total patches mapped in HRT: %d | MacroDict: %d", ctx->patch_count, ctx->macro_dict.count);
    Py_INCREF(code_obj);
    int dfs_idx = 0;
    PyObject* result = apply_expansion_recursive(code_obj, ctx, &dfs_idx);
    Py_DECREF(code_obj);
    HBC6_LOG("=== HBC6 PATCH ENGINE COMPLETE ===");
    return result;
}