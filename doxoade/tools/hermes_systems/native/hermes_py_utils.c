// doxoade/tools/hermes_systems/native/hermes_py_utils.c
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <marshal.h>
#include <windows.h>

#include "hermes_cache.h"
#include "hermes_mmap.h"
#include "hermes_hbc6_patches.h" // 🚀 Puxa as structs HBC6 e o protótipo correto

// ═══════════════════════════════════════════════════════════════════
// PROTÓTIPOS EXTERNOS (Apenas do HBC5)
// ═══════════════════════════════════════════════════════════════════
typedef struct {
    char* buffer;
    char** pointers;
    uint16_t* lengths;
    uint16_t count;
} HermesDict;

typedef struct {
    uint8_t flags;
    uint8_t bitmap[32];
    HermesDict local_dict;
    const uint8_t* payload_ptr;
    uint32_t payload_size;
    size_t header_size;
} HBC5Context;

extern int parse_hbc5_header(const uint8_t* data, size_t data_size, HBC5Context* ctx);
extern void free_hbc5_context(HBC5Context* ctx);
extern PyObject* walk_and_decode_inplace(PyObject* code_obj, const uint8_t* bitmap, const HermesDict* l_dict);

// ═══════════════════════════════════════════════════════════════════
// TELEMETRIA DE PRECISÃO (Windows Hardware Timer)
// ═══════════════════════════════════════════════════════════════════
static double _get_time_ms() {
    LARGE_INTEGER freq, count;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&count);
    return (double)count.QuadPart / (double)freq.QuadPart * 1000.0;
}
#define TIMER_START(name) double timer_##name = _get_time_ms();
#define TIMER_END(name) fprintf(stderr, "[HERMES-C] %-30s %8.3f ms\n", #name, _get_time_ms() - timer_##name);

// ═══════════════════════════════════════════════════════════════════
// GLOBAL DICTIONARY (HGD1) - Singleton
// ═══════════════════════════════════════════════════════════════════
#pragma pack(push, 1)
typedef struct {
    char magic[4];
    uint32_t version;
    uint16_t count;
    uint16_t base_token;
    uint8_t reserved[24];
} HGD1_Header;
#pragma pack(pop)

