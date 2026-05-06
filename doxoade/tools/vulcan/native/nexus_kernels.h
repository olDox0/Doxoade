#ifndef NEXUS_KERNELS_H
#define NEXUS_KERNELS_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>

// Protótipos das funções do Kernel C (.c)
//void *nexus_internal_memmem(const void *h, size_t hl, const void *n, size_t nl);
//int64_t nexus_raw_search(const uint8_t* h, int64_t hl, const uint8_t* n, int64_t nl);
int64_t nexus_select_int(int64_t condition, int64_t a, int64_t b);
int32_t nexus_starts_with_branchless(const uint8_t* data, const uint8_t* prefix, int32_t len);
int64_t nexus_branchless_select(int64_t selector, int64_t val_a, int64_t val_b);
double nexus_branchless_div(double a, double b);
//void nexus_path_normalize(char* path);
const char* nexus_get_filename(const char* path);


// Implementação interna para garantir portabilidade no Windows
static inline void *nexus_internal_memmem(const void *h, size_t hl, const void *n, size_t nl) {
    if (nl == 0) return (void *)h;
    if (hl < nl) return NULL;
    const unsigned char *haystack = (const unsigned char *)h;
    const unsigned char *needle = (const unsigned char *)n;
    for (size_t i = 0; i <= hl - nl; i++) {
        if (haystack[i] == needle[0] && memcmp(&haystack[i], needle, nl) == 0) {
            return (void *)&haystack[i];
        }
    }
    return NULL;
}


// ATENÇÃO: O uso de 'static inline' faz o GCC copiar o código para o ponto de chamada
static inline int64_t nexus_raw_search(const uint8_t* h, int64_t hl, const uint8_t* n, int64_t nl) {
    if (nl <= 0 || hl < nl) return -1;
    uint8_t* pos = (uint8_t*)nexus_internal_memmem(h, (size_t)hl, n, (size_t)nl);
    return pos ? (int64_t)(pos - h) : -1;
}


static inline void nexus_path_normalize(char* path) {
    if (!path) return;
    for (; *path; path++) if (*path == '\\') *path = '/';
}

#endif