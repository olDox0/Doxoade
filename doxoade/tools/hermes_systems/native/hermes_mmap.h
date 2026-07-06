// doxoade/tools/hermes_systems/native/hermes_mmap.h
#pragma once
#include <windows.h>
#include <stdint.h>
#include <stdio.h>

typedef struct {
    void* address;        // Ponteiro para o início do mmap (O Header HGD1)
    HANDLE file_handle;
    HANDLE mapping_handle;
    size_t size;
} MmapContext;

// Abre o arquivo e mapeia na memória virtual (Zero-Copy)
static inline int hermes_mmap_open(const char* path, MmapContext* ctx) {
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

// Libera o mmap
static inline void hermes_mmap_close(MmapContext* ctx) {
    if (ctx->address) UnmapViewOfFile(ctx->address);
    if (ctx->mapping_handle) CloseHandle(ctx->mapping_handle);
    if (ctx->file_handle) CloseHandle(ctx->file_handle);
    ctx->address = NULL;
}