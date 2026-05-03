// doxoade/doxoade/tools/vulcan/nexus_math.c
#include <stdint.h>

/**
 * Nexus Branchless Varint Engine - Tier 1 Core
 */
#ifdef _WIN32
    #define EXPORT __declspec(dllexport)
#else
    #define EXPORT
#endif

EXPORT int nexus_encode_varint_branchless(uint64_t n, uint8_t* out) {
    uint32_t bits = n ? 64 - __builtin_clzll(n) : 1;
    uint32_t bytes = (bits + 6) / 7;

    switch(bytes) {
        case 5: out[4] = (uint8_t)(n >> 28); n |= 0x08000000;
        case 4: out[3] = (uint8_t)((n >> 21) | 0x80);
        case 3: out[2] = (uint8_t)((n >> 14) | 0x80);
        case 2: out[1] = (uint8_t)((n >> 7) | 0x80);
        case 1: out[0] = (uint8_t)(n & 0x7F);
    }
    
    if (bytes > 1) out[bytes-1] &= 0x7F; 
    else out[0] &= 0x7F;

    return bytes;
}