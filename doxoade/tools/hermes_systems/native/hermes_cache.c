// doxoade/tools/hermes_systems/native/hermes_cache.c
#include "hermes_cache.h"
#include "hermes_mmap.h"
#include <process.h>
#include <stdlib.h>
#include <marshal.h>
#include <sys/stat.h>
#include <stdio.h>
#include <string.h>
#include <windows.h>

// ═══════════════════════════════════════════════════════════════════
// LOG CONDICIONAL
// ═══════════════════════════════════════════════════════════════════
static int g_verbose = -1;
#define HERMES_LOG(fmt, ...) do { \
    if (g_verbose == -1) g_verbose = (getenv("HERMES_VERBOSE") != NULL); \
    if (g_verbose) fprintf(stderr, "[HERMES-C] " fmt "\n", ##__VA_ARGS__); \
} while(0)

// ═══════════════════════════════════════════════════════════════════
// ESTRUTURAS E FUNÇÕES AUXILIARES (DISK CACHE)
// ═══════════════════════════════════════════════════════════════════
typedef struct {
    uint64_t hermes_mtime;
    uint64_t hermes_size;
} HCacheHeader;

static void get_hcache_path(const char* hermes_path, char* out, size_t out_size) {
    strncpy(out, hermes_path, out_size);
    char* last_slash = strrchr(out, '\\');
    if (!last_slash) last_slash = strrchr(out, '/');
    if (last_slash) {
        char* build_pos = strstr(out, "build");
        if (build_pos) {
            memcpy(build_pos, "cache", 5);
        }
    }
    char* dot = strrchr(out, '.');
    if (dot) strcpy(dot, ".hcache");
}

static int get_file_stats(const char* path, uint64_t* mtime, uint64_t* size) {
    struct stat st;
    if (stat(path, &st) != 0) return 0;
    *mtime = (uint64_t)st.st_mtime;
    *size = (uint64_t)st.st_size;
    return 1;
}

// ═══════════════════════════════════════════════════════════════════
// 🚀 PIPELINE ASSÍNCRONO: Fire-and-Forget Disk Save
// ═══════════════════════════════════════════════════════════════════
typedef struct {
    char hcache_path[512];
    uint64_t hermes_mtime;
    uint64_t hermes_size;
    PyObject* code_obj;  // <-- ADICIONADO: Campo que estava faltando
} AsyncSaveJob;

static unsigned __stdcall async_save_worker(void* arg) {
    AsyncSaveJob* job = (AsyncSaveJob*)arg;
    
    // 🚀 ADQUIRIR GIL APENAS PARA MARSHAL
    PyGILState_STATE gstate = PyGILState_Ensure();
    PyObject* marshal_bytes = PyMarshal_WriteObjectToString(job->code_obj, Py_MARSHAL_VERSION);
    Py_DECREF(job->code_obj); // Libera referência mantida pelo job
    
    if (!marshal_bytes) {
        PyGILState_Release(gstate);
        free(job);
        return 1;
    }
    
    const char* payload = PyBytes_AsString(marshal_bytes);
    Py_ssize_t payload_size = PyBytes_Size(marshal_bytes);
    
    char* payload_copy = (char*)malloc(payload_size);
    if (!payload_copy) {
        Py_DECREF(marshal_bytes);
        PyGILState_Release(gstate);
        free(job);
        return 1;
    }
    memcpy(payload_copy, payload, payload_size);
    Py_DECREF(marshal_bytes);
    PyGILState_Release(gstate); // 🚀 LIBERA GIL ANTES DO I/O

    // 1. Garante que o diretório existe
    char dir_path[512];
    strncpy(dir_path, job->hcache_path, sizeof(dir_path));
    char* last_slash = strrchr(dir_path, '\\');
    if (!last_slash) last_slash = strrchr(dir_path, '/');
    if (last_slash) {
        *last_slash = '\0';
        CreateDirectoryA(dir_path, NULL);
    }

    // 2. Escreve no disco (I/O Puro, sem GIL)
    FILE* f = fopen(job->hcache_path, "wb");
    if (f) {
        HCacheHeader hdr = { job->hermes_mtime, job->hermes_size };
        fwrite(&hdr, sizeof(HCacheHeader), 1, f);
        fwrite(payload_copy, 1, payload_size, f);
        fclose(f);
    }

    // 3. Limpa a memória
    free(payload_copy);
    free(job);
    return 0;
}

