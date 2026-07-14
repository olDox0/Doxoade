// doxoade/tools/hermes_systems/native/hermes_py_utils.c
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <marshal.h>
#include <windows.h>
#include <emmintrin.h>  // SSE2
#include "hermes_cache.h"
#include "hermes_mmap.h"

// ═══════════════════════════════════════════════════════════════════
// MACROS E TELEMETRIA
// ═══════════════════════════════════════════════════════════════════
#define READ_U16(p) ((uint16_t)((p)[0] | ((p)[1] << 8)))
#define READ_U32(p) ((uint32_t)((p)[0] | ((p)[1] << 8) | ((p)[2] << 16) | ((p)[3] << 24)))
#define MACRO_OPCODE 0xC0

static int g_verbose = -1;
#define HERMES_LOG(fmt, ...) do { \
    if (g_verbose == -1) g_verbose = (getenv("HERMES_VERBOSE") != NULL); \
    if (g_verbose) fprintf(stderr, "[HERMES-C] " fmt "\n", ##__VA_ARGS__); \
} while(0)

static double get_time_ms() {
    LARGE_INTEGER freq, count;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&count);
    return (double)count.QuadPart / (double)freq.QuadPart * 1000.0;
}

#define TIMER_START(name) double timer_##name = get_time_ms();
#define TIMER_END(name) do { \
    if (g_verbose == -1) g_verbose = (getenv("HERMES_VERBOSE") != NULL); \
    if (g_verbose) fprintf(stderr, "[HERMES-C] %-30s %8.3f ms\n", #name, get_time_ms() - timer_##name); \
} while(0)

// ═══════════════════════════════════════════════════════════════════
// ESTRUTURAS HBC5 (Externas)
// ═══════════════════════════════════════════════════════════════════
typedef struct { char* buffer; char** pointers; uint16_t* lengths; uint16_t count; } HermesDict;
typedef struct { uint8_t flags; uint8_t bitmap[32]; HermesDict local_dict; const uint8_t* payload_ptr; uint32_t payload_size; size_t header_size; } HBC5Context;
extern int parse_hbc5_header(const uint8_t* data, size_t data_size, HBC5Context* ctx);
extern void free_hbc5_context(HBC5Context* ctx);
extern PyObject* walk_and_decode_inplace(PyObject* code_obj, const uint8_t* bitmap, const HermesDict* l_dict);

// ═══════════════════════════════════════════════════════════════════
// ESTRUTURAS HBC6 (Unificadas)
// ═══════════════════════════════════════════════════════════════════
#pragma pack(push, 1)
typedef struct { uint32_t co_index; uint32_t offset; uint16_t token_id; uint16_t orig_ngram_len; } HBC6_Patch;
#pragma pack(pop)
typedef struct { const uint8_t* opcodes; uint16_t len; } HBC6_MacroDef;
typedef struct { HBC6_MacroDef* defs; uint16_t count; } HBC6_MacroDict;
typedef struct { uint8_t flags; HBC6_Patch* patches; uint32_t patch_count; HBC6_MacroDict macro_dict; const uint8_t* payload_ptr; uint32_t payload_size; } HBC6Context;

// ═══════════════════════════════════════════════════════════════════
// STRINGS INTERNADAS (Cache de strings Python)
// ═══════════════════════════════════════════════════════════════════
static PyObject* g_str_co_code = NULL;
static PyObject* g_str_co_consts = NULL;
static PyObject* g_str_replace = NULL;

static void init_interned_strings(void) {
    if (!g_str_co_code) {
        g_str_co_code = PyUnicode_InternFromString("co_code");
        g_str_co_consts = PyUnicode_InternFromString("co_consts");
        g_str_replace = PyUnicode_InternFromString("replace");
    }
}

// ═══════════════════════════════════════════════════════════════════
// 🚀 HBC6: BUFFER POOL + SIMD SCANNER
// ═══════════════════════════════════════════════════════════════════
#define BUFFER_POOL_SIZE (4 * 1024 * 1024)
static uint8_t* g_buffer_pool = NULL;
static size_t g_pool_used = 0;

