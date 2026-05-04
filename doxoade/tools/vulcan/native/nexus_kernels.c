#include <stdint.h>
#include <string.h>
#include <stdlib.h>

/**
 * Implementação portável do memmem (Necessário para Windows/MinGW)
 */
void *nexus_internal_memmem(const void *haystack, size_t h_len, const void *needle, size_t n_len) {
    if (n_len == 0) return (void *)haystack;
    if (h_len < n_len) return NULL;
    const unsigned char *h = (const unsigned char *)haystack;
    const unsigned char *n = (const unsigned char *)needle;
    for (size_t i = 0; i <= h_len - n_len; i++) {
        if (h[i] == n[0] && memcmp(&h[i], n, n_len) == 0) {
            return (void *)&h[i];
        }
    }
    return NULL;
}

/**
 * Kernel C: Busca ultra-veloz de bytes em blocos de memória.
 * Agora compatível com Windows.
 */
int64_t nexus_raw_search(const uint8_t* haystack, int64_t h_len, const uint8_t* needle, int64_t n_len) {
    if (n_len <= 0 || h_len < n_len) return -1;
    
    uint8_t* pos = (uint8_t*)nexus_internal_memmem(haystack, (size_t)h_len, needle, (size_t)n_len);
    
    if (pos) return (int64_t)(pos - haystack);
    return -1;
}
/**
 * nexus_select_int: Seleção Branchless
 * Se condition for 1, retorna a. Se 0, retorna b.
 * Zero saltos de CPU.
 */
int64_t nexus_select_int(int64_t condition, int64_t a, int64_t b) {
    // Usa máscara de bits para selecionar o valor sem usar 'if'
    return (a & -condition) | (b & ~-condition);
}

/**
 * nexus_fast_check: Validação de buffer sem 'if'
 * Retorna 1 se o buffer começar com o padrão, 0 caso contrário.
 */
int32_t nexus_starts_with_branchless(const uint8_t* data, const uint8_t* prefix, int32_t len) {
    // Compara a memória de forma direta
    return (memcmp(data, prefix, len) == 0);
}