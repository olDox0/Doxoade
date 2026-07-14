// doxoade/tools/hermes_systems/native/hermes_hbc5_parser.c
#include <Python.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

// ═══════════════════════════════════════════════════════════════════
// ESTRUTURAS DE DADOS
// ═══════════════════════════════════════════════════════════════════
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

// ═══════════════════════════════════════════════════════════════════
// BUFFER POOL GLOBAL (Reutilização de Memória)
// ═══════════════════════════════════════════════════════════════════
#define POOL_MAX_TOKENS 2048
#define POOL_MAX_BUFFER_SIZE (1024 * 1024)  // 1MB

typedef struct {
    char* buffer;
    char** pointers;
    uint16_t* lengths;
    uint16_t count;
    size_t buffer_offset;
    uint16_t capacity;  // ← ADICIONADO
    uint16_t used;      // ← ADICIONADO
    int initialized;
} HBC5_BufferPool;

static HBC5_BufferPool g_pool = {0};

// Inicializa o pool uma única vez
static void init_buffer_pool(void) {
    if (g_pool.initialized) return;
    
    g_pool.buffer = (char*)malloc(POOL_MAX_BUFFER_SIZE);
    g_pool.pointers = (char**)malloc(POOL_MAX_TOKENS * sizeof(char*));
    g_pool.lengths = (uint16_t*)malloc(POOL_MAX_TOKENS * sizeof(uint16_t));
    g_pool.capacity = POOL_MAX_TOKENS;
    g_pool.used = 0;
    g_pool.buffer_offset = 0;
    g_pool.initialized = 1;
}

// Reseta o pool (não libera memória, só marca como disponível)
static void reset_buffer_pool(void) {
    g_pool.used = 0;
    g_pool.buffer_offset = 0;
}

// ═══════════════════════════════════════════════════════════════════
// PARSE HBC5 COM BUFFER POOL (Zero-Allocation no Loop Crítico)
// ═══════════════════════════════════════════════════════════════════
int parse_hbc5_header(const uint8_t* data, size_t data_size, HBC5Context* ctx) {
    // Validação de tamanho mínimo
    if (!data || data_size < 44 || !ctx) return -1;
    
    // Validação de Magic ("HBC5")
    if (memcmp(data, "HBC5", 4) != 0) return -1;
    
    // Inicializa o pool se necessário
    init_buffer_pool();
    
    // Reseta o pool para este parse
    reset_buffer_pool();
    
    size_t offset = 4;
    
    // Version
    uint8_t version = data[offset];
    if (version != 0x05) return -1;
    offset += 1;
    
    // Flags
    ctx->flags = data[offset];
    offset += 1;
    
    // Token Count
    uint16_t token_count = READ_U16(&data[offset]);
    offset += 2;
    
    // Bitmap (32 bytes)
    memcpy(ctx->bitmap, &data[offset], 32);
    offset += 32;
    
    // ═══════════════════════════════════════════════════════════════════
    // LEITURA DE TOKENS (Usando Buffer Pool)
    // ═══════════════════════════════════════════════════════════════════
    if (token_count > g_pool.capacity) {
        fprintf(stderr, "[HERMES-C-ERR] Token count (%u) excede pool capacity (%u)\n", 
                token_count, g_pool.capacity);
        return -1;
    }
    
    // Lê todos os tokens em um único loop (sem malloc individual)
    size_t buffer_offset = 0;
    for (uint16_t i = 0; i < token_count; i++) {
        if (offset + 4 > data_size) return -1;
        
        uint16_t plen = READ_U16(&data[offset + 2]);
        offset += 4;
        
        if (offset + plen > data_size) return -1;
        
        // Copia o token para o buffer pool
        if (buffer_offset + plen > POOL_MAX_BUFFER_SIZE) {
            fprintf(stderr, "[HERMES-C-ERR] Buffer pool overflow\n");
            return -1;
        }
        
        memcpy(&g_pool.buffer[buffer_offset], &data[offset], plen);
        g_pool.pointers[i] = &g_pool.buffer[buffer_offset];
        g_pool.lengths[i] = plen;
        
        buffer_offset += plen;
        offset += plen;
    }
    
    // Payload
    if (offset + 4 > data_size) return -1;
    uint32_t payload_size = READ_U32(&data[offset]);
    offset += 4;
    
    if (offset + payload_size > data_size) return -1;
    
    ctx->payload_ptr = &data[offset];
    ctx->payload_size = payload_size;
    ctx->header_size = offset;
    
    // Configura o dicionário local para usar o pool
    ctx->local_dict.buffer = g_pool.buffer;
    ctx->local_dict.pointers = g_pool.pointers;
    ctx->local_dict.lengths = g_pool.lengths;
    ctx->local_dict.count = token_count;
    
    return 0;
}

// ═══════════════════════════════════════════════════════════════════
// FREE CONTEXT (Não libera o pool, só limpa referências)
// ═══════════════════════════════════════════════════════════════════
void free_hbc5_context(HBC5Context* ctx) {
    if (!ctx) return;
    
    // Não libera o pool (é global e reutilizável)
    // Só limpa as referências no contexto
    ctx->local_dict.buffer = NULL;
    ctx->local_dict.pointers = NULL;
    ctx->local_dict.lengths = NULL;
    ctx->local_dict.count = 0;
    ctx->payload_ptr = NULL;
    ctx->payload_size = 0;
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

PyObject* walk_and_decode_inplace(PyObject* code_obj, const uint8_t* bitmap, const HermesDict* l_dict) {
    if (!PyCode_Check(code_obj)) return code_obj;
    
    PyObject* co_consts = PyObject_GetAttrString(code_obj, "co_consts");
    if (!co_consts || !PyTuple_Check(co_consts)) {
        Py_XDECREF(co_consts);
        Py_INCREF(code_obj);
        return code_obj;
    }
    
    Py_ssize_t n = PyTuple_Size(co_consts);
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject* item = PyTuple_GetItem(co_consts, i);
        if (PyUnicode_Check(item)) {
            Py_ssize_t len;
            const char* s = PyUnicode_AsUTF8AndSize(item, &len);
            if (!s) continue;
            
            int needs_decode = 0;
            for (Py_ssize_t k = 0; k < len; k++) {
                uint8_t c = (uint8_t)s[k];
                if (c >= 0x80 && (bitmap[c >> 3] >> (c & 7)) & 1) {
                    needs_decode = 1;
                    break;
                }
            }
            
            if (needs_decode) {
                size_t final_size = calculate_expanded_size(s, len, bitmap, l_dict);
                char* buffer = (char*)malloc(final_size + 1);
                if (!buffer) continue;
                
                expand_string(s, len, buffer, bitmap, l_dict);
                buffer[final_size] = '\0';
                
                PyObject* new_str = PyUnicode_DecodeUTF8(buffer, final_size, "strict");
                free(buffer);
                
                if (new_str) {
                    PyTuple_SetItem(co_consts, i, new_str);
                }
            }
        } else if (PyCode_Check(item)) {
            PyObject* processed = walk_and_decode_inplace(item, bitmap, l_dict);
            if (processed != item) {
                PyTuple_SetItem(co_consts, i, processed);
            }
        }
    }
    
    Py_DECREF(co_consts);
    
    // Retorna o code_obj original (não cria novo)
    Py_INCREF(code_obj);
    return code_obj;
}