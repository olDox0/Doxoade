#include <stdint.h>
#include <string.h>

/**
 * Kernel C: Busca de Substring em Bloco Bruto.
 * Otimizado para não gerar alocações e rodar em nível de registrador.
 */
int32_t nexus_find_in_buffer(const char* buffer, int32_t buf_len, const char* pattern, int32_t pat_len) {
    if (pat_len == 0 || buf_len < pat_len) return -1;
    
    char* found = (char*)memmem(buffer, buf_len, pattern, pat_len);
    if (found) {
        return (int32_t)(found - buffer);
    }
    return -1;
}