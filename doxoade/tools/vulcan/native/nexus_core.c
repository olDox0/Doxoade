#define _GNU_SOURCE
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

/**
 * nexus_get_filename: Extrai o nome do arquivo de um path string.
 * Simula o 'Path(p).name' em velocidade de hardware.
 */
const char* nexus_get_filename(const char* path) {
    if (!path) return "";
    const char* last_slash = NULL;
    const char* p = path;
    
    // Varredura única em busca da última barra (Windows ou Unix)
    while (*p) {
        if (*p == '/' || *p == '\\') {
            last_slash = p;
        }
        p++;
    }
    
    // Se não achou barra, o path já é o nome do arquivo
    return last_slash ? (last_slash + 1) : path;
}