// doxoade/tools/hermes_systems/native/hermes_hbc5_parser.c
#include <Python.h>   // 🚀 ADICIONE ESTA LINHA
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

// ═══════════════════════════════════════════════════════════════════════════════
// ESTRUTURAS DE DADOS
// ═══════════════════════════════════════════════════════════════════════════════
typedef struct {
    char* buffer;
    char** pointers;
    uint16_t* lengths;
    uint16_t count;
} HermesDict;

typedef struct {
    uint8_t flags;
    uint8_t bitmap[32];
    HermesDict local_dict;
    const uint8_t* payload_ptr;
    uint32_t payload_size;
    size_t header_size;
} HBC5Context;

#define READ_U16(p) ((uint16_t)((p)[0] | ((p)[1] << 8)))
#define READ_U32(p) ((uint32_t)((p)[0] | ((p)[1] << 8) | ((p)[2] << 16) | ((p)[3] << 24)))

// ═══════════════════════════════════════════════════════════════════════════════
// MOTOR DE PARSE HBC5 (COM DIAGNÓSTICO DE FALHA)
// ═══════════════════════════════════════════════════════════════════════════════

int parse_hbc5_header(const uint8_t* data, size_t data_size, HBC5Context* ctx) {
    // 1. Validação de Tamanho Mínimo
    if (!data || data_size < 44 || !ctx) {
        fprintf(stderr, "[HERMES-C-ERR] Falha: data_size (%zu) < 44 bytes ou ctx nulo.\n", data_size);
        return -1;
    }

    // 2. Validação de Magic ("HBC5")
    if (data[0] != 'H' || data[1] != 'B' || data[2] != 'C' || data[3] != '5') {
        fprintf(stderr, "[HERMES-C-ERR] Magic Inválido: Esperado 'HBC5', Lido '%c%c%c%c' (0x%02x%02x%02x%02x)\n", 
                data[0], data[1], data[2], data[3], data[0], data[1], data[2], data[3]);
        return -1;
    }
    
    size_t offset = 4;
    
    // 3. Validação de Version (0x05)
    uint8_t version = data[offset];
    if (version != 0x05) {
        fprintf(stderr, "[HERMES-C-ERR] Version Inválida: Esperado 0x05, Lido 0x%02x\n", version);
        return -1;
    }
    offset += 1;

    // 4. Extraindo Flags
    ctx->flags = data[offset];
    offset += 1;

    // 5. Lendo Token Count
    if (offset + 2 > data_size) {
        fprintf(stderr, "[HERMES-C-ERR] Truncado ao ler Token Count (offset %zu)\n", offset);
        return -1;
    }
    uint16_t token_count = READ_U16(&data[offset]);
    offset += 2;
    ctx->local_dict.count = token_count;

    // 6. Extraindo Bitmap (32 bytes)
    if (offset + 32 > data_size) {
        fprintf(stderr, "[HERMES-C-ERR] Truncado ao ler Bitmap (offset %zu)\n", offset);
        return -1;
    }
    memcpy(ctx->bitmap, &data[offset], 32);
    offset += 32;

    // ═══════════════════════════════════════════════════════════════════════════
    // 7. ESTRATÉGIA TWO-PASS (Com Diagnóstico de Loop)
    // ═══════════════════════════════════════════════════════════════════════════
    
    size_t total_pattern_size = 0;
    size_t temp_offset = offset;
    
    for (uint16_t i = 0; i < token_count; i++) {
        if (temp_offset + 4 > data_size) {
            fprintf(stderr, "[HERMES-C-ERR] Truncado no loop de tokens (Passo 1). Index: %u, Offset: %zu, Size: %zu\n", 
                    i, temp_offset, data_size);
            return -1;
        }
        uint16_t plen = READ_U16(&data[temp_offset + 2]); 
        total_pattern_size += plen;
        temp_offset += 4 + plen;
    }

    if (total_pattern_size > 0) {
        ctx->local_dict.buffer = (char*)malloc(total_pattern_size);
        if (!ctx->local_dict.buffer) {
            fprintf(stderr, "[HERMES-C-ERR] Falha no malloc do buffer de tokens (%zu bytes)\n", total_pattern_size);
            return -1;
        }
    } else {
        ctx->local_dict.buffer = NULL;
    }

    if (token_count > 0) {
        ctx->local_dict.pointers = (char**)malloc(token_count * sizeof(char*));
        ctx->local_dict.lengths = (uint16_t*)malloc(token_count * sizeof(uint16_t));
        if (!ctx->local_dict.pointers || !ctx->local_dict.lengths) {
            fprintf(stderr, "[HERMES-C-ERR] Falha no malloc dos arrays de ponteiros\n");
            free(ctx->local_dict.buffer);
            return -1;
        }
    } else {
        ctx->local_dict.pointers = NULL;
        ctx->local_dict.lengths = NULL;
    }

    char* current_buffer_pos = ctx->local_dict.buffer;
    
    for (uint16_t i = 0; i < token_count; i++) {
        if (offset + 4 > data_size) {
            fprintf(stderr, "[HERMES-C-ERR] Truncado no loop de tokens (Passo 2). Index: %u, Offset: %zu\n", i, offset);
            goto cleanup_error;
        }
        
        uint16_t plen = READ_U16(&data[offset + 2]);
        offset += 4;
        
        if (offset + plen > data_size) {
            fprintf(stderr, "[HERMES-C-ERR] Pattern excede tamanho do arquivo. Index: %u, Offset: %zu, Plen: %u\n", 
                    i, offset, plen);
            goto cleanup_error;
        }
        
        memcpy(current_buffer_pos, &data[offset], plen);
        
        ctx->local_dict.pointers[i] = current_buffer_pos;
        ctx->local_dict.lengths[i] = plen;
        
        current_buffer_pos += plen;
        offset += plen;
    }

    // 8. Extraindo o Payload (Marshalled Bytecode)
    if (offset + 4 > data_size) {
        fprintf(stderr, "[HERMES-C-ERR] Truncado ao ler tamanho do Payload (offset %zu)\n", offset);
        goto cleanup_error;
    }
    
    ctx->payload_size = READ_U32(&data[offset]);
    offset += 4;
    
    if (offset + ctx->payload_size > data_size) {
        fprintf(stderr, "[HERMES-C-ERR] Payload excede tamanho do arquivo. Offset: %zu, PayloadSize: %u, FileSize: %zu\n", 
                offset, ctx->payload_size, data_size);
        goto cleanup_error;
    }
    
    ctx->payload_ptr = &data[offset];
    ctx->header_size = offset;

    return 0; // SUCESSO

cleanup_error:
    if (ctx->local_dict.buffer) free(ctx->local_dict.buffer);
    if (ctx->local_dict.pointers) free(ctx->local_dict.pointers);
    if (ctx->local_dict.lengths) free(ctx->local_dict.lengths);
    return -1;
}

