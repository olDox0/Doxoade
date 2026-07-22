// doxoade/tools/hermes_systems/native/hermes_py_utils.c
// Hermes Bridge v3.0 — Unified HBC5/HBC6 Loader with Sotéria Integration
// Correções: VULN-1 a VULN-6 identificadas na auditoria forense.

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <marshal.h>
#include <windows.h>
#include <emmintrin.h>  // SSE2
#include <lz4.h>

#include "hermes_cache.h"
#include "hermes_mmap.h"
#include "hermes_async_log.h"

// ═══════════════════════════════════════════════════════════════════
// CONSTS DESERIALIZER - HBC6-P2
// ═══════════════════════════════════════════════════════════════════

#define TAG_NONE        0
#define TAG_BOOL        1
#define TAG_INT         2
#define TAG_FLOAT       3
#define TAG_STRING_REF  4
#define TAG_BYTES       5
#define TAG_TUPLE       6
#define TAG_CODE_REF    7
#define TAG_ELLIPSIS    8

// ═══════════════════════════════════════════════════════════════════
// EXPORTAÇÃO
// ═══════════════════════════════════════════════════════════════════
#ifdef _WIN32
#define HERMES_EXPORT __declspec(dllexport)
#else
#define HERMES_EXPORT __attribute__((visibility("default")))
#endif

// ═══════════════════════════════════════════════════════════════════
// MACROS E TELEMETRIA
// ═══════════════════════════════════════════════════════════════════
// [FIX VULN-1] Definição única das macros (removida duplicação)
#define READ_U16(p) ((uint16_t)((p)[0] | ((p)[1] << 8)))
#define READ_U32(p) ((uint32_t)((p)[0] | ((p)[1] << 8) | ((p)[2] << 16) | ((p)[3] << 24)))
#define MACRO_OPCODE 0xC0

static int g_verbose = -1;

#define HERMES_LOG(fmt, ...) do { \
    if (g_verbose == -1) g_verbose = (getenv("HERMES_VERBOSE") != NULL); \
    if (g_verbose) hermes_log_push(LOG_LEVEL_INFO, fmt, ##__VA_ARGS__); \
} while(0)

static double get_time_ms(void) {
    LARGE_INTEGER freq, count;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&count);
    return (double)count.QuadPart / (double)freq.QuadPart * 1000.0;
}

#define TIMER_START(name) double timer_##name = get_time_ms();
#define TIMER_END(name) do { \
    if (g_verbose == -1) g_verbose = (getenv("HERMES_VERBOSE") != NULL); \
    if (g_verbose) { \
        double elapsed = get_time_ms() - timer_##name; \
        hermes_log_push(LOG_LEVEL_INFO, "%-30s %8.3f ms", #name, elapsed); \
    } \
} while(0)

// ═══════════════════════════════════════════════════════════════════
// ESTRUTURAS HBC5
// ═══════════════════════════════════════════════════════════════════
typedef struct {
    char*     buffer;
    char**    pointers;
    uint16_t* lengths;
    uint16_t  count;
} HermesDict;

typedef struct {
    uint8_t        flags;
    uint8_t        bitmap[32];
    HermesDict     local_dict;
    const uint8_t* payload_ptr;
    uint32_t       payload_size;
    size_t         header_size;
} HBC5Context;

extern int      parse_hbc5_header(const uint8_t* data, size_t data_size, HBC5Context* ctx);
extern void     free_hbc5_context(HBC5Context* ctx);
extern PyObject* walk_and_decode_inplace(PyObject* code_obj, const uint8_t* bitmap,
                                         const HermesDict* l_dict);

// ═══════════════════════════════════════════════════════════════════
// ESTRUTURAS HBC6
// ═══════════════════════════════════════════════════════════════════
#pragma pack(push, 1)
typedef struct {
    uint32_t co_index;
    uint32_t offset;
    uint16_t token_id;
    uint16_t orig_ngram_len;
} HBC6_Patch;
#pragma pack(pop)

typedef struct {
    const uint8_t* opcodes;
    uint16_t       len;
} HBC6_MacroDef;

typedef struct {
    HBC6_MacroDef* defs;
    uint16_t       count;
} HBC6_MacroDict;

typedef struct {
    uint8_t        flags;
    HBC6_Patch*    patches;
    uint32_t       patch_count;
    HBC6_MacroDict macro_dict;
    const uint8_t* payload_ptr;
    uint32_t       payload_size;
    uint8_t*       decompressed_payload;   // ← ADICIONE
    uint32_t       decompressed_size;      // ← ADICIONE
} HBC6Context;

// ═══════════════════════════════════════════════════════════════════
// STRINGS INTERNADAS
// ═══════════════════════════════════════════════════════════════════
static PyObject* g_str_co_code   = NULL;
static PyObject* g_str_co_consts = NULL;
static PyObject* g_str_replace   = NULL;

