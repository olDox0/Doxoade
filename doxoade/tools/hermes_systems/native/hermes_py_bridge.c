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
// MACROS DE LEITURA BINÁRIA (Little-Endian)
// ═══════════════════════════════════════════════════════════════════════════════
#define READ_U16(p) ((uint16_t)((p)[0] | ((p)[1] << 8)))
#define READ_U32(p) ((uint32_t)((p)[0] | ((p)[1] << 8) | ((p)[2] << 16) | ((p)[3] << 24)))

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

// Protótipos do Parser HBC5 (Implementados em hermes_hbc5_parser.c)
int parse_hbc5_header(const uint8_t* data, size_t data_size, HBC5Context* ctx);
void free_hbc5_context(HBC5Context* ctx);

// ═══════════════════════════════════════════════════════════════════════════════
// ESTRUTURAS DO PARSER HBC6 (Patch-in-RAM)
// ═══════════════════════════════════════════════════════════════════════════════
typedef struct {
    uint32_t co_index;
    uint32_t offset;
    uint16_t token_id;
    uint16_t orig_ngram_len; // 🚀 CRÍTICO: Tamanho original para o Chunk Copying
} HBC6_Patch;

typedef struct {
    HBC6_Patch* patches;
    uint32_t patch_count;
    const uint8_t* payload_ptr;
    uint32_t payload_size;
} HBC6Context;

// Protótipos do Parser HBC6
static int parse_hbc6_header(const uint8_t* data, size_t data_size, HBC6Context* ctx);
static void free_hbc6_context(HBC6Context* ctx);
static PyObject* apply_hbc6_patches(PyObject* code_obj, HBC6_Patch* patches, int patch_count, int* current_dfs_index);

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
// MOTOR BRANCHLESS (Expansão de Strings - Local Dict HBC5)
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

static int walk_and_decode_inplace(PyObject* code_obj, const uint8_t* bitmap, const HermesDict* l_dict) {
    if (!PyCode_Check(code_obj)) return 0;
    PyObject* co_consts = PyObject_GetAttrString(code_obj, "co_consts");
    if (!co_consts || !PyTuple_Check(co_consts)) { Py_XDECREF(co_consts); return -1; }
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
                if (c >= 0x80 && (bitmap[c >> 3] >> (c & 7)) & 1) { needs_decode = 1; break; }
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
        } else if (PyCode_Check(item)) {
            if (walk_and_decode_inplace(item, bitmap, l_dict) != 0) { Py_DECREF(co_consts); return -1; }
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
    if (hFile == INVALID_HANDLE_VALUE) { TIMER_END(cache_check) return NULL; }
    DWORD fSize = GetFileSize(hFile, NULL);
    if (fSize == 0 || fSize == INVALID_FILE_SIZE) { CloseHandle(hFile); TIMER_END(cache_check) return NULL; }
    HANDLE hMap = CreateFileMappingA(hFile, NULL, PAGE_READONLY, 0, 0, NULL);
    if (!hMap) { CloseHandle(hFile); TIMER_END(cache_check); return NULL; }
    const char* view = (const char*)MapViewOfFile(hMap, FILE_MAP_READ, 0, 0, 0);
    if (!view) { CloseHandle(hMap); CloseHandle(hFile); TIMER_END(cache_check); return NULL; }
    TIMER_START(cache_load)
    if (!g_marshal_mod) g_marshal_mod = PyImport_ImportModule("marshal");
    PyObject* bytes_obj = PyBytes_FromStringAndSize(view, fSize);
    UnmapViewOfFile(view); CloseHandle(hMap); CloseHandle(hFile);
    if (!bytes_obj || !g_marshal_mod) { TIMER_END(cache_load); return NULL; }
    PyObject* code_obj = PyObject_CallMethod(g_marshal_mod, "loads", "O", bytes_obj);
    Py_DECREF(bytes_obj);
    TIMER_END(cache_load)
    if (code_obj && PyCode_Check(code_obj)) return code_obj;
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
    Py_ssize_t size; const char* buffer;
    if (PyBytes_AsStringAndSize(bytes_obj, (char**)&buffer, &size) == -1) { Py_DECREF(bytes_obj); TIMER_END(cache_save); return; }
    HANDLE hFile = CreateFileA(cache_path, GENERIC_READ | GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile != INVALID_HANDLE_VALUE) {
        HANDLE hMap = CreateFileMappingA(hFile, NULL, PAGE_READWRITE, 0, size, NULL);
        if (hMap) {
            char* view = (char*)MapViewOfFile(hMap, FILE_MAP_WRITE, 0, 0, size);
            if (view) { memcpy(view, buffer, size); FlushViewOfFile(view, size); UnmapViewOfFile(view); }
            CloseHandle(hMap);
        }
        CloseHandle(hFile);
    }
    Py_DECREF(bytes_obj);
    TIMER_END(cache_save)
}