static uint8_t* get_buffer(size_t needed) {
    if (!g_buffer_pool) g_buffer_pool = (uint8_t*)malloc(BUFFER_POOL_SIZE);
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
// 🚀 HBC6: PARSER E EXPANSÃO
// ═══════════════════════════════════════════════════════════════════
static int hermes_parse_hbc6_header(const uint8_t* data, size_t data_size, HBC6Context* ctx) {
    if (!data || data_size < 9 || !ctx) return -1;
    if (memcmp(data, "HBC6", 4) != 0 || data[4] != 0x06) return -1;
    
    size_t offset = 6; 
    ctx->flags = data[5];
    
    if (offset + 4 > data_size) return -1;
    uint32_t hrt_size = READ_U32(&data[offset]); offset += 4;
    if (hrt_size % 12 != 0 || offset + hrt_size > data_size) return -1;
    
    ctx->patch_count = hrt_size / 12;
    ctx->patches = (HBC6_Patch*)&data[offset]; offset += hrt_size;
    
    if (offset + 4 > data_size) return -1;
    uint32_t macro_dict_size = READ_U32(&data[offset]); offset += 4;
    
    ctx->macro_dict.count = 0; ctx->macro_dict.defs = NULL;
    if (macro_dict_size >= 2 && offset + macro_dict_size <= data_size) {
        uint16_t dict_count = READ_U16(&data[offset]); offset += 2;
        ctx->macro_dict.count = dict_count;
        ctx->macro_dict.defs = (HBC6_MacroDef*)calloc(dict_count, sizeof(HBC6_MacroDef));
        if (!ctx->macro_dict.defs) return -1;
        
        for (uint16_t i = 0; i < dict_count; i++) {
            if (offset + 4 > data_size) { free(ctx->macro_dict.defs); return -1; }
            uint16_t tid = READ_U16(&data[offset]); offset += 2;
            uint16_t len = READ_U16(&data[offset]); offset += 2;
            if (offset + len > data_size) { free(ctx->macro_dict.defs); return -1; }
            
            if (tid < dict_count) { 
                ctx->macro_dict.defs[tid].opcodes = &data[offset]; 
                ctx->macro_dict.defs[tid].len = len; 
            }
            offset += len;
        }
    }
    
    if (offset + 4 > data_size) { 
        if(ctx->macro_dict.defs) free(ctx->macro_dict.defs); 
        return -1; 
    }
    ctx->payload_size = READ_U32(&data[offset]); offset += 4;
    if (offset + ctx->payload_size > data_size) { 
        if(ctx->macro_dict.defs) free(ctx->macro_dict.defs); 
        return -1; 
    }
    ctx->payload_ptr = &data[offset];
    return 0;
}

static void hermes_free_hbc6_context(HBC6Context* ctx) {
    if (ctx && ctx->macro_dict.defs) { 
        free(ctx->macro_dict.defs); 
        ctx->macro_dict.defs = NULL; 
    }
}

static PyObject* expand_bytecode_inplace(PyObject* co_code_bytes, HBC6Context* ctx) {
    Py_ssize_t orig_len = PyBytes_Size(co_code_bytes);
    const uint8_t* src = (const uint8_t*)PyBytes_AsString(co_code_bytes);
    
    if (!has_macro_opcodes_simd(src, orig_len)) { 
        Py_INCREF(co_code_bytes); 
        return co_code_bytes; 
    }
    
    size_t max_len = orig_len * 2;
    uint8_t* dst = get_buffer(max_len);
    int is_pool = (dst == g_buffer_pool);
    size_t i = 0, j = 0;
    
    while (i < orig_len) {
        if (src[i] == MACRO_OPCODE && (i + 1) < orig_len) {
            uint8_t token_idx = src[i+1];
            if (token_idx < ctx->macro_dict.count && ctx->macro_dict.defs[token_idx].opcodes) {
                const HBC6_MacroDef* def = &ctx->macro_dict.defs[token_idx];
                if (j + def->len > max_len) {
                    max_len *= 2; 
                    uint8_t* new_dst = (uint8_t*)malloc(max_len);
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
        if (ctx->patches[i].co_index == my_idx) { 
            has_patches = 1; 
            break; 
        }
    }
    
    if (has_patches) {
        PyObject* co_code = PyObject_GetAttr(code_obj, g_str_co_code); // <-- PONTO E VÍRGULA CORRIGIDO
        if (co_code && PyBytes_Check(co_code)) {
            PyObject* expanded = expand_bytecode_inplace(co_code, ctx);
            if (expanded && expanded != co_code) {
                PyObject* kwargs = PyDict_New(); 
                PyDict_SetItemString(kwargs, "co_code", expanded);
                PyObject* args = PyTuple_New(0); 
                PyObject* meth = PyObject_GetAttrString(code_obj, "replace");
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
        Py_XDECREF(co_code);
    }
    
    PyObject* co_consts = PyObject_GetAttrString(final_obj, "co_consts");
    if (co_consts && PyTuple_Check(co_consts)) {
        Py_ssize_t n = PyTuple_Size(co_consts); 
        PyObject* new_consts = PyTuple_New(n); 
        int changed = 0;
        
        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject* item = PyTuple_GetItem(co_consts, i);
            if (PyCode_Check(item)) {
                PyObject* child = apply_expansion_recursive(item, ctx, dfs_idx);
                if (child != item) changed = 1; 
                PyTuple_SetItem(new_consts, i, child);
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
            PyObject* upd = PyObject_Call(meth, args, kwargs);
            Py_DECREF(meth); Py_DECREF(args); Py_DECREF(kwargs);
            if (upd) { 
                Py_DECREF(final_obj); 
                final_obj = upd; 
            }
        }
        Py_DECREF(new_consts);
    }
    Py_XDECREF(co_consts);
    return final_obj;
}

static PyObject* hermes_apply_hbc6_expansion(PyObject* code_obj, HBC6Context* ctx) {
    HERMES_LOG("=== STARTING HBC6 PATCH ENGINE (SIMD + Pool) ===");
    Py_INCREF(code_obj); 
    int dfs = 0;
    PyObject* res = apply_expansion_recursive(code_obj, ctx, &dfs);
    Py_DECREF(code_obj);
    HERMES_LOG("=== HBC6 PATCH ENGINE COMPLETE ===");
    return res;
}

// ═══════════════════════════════════════════════════════════════════
// HGD1 (GLOBAL DICT) E WALKER
// ═══════════════════════════════════════════════════════════════════
#pragma pack(push, 1)
typedef struct { char magic[4]; uint32_t version; uint16_t count; uint16_t base_token; uint8_t reserved[24]; } HGD1_Header;
typedef struct { uint32_t offset; uint32_t length; } HGD1_Entry;
#pragma pack(pop)

typedef struct { MmapContext gd_mmap; const HGD1_Header* gd_header; int is_initialized; } HermesContext;
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

static PyObject* expand_string_global(PyObject* str_obj, const HGD1_Header* gd_header) {
    Py_ssize_t len; 
    const char* s = PyUnicode_AsUTF8AndSize(str_obj, &len); 
    if (!s) return NULL;
    
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
        if (cp >= base_token && cp < (base_token + count)) {
            uint16_t idx = cp - base_token; 
            const HGD1_Entry* entry = &entries[idx];
            const char* pattern = (const char*)(base_addr + entry->offset); 
            uint32_t plen = entry->length;
            
            while (out_pos + plen >= out_cap) { 
                out_cap *= 2; 
                out = (char*)realloc(out, out_cap); 
                if (!out) return PyErr_NoMemory(); 
            }
            memcpy(out + out_pos, pattern, plen); 
            out_pos += plen;
        } else {
            if (out_pos + 1 >= out_cap) { 
                out_cap *= 2; 
                out = (char*)realloc(out, out_cap); 
                if (!out) return PyErr_NoMemory(); 
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
        PyObject* item = PyTuple_GetItem(co_consts, i); 
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
        PyTuple_SetItem(new_consts, i, replaced);
    }
    Py_DECREF(co_consts);
    
    PyObject* meth = PyObject_GetAttrString(code_obj, "replace"); 
    if (!meth) { Py_DECREF(new_consts); return NULL; }
    
    PyObject* kwargs = PyDict_New(); 
    PyDict_SetItemString(kwargs, "co_consts", new_consts);
    PyObject* args = PyTuple_New(0); 
    PyObject* res = PyObject_Call(meth, args, kwargs);
    
    Py_DECREF(args); Py_DECREF(kwargs); Py_DECREF(meth); Py_DECREF(new_consts); 
    return res;
}

// ═══════════════════════════════════════════════════════════════════
// ROTEADOR PRINCIPAL
// ═══════════════════════════════════════════════════════════════════
static PyObject* load_module(PyObject* self, PyObject* args) {
    const char* hermes_path; 
    const char* global_dict_path;
    if (!PyArg_ParseTuple(args, "ss", &hermes_path, &global_dict_path)) return NULL;
    
    TIMER_START(total_load);
    
    if (!g_ctx.is_initialized && init_global_dict(global_dict_path) != 0) {
        PyErr_SetString(PyExc_RuntimeError, "Falha ao carregar Global Dictionary (HGD1)"); 
        return NULL;
    }
    
    PyObject* cached = cache_ram_get(hermes_path);
    if (cached) { 
        HERMES_LOG("HIT NO RAM CACHE"); 
        Py_INCREF(cached); 
        TIMER_END(total_load); 
        return cached; 
    }
    
    TIMER_START(disk_cache); 
    cached = cache_disk_load(hermes_path); 
    TIMER_END(disk_cache);
    
    if (cached) { 
        HERMES_LOG("HIT NO DISK CACHE"); 
        cache_ram_put(hermes_path, cached); 
        TIMER_END(total_load); 
        return cached; 
    }
    
    HERMES_LOG("MISS NO CACHE (Cold Start)");
    TIMER_START(mmap_open); 
    MmapContext ctx = {0};
    if (hermes_mmap_open(hermes_path, &ctx) != 0) { 
        PyErr_Format(PyExc_FileNotFoundError, "Failed to mmap: %s", hermes_path); 
        return NULL; 
    }
    TIMER_END(mmap_open);
    
    PyObject* final_code_obj = NULL; 
    const uint8_t* data = (const uint8_t*)ctx.address;
    
    if (data[0] == 'H' && data[1] == 'B' && data[2] == 'C' && data[3] == '5') {
        TIMER_START(parse_hbc5); 
        HBC5Context hbc5_ctx = {0};
        if (parse_hbc5_header(data, ctx.size, &hbc5_ctx) == 0) {
            PyObject* raw_code = PyMarshal_ReadObjectFromString((const char*)hbc5_ctx.payload_ptr, hbc5_ctx.payload_size);
            if (raw_code) {
                if (hbc5_ctx.local_dict.count == 0) {
                    final_code_obj = raw_code;
                } else { 
                    final_code_obj = walk_and_decode_inplace(raw_code, hbc5_ctx.bitmap, &hbc5_ctx.local_dict); 
                    Py_DECREF(raw_code); 
                }
            }
        }
        free_hbc5_context(&hbc5_ctx); 
        TIMER_END(parse_hbc5);
    } else if (data[0] == 'H' && data[1] == 'B' && data[2] == 'C' && data[3] == '6') {
        TIMER_START(parse_hbc6); 
        HBC6Context hbc6_ctx = {0};
        if (hermes_parse_hbc6_header(data, ctx.size, &hbc6_ctx) != 0) {
            hermes_mmap_close(&ctx); 
            TIMER_END(parse_hbc6);
            PyErr_SetString(PyExc_RuntimeError, "HBC6: Failed to parse header"); 
            return NULL;
        }
        
        PyObject* raw_code = PyMarshal_ReadObjectFromString((const char*)hbc6_ctx.payload_ptr, hbc6_ctx.payload_size);
        if (!raw_code) { 
            hermes_free_hbc6_context(&hbc6_ctx); 
            hermes_mmap_close(&ctx); 
            TIMER_END(parse_hbc6); 
            return NULL; 
        }
        
        final_code_obj = raw_code;
        
        if ((hbc6_ctx.flags & 0x01) && g_ctx.gd_header) {
            TIMER_START(expand_strings); 
            PyObject* expanded = walk_and_decode_inplace_global(raw_code, g_ctx.gd_header);
            if (expanded) { 
                Py_DECREF(raw_code); 
                final_code_obj = expanded; 
            } 
            TIMER_END(expand_strings);
        }
        
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
        PyErr_SetString(PyExc_RuntimeError, "Formato desconhecido"); 
        return NULL;
    }
    
    hermes_mmap_close(&ctx);
    
    if (!final_code_obj) { 
        PyErr_SetString(PyExc_RuntimeError, "Falha no pipeline de parse/patch"); 
        return NULL; 
    }
    
    TIMER_START(disk_save); 
    cache_disk_save(hermes_path, final_code_obj); 
    TIMER_END(disk_save);
    
    cache_ram_put(hermes_path, final_code_obj); 
    TIMER_END(total_load);
    
    Py_INCREF(final_code_obj); 
    return final_code_obj;
}

static PyMethodDef HermesMethods[] = { 
    {"load_module", load_module, METH_VARARGS, "Carrega módulo Hermes"}, 
    {NULL, NULL, 0, NULL} 
};

static struct PyModuleDef hermesmodule = { 
    PyModuleDef_HEAD_INIT, 
    "hermes_bridge", 
    "Hermes C-Bridge v2.2 (Unified)", 
    -1, 
    HermesMethods 
};

PyMODINIT_FUNC PyInit_hermes_bridge(void) { 
    cache_ram_init(256); 
    return PyModule_Create(&hermesmodule); 
}