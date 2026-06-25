#include <stdint.h>
#include <stdio.h>

/**
 * VLS - Vulcan Linear Scanner
 * Varre o vetor de bitmaps e retorna IDs que dão match.
 */
__declspec(dllexport) int vls_filter_bitmaps(
    const uint64_t* bitmaps, 
    int32_t* results, 
    int total_count, 
    uint64_t mask
) {
    int match_count = 0;
    for (int i = 0; i < total_count; i++) {
        // Operação de 1 ciclo: Bitwise AND
        if ((bitmaps[i] & mask) == mask) {
            results[match_count++] = i + 1; // Retorna o ID (RowID)
        }
    }
    return match_count;
}