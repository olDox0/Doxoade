// doxoade/tools/vulcan/native/mercury_core.c
/*
 * Mercury Core Engine v3.1 — DLL Pura (Zero Python.h)
 * CORREÇÃO: Parse correto do cabeçalho HBD1 (token_count já vem no header).
 */
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

#ifdef _WIN32
    #define MERCURY_EXPORT __declspec(dllexport)
#else
    #define MERCURY_EXPORT __attribute__((visibility("default")))
#endif

typedef struct {
    char* buffer;
    char* pointers[256];
    int   lengths[256];
    int   count;
} TokenDictionary;

/* CORREÇÃO: tk_count agora é passado como argumento, pois já está no header HBD1 */
static int load_dictionary_contiguous(
    const uint8_t* data,
    size_t         data_size,
    size_t*        offset,
    uint16_t       tk_count,
    TokenDictionary* dict
) {
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

MERCURY_EXPORT char* mercury_decode_hbd1(
    const char* input_data,
    size_t      input_size,
    size_t*     out_size
) {
    if (!input_data || input_size < 11 || !out_size) return NULL;
    const uint8_t* data = (const uint8_t*)input_data;
    
    /* Validação do magic */
    if (memcmp(data, "HBD1", 4) != 0) return NULL;
    
    /* Parse header HBD1 (Corrigido) */
    uint16_t tk_count = (uint16_t)(data[5] | (data[6] << 8));
    uint32_t orig_sz  = (uint32_t)(data[7] | (data[8] << 8) | (data[9] << 16) | (data[10] << 24));
    
    /* Carrega dicionário contíguo (inicia no offset 11) */
    size_t offset = 11;
    TokenDictionary dict;
    if (load_dictionary_contiguous(data, input_size, &offset, tk_count, &dict) != 0) {
        return NULL; // Falha ao carregar dicionário
    }

    /* Lê payload_size */
    if (offset + 4 > input_size) {
        free_dictionary(&dict);
        return NULL;
    }
    uint32_t payload_size = (uint32_t)(data[offset] | (data[offset+1] << 8) |
                                       (data[offset+2] << 16) | (data[offset+3] << 24));
    offset += 4;

    if (offset + payload_size > input_size) {
        free_dictionary(&dict);
        return NULL;
    }

    /* Pré-aloca buffer de saída */
    char* out_buf = (char*)malloc(orig_sz > 0 ? orig_sz + 1 : 1);
    if (!out_buf) {
        free_dictionary(&dict);
        return NULL;
    }

    /* Loop de expansão (Branchless-ish) */
    const uint8_t* payload = data + offset;
    size_t out_pos = 0;
    size_t i = 0;
    while (i < payload_size) {
        uint8_t c = payload[i];
        if (c == 0xFF && i + 1 < payload_size) {
            uint8_t idx = payload[i+1];
            if (idx < dict.count) {
                size_t tok_len = dict.lengths[idx];
                /* 🛡️ Proteção contra buffer overflow em caso de payload corrompido */
                if (out_pos + tok_len > orig_sz) {
                    free(out_buf);
                    free_dictionary(&dict);
                    return NULL; 
                }
                memcpy(out_buf + out_pos, dict.pointers[idx], tok_len);
                out_pos += tok_len;
                i += 2;
                continue;
            }
        }
        /* 🛡️ Proteção contra buffer overflow */
        if (out_pos + 1 > orig_sz) {
            free(out_buf);
            free_dictionary(&dict);
            return NULL; 
        }
        out_buf[out_pos++] = c;
        i++;
    }
    out_buf[out_pos] = '\0';
    *out_size = out_pos;

    free_dictionary(&dict);
    return out_buf;
}

MERCURY_EXPORT void mercury_free(void* ptr) {
    if (ptr) free(ptr);
}

MERCURY_EXPORT const char* mercury_version() {
    return "Mercury Core Engine v3.1 (HBD1 Fix)";
}