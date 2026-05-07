// nexus_kernels.c
#include <stdint.h>
#include <stddef.h>
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
    
    // Otimização: usa memmem (ou a versão portável que fizemos)
    void* pos = nexus_internal_memmem(haystack, h_len, needle, n_len);
    
    if (pos) return (int64_t)((uint8_t*)pos - haystack);
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

/**
 * nexus_branchless_select: Seleção sem desvio de execução.
 * Selector deve ser 0 ou 1.
 * Se 1, retorna val_a. Se 0, retorna val_b.
 */
int64_t nexus_branchless_select(int64_t selector, int64_t val_a, int64_t val_b) {
    // O GCC converte este operador ternário simples em instruções CMOV 
    // no x86_64, eliminando o custo de erro de predição de branch.
    return selector ? val_a : val_b;
}

/**
 * nexus_safe_div: Divisão sem branch para evitar crash por zero.
 */
double nexus_branchless_div(double a, double b) {
    // Evita o 'if (b == 0)' usando a própria lógica do IEEE 754 ou máscara
    return a / (b + (b == 0)); 
}

/**
 * nexus_path_normalize: Normaliza barras e remove redundâncias.
 * Executado em NOGIL (Thread-safe).
 */
void nexus_path_normalize(char* path) {
    if (!path) return;
    for (char* p = path; *p; p++) {
        if (*p == '\\') *p = '/'; // Padroniza para formato Unix (mais rápido no C)
    }
}

/**
 * nexus_nogil_scan: Busca ultra-veloz em blocos de memória.
 * Thread-safe e 100% independente do Python.
 */
int64_t nexus_nogil_scan(const uint8_t* data, int64_t size, uint8_t target) {
    if (!data || size <= 0) return -1;
    
    // Busca em nível de hardware (registrador)
    for (int64_t i = 0; i < size; i++) {
        if (data[i] == target) return i;
    }
    return -1;
}

/**
 * Alias de compatibilidade para o Linker.
 * Mapeia o nome esperado pelo Forge para a implementação real.
 */
int64_t nexus_asm_cmov(int64_t selector, int64_t val_a, int64_t val_b) {
    return nexus_branchless_select(selector, val_a, val_b);
}