typedef struct {
    MmapContext gd_mmap;
    const HGD1_Header* gd_header;
    int is_initialized;
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

// ═══════════════════════════════════════════════════════════════════
// O ROTEADOR PRINCIPAL (A API Python)
// ═══════════════════════════════════════════════════════════════════
static PyObject* load_module(PyObject* self, PyObject* args) {
    const char* hermes_path;
    const char* global_dict_path;

    if (!PyArg_ParseTuple(args, "ss", &hermes_path, &global_dict_path)) {
        return NULL;
    }

    TIMER_START(total_load);

    if (!g_ctx.is_initialized) {
        if (init_global_dict(global_dict_path) != 0) {
            PyErr_SetString(PyExc_RuntimeError, "Falha ao carregar Global Dictionary (HGD1)");
            return NULL;
        }
    }

    // TIER 1: RAM CACHE
    PyObject* cached = cache_ram_get(hermes_path);
    if (cached) {
        fprintf(stderr, "[HERMES-C] \xe2\x9c\x94 HIT NO CACHE (Warm Start)\n");
        Py_INCREF(cached);
        TIMER_END(total_load);
        return cached;
    }

    // TIER 2: DISK MARSHAL CACHE
    TIMER_START(disk_cache);
    cached = cache_disk_load(hermes_path);
    TIMER_END(disk_cache);

    if (cached) {
        fprintf(stderr, "[HERMES-C] \xe2\x9c\x94 HIT NO DISK CACHE (Disk Hit)\n");
        cache_ram_put(hermes_path, cached);
        TIMER_END(total_load);
        return cached;
    }

    fprintf(stderr, "[HERMES-C] \xe2\x9c\x98 MISS NO CACHE (Cold Start)\n");

    // COLD PATH: PARSE & PATCH
    TIMER_START(mmap_open);
    MmapContext ctx = {0};
    if (hermes_mmap_open(hermes_path, &ctx) != 0) {
        PyErr_Format(PyExc_FileNotFoundError, "Failed to mmap: %s", hermes_path);
        return NULL;
    }
    TIMER_END(mmap_open);

    PyObject* final_code_obj = NULL;
    const uint8_t* data = (const uint8_t*)ctx.address;

    // Roteamento de Formato
    if (data[0] == 'H' && data[1] == 'B' && data[2] == 'C' && data[3] == '5') {
        TIMER_START(parse_hbc5);
        HBC5Context hbc5_ctx = {0};
        if (parse_hbc5_header(data, ctx.size, &hbc5_ctx) == 0) {
            PyObject* raw_code = PyMarshal_ReadObjectFromString(
                (const char*)hbc5_ctx.payload_ptr, hbc5_ctx.payload_size
            );
            if (raw_code) {
                final_code_obj = walk_and_decode_inplace(raw_code, hbc5_ctx.bitmap, &hbc5_ctx.local_dict);
                Py_DECREF(raw_code);
            }
        }
        free_hbc5_context(&hbc5_ctx);
        TIMER_END(parse_hbc5);
    } 
    else if (data[0] == 'H' && data[1] == 'B' && data[2] == 'C' && data[3] == '6') {
        fprintf(stderr, "[HERMES-C] \xf0\x9f\xa7\xac Formato HBC6 detectado (Patch-in-RAM)\n");
        TIMER_START(parse_hbc6);
        
        HBC6Context hbc6_ctx = {0};
        if (hermes_parse_hbc6_header(data, ctx.size, &hbc6_ctx) != 0) {
            hermes_mmap_close(&ctx);
            PyErr_SetString(PyExc_RuntimeError, "Falha ao parsear header HBC6");
            return NULL;
        }

        // 1. Marshal do Payload Intacto (Zero-Copy via Python C-API)
        PyObject* raw_code = PyMarshal_ReadObjectFromString(
            (const char*)hbc6_ctx.payload_ptr, hbc6_ctx.payload_size
        );

        // 2. Aplicar Patches (DFS Walker)
        // 🛡️ O hermes_apply_hbc6_patches agora gerencia as referências internamente
        if (raw_code) {
            final_code_obj = hermes_apply_hbc6_patches(raw_code, hbc6_ctx.patches, hbc6_ctx.patch_count);
            Py_DECREF(raw_code); // Agora é seguro liberar, pois o patcher já terminou
        }
        
        hermes_free_hbc6_context(&hbc6_ctx);
        TIMER_END(parse_hbc6);
    } else {
        hermes_mmap_close(&ctx);
        PyErr_SetString(PyExc_ValueError, "Formato Hermes desconhecido");
        return NULL;
    }

    hermes_mmap_close(&ctx);

    if (!final_code_obj) {
        PyErr_SetString(PyExc_RuntimeError, "Falha no pipeline de parse/patch");
        return NULL;
    }

    // SALVA NOS CACHES
    TIMER_START(disk_save);
    cache_disk_save(hermes_path, final_code_obj);
    TIMER_END(disk_save);

    cache_ram_put(hermes_path, final_code_obj);
    TIMER_END(total_load);
    
    Py_INCREF(final_code_obj);
    return final_code_obj;
}

// ═══════════════════════════════════════════════════════════════════
// REGISTRO DO MÓDULO PYTHON
// ═══════════════════════════════════════════════════════════════════
static PyMethodDef HermesMethods[] = {
    {"load_module", load_module, METH_VARARGS, "Carrega módulo Hermes com Cache L1/L2"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef hermesmodule = {
    PyModuleDef_HEAD_INIT, "hermes_bridge", "Hermes C-Bridge v2.1 (Tier 2 Disk Cache)", -1, HermesMethods
};

PyMODINIT_FUNC PyInit_hermes_bridge(void) {
    cache_ram_init(256);
    return PyModule_Create(&hermesmodule);
}