static void init_interned_strings(void) {
    if (!g_str_co_code) {
        g_str_co_code   = PyUnicode_InternFromString("co_code");
        g_str_co_consts = PyUnicode_InternFromString("co_consts");
        g_str_replace   = PyUnicode_InternFromString("replace");
    }
}

// ═══════════════════════════════════════════════════════════════════
// BUFFER POOL + SIMD SCANNER
// ═══════════════════════════════════════════════════════════════════
#define BUFFER_POOL_SIZE (4 * 1024 * 1024)
static uint8_t* g_buffer_pool = NULL;
static size_t   g_pool_used   = 0;

static uint8_t* get_buffer(size_t needed) {
    if (!g_buffer_pool) g_buffer_pool = (uint8_t*)malloc(BUFFER_POOL_SIZE);
    if (!g_buffer_pool) return NULL;
    if (g_pool_used + needed > BUFFER_POOL_SIZE) g_pool_used = 0;
    uint8_t* ptr = g_buffer_pool + g_pool_used;
    g_pool_used += needed;
    return ptr;
}

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
// HBC6: PARSER
// ═══════════════════════════════════════════════════════════════════
static int hermes_parse_hbc6_header(const uint8_t* data, size_t data_size, HBC6Context* ctx) {
    if (!data || data_size < 9 || !ctx) return -1;
    if (memcmp(data, "HBC6", 4) != 0 || data[4] != 0x06) return -1;

    size_t offset = 6;
    ctx->flags = data[5];
    ctx->decompressed_payload = NULL;   // ← NOVO
    ctx->decompressed_size = 0;         // ← NOVO

    // 1. HRT
    if (offset + 4 > data_size) return -1;
    uint32_t hrt_size = READ_U32(&data[offset]); offset += 4;
    if (hrt_size % 12 != 0 || offset + hrt_size > data_size) return -1;
    ctx->patch_count = hrt_size / 12;
    ctx->patches = (HBC6_Patch*)&data[offset]; offset += hrt_size;

    // 2. MacroDict
    if (offset + 4 > data_size) return -1;
    uint32_t macro_dict_size = READ_U32(&data[offset]); offset += 4;
    ctx->macro_dict.count = 0;
    ctx->macro_dict.defs = NULL;
    if (macro_dict_size >= 1 && offset + macro_dict_size <= data_size) {
        uint8_t dict_count = data[offset];
        size_t md_offset = offset + 1;
        if (dict_count > 0 && dict_count < 256) {
            ctx->macro_dict.count = dict_count;
            ctx->macro_dict.defs = (HBC6_MacroDef*)calloc(dict_count, sizeof(HBC6_MacroDef));
            if (!ctx->macro_dict.defs) return -1;
            for (uint8_t i = 0; i < dict_count; i++) {
                if (md_offset + 2 > offset + macro_dict_size) {
                    free(ctx->macro_dict.defs); ctx->macro_dict.defs = NULL;
                    return -1;
                }
                uint8_t tid = data[md_offset]; md_offset += 1;
                uint8_t len = data[md_offset]; md_offset += 1;
                if (md_offset + len > offset + macro_dict_size) {
                    free(ctx->macro_dict.defs); ctx->macro_dict.defs = NULL;
                    return -1;
                }
                if (tid < dict_count) {
                    ctx->macro_dict.defs[tid].opcodes = &data[md_offset];
                    ctx->macro_dict.defs[tid].len = len;
                }
                md_offset += len;
            }
        }
        offset += macro_dict_size;
    }

    // 3. Payload
    if (offset + 4 > data_size) {
        if (ctx->macro_dict.defs) { free(ctx->macro_dict.defs); ctx->macro_dict.defs = NULL; }
        return -1;
    }
    ctx->payload_size = READ_U32(&data[offset]); offset += 4;
    if (offset + ctx->payload_size > data_size) {
        if (ctx->macro_dict.defs) { free(ctx->macro_dict.defs); ctx->macro_dict.defs = NULL; }
        return -1;
    }
    ctx->payload_ptr = &data[offset];
    ctx->decompressed_payload = NULL;
    ctx->decompressed_size = 0;

    // 🚀 Descompressão LZ4 quando flags & 0x20
    if (ctx->flags & 0x20) {
        if (ctx->payload_size < 4) {
            if (ctx->macro_dict.defs) { free(ctx->macro_dict.defs); ctx->macro_dict.defs = NULL; }
            return -1;
        }
        int orig_size;
        memcpy(&orig_size, ctx->payload_ptr, 4);
        if (orig_size <= 0 || orig_size > 64 * 1024 * 1024) {
            if (ctx->macro_dict.defs) { free(ctx->macro_dict.defs); ctx->macro_dict.defs = NULL; }
            return -1;
        }
        ctx->decompressed_payload = (uint8_t*)malloc(orig_size);
        if (!ctx->decompressed_payload) {
            if (ctx->macro_dict.defs) { free(ctx->macro_dict.defs); ctx->macro_dict.defs = NULL; }
            return -1;
        }
        int result = LZ4_decompress_safe(
            (const char*)(ctx->payload_ptr + 4),
            (char*)ctx->decompressed_payload,
            (int)(ctx->payload_size - 4),
            orig_size
        );
        if (result < 0) {
            free(ctx->decompressed_payload);
            ctx->decompressed_payload = NULL;
            if (ctx->macro_dict.defs) { free(ctx->macro_dict.defs); ctx->macro_dict.defs = NULL; }
            return -1;
        }
        ctx->decompressed_size = (uint32_t)result;
        HERMES_LOG("LZ4 descomprimido: %u → %d bytes", ctx->payload_size, result);
    }

    return 0;
}

