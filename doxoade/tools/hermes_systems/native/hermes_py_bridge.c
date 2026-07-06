// doxoade/tools/hermes_systems/native/hermes_py_bridge.c
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <windows.h>

// ═══════════════════════════════════════════════════════════════════════════════
// TELEMETRIA DE PRECISÃO (Windows Hardware Timer)
// ═══════════════════════════════════════════════════════════════════════════════
static double _get_time_ms() {
    LARGE_INTEGER freq, count;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&count);
    return (double)count.QuadPart / (double)freq.QuadPart * 1000.0;
}

#define TIMER_START(name) double timer_##name = _get_time_ms();
#define TIMER_END(name) fprintf(stderr, "[HERMES-C] %-30s %8.3f ms\n", #name, _get_time_ms() - timer_##name);

// ═══════════════════════════════════════════════════════════════════════════════
// ESTRUTURAS DO PARSER HBC5
// ═══════════════════════════════════════════════════════════════════════════════
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

// Protótipos do Parser (Implementados em hermes_hbc5_parser.c)
int parse_hbc5_header(const uint8_t* data, size_t data_size, HBC5Context* ctx);
void free_hbc5_context(HBC5Context* ctx);

// ═══════════════════════════════════════════════════════════════════════════════
// MOTOR MMAP (Zero-Copy via Windows API)
// ═══════════════════════════════════════════════════════════════════════════════
typedef struct {
    void* address;
    HANDLE file_handle;
    HANDLE mapping_handle;
    size_t size;
} MmapContext;

static int hermes_mmap_open(const char* path, MmapContext* ctx) {
    ctx->file_handle = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (ctx->file_handle == INVALID_HANDLE_VALUE) return -1;
    
    ctx->size = GetFileSize(ctx->file_handle, NULL);
    if (ctx->size == 0) { CloseHandle(ctx->file_handle); return -1; }
    
    ctx->mapping_handle = CreateFileMappingA(ctx->file_handle, NULL, PAGE_READONLY, 0, 0, NULL);
    if (!ctx->mapping_handle) { CloseHandle(ctx->file_handle); return -1; }
    
    ctx->address = MapViewOfFile(ctx->mapping_handle, FILE_MAP_READ, 0, 0, 0);
    if (!ctx->address) {
        CloseHandle(ctx->mapping_handle);
        CloseHandle(ctx->file_handle);
        return -1;
    }
    return 0;
}

static void hermes_mmap_close(MmapContext* ctx) {
    if (ctx->address) UnmapViewOfFile(ctx->address);
    if (ctx->mapping_handle) CloseHandle(ctx->mapping_handle);
    if (ctx->file_handle) CloseHandle(ctx->file_handle);
    ctx->address = NULL;
}

// ═══════════════════════════════════════════════════════════════════════════════
// ESTRUTURAS DO GLOBAL DICTIONARY (HGD1)
// ═══════════════════════════════════════════════════════════════════════════════
#pragma pack(push, 1)
typedef struct {
    char magic[4];
    uint32_t version;
    uint16_t count;
    uint16_t base_token;
    uint8_t reserved[24];
} HGD1_Header;

typedef struct {
    uint32_t offset;
    uint32_t length;
} HGD1_Entry;
#pragma pack(pop)

// ═══════════════════════════════════════════════════════════════════════════════
// CONTEXTO GLOBAL (Singleton)
// ═══════════════════════════════════════════════════════════════════════════════
typedef struct {
    MmapContext gd_mmap;
    const HGD1_Header* gd_header;
    int is_initialized;
} HermesContext;

static HermesContext g_ctx = {0};
static PyObject* g_marshal_mod = NULL;

static int init_global_dict(const char* gd_path) {
    if (hermes_mmap_open(gd_path, &g_ctx.gd_mmap) != 0) return -1;
    g_ctx.gd_header = (const HGD1_Header*)g_ctx.gd_mmap.address;
    if (memcmp(g_ctx.gd_header->magic, "HGD1", 4) != 0) {
        hermes_mmap_close(&g_ctx.gd_mmap);
        return -1;
    }
    g_ctx.is_initialized = 1;
    return 0;
}

