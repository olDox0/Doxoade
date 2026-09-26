// doxoade/tools/hermes_systems/native/hermes_mmap.h
#pragma once
#include <stdint.h>
#include <stdio.h>

#ifdef _WIN32
    #include <windows.h>
    typedef struct {
        void* address;        
        HANDLE file_handle;
        HANDLE mapping_handle;
        size_t size;
    } MmapContext;

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

    static inline void hermes_mmap_close(MmapContext* ctx) {
        if (ctx->address) UnmapViewOfFile(ctx->address);
        if (ctx->mapping_handle) CloseHandle(ctx->mapping_handle);
        if (ctx->file_handle) CloseHandle(ctx->file_handle);
        ctx->address = NULL;
    }
#else
    #include <unistd.h>
    #include <fcntl.h>
    #include <sys/mman.h>
    #include <sys/stat.h>

    typedef struct {
        void* address;
        int fd;
        size_t size;
    } MmapContext;

    static inline int hermes_mmap_open(const char* path, MmapContext* ctx) {
        ctx->fd = open(path, O_RDONLY);
        if (ctx->fd < 0) return -1;
        struct stat st;
        if (fstat(ctx->fd, &st) != 0 || st.st_size == 0) {
            close(ctx->fd);
            return -1;
        }
        ctx->size = (size_t)st.st_size;
        ctx->address = mmap(NULL, ctx->size, PROT_READ, MAP_SHARED, ctx->fd, 0);
        if (ctx->address == MAP_FAILED) {
            close(ctx->fd);
            ctx->address = NULL;
            return -1;
        }
        return 0;
    }

    static inline void hermes_mmap_close(MmapContext* ctx) {
        if (ctx->address && ctx->address != MAP_FAILED) {
            munmap(ctx->address, ctx->size);
        }
        if (ctx->fd >= 0) {
            close(ctx->fd);
        }
        ctx->address = NULL;
    }
#endif