// ═══════════════════════════════════════════════════════════════════════════════
// PARSER HBC6 (Header)
// ═══════════════════════════════════════════════════════════════════════════════
static int parse_hbc6_header(const uint8_t* data, size_t data_size, HBC6Context* ctx) {
    if (!data || data_size < 9 || !ctx) return -1;
    if (memcmp(data, "HBC6", 4) != 0 || data[4] != 0x06) return -1;
    size_t offset = 5;
    if (offset + 4 > data_size) return -1;
    uint32_t hrt_size = READ_U32(&data[offset]); offset += 4;
    if (hrt_size % 12 != 0) return -1;
    ctx->patch_count = hrt_size / 12;
    if (offset + hrt_size > data_size) return -1;
    if (ctx->patch_count > 0) {
        ctx->patches = (HBC6_Patch*)malloc(hrt_size);
        if (!ctx->patches) return -1;
        for (uint32_t i = 0; i < ctx->patch_count; i++) {
            ctx->patches[i].co_index      = READ_U32(&data[offset]); offset += 4;
            ctx->patches[i].offset        = READ_U32(&data[offset]); offset += 4;
            ctx->patches[i].token_id      = READ_U16(&data[offset]); offset += 2;
            ctx->patches[i].orig_ngram_len= READ_U16(&data[offset]); offset += 2;
        }
    } else { ctx->patches = NULL; }
    if (offset + 4 > data_size) return -1;
    ctx->payload_size = READ_U32(&data[offset]); offset += 4;
    if (offset + ctx->payload_size > data_size) return -1;
    ctx->payload_ptr = &data[offset];
    return 0;
}

static void free_hbc6_context(HBC6Context* ctx) {
    if (ctx && ctx->patches) { free(ctx->patches); ctx->patches = NULL; }
}