void free_hbc5_context(HBC5Context* ctx) {
    if (ctx->local_dict.buffer) free(ctx->local_dict.buffer);
    if (ctx->local_dict.pointers) free(ctx->local_dict.pointers);
    if (ctx->local_dict.lengths) free(ctx->local_dict.lengths);
    memset(ctx, 0, sizeof(HBC5Context));
}

// ═══════════════════════════════════════════════════════════════════
// MOTOR BRANCHLESS (Expansão de Strings - Local Dict HBC5)
// ═══════════════════════════════════════════════════════════════════
static inline void get_pattern_data(uint16_t token, const HermesDict* l_dict,
                                    char** out_ptr, int* out_len) {
    uint16_t index = token - 0x80;
    *out_ptr = l_dict->pointers[index];
    *out_len = l_dict->lengths[index];
}

static size_t calculate_expanded_size(const char* src, size_t src_len,
                                      const uint8_t* bitmap, const HermesDict* l_dict) {
    size_t final_size = 0;
    for (size_t i = 0; i < src_len; i++) {
        uint8_t c = (uint8_t)src[i];
        int has_tok = (bitmap[c >> 3] >> (c & 7)) & 1;
        if (has_tok && c >= 0x80) {
            char* p; int l;
            get_pattern_data(c, l_dict, &p, &l);
            final_size += l;
        } else {
            final_size += 1;
        }
    }
    return final_size;
}

static void expand_string(const char* src, size_t src_len, char* dst,
                          const uint8_t* bitmap, const HermesDict* l_dict) {
    char* out = dst;
    for (size_t i = 0; i < src_len; i++) {
        uint8_t c = (uint8_t)src[i];
        int has_tok = (bitmap[c >> 3] >> (c & 7)) & 1;
        if (has_tok && c >= 0x80) {
            char* p; int l;
            get_pattern_data(c, l_dict, &p, &l);
            memcpy(out, p, l);
            out += l;
        } else {
            *out++ = c;
        }
    }
}

// 🚀 CRÍTICO: NÃO PODE SER static, senão o linker não consegue achar!
int walk_and_decode_inplace(PyObject* code_obj, const uint8_t* bitmap, const HermesDict* l_dict) {
    if (!PyCode_Check(code_obj)) return 0;
    
    PyObject* co_consts = PyObject_GetAttrString(code_obj, "co_consts");
    if (!co_consts || !PyTuple_Check(co_consts)) { Py_XDECREF(co_consts); return -1; }
    
    Py_ssize_t n = PyTuple_Size(co_consts);
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject* item = PyTuple_GetItem(co_consts, i);
        if (PyUnicode_Check(item)) {
            Py_ssize_t len;
            const char* s = PyUnicode_AsUTF8AndSize(item, &len);
            if (!s) { Py_DECREF(co_consts); return -1; }
            
            int needs_decode = 0;
            for (Py_ssize_t k = 0; k < len; k++) {
                uint8_t c = (uint8_t)s[k];
                if (c >= 0x80 && (bitmap[c >> 3] >> (c & 7)) & 1) { needs_decode = 1; break; }
            }
            
            if (needs_decode) {
                size_t final_size = calculate_expanded_size(s, len, bitmap, l_dict);
                char* buffer = (char*)malloc(final_size + 1);
                if (!buffer) { Py_DECREF(co_consts); return -1; }
                
                expand_string(s, len, buffer, bitmap, l_dict);
                buffer[final_size] = '\0';
                
                PyObject* new_str = PyUnicode_DecodeUTF8(buffer, final_size, "strict");
                free(buffer);
                if (!new_str) { Py_DECREF(co_consts); return -1; }
                
                Py_DECREF(item);
                PyTuple_SetItem(co_consts, i, new_str);
            }
        } else if (PyCode_Check(item)) {
            if (walk_and_decode_inplace(item, bitmap, l_dict) != 0) { Py_DECREF(co_consts); return -1; }
        }
    }
    Py_DECREF(co_consts);
    return 0;
}