static void hermes_free_hbc6_context(HBC6Context* ctx) {
    if (ctx) {
        if (ctx->macro_dict.defs) {
            free(ctx->macro_dict.defs);
            ctx->macro_dict.defs = NULL;
        }
        if (ctx->decompressed_payload) {
            free(ctx->decompressed_payload);
            ctx->decompressed_payload = NULL;
        }
    }
}

// ═══════════════════════════════════════════════════════════════════
// CUSTOM DESERIALIZER (HBC6-P2)
// ═══════════════════════════════════════════════════════════════════

typedef struct {
    const uint8_t* data;
    size_t         size;
    size_t         offset;
    // String pool
    const char**   pool;
    uint32_t       pool_count;
} P2Reader;

static inline uint16_t p2_read_u16(P2Reader* r) {
    uint16_t v = READ_U16(&r->data[r->offset]);
    r->offset += 2;
    return v;
}

static inline uint32_t p2_read_u32(P2Reader* r) {
    uint32_t v = READ_U32(&r->data[r->offset]);
    r->offset += 4;
    return v;
}

static inline const char* p2_read_string_ref(P2Reader* r) {
    uint16_t idx = p2_read_u16(r);
    if (idx < r->pool_count) return r->pool[idx];
    return "";
}

static PyObject* p2_read_const(P2Reader* r);

static PyObject* p2_read_code_obj(P2Reader* r) {
    // Header fixo
    uint16_t argcount      = p2_read_u16(r);
    uint16_t posonly       = p2_read_u16(r);
    uint16_t kwonly        = p2_read_u16(r);
    uint16_t nlocals       = p2_read_u16(r);
    uint16_t stacksize     = p2_read_u16(r);
    uint32_t flags         = p2_read_u32(r);
    uint32_t firstlineno   = p2_read_u32(r);

    // co_code
    uint32_t code_size = p2_read_u32(r);
    PyObject* co_code = PyBytes_FromStringAndSize(
        (const char*)&r->data[r->offset], code_size);
    r->offset += code_size;

    // co_consts
    uint32_t consts_size = p2_read_u32(r);
    size_t consts_end = r->offset + consts_size;
    uint16_t const_count = p2_read_u16(r);
    PyObject* co_consts = PyTuple_New(const_count);
    for (uint16_t i = 0; i < const_count; i++) {
        PyObject* c = p2_read_const(r);
        PyTuple_SetItem(co_consts, i, c);
    }
    r->offset = consts_end;

    // co_names (refs para pool)
    uint16_t names_count = p2_read_u16(r);
    PyObject* co_names = PyTuple_New(names_count);
    for (uint16_t i = 0; i < names_count; i++) {
        const char* s = p2_read_string_ref(r);
        PyTuple_SetItem(co_names, i, PyUnicode_FromString(s));
    }

    // co_varnames
    uint16_t varnames_count = p2_read_u16(r);
    PyObject* co_varnames = PyTuple_New(varnames_count);
    for (uint16_t i = 0; i < varnames_count; i++) {
        const char* s = p2_read_string_ref(r);
        PyTuple_SetItem(co_varnames, i, PyUnicode_FromString(s));
    }

    // co_freevars
    uint16_t freevars_count = p2_read_u16(r);
    PyObject* co_freevars = PyTuple_New(freevars_count);
    for (uint16_t i = 0; i < freevars_count; i++) {
        const char* s = p2_read_string_ref(r);
        PyTuple_SetItem(co_freevars, i, PyUnicode_FromString(s));
    }

    // co_cellvars
    uint16_t cellvars_count = p2_read_u16(r);
    PyObject* co_cellvars = PyTuple_New(cellvars_count);
    for (uint16_t i = 0; i < cellvars_count; i++) {
        const char* s = p2_read_string_ref(r);
        PyTuple_SetItem(co_cellvars, i, PyUnicode_FromString(s));
    }

    // co_linetable
    uint32_t linetable_size = p2_read_u32(r);
    PyObject* co_linetable = PyBytes_FromStringAndSize(
        (const char*)&r->data[r->offset], linetable_size);
    r->offset += linetable_size;

    // co_exceptiontable
    uint32_t exctable_size = p2_read_u32(r);
    PyObject* co_exceptiontable = PyBytes_FromStringAndSize(
        (const char*)&r->data[r->offset], exctable_size);
    r->offset += exctable_size;

    // filename, name, qualname (refs para pool)
    const char* filename = p2_read_string_ref(r);
    const char* name     = p2_read_string_ref(r);
    const char* qualname = p2_read_string_ref(r);

    // Monta o code object via PyCode_NewWithPosOnlyArgs
    PyObject* fn_obj  = PyUnicode_FromString(filename);
    PyObject* nm_obj  = PyUnicode_FromString(name);
    PyObject* qn_obj  = PyUnicode_FromString(qualname);

    PyObject* code_obj = (PyObject*)PyCode_NewWithPosOnlyArgs(
        argcount, posonly, kwonly, nlocals, stacksize, flags,
        co_code, co_consts, co_names, co_varnames,
        co_freevars, co_cellvars,
        fn_obj, nm_obj, qn_obj,
        firstlineno,
        co_linetable,
        co_exceptiontable
    );

    Py_DECREF(fn_obj);
    Py_DECREF(nm_obj);
    Py_DECREF(qn_obj);

    Py_DECREF(co_code);
    Py_DECREF(co_consts);
    Py_DECREF(co_names);
    Py_DECREF(co_varnames);
    Py_DECREF(co_freevars);
    Py_DECREF(co_cellvars);
    Py_DECREF(co_linetable);
    Py_DECREF(co_exceptiontable);

    return code_obj;
}