// ═══════════════════════════════════════════════════════════════════════════════
// MOTOR HBC6: WALKER DFS E APLICADOR DE PATCHES (CHUNK COPYING - ZERO OVERFLOW)
// ═══════════════════════════════════════════════════════════════════════════════
static PyObject* apply_hbc6_patches(PyObject* code_obj, HBC6_Patch* patches, int patch_count, int* current_dfs_index) {
    if (!PyCode_Check(code_obj)) { Py_INCREF(code_obj); return code_obj; }

    int my_index = (*current_dfs_index)++;
    fprintf(stderr, "[HERMES-C]   DFS visiting CodeObject index %d\n", my_index);

    PyObject* co_code = PyObject_GetAttrString(code_obj, "co_code");
    if (!co_code || !PyBytes_Check(co_code)) { Py_XDECREF(co_code); Py_INCREF(code_obj); return code_obj; }

    Py_ssize_t orig_len;
    char* orig_buf;
    if (PyBytes_AsStringAndSize(co_code, &orig_buf, &orig_len) == -1) {
        Py_DECREF(co_code); Py_INCREF(code_obj); return code_obj;
    }

    // 1. Calcula o Delta Total para este CodeObject
    size_t total_delta = 0;
    int patches_for_this_obj = 0;
    for (int i = 0; i < patch_count; i++) {
        if (patches[i].co_index == (uint32_t)my_index) {
            patches_for_this_obj++;
            total_delta += (patches[i].orig_ngram_len - 2); // 2 bytes do Token
        }
    }

    PyObject* final_code_obj = code_obj;
    Py_INCREF(final_code_obj);

    // 2. Aplica os Patches (Chunk Copying)
    if (patches_for_this_obj > 0 && total_delta > 0) {
        size_t new_len = orig_len - total_delta;
        fprintf(stderr, "[HERMES-C]   Allocating new buffer: %zu bytes (saved %zu)\n", new_len, total_delta);
        
        char* new_buf = (char*)malloc(new_len);
        if (!new_buf) { Py_DECREF(co_code); Py_DECREF(final_code_obj); return code_obj; }

        // ESTRATÉGIA CHUNK COPYING (Zero Overflow)
        size_t src_pos = 0;
        size_t dst_pos = 0;

        for (int i = 0; i < patch_count; i++) {
            if (patches[i].co_index == (uint32_t)my_index) {
                uint32_t off = patches[i].offset;
                uint16_t tok = patches[i].token_id;
                uint16_t orig_ng_len = patches[i].orig_ngram_len;

                // Copia o gap antes do patch
                size_t gap = off - src_pos;
                if (gap > 0) {
                    memcpy(new_buf + dst_pos, orig_buf + src_pos, gap);
                    dst_pos += gap;
                }

                // Injeta o Token de Macro (0xFE + ID)
                new_buf[dst_pos] = (char)0xFE; 
                new_buf[dst_pos + 1] = (char)tok;
                dst_pos += 2;

                src_pos = off + orig_ng_len;
            }
        }

        // Copia a cauda final
        if (src_pos < (size_t)orig_len) {
            memcpy(new_buf + dst_pos, orig_buf + src_pos, orig_len - src_pos);
        }

        // 3. Cria o novo bytes encolhido
        PyObject* new_bytes = PyBytes_FromStringAndSize(new_buf, new_len);
        free(new_buf);

        if (!new_bytes) { Py_DECREF(co_code); Py_DECREF(final_code_obj); return code_obj; }

        // 4. O TRUQUE DE OURO: Chama .replace(co_code=new_bytes, co_linetable=b'')
        PyObject* replace_method = PyObject_GetAttrString(code_obj, "replace");
        if (replace_method) {
            PyObject* args = PyTuple_New(0);
            PyObject* kwargs = PyDict_New();
            PyObject* empty_bytes = PyBytes_FromStringAndSize("", 0);

            PyDict_SetItemString(kwargs, "co_code", new_bytes);
            PyDict_SetItemString(kwargs, "co_linetable", empty_bytes);

            PyObject* new_code_obj = PyObject_Call(replace_method, args, kwargs);

            Py_DECREF(args); Py_DECREF(kwargs); Py_DECREF(replace_method); 
            Py_DECREF(new_bytes); Py_DECREF(empty_bytes); Py_DECREF(co_code);

            if (new_code_obj) {
                Py_DECREF(final_code_obj);
                final_code_obj = new_code_obj;
            }
        } else {
            Py_DECREF(new_bytes);
            Py_DECREF(co_code);
        }
    } else {
        Py_DECREF(co_code);
    }

    // 5. RECURSÃO DFS (Processa as funções aninhadas em co_consts)
    PyObject* co_consts = PyObject_GetAttrString(final_code_obj, "co_consts");
    if (co_consts && PyTuple_Check(co_consts)) {
        Py_ssize_t n = PyTuple_Size(co_consts);
        int changed = 0;

        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject* item = PyTuple_GetItem(co_consts, i);
            if (PyCode_Check(item)) {
                PyObject* patched_child = apply_hbc6_patches(item, patches, patch_count, current_dfs_index);
                if (patched_child != item) {
                    Py_INCREF(patched_child);
                    PyTuple_SetItem(co_consts, i, patched_child);
                    changed = 1;
                }
            }
        }

        if (changed) {
            PyObject* replace_method = PyObject_GetAttrString(final_code_obj, "replace");
            if (replace_method) {
                PyObject* args = PyTuple_New(0);
                PyObject* kwargs = PyDict_New();
                PyDict_SetItemString(kwargs, "co_consts", co_consts);

                PyObject* newer_code_obj = PyObject_Call(replace_method, args, kwargs);
                Py_DECREF(args); Py_DECREF(kwargs); Py_DECREF(replace_method);

                if (newer_code_obj) {
                    Py_DECREF(final_code_obj);
                    final_code_obj = newer_code_obj;
                }
            }
        }
    }
    Py_XDECREF(co_consts);

    return final_code_obj;
}

