// doxoade/tools/hermes_systems/native/hermes_cache.c
#include "hermes_cache.h"
#include "hermes_mmap.h"
#include <marshal.h>
#include <sys/stat.h>
#include <stdio.h>
#include <string.h>
#include <windows.h>

// ═══════════════════════════════════════════════════════════════════
// TIER 1: RAM LRU (Hash Map Simples com Array Circular)
// ═══════════════════════════════════════════════════════════════════
#define MAX_RAM_CACHE 256
typedef struct { char path[256]; PyObject* obj; } RamEntry;
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
            return g_ram_cache[i].obj; // Borrowed reference
        }
    }
    return NULL;
}

void cache_ram_put(const char* hermes_path, PyObject* code_obj) {
    int idx = g_ram_idx % g_ram_max;
    if (g_ram_cache[idx].obj) {
        Py_DECREF(g_ram_cache[idx].obj); // Libera o antigo
    }
    strncpy(g_ram_cache[idx].path, hermes_path, 255);
    g_ram_cache[idx].path[255] = '\0';
    Py_INCREF(code_obj); // Cache segura uma referência
    g_ram_cache[idx].obj = code_obj;
    g_ram_idx++;
}

// ═══════════════════════════════════════════════════════════════════
// TIER 2: DISK MARSHAL CACHE (O "Pulo do Gato")
// ═══════════════════════════════════════════════════════════════════

// Header do .hcache (16 bytes) para validação de staleness
typedef struct {
    uint64_t hermes_mtime;
    uint64_t hermes_size;
} HCacheHeader;

static void get_hcache_path(const char* hermes_path, char* out, size_t out_size) {
    // Converte: .../build/doxoade.cli.hermes -> .../cache/doxoade.cli.hcache
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

    // Validação de Staleness (Zero-Copy)
    HCacheHeader* hdr = (HCacheHeader*)ctx.address;
    if (hdr->hermes_mtime != hermes_mtime || hdr->hermes_size != hermes_size) {
        hermes_mmap_close(&ctx);
        return NULL; // Stale! O .hermes mudou.
    }

    // 🚀 ZERO-COPY MARSHAL LOAD
    const char* payload = (const char*)ctx.address + sizeof(HCacheHeader);
    Py_ssize_t payload_size = (Py_ssize_t)(ctx.size - sizeof(HCacheHeader));
    
    PyObject* code_obj = PyMarshal_ReadObjectFromString(payload, payload_size);
    hermes_mmap_close(&ctx); // Podemos fechar o mmap, o Python já copiou para a heap interna dele

    return code_obj; // NEW REFERENCE
}

int cache_disk_save(const char* hermes_path, PyObject* code_obj) {
    char hcache_path[512];
    get_hcache_path(hermes_path, hcache_path, sizeof(hcache_path));

    uint64_t hermes_mtime, hermes_size;
    if (!get_file_stats(hermes_path, &hermes_mtime, &hermes_size)) return 0;

    // 1. Serializa o CodeObject usando o Marshal nativo do CPython
    PyObject* marshal_bytes = PyMarshal_WriteObjectToString(code_obj, Py_MARSHAL_VERSION);
    if (!marshal_bytes) return 0;

    const char* payload = PyBytes_AsString(marshal_bytes);
    Py_ssize_t payload_size = PyBytes_Size(marshal_bytes);

    // 2. Garante que o diretório de cache existe
    char dir_path[512];
    strncpy(dir_path, hcache_path, sizeof(dir_path));
    char* last_slash = strrchr(dir_path, '\\');
    if (!last_slash) last_slash = strrchr(dir_path, '/');
    if (last_slash) {
        *last_slash = '\0';
        CreateDirectoryA(dir_path, NULL); // Ignora erro se já existir
    }

    // 3. Escreve o Header + Payload no disco
    FILE* f = fopen(hcache_path, "wb");
    if (!f) {
        Py_DECREF(marshal_bytes);
        return 0;
    }

    HCacheHeader hdr = { hermes_mtime, hermes_size };
    fwrite(&hdr, sizeof(HCacheHeader), 1, f);
    fwrite(payload, 1, payload_size, f);
    fclose(f);

    Py_DECREF(marshal_bytes);
    return 1;
}