static PyObject* p2_read_const(P2Reader* r) {
    uint8_t tag = r->data[r->offset++];
    switch (tag) {
        case TAG_NONE:      Py_RETURN_NONE;
        case TAG_BOOL:      return PyBool_FromLong(r->data[r->offset++]);
        case TAG_INT: {
            // Varint encoding
            int64_t val = 0;
            int shift = 0;
            while (1) {
                uint8_t b = r->data[r->offset++];
                val |= (int64_t)(b & 0x7F) << shift;
                if (!(b & 0x80)) break;
                shift += 7;
            }
            return PyLong_FromLongLong(val);
        }
        case TAG_FLOAT: {
            double val;
            memcpy(&val, &r->data[r->offset], 8);
            r->offset += 8;
            return PyFloat_FromDouble(val);
        }
        case TAG_STRING_REF: {
            const char* s = p2_read_string_ref(r);
            return PyUnicode_FromString(s);
        }
        case TAG_BYTES: {
            uint32_t len = p2_read_u32(r);
            PyObject* b = PyBytes_FromStringAndSize(
                (const char*)&r->data[r->offset], len);
            r->offset += len;
            return b;
        }
        case TAG_TUPLE: {
            uint16_t count = p2_read_u16(r);
            PyObject* t = PyTuple_New(count);
            for (uint16_t i = 0; i < count; i++) {
                PyTuple_SetItem(t, i, p2_read_const(r));
            }
            return t;
        }
        case TAG_CODE_REF:
            return p2_read_code_obj(r);
        case TAG_ELLIPSIS:
            return Py_Ellipsis;  // Py_INCREF implícito
        default:
            Py_RETURN_NONE;
    }
}

// Entry point: desserializa payload HBC6-P2
static PyObject* p2_deserialize(const uint8_t* data, size_t size) {
    P2Reader r = { .data = data, .size = size, .offset = 0 };

    // 1. Lê string pool
    uint32_t pool_count = p2_read_u32(&r);
    r.pool = (const char**)malloc(pool_count * sizeof(char*));
    for (uint32_t i = 0; i < pool_count; i++) {
        uint16_t len = p2_read_u16(&r);
        r.pool[i] = (const char*)&r.data[r.offset];
        r.offset += len;
    }
    r.pool_count = pool_count;

    // 2. Lê code object raiz
    PyObject* code_obj = p2_read_code_obj(&r);

    free(r.pool);
    return code_obj;
}