// ═══════════════════════════════════════════════════════════════════════════════
// MOTOR BRANCHLESS (Expansão de Strings - Local Dict)
// ═══════════════════════════════════════════════════════════════════════════════
static inline void get_pattern_data(uint16_t token, const HermesDict* l_dict, 
                                    char** out_ptr, int* out_len) {
    uint16_t index = token - 0x80; 
    *out_ptr = l_dict->pointers[index];
    *out_len = l_dict->lengths[index];
}

static size_t calculate_expanded_size(const char* src, size_t src_len, 
                                      const uint8_t* bitmap, const HermesDict* l_dict) {
    size_t final_size = 0;
    for (size_t i = 0; i < src_len; i++) {
        uint8_t c = (uint8_t)src[i];
        int has_tok = (bitmap[c >> 3] >> (c & 7)) & 1;
        if (has_tok && c >= 0x80) {
            char* p; int l;
            get_pattern_data(c, l_dict, &p, &l);
            final_size += l;
        } else {
            final_size += 1;
        }
    }
    return final_size;
}

static void expand_string(const char* src, size_t src_len, char* dst, 
                          const uint8_t* bitmap, const HermesDict* l_dict) {
    char* out = dst;
    for (size_t i = 0; i < src_len; i++) {
        uint8_t c = (uint8_t)src[i];
        int has_tok = (bitmap[c >> 3] >> (c & 7)) & 1;
        if (has_tok && c >= 0x80) {
            char* p; int l;
            get_pattern_data(c, l_dict, &p, &l);
            memcpy(out, p, l);
            out += l;
        } else {
            *out++ = c;
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// WALKER IN-PLACE (Zero Cloning)
// ═══════════════════════════════════════════════════════════════════════════════
static int walk_and_decode_inplace(PyObject* code_obj, const uint8_t* bitmap, const HermesDict* l_dict) {
    if (!PyCode_Check(code_obj)) return 0;

    PyObject* co_consts = PyObject_GetAttrString(code_obj, "co_consts");
    if (!co_consts || !PyTuple_Check(co_consts)) {
        Py_XDECREF(co_consts);
        return -1;
    }

    Py_ssize_t n = PyTuple_Size(co_consts);
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject* item = PyTuple_GetItem(co_consts, i);
        
        if (PyUnicode_Check(item)) {
            Py_ssize_t len;
            const char* s = PyUnicode_AsUTF8AndSize(item, &len);
            if (!s) { Py_DECREF(co_consts); return -1; }

            int needs_decode = 0;
            for (Py_ssize_t k = 0; k < len; k++) {
                uint8_t c = (uint8_t)s[k];
                if (c >= 0x80 && (bitmap[c >> 3] >> (c & 7)) & 1) {
                    needs_decode = 1;
                    break;
                }
            }

            if (needs_decode) {
                size_t final_size = calculate_expanded_size(s, len, bitmap, l_dict);
                char* buffer = (char*)malloc(final_size + 1);
                if (!buffer) { Py_DECREF(co_consts); return -1; }
                
                expand_string(s, len, buffer, bitmap, l_dict);
                buffer[final_size] = '\0';
                
                PyObject* new_str = PyUnicode_DecodeUTF8(buffer, final_size, "strict");
                free(buffer);
                if (!new_str) { Py_DECREF(co_consts); return -1; }
                
                Py_DECREF(item);
                PyTuple_SetItem(co_consts, i, new_str);
            }
        } 
        else if (PyCode_Check(item)) {
            if (walk_and_decode_inplace(item, bitmap, l_dict) != 0) {
                Py_DECREF(co_consts);
                return -1;
            }
        }
    }
    Py_DECREF(co_consts);
    return 0;
}

// ═══════════════════════════════════════════════════════════════════════════════
// CACHE RAW (Otimizado com mmap + Telemetria)
// ═══════════════════════════════════════════════════════════════════════════════
static PyObject* try_load_from_cache(const char* hermes_path) {
    TIMER_START(cache_check)
    char cache_path[512];
    snprintf(cache_path, sizeof(cache_path), "%s.cache", hermes_path);
    
    HANDLE hFile = CreateFileA(cache_path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile == INVALID_HANDLE_VALUE) {
        TIMER_END(cache_check)
        return NULL;
    }

    DWORD fSize = GetFileSize(hFile, NULL);
    if (fSize == 0 || fSize == INVALID_FILE_SIZE) {
        CloseHandle(hFile);
        TIMER_END(cache_check)
        return NULL;
    }

    HANDLE hMap = CreateFileMappingA(hFile, NULL, PAGE_READONLY, 0, 0, NULL);
    if (!hMap) { CloseHandle(hFile); TIMER_END(cache_check); return NULL; }
    
    const char* view = (const char*)MapViewOfFile(hMap, FILE_MAP_READ, 0, 0, 0);
    if (!view) { CloseHandle(hMap); CloseHandle(hFile); TIMER_END(cache_check); return NULL; }

    TIMER_START(cache_load)
    if (!g_marshal_mod) g_marshal_mod = PyImport_ImportModule("marshal");
    PyObject* bytes_obj = PyBytes_FromStringAndSize(view, fSize);
    UnmapViewOfFile(view);
    CloseHandle(hMap);
    CloseHandle(hFile);
    
    if (!bytes_obj || !g_marshal_mod) { TIMER_END(cache_load); return NULL; }
    
    PyObject* code_obj = PyObject_CallMethod(g_marshal_mod, "loads", "O", bytes_obj);
    Py_DECREF(bytes_obj);
    TIMER_END(cache_load)
    
    if (code_obj && PyCode_Check(code_obj)) {
        return code_obj;
    }
    Py_XDECREF(code_obj);
    return NULL;
}

static void save_to_cache(const char* hermes_path, PyObject* code_obj) {
    TIMER_START(cache_save)
    char cache_path[512];
    snprintf(cache_path, sizeof(cache_path), "%s.cache", hermes_path);

    if (!g_marshal_mod) g_marshal_mod = PyImport_ImportModule("marshal");
    if (!g_marshal_mod) { TIMER_END(cache_save); return; }
    
    PyObject* bytes_obj = PyObject_CallMethod(g_marshal_mod, "dumps", "O", code_obj);
    if (!bytes_obj) { TIMER_END(cache_save); return; }
    
    Py_ssize_t size;
    const char* buffer;
    if (PyBytes_AsStringAndSize(bytes_obj, (char**)&buffer, &size) == -1) {
        Py_DECREF(bytes_obj);
        TIMER_END(cache_save);
        return;
    }

    HANDLE hFile = CreateFileA(cache_path, GENERIC_READ | GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile != INVALID_HANDLE_VALUE) {
        HANDLE hMap = CreateFileMappingA(hFile, NULL, PAGE_READWRITE, 0, size, NULL);
        if (hMap) {
            char* view = (char*)MapViewOfFile(hMap, FILE_MAP_WRITE, 0, 0, size);
            if (view) {
                memcpy(view, buffer, size);
                FlushViewOfFile(view, size);
                UnmapViewOfFile(view);
            }
            CloseHandle(hMap);
        }
        CloseHandle(hFile);
    }
    Py_DECREF(bytes_obj);
    TIMER_END(cache_save)
}

// ═══════════════════════════════════════════════════════════════════════════════
// API PYTHON (O Hook de Injeção com Telemetria)
// ═══════════════════════════════════════════════════════════════════════════════
static PyObject* hermes_load_module(PyObject* self, PyObject* args) {
    const char* hermes_path;
    if (!PyArg_ParseTuple(args, "s", &hermes_path)) return NULL;

    fprintf(stderr, "\n[HERMES-C] === INICIANDO CARGA: %s ===\n", hermes_path);
    fflush(stderr);

    // 1. TENTATIVA DE FAST PATH (MARSHAL CACHE - WARM START)
    PyObject* cached_code = try_load_from_cache(hermes_path);
    if (cached_code) {
        fprintf(stderr, "[HERMES-C] ✔ HIT NO CACHE (Warm Start)\n");
        fflush(stderr);
        return cached_code;
    }

    fprintf(stderr, "[HERMES-C] ✘ MISS NO CACHE (Cold Start)\n");
    fflush(stderr);

    // 2. ZERO-COPY VIA MMAP (Cold Start)
    TIMER_START(mmap_open)
    MmapContext hermes_mmap;
    if (hermes_mmap_open(hermes_path, &hermes_mmap) != 0) {
        PyErr_SetString(PyExc_FileNotFoundError, hermes_path);
        return NULL;
    }
    TIMER_END(mmap_open)

    const uint8_t* data = (const uint8_t*)hermes_mmap.address;
    size_t data_size = hermes_mmap.size;

    TIMER_START(parse_hbc5)
    HBC5Context ctx;
    if (parse_hbc5_header(data, data_size, &ctx) != 0) {
        hermes_mmap_close(&hermes_mmap);
        PyErr_SetString(PyExc_RuntimeError, "Falha ao parsear header HBC5");
        return NULL;
    }
    TIMER_END(parse_hbc5)

    // 3. DESERIALIZA O PAYLOAD
    TIMER_START(payload_marshal)
    if (!g_marshal_mod) g_marshal_mod = PyImport_ImportModule("marshal");
    PyObject* payload_bytes = PyBytes_FromStringAndSize((const char*)ctx.payload_ptr, ctx.payload_size);
    PyObject* code_obj = PyObject_CallMethod(g_marshal_mod, "loads", "O", payload_bytes);
    
    Py_DECREF(payload_bytes);
    hermes_mmap_close(&hermes_mmap);
    TIMER_END(payload_marshal)

    if (!code_obj || !PyCode_Check(code_obj)) {
        free_hbc5_context(&ctx);
        PyErr_SetString(PyExc_RuntimeError, "Falha ao deserializar PyCodeObject via marshal");
        return NULL;
    }

    // 4. MOTOR BRANCHLESS IN-PLACE
    TIMER_START(walk_inplace)
    if (walk_and_decode_inplace(code_obj, ctx.bitmap, &ctx.local_dict) != 0) {
        Py_DECREF(code_obj);
        free_hbc5_context(&ctx);
        PyErr_SetString(PyExc_RuntimeError, "Falha na expansão branchless in-place");
        return NULL;
    }
    free_hbc5_context(&ctx);
    TIMER_END(walk_inplace)

    // 5. SALVA NO CACHE PARA O PRÓXIMO BOOT (Warm Start)
    save_to_cache(hermes_path, code_obj);

    fprintf(stderr, "[HERMES-C] === CARGA CONCLUÍDA ===\n\n");
    fflush(stderr);

    return code_obj; 
}

// ═══════════════════════════════════════════════════════════════════════════════
// REGISTRO DO MÓDULO
// ═══════════════════════════════════════════════════════════════════════════════
static PyMethodDef HermesBridgeMethods[] = {
    {"load_module", hermes_load_module, METH_VARARGS, "Carrega e decodifica .hermes HBC5 direto em PyCodeObject"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef hermes_bridge_module = {
    PyModuleDef_HEAD_INIT,
    "hermes_bridge",
    "Motor Nativo de Bypass do Import Machinery (Dual-Dictionary Branchless)",
    -1,
    HermesBridgeMethods
};

PyMODINIT_FUNC PyInit_hermes_bridge(void) {
    // Desativa o buffer do stderr para telemetria em tempo real
    setvbuf(stderr, NULL, _IONBF, 0);
    
    const char* gd_path = ".doxoade/hermes/master.bin";
    init_global_dict(gd_path);
    
    return PyModule_Create(&hermes_bridge_module);
}