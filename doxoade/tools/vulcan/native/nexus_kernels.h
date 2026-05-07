// doxoade/tools/vulcan/native/nexus_kernels.h
//#ifndef NEXUS_KERNELS_H
//#define NEXUS_KERNELS_H
#ifndef NEXUS_ASM_H
#define NEXUS_ASM_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>

/* --- NEXUS ENGINE: HEADER-ONLY CORE --- 
   O uso de 'static inline' resolve erros de linker em projetos externos
   e garante performance máxima (Zero Call Overhead).
*/

uint64_t nexus_asm_crc32(const uint8_t* buf, int64_t len);
int64_t nexus_asm_search_char(const uint8_t* buf, int64_t len, int64_t target);

static inline int64_t nexus_asm_vec_search(const uint8_t* buf, int64_t len, int64_t target) {
    if (!buf || len <= 0) return -1;
    for (int64_t i = 0; i < len; i++) {
        if (buf[i] == (uint8_t)target) return i;
    }
    return -1;
}

static inline long nexus_asm_popcount(long value) {
    #ifdef _MSC_VER
        return (long)__popcnt((unsigned int)value);
    #else
        return (long)__builtin_popcountl((unsigned long)value);
    #endif
}

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

static inline int64_t nexus_raw_search(const uint8_t* h, int64_t hl, const uint8_t* n, int64_t nl) {
    if (nl <= 0 || hl < nl) return -1;
    // (Omiti a implementação do memmem por brevidade, mas mantenha a que fizemos antes)
    const unsigned char *haystack = (const unsigned char *)h;
    const unsigned char *needle = (const unsigned char *)n;
    for (size_t i = 0; i <= (size_t)(hl - nl); i++) {
        if (haystack[i] == needle[0] && memcmp(&haystack[i], needle, (size_t)nl) == 0) {
            return (int64_t)i;
        }
    }
    return -1;
}

static inline int64_t nexus_branchless_select(int64_t selector, int64_t val_a, int64_t val_b) {
    return selector ? val_a : val_b;
}

static inline int64_t nexus_asm_cmov(int64_t selector, int64_t val_true, int64_t val_false) {
    return selector ? val_true : val_false;
}

static inline int64_t nexus_select_int(int64_t condition, int64_t a, int64_t b) {
    return (a & -condition) | (b & ~-condition);
}

static inline double nexus_branchless_div(double a, double b) {
    return a / (b + (b == 0)); 
}

static inline int32_t nexus_starts_with_branchless(const uint8_t* data, const uint8_t* prefix, int32_t len) {
    return (memcmp(data, prefix, len) == 0);
}

static inline void nexus_path_normalize(char* path) {
    if (!path) return;
    for (; *path; path++) if (*path == '\\') *path = '/';
}

static inline const char* nexus_get_filename(const char* path) {
    if (!path) return "";
    const char* last = path;
    for (const char* p = path; *p; p++) {
        if (*p == '/' || *p == '\\') last = p + 1;
    }
    return last;
}

static inline int nexus_encode_varint_branchless(uint64_t n, uint8_t* out) {
    // Calcula quantos bits são necessários
    uint32_t bits = n ? 64 - __builtin_clzll(n) : 1;
    uint32_t bytes = (bits + 6) / 7;

    // Codificação sem branches para máxima velocidade no N2808
    switch(bytes) {
        case 9: out[8] = (uint8_t)((n >> 56) | 0x80);
        case 8: out[7] = (uint8_t)((n >> 49) | 0x80);
        case 7: out[6] = (uint8_t)((n >> 42) | 0x80);
        case 6: out[5] = (uint8_t)((n >> 35) | 0x80);
        case 5: out[4] = (uint8_t)((n >> 28) | 0x80);
        case 4: out[3] = (uint8_t)((n >> 21) | 0x80);
        case 3: out[2] = (uint8_t)((n >> 14) | 0x80);
        case 2: out[1] = (uint8_t)((n >> 7) | 0x80);
        case 1: out[0] = (uint8_t)(n & 0x7F);
    }
    
    // O último byte não tem o bit de continuação (0x80)
    out[bytes-1] &= 0x7F;
    return (int)bytes;
}

#endif