// ═══════════════════════════════════════════════════════════════════
// HBC6: EXPANSÃO DE BYTECODE
// ═══════════════════════════════════════════════════════════════════
static PyObject* expand_bytecode_inplace(PyObject* co_code_bytes, HBC6Context* ctx) {
    Py_ssize_t orig_len = PyBytes_Size(co_code_bytes);
    const uint8_t* src = (const uint8_t*)PyBytes_AsString(co_code_bytes);

    if (!has_macro_opcodes_simd(src, orig_len)) {
        Py_INCREF(co_code_bytes);
        return co_code_bytes;
    }

    size_t max_len = (size_t)orig_len * 2;
    uint8_t* dst = get_buffer(max_len);
    if (!dst) return PyErr_NoMemory();

    int is_pool = (dst >= g_buffer_pool && dst < g_buffer_pool + BUFFER_POOL_SIZE);
    size_t i = 0, j = 0;

    while (i < (size_t)orig_len) {
        if (src[i] == MACRO_OPCODE && (i + 1) < (size_t)orig_len) {
            uint8_t token_idx = src[i + 1];
            if (token_idx < ctx->macro_dict.count
                && ctx->macro_dict.defs[token_idx].opcodes != NULL
                && ctx->macro_dict.defs[token_idx].len > 0) {
                const HBC6_MacroDef* def = &ctx->macro_dict.defs[token_idx];
                if (j + def->len > max_len) {
                    max_len *= 2;
                    uint8_t* new_dst = (uint8_t*)malloc(max_len);
                    if (!new_dst) { if (!is_pool) free(dst); return PyErr_NoMemory(); }
                    memcpy(new_dst, dst, j);
                    if (!is_pool) free(dst);
                    dst = new_dst;
                    is_pool = 0;
                }
                memcpy(dst + j, def->opcodes, def->len);
                j += def->len;
                i += 2;
                continue;
            }
        }
        dst[j++] = src[i++];
    }

    PyObject* new_bytes = PyBytes_FromStringAndSize((char*)dst, j);
    if (!is_pool) free(dst);
    return new_bytes;
}

// [FIX VULN-3] Corrigido use-after-free: não fazer Py_DECREF(expanded)
// quando expanded == co_code (o Py_XDECREF(co_code) já cuida do refcount)
static PyObject* apply_expansion_recursive(PyObject* code_obj, HBC6Context* ctx, int* dfs_idx) {
    if (!PyCode_Check(code_obj)) {
        Py_INCREF(code_obj);
        return code_obj;
    }

    int my_idx = (*dfs_idx)++;
    PyObject* final_obj = code_obj;
    Py_INCREF(final_obj);

    int has_patches = 0;
    for (uint32_t i = 0; i < ctx->patch_count; i++) {
        if (ctx->patches[i].co_index == (uint32_t)my_idx) {
            has_patches = 1;
            break;
        }
    }

    if (has_patches) {
        PyObject* co_code = PyObject_GetAttr(code_obj, g_str_co_code);
        if (co_code && PyBytes_Check(co_code)) {
            PyObject* expanded = expand_bytecode_inplace(co_code, ctx);
            if (expanded && expanded != co_code) {
                // Bytecode foi expandido — substitui o code object
                PyObject* kwargs = PyDict_New();
                PyDict_SetItemString(kwargs, "co_code", expanded);
                PyObject* args = PyTuple_New(0);
                PyObject* meth = PyObject_GetAttrString(code_obj, "replace");
                if (meth) {
                    PyObject* new_obj = PyObject_Call(meth, args, kwargs);
                    Py_DECREF(meth);
                    if (new_obj) {
                        Py_DECREF(final_obj);
                        final_obj = new_obj;
                    }
                }
                Py_DECREF(args);
                Py_DECREF(kwargs);
                Py_DECREF(expanded);
            }
            // [FIX] Quando expanded == co_code, NÃO fazer Py_DECREF(expanded)
            // O Py_XDECREF(co_code) abaixo já decrementa o refcount corretamente
        }
        Py_XDECREF(co_code);
    }

    // Recursão em co_consts (code objects aninhados)
    PyObject* co_consts = PyObject_GetAttrString(final_obj, "co_consts");
    if (co_consts && PyTuple_Check(co_consts)) {
        Py_ssize_t n = PyTuple_Size(co_consts);
        PyObject* new_consts = PyTuple_New(n);
        if (!new_consts) { Py_DECREF(co_consts); return final_obj; }

        int changed = 0;
        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject* item = PyTuple_GetItem(co_consts, i);  // borrowed ref
            if (PyCode_Check(item)) {
                PyObject* child = apply_expansion_recursive(item, ctx, dfs_idx);
                if (child != item) changed = 1;
                PyTuple_SetItem(new_consts, i, child);  // steals ref
            } else {
                Py_INCREF(item);
                PyTuple_SetItem(new_consts, i, item);
            }
        }

        if (changed) {
            PyObject* kwargs = PyDict_New();
            PyDict_SetItemString(kwargs, "co_consts", new_consts);
            PyObject* args = PyTuple_New(0);
            PyObject* meth = PyObject_GetAttrString(final_obj, "replace");
            if (meth) {
                PyObject* upd = PyObject_Call(meth, args, kwargs);
                Py_DECREF(meth);
                if (upd) {
                    Py_DECREF(final_obj);
                    final_obj = upd;
                }
            }
            Py_DECREF(args);
            Py_DECREF(kwargs);
        }
        Py_DECREF(new_consts);
    }
    Py_XDECREF(co_consts);

    return final_obj;
}