int cache_disk_save(const char* hermes_path, PyObject* code_obj) {
    char hcache_path[512];
    get_hcache_path(hermes_path, hcache_path, sizeof(hcache_path));
    
    uint64_t hermes_mtime, hermes_size;
    if (!get_file_stats(hermes_path, &hermes_mtime, &hermes_size)) return 0;

    AsyncSaveJob* job = (AsyncSaveJob*)malloc(sizeof(AsyncSaveJob));
    if (!job) return 0;
    
    strncpy(job->hcache_path, hcache_path, sizeof(job->hcache_path) - 1);
    job->hcache_path[sizeof(job->hcache_path) - 1] = '\0';
    job->hermes_mtime = hermes_mtime;
    job->hermes_size = hermes_size;
    job->code_obj = code_obj;
    Py_INCREF(code_obj); // Thread background segura referência

    uintptr_t thrd = _beginthreadex(NULL, 0, async_save_worker, job, 0, NULL);
    if (thrd != 0) {
        CloseHandle((HANDLE)thrd);
    } else {
        async_save_worker(job); // Fallback síncrono
    }
    
    HERMES_LOG("💾 ASYNC MARSHAL+SAVE DESPATCHED");
    return 1;
}

// ═══════════════════════════════════════════════════════════════════
// TIER 1: RAM LRU (Hash Map Simples com Array Circular)
// ═══════════════════════════════════════════════════════════════════
#define MAX_RAM_CACHE 256
typedef struct {
    char path[256];
    PyObject* obj;
} RamEntry;

static RamEntry g_ram_cache[MAX_RAM_CACHE];
static int g_ram_idx = 0;
static int g_ram_max = MAX_RAM_CACHE;

void cache_ram_init(int max_size) {
    g_ram_max = (max_size > MAX_RAM_CACHE) ? MAX_RAM_CACHE : max_size;
    memset(g_ram_cache, 0, sizeof(g_ram_cache));
}

PyObject* cache_ram_get(const char* hermes_path) {
    for (int i = 0; i < g_ram_max; i++) {
        if (g_ram_cache[i].obj && strcmp(g_ram_cache[i].path, hermes_path) == 0) {
            HERMES_LOG("✔ HIT NO RAM CACHE");
            return g_ram_cache[i].obj; // Borrowed reference
        }
    }
    return NULL;
}

void cache_ram_put(const char* hermes_path, PyObject* code_obj) {
    int idx = g_ram_idx % g_ram_max;
    if (g_ram_cache[idx].obj) {
        Py_DECREF(g_ram_cache[idx].obj);
    }
    strncpy(g_ram_cache[idx].path, hermes_path, 255);
    g_ram_cache[idx].path[255] = '\0';
    Py_INCREF(code_obj);
    g_ram_cache[idx].obj = code_obj;
    g_ram_idx++;
}

// ═══════════════════════════════════════════════════════════════════
// TIER 2: DISK MARSHAL CACHE LOAD
// ═══════════════════════════════════════════════════════════════════
PyObject* cache_disk_load(const char* hermes_path) {
    char hcache_path[512];
    get_hcache_path(hermes_path, hcache_path, sizeof(hcache_path));
    
    uint64_t hermes_mtime, hermes_size;
    if (!get_file_stats(hermes_path, &hermes_mtime, &hermes_size)) return NULL;

    MmapContext ctx = {0};
    if (hermes_mmap_open(hcache_path, &ctx) != 0) return NULL;

    if (ctx.size < sizeof(HCacheHeader)) {
        hermes_mmap_close(&ctx);
        return NULL;
    }

    HCacheHeader* hdr = (HCacheHeader*)ctx.address;
    if (hdr->hermes_mtime != hermes_mtime || hdr->hermes_size != hermes_size) {
        HERMES_LOG("✘ STALE CACHE (arquivo mudou)");
        hermes_mmap_close(&ctx);
        return NULL;
    }

    HERMES_LOG("✔ HIT NO DISK CACHE (Disk Hit)");
    const char* payload = (const char*)ctx.address + sizeof(HCacheHeader);
    Py_ssize_t payload_size = (Py_ssize_t)(ctx.size - sizeof(HCacheHeader));
    
    PyObject* code_obj = PyMarshal_ReadObjectFromString(payload, payload_size);
    hermes_mmap_close(&ctx); 
    return code_obj; // NEW REFERENCE
}