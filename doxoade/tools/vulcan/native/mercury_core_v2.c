// doxoade/tools/vulcan/native/mercury_core.c
/*
 * Mercury Core Engine v3.0 — DLL Pura (Zero Python.h)
 * ====================================================
 * Estratégia: Compilar como DLL independente, carregar via ctypes.
 *
 * Vantagens:
 *   - Zero dependência de Python.h
 *   - Funciona com qualquer compilador (GCC/MinGW, MSVC, Clang)
 *   - Performance máxima (zero overhead PyObject)
 *   - Reutilizável em qualquer linguagem
 *
 * Otimizações aplicadas (herdadas do v2):
 *   1. Buffer contíguo para tokens (elimina N mallocs no loop)
 *   2. Branchless expansion
 *   3. Pointer chasing otimizado
 *
 * Formato HBD1 (compatível com hermes_data.py):
 *   [4B] Magic: "HBD1"
 *   [1B] Version: 0x01
 *   [2B] token_count (uint16)
 *   [4B] orig_size (uint32) — tamanho original descompactado
 *   [N×] tokens: [2B len][len bytes pattern]
 *   [4B] payload_size (uint32)
 *   [payload_size B] payload comprimido
 *
 * Compilação:
 *   gcc -O3 -shared -static-libgcc -fPIC -march=westmere -msse4.2 \
 *       mercury_core.c -o mercury_core.dll
 */

#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

/* ═══════════════════════════════════════════════════════════════════════
 * EXPORT MACROS (Windows/Linux)
 * ═══════════════════════════════════════════════════════════════════════ */
#ifdef _WIN32
    #define MERCURY_EXPORT __declspec(dllexport)
#else
    #define MERCURY_EXPORT __attribute__((visibility("default")))
#endif

/* ═══════════════════════════════════════════════════════════════════════
 * ESTRUTURA DE TOKENS (Buffer Contíguo — Zero malloc no loop)
 * ═══════════════════════════════════════════════════════════════════════ */
typedef struct {
    char* buffer;           // Buffer único para todos os tokens
    char* pointers[256];    // Apenas ponteiros (não strings alocadas)
    int   lengths[256];     // Tamanhos dos tokens
    int   count;            // Número de tokens carregados
} TokenDictionary;

/* ═══════════════════════════════════════════════════════════════════════
 * CARREGA DICIONÁRIO DE TOKENS (Buffer Contíguo)
 * ═══════════════════════════════════════════════════════════════════════ */
static int load_dictionary_contiguous(
    const uint8_t* data,
    size_t         data_size,
    size_t*        offset,
    TokenDictionary* dict
) {
    if (*offset + 2 > data_size) return -1;

    uint16_t tk_count = (uint16_t)(data[*offset] | (data[*offset + 1] << 8));
    *offset += 2;

    if (tk_count > 254) return -1;

    /* 1ª passada: calcula tamanho total necessário */
    size_t total_token_size = 0;
    size_t temp_offset = *offset;
    for (int i = 0; i < tk_count; i++) {
        if (temp_offset + 2 > data_size) return -1;
        uint16_t plen = (uint16_t)(data[temp_offset] | (data[temp_offset + 1] << 8));
        temp_offset += 2 + plen;
        total_token_size += plen;
    }

    /* Aloca UM buffer contíguo para todos os tokens */
    dict->buffer = (char*)malloc(total_token_size > 0 ? total_token_size : 1);
    if (!dict->buffer) return -1;

    dict->count = tk_count;
    char* current = dict->buffer;

    /* 2ª passada: preenche ponteiros (sem malloc individual!) */
    for (int i = 0; i < tk_count; i++) {
        if (*offset + 2 > data_size) {
            free(dict->buffer);
            dict->buffer = NULL;
            return -1;
        }
        uint16_t plen = (uint16_t)(data[*offset] | (data[*offset + 1] << 8));
        *offset += 2;

        if (*offset + plen > data_size) {
            free(dict->buffer);
            dict->buffer = NULL;
            return -1;
        }

        memcpy(current, data + *offset, plen);
        dict->pointers[i] = current;
        dict->lengths[i]  = plen;
        current += plen;
        *offset += plen;
    }

    return 0;
}

static void free_dictionary(TokenDictionary* dict) {
    if (dict->buffer) {
        free(dict->buffer);
        dict->buffer = NULL;
    }
}