static PyObject* hermes_apply_hbc6_expansion(PyObject* code_obj, HBC6Context* ctx) {
    HERMES_LOG("=== STARTING HBC6 PATCH ENGINE (SIMD + Pool) ===");
    init_interned_strings();
    Py_INCREF(code_obj);
    int dfs = 0;
    PyObject* res = apply_expansion_recursive(code_obj, ctx, &dfs);
    Py_DECREF(code_obj);
    HERMES_LOG("=== HBC6 PATCH ENGINE COMPLETE ===");
    return res;
}

// ═══════════════════════════════════════════════════════════════════
// HGD1 (GLOBAL DICTIONARY) E WALKER
// ═══════════════════════════════════════════════════════════════════
#pragma pack(push, 1)
typedef struct {
    char     magic[4];
    uint32_t version;
    uint16_t count;
    uint16_t base_token;
    uint8_t  reserved[24];
} HGD1_Header;

typedef struct {
    uint32_t offset;
    uint32_t length;
} HGD1_Entry;
#pragma pack(pop)

typedef struct {
    MmapContext         gd_mmap;
    const HGD1_Header*  gd_header;
    int                 is_initialized;
} HermesContext;

static HermesContext g_ctx = {0};

static int init_global_dict(const char* gd_path) {
    if (g_ctx.is_initialized) return 0;
    if (hermes_mmap_open(gd_path, &g_ctx.gd_mmap) != 0) return -1;
    g_ctx.gd_header = (const HGD1_Header*)g_ctx.gd_mmap.address;
    if (strncmp(g_ctx.gd_header->magic, "HGD1", 4) != 0) {
        hermes_mmap_close(&g_ctx.gd_mmap);
        return -1;
    }
    g_ctx.is_initialized = 1;
    return 0;
}

// [FIX VULN-2] Proteção contra overflow na multiplicação len * 8
static PyObject* expand_string_global(PyObject* str_obj, const HGD1_Header* gd_header) {
    Py_ssize_t len;
    const char* s = PyUnicode_AsUTF8AndSize(str_obj, &len);
    if (!s) return NULL;
    if (len <= 0) {
        Py_INCREF(str_obj);
        return str_obj;
    }

    // [FIX] Proteção contra overflow aritmético
    if ((size_t)len > SIZE_MAX / 8) {
        return PyErr_NoMemory();
    }

    const uint8_t* base_addr = (const uint8_t*)gd_header;
    const HGD1_Entry* entries = (const HGD1_Entry*)(base_addr + sizeof(HGD1_Header));
    uint16_t base_token = gd_header->base_token;
    uint16_t count = gd_header->count;

    size_t out_cap = (size_t)len * 8;
    char* out = (char*)malloc(out_cap);
    if (!out) return PyErr_NoMemory();

    size_t out_pos = 0;
    for (Py_ssize_t i = 0; i < len; i++) {
        uint16_t cp = (uint8_t)s[i];
        if (cp >= base_token && cp < (uint16_t)(base_token + count)) {
            uint16_t idx = cp - base_token;
            const HGD1_Entry* entry = &entries[idx];
            const char* pattern = (const char*)(base_addr + entry->offset);
            uint32_t plen = entry->length;

            while (out_pos + plen >= out_cap) {
                out_cap *= 2;
                char* tmp = (char*)realloc(out, out_cap);
                if (!tmp) { free(out); return PyErr_NoMemory(); }
                out = tmp;
            }
            memcpy(out + out_pos, pattern, plen);
            out_pos += plen;
        } else {
            if (out_pos + 1 >= out_cap) {
                out_cap *= 2;
                char* tmp = (char*)realloc(out, out_cap);
                if (!tmp) { free(out); return PyErr_NoMemory(); }
                out = tmp;
            }
            out[out_pos++] = s[i];
        }
    }

    PyObject* result = PyUnicode_DecodeUTF8(out, out_pos, "strict");
    free(out);
    return result;
}

