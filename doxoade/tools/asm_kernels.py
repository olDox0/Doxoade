# doxoade/tools/asm_kernels.py

SIMD_ACCELERATORS = {
    "avx2_string_scan": """
#include <immintrin.h>
#include <stdint.h>

// Busca a primeira ocorrência de um caractere em um bloco de 32 bytes
int find_byte_avx2(const uint8_t* data, uint8_t target, int len) {
    __m256i v_target = _mm256_set1_epi8(target);
    for (int i = 0; i <= len - 32; i += 32) {
        __m256i chunk = _mm256_loadu_si256((const __m256i*)(data + i));
        __m256i cmp = _mm256_cmpeq_epi8(chunk, v_target);
        int mask = _mm256_movemask_epi8(cmp);
        if (mask != 0) return i + __builtin_ctz(mask); // Retorna a posição exata
    }
    return -1; // Não encontrado no bloco vetorial
}
"""
}

STRING_ACCELERATORS = {
    # Busca por blocos de 32 bytes usando AVX2 (Simulado via memmem/strstr em C alto nível)
    "buffer_scan_v2": """
        // Kernel de alta velocidade para busca em buffers brutos
        char* ptr = (char*)memmem(buffer, buf_len, pattern, pat_len);
        while (ptr != NULL) {
            record_hit(ptr - buffer);
            ptr = (char*)memmem(ptr + 1, buf_len - (ptr - buffer + 1), pattern, pat_len);
        }
    """
}