/* ═══════════════════════════════════════════════════════════════════════
 * DECODE PRINCIPAL (HBD1 → UTF-8 string)
 *
 * Retorna: buffer alocado com a string descompactada (caller deve free)
 *          ou NULL em caso de erro.
 *          *out_size recebe o tamanho da string (sem o null terminator).
 * ═══════════════════════════════════════════════════════════════════════ */
MERCURY_EXPORT char* mercury_decode_hbd1(
    const char* input_data,
    size_t      input_size,
    size_t*     out_size
) {
    if (!input_data || input_size < 11 || !out_size) return NULL;

    const uint8_t* data = (const uint8_t*)input_data;

    /* Validação do magic */
    if (memcmp(data, "HBD1", 4) != 0) return NULL;

    /* Parse header mínimo */
    /* uint8_t version = data[4]; */  /* reservado */
    /* token_count em data[5..6] */

    /* Tamanho original (informativo, usamos para pré-alocar) */
    uint32_t orig_sz = (uint32_t)(data[7]  | (data[8]  << 8) |
                                  (data[9]  << 16) | (data[10] << 16) << 8);

    /* Carrega dicionário contíguo */
    TokenDictionary dict = {0};
    size_t offset = 11;

    if (load_dictionary_contiguous(data, input_size, &offset, &dict) != 0) {
        return NULL;
    }

    /* Validação do payload */
    if (offset + 4 > input_size) {
        free_dictionary(&dict);
        return NULL;
    }

    uint32_t payload_sz = (uint32_t)(data[offset]      | (data[offset + 1] << 8) |
                                     (data[offset + 2] << 16) | (data[offset + 3] << 24));
    offset += 4;

    if (offset + payload_sz > input_size) {
        free_dictionary(&dict);
        return NULL;
    }

    /* Pré-aloca buffer de saída (usa orig_sz se disponível, senão estima) */
    size_t out_cap = (orig_sz > 0) ? (orig_sz + 1) : (payload_sz * 4 + 1);
    char* out = (char*)malloc(out_cap);
    if (!out) {
        free_dictionary(&dict);
        return NULL;
    }

    /* ═══════════════════════════════════════════════════════════════════
     * EXPANSÃO BRANCHLESS (Pointer Chasing Otimizado)
     * ═══════════════════════════════════════════════════════════════════ */
    char*              dst = out;
    const uint8_t*     src = data + offset;
    const uint8_t*     end = src + payload_sz;
    char*              out_end = out + out_cap;

    while (src < end) {
        uint8_t c = *src++;

        if (c == 0xFF) {
            /* Token escape: próximo byte é o token ID */
            if (src < end) {
                uint8_t tid = *src++;
                if (tid < dict.count) {
                    int len = dict.lengths[tid];
                    /* Expande buffer se necessário (raro, mas seguro) */
                    if (dst + len > out_end) {
                        size_t new_cap = out_cap * 2;
                        char* new_buf = (char*)realloc(out, new_cap);
                        if (!new_buf) {
                            free(out);
                            free_dictionary(&dict);
                            return NULL;
                        }
                        dst = new_buf + (dst - out);
                        out_end = new_buf + new_cap;
                        out = new_buf;
                        out_cap = new_cap;
                    }
                    memcpy(dst, dict.pointers[tid], len);
                    dst += len;
                }
            }
        } else {
            /* Caractere literal */
            if (dst + 1 > out_end) {
                size_t new_cap = out_cap * 2;
                char* new_buf = (char*)realloc(out, new_cap);
                if (!new_buf) {
                    free(out);
                    free_dictionary(&dict);
                    return NULL;
                }
                dst = new_buf + (dst - out);
                out_end = new_buf + new_cap;
                out = new_buf;
                out_cap = new_cap;
            }
            *dst++ = (char)c;
        }
    }

    *dst = '\0';
    *out_size = (size_t)(dst - out);

    free_dictionary(&dict);
    return out;
}

/* ═══════════════════════════════════════════════════════════════════════
 * FREE (caller deve liberar o buffer retornado por mercury_decode_hbd1)
 * ═══════════════════════════════════════════════════════════════════════ */
MERCURY_EXPORT void mercury_free(void* ptr) {
    if (ptr) free(ptr);
}

/* ═══════════════════════════════════════════════════════════════════════
 * VERSION INFO
 * ═══════════════════════════════════════════════════════════════════════ */
MERCURY_EXPORT const char* mercury_version(void) {
    return "Mercury Core Engine v3.0 (DLL Pura — Zero Python.h — Branchless)";
}