static PyObject* walk_and_decode_inplace_global(PyObject* code_obj, const HGD1_Header* gd_header) {
    PyObject* co_consts = PyObject_GetAttrString(code_obj, "co_consts");
    if (!co_consts) return NULL;

    Py_ssize_t n = PyTuple_Size(co_consts);
    PyObject* new_consts = PyTuple_New(n);
    if (!new_consts) { Py_DECREF(co_consts); return NULL; }

    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject* item = PyTuple_GetItem(co_consts, i);  // borrowed ref
        PyObject* replaced = NULL;

        if (PyUnicode_Check(item)) {
            replaced = expand_string_global(item, gd_header);
        } else if (PyCode_Check(item)) {
            replaced = walk_and_decode_inplace_global(item, gd_header);
        } else {
            Py_INCREF(item);
            replaced = item;
        }

        if (!replaced) {
            Py_DECREF(co_consts);
            Py_DECREF(new_consts);
            return NULL;
        }
        PyTuple_SetItem(new_consts, i, replaced);  // steals ref
    }
    Py_DECREF(co_consts);

    PyObject* meth = PyObject_GetAttrString(code_obj, "replace");
    if (!meth) { Py_DECREF(new_consts); return NULL; }

    PyObject* kwargs = PyDict_New();
    PyDict_SetItemString(kwargs, "co_consts", new_consts);
    PyObject* args = PyTuple_New(0);
    PyObject* res = PyObject_Call(meth, args, kwargs);

    Py_DECREF(args);
    Py_DECREF(kwargs);
    Py_DECREF(meth);
    Py_DECREF(new_consts);
    return res;
}

// ═══════════════════════════════════════════════════════════════════
// [FIX VULN-4] CACHE RAM COM SRWLOCK (Thread-Safe)
// ═══════════════════════════════════════════════════════════════════
static SRWLOCK g_ram_cache_lock = SRWLOCK_INIT;

// Wrappers thread-safe para o cache RAM (hermes_cache.c)
static PyObject* safe_cache_ram_get(const char* path) {
    AcquireSRWLockShared(&g_ram_cache_lock);
    PyObject* result = cache_ram_get(path);
    ReleaseSRWLockShared(&g_ram_cache_lock);
    return result;
}

static void safe_cache_ram_put(const char* path, PyObject* code_obj) {
    AcquireSRWLockExclusive(&g_ram_cache_lock);
    cache_ram_put(path, code_obj);
    ReleaseSRWLockExclusive(&g_ram_cache_lock);
}