// ═══════════════════════════════════════════════════════════════════════════════
// API PYTHON (O Hook de Injeção com Telemetria e Roteador HBC5/HBC6)
// ═══════════════════════════════════════════════════════════════════════════════
static PyObject* hermes_load_module(PyObject* self, PyObject* args) {
    const char* hermes_path;
    const char* global_dict_path;
    if (!PyArg_ParseTuple(args, "ss", &hermes_path, &global_dict_path)) return NULL;

    fprintf(stderr, "\n[HERMES-C] === INICIANDO CARGA: %s ===\n", hermes_path);
    fflush(stderr);

    if (!g_ctx.is_initialized) {
        if (init_global_dict(global_dict_path) != 0) {
            fprintf(stderr, "[HERMES-C] ⚠ Falha ao mapear Global Dict em: %s\n", global_dict_path);
        } else {
            fprintf(stderr, "[HERMES-C] ✔ Global Dict carregado de: %s\n", global_dict_path);
        }
    }

    PyObject* cached_code = try_load_from_cache(hermes_path);
    if (cached_code) {
        fprintf(stderr, "[HERMES-C] ✔ HIT NO CACHE (Warm Start)\n");
        fflush(stderr);
        return cached_code;
    }
    fprintf(stderr, "[HERMES-C] ✘ MISS NO CACHE (Cold Start)\n");
    fflush(stderr);

    TIMER_START(mmap_open)
    MmapContext hermes_mmap;
    if (hermes_mmap_open(hermes_path, &hermes_mmap) != 0) {
        PyErr_SetString(PyExc_FileNotFoundError, hermes_path);
        return NULL;
    }
    TIMER_END(mmap_open)

    const uint8_t* data = (const uint8_t*)hermes_mmap.address;
    size_t data_size = hermes_mmap.size;
    PyObject* code_obj = NULL;

    // ═══════════════════════════════════════════════════════════════════
    // ROTEADOR DE FORMATO (HBC5 vs HBC6)
    // ═══════════════════════════════════════════════════════════════════
    if (data_size >= 4 && memcmp(data, "HBC6", 4) == 0) {
        fprintf(stderr, "[HERMES-C] 🧬 Formato HBC6 detectado (Patch-in-RAM)\n");
        TIMER_START(parse_hbc6)
        HBC6Context hbc6_ctx;
        if (parse_hbc6_header(data, data_size, &hbc6_ctx) != 0) {
            hermes_mmap_close(&hermes_mmap);
            PyErr_SetString(PyExc_RuntimeError, "Falha ao parsear header HBC6");
            return NULL;
        }
        TIMER_END(parse_hbc6)

        TIMER_START(payload_marshal_hbc6)
        if (!g_marshal_mod) g_marshal_mod = PyImport_ImportModule("marshal");
        PyObject* payload_bytes = PyBytes_FromStringAndSize((const char*)hbc6_ctx.payload_ptr, hbc6_ctx.payload_size);
        code_obj = PyObject_CallMethod(g_marshal_mod, "loads", "O", payload_bytes);
        Py_DECREF(payload_bytes);
        hermes_mmap_close(&hermes_mmap);
        TIMER_END(payload_marshal_hbc6)

        if (!code_obj || !PyCode_Check(code_obj)) {
            free_hbc6_context(&hbc6_ctx);
            PyErr_SetString(PyExc_RuntimeError, "Falha ao deserializar PyCodeObject HBC6");
            return NULL;
        }

        TIMER_START(apply_hbc6_patches)
        int dfs_index = 0;
        PyObject* patched_obj = apply_hbc6_patches(code_obj, hbc6_ctx.patches, hbc6_ctx.patch_count, &dfs_index);
        Py_DECREF(code_obj);
        code_obj = patched_obj;
        free_hbc6_context(&hbc6_ctx);
        TIMER_END(apply_hbc6_patches)

    } else {
        TIMER_START(parse_hbc5)
        HBC5Context ctx;
        if (parse_hbc5_header(data, data_size, &ctx) != 0) {
            hermes_mmap_close(&hermes_mmap);
            PyErr_SetString(PyExc_RuntimeError, "Falha ao parsear header HBC5");
            return NULL;
        }
        TIMER_END(parse_hbc5)

        TIMER_START(payload_marshal)
        if (!g_marshal_mod) g_marshal_mod = PyImport_ImportModule("marshal");
        PyObject* payload_bytes = PyBytes_FromStringAndSize((const char*)ctx.payload_ptr, ctx.payload_size);
        code_obj = PyObject_CallMethod(g_marshal_mod, "loads", "O", payload_bytes);
        Py_DECREF(payload_bytes);
        hermes_mmap_close(&hermes_mmap);
        TIMER_END(payload_marshal)

        if (!code_obj || !PyCode_Check(code_obj)) {
            free_hbc5_context(&ctx);
            PyErr_SetString(PyExc_RuntimeError, "Falha ao deserializar PyCodeObject HBC5");
            return NULL;
        }

        TIMER_START(walk_inplace)
        if (walk_and_decode_inplace(code_obj, ctx.bitmap, &ctx.local_dict) != 0) {
            Py_DECREF(code_obj);
            free_hbc5_context(&ctx);
            PyErr_SetString(PyExc_RuntimeError, "Falha na expansão branchless in-place");
            return NULL;
        }
        free_hbc5_context(&ctx);
        TIMER_END(walk_inplace)
    }

    if (!code_obj) {
        PyErr_SetString(PyExc_RuntimeError, "CodeObject final é nulo");
        return NULL;
    }

    save_to_cache(hermes_path, code_obj);
    fprintf(stderr, "[HERMES-C] === CARGA CONCLUÍDA ===\n\n");
    fflush(stderr);
    return code_obj; 
}

// ═══════════════════════════════════════════════════════════════════════════════
// REGISTRO DO MÓDULO
// ═══════════════════════════════════════════════════════════════════════════════
static PyMethodDef HermesBridgeMethods[] = {
    {"load_module", hermes_load_module, METH_VARARGS, "Carrega e decodifica .hermes HBC5/HBC6 direto em PyCodeObject"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef hermes_bridge_module = {
    PyModuleDef_HEAD_INIT,
    "hermes_bridge",
    "Motor Nativo de Bypass do Import Machinery (Dual-Dictionary + HBC6 Patch-in-RAM)",
    -1,
    HermesBridgeMethods
};

PyMODINIT_FUNC PyInit_hermes_bridge(void) {
    setvbuf(stderr, NULL, _IONBF, 0);
    const char* gd_path = ".doxoade/hermes/master.bin";
    init_global_dict(gd_path);
    return PyModule_Create(&hermes_bridge_module);
}