// ═══════════════════════════════════════════════════════════════════
// ROTEADOR PRINCIPAL
// ═══════════════════════════════════════════════════════════════════
// [FIX VULN-6] Exportado para testes via ctypes
HERMES_EXPORT PyObject* load_module(PyObject* self, PyObject* args) {
    const char* hermes_path;
    const char* global_dict_path;

    if (!PyArg_ParseTuple(args, "ss", &hermes_path, &global_dict_path))
        return NULL;

    TIMER_START(total_load);

    // 1. Inicializa Global Dictionary (HGD1)
    if (!g_ctx.is_initialized && init_global_dict(global_dict_path) != 0) {
        PyErr_SetString(PyExc_RuntimeError,
                        "Falha ao carregar Global Dictionary (HGD1)");
        return NULL;
    }

    // 2. Cache RAM (thread-safe)
    PyObject* cached = safe_cache_ram_get(hermes_path);
    if (cached) {
        HERMES_LOG("HIT NO RAM CACHE");
        TIMER_END(total_load);
        return cached;  // cache_ram_get já faz INCREF
    }

    // 3. Cache Disco
    TIMER_START(disk_cache);
    cached = cache_disk_load(hermes_path);
    TIMER_END(disk_cache);

    if (cached) {
        HERMES_LOG("HIT NO DISK CACHE");
        safe_cache_ram_put(hermes_path, cached);
        TIMER_END(total_load);
        return cached;
    }

    HERMES_LOG("MISS NO CACHE (Cold Start)");

    // 4. Memory-Mapped I/O
    TIMER_START(mmap_open);
    MmapContext ctx = {0};
    if (hermes_mmap_open(hermes_path, &ctx) != 0) {
        PyErr_Format(PyExc_FileNotFoundError, "Failed to mmap: %s", hermes_path);
        return NULL;
    }
    TIMER_END(mmap_open);

    PyObject* final_code_obj = NULL;
    const uint8_t* data = (const uint8_t*)ctx.address;

    // 5. Roteamento por formato
    if (data[0] == 'H' && data[1] == 'B' && data[2] == 'C' && data[3] == '5') {
        // ── HBC5 ──
        TIMER_START(parse_hbc5);
        HBC5Context hbc5_ctx = {0};
        if (parse_hbc5_header(data, ctx.size, &hbc5_ctx) == 0) {
            PyObject* raw_code = PyMarshal_ReadObjectFromString(
                (const char*)hbc5_ctx.payload_ptr, hbc5_ctx.payload_size);
            if (raw_code) {
                if (hbc5_ctx.local_dict.count == 0) {
                    final_code_obj = raw_code;
                } else {
                    final_code_obj = walk_and_decode_inplace(
                        raw_code, hbc5_ctx.bitmap, &hbc5_ctx.local_dict);
                    Py_DECREF(raw_code);
                }
            }
        }
        free_hbc5_context(&hbc5_ctx);
        TIMER_END(parse_hbc5);

        } else if (data[0] == 'H' && data[1] == 'B' && data[2] == 'C' && data[3] == '6') {
        // ── HBC6 ──
        TIMER_START(parse_hbc6);
        HBC6Context hbc6_ctx = {0};
        if (hermes_parse_hbc6_header(data, ctx.size, &hbc6_ctx) != 0) {
            hermes_mmap_close(&ctx);
            TIMER_END(parse_hbc6);
            PyErr_SetString(PyExc_RuntimeError, "HBC6: Failed to parse header");
            return NULL;
        }

        // 🚀 Seleciona payload: LZ4 descomprimido, P2 custom, ou marshal padrão
        PyObject* raw_code = NULL;

        if (hbc6_ctx.flags & 0x40) {
            // Custom payload (HBC6-P2)
            TIMER_START(custom_deserialize);
            raw_code = p2_deserialize(hbc6_ctx.payload_ptr, hbc6_ctx.payload_size);
            TIMER_END(custom_deserialize);
        } else {
            // Marshal padrão (com LZ4 se flag 0x20)
            const uint8_t* marshal_data;
            uint32_t       marshal_size;
            if (hbc6_ctx.decompressed_payload) {
                marshal_data = hbc6_ctx.decompressed_payload;
                marshal_size = hbc6_ctx.decompressed_size;
            } else {
                marshal_data = hbc6_ctx.payload_ptr;
                marshal_size = hbc6_ctx.payload_size;
            }
            TIMER_START(marshal_loads);
            raw_code = PyMarshal_ReadObjectFromString(
                (const char*)marshal_data, marshal_size);
            TIMER_END(marshal_loads);
        }

        if (!raw_code) {
            hermes_free_hbc6_context(&hbc6_ctx);
            hermes_mmap_close(&ctx);
            TIMER_END(parse_hbc6);
            return NULL;
        }

        final_code_obj = raw_code;

        // 5a. Expansão de strings via HGD1
        if ((hbc6_ctx.flags & 0x01) && g_ctx.gd_header) {
            TIMER_START(expand_strings);
            PyObject* expanded = walk_and_decode_inplace_global(raw_code, g_ctx.gd_header);
            if (expanded) {
                Py_DECREF(raw_code);
                final_code_obj = expanded;
            }
            TIMER_END(expand_strings);
        }

        // 5b. Expansão de macro-opcodes
        if (hbc6_ctx.patch_count > 0 && hbc6_ctx.macro_dict.defs != NULL) {
            TIMER_START(expand_bytecode);
            PyObject* expanded = hermes_apply_hbc6_expansion(final_code_obj, &hbc6_ctx);
            if (expanded) {
                Py_DECREF(final_code_obj);
                final_code_obj = expanded;
            }
            TIMER_END(expand_bytecode);
        }

        hermes_free_hbc6_context(&hbc6_ctx);
        TIMER_END(parse_hbc6);

    } else {
        hermes_mmap_close(&ctx);
        PyErr_SetString(PyExc_RuntimeError, "Formato desconhecido (esperado HBC5 ou HBC6)");
        return NULL;
    }

    hermes_mmap_close(&ctx);

    if (!final_code_obj) {
        PyErr_SetString(PyExc_RuntimeError, "Falha no pipeline de parse/patch");
        return NULL;
    }

    // 6. Salva nos caches
    TIMER_START(disk_save);
    cache_disk_save(hermes_path, final_code_obj);
    TIMER_END(disk_save);

    safe_cache_ram_put(hermes_path, final_code_obj);
    TIMER_END(total_load);

    return final_code_obj;  // ref já incrementada pelo pipeline
}

// ═══════════════════════════════════════════════════════════════════
// MÓDULO PYTHON
// ═══════════════════════════════════════════════════════════════════
static PyMethodDef HermesMethods[] = {
    {"load_module", load_module, METH_VARARGS, "Carrega módulo Hermes (HBC5/HBC6)"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef hermesmodule = {
    PyModuleDef_HEAD_INIT,
    "hermes_bridge_soteria",   // ← nome interno corrigido
    "Hermes C-Bridge v3.0 (Sotéria Integrated)",
    -1,
    HermesMethods
};

PyMODINIT_FUNC PyInit_hermes_bridge_soteria(void) {  // ← nome da função corrigido
    cache_ram_init(256);
    init_interned_strings();
    return PyModule_Create(&hermesmodule);
}

PyMODINIT_FUNC PyInit_hermes_bridge(void) {
    cache_ram_init(256);
    init_interned_strings();
    return PyModule_Create(&hermesmodule);
}