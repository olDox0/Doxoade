// doxoade/tools/hermes_systems/native/hermes_hbc6_patches.c
#include <Python.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include "hermes_hbc6_patches.h"

#define HBC6_LOG(fmt, ...) fprintf(stderr, "[HERMES-C:HBC6] " fmt "\n", ##__VA_ARGS__)

// ═══════════════════════════════════════════════════════════════════
// WALKER DFS (Modo Empacotador - Carregamento Intacto)
// ═══════════════════════════════════════════════════════════════════
static PyObject* apply_hbc6_patches_recursive(
    PyObject* code_obj, 
    HBC6_Patch* patches, 
    int patch_count, 
    int* current_dfs_index
) {
    if (!PyCode_Check(code_obj)) {
        Py_INCREF(code_obj);
        return code_obj;
    }

    int my_index = (*current_dfs_index)++;
    HBC6_LOG("DFS visiting CodeObject index %d (Size: %zd bytes)", my_index, PyBytes_Size(PyObject_GetAttrString(code_obj, "co_code")));

    // 🛡️ MODO EMPACOTADOR: Apenas traversa a árvore DFS para telemetria.
    // A injeção de NOPs foi desativada devido ao Py_FatalError (Stack Effect Mismatch) do CPython 3.11+.
    
    PyObject* final_code_obj = code_obj;
    Py_INCREF(final_code_obj);

    // RECURSÃO DFS (Processa as funções aninhadas em co_consts)
    PyObject* co_consts = PyObject_GetAttrString(final_code_obj, "co_consts");
    if (co_consts && PyTuple_Check(co_consts)) {
        Py_ssize_t n = PyTuple_Size(co_consts);
        int changed = 0;
        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject* item = PyTuple_GetItem(co_consts, i);
            if (PyCode_Check(item)) {
                PyObject* patched_child = apply_hbc6_patches_recursive(
                    item, patches, patch_count, current_dfs_index
                );
                if (patched_child != item) {
                    if (PyTuple_SetItem(co_consts, i, patched_child) < 0) {
                        Py_DECREF(patched_child); 
                    } else {
                        changed = 1;
                    }
                }
            }
        }
        // Como não modificamos os filhos, 'changed' será 0, mas a traversa prova que o DFS funciona.
    }
    Py_XDECREF(co_consts);

    return final_code_obj;
}

// ═══════════════════════════════════════════════════════════════════
// API PÚBLICA
// ═══════════════════════════════════════════════════════════════════
PyObject* hermes_apply_hbc6_patches(PyObject* code_obj, HBC6_Patch* patches, int patch_count) {
    HBC6_LOG("=== STARTING HBC6 PATCH ENGINE (Packager Mode) ===");
    HBC6_LOG("Total patches mapped in HRT: %d", patch_count);
    
    Py_INCREF(code_obj);
    int dfs_index = 0;
    PyObject* result = apply_hbc6_patches_recursive(code_obj, patches, patch_count, &dfs_index);
    Py_DECREF(code_obj);
    
    HBC6_LOG("=== HBC6 PATCH ENGINE COMPLETE (CodeObject Intacto) ===");
    return result;
}

// ═══════════════════════════════════════════════════════════════════
// PARSER HBC6 (Header)
// ═══════════════════════════════════════════════════════════════════
#define READ_U16(p) ((uint16_t)((p)[0] | ((p)[1] << 8)))
#define READ_U32(p) ((uint32_t)((p)[0] | ((p)[1] << 8) | ((p)[2] << 16) | ((p)[3] << 24)))

int hermes_parse_hbc6_header(const uint8_t* data, size_t data_size, HBC6Context* ctx) {
    if (!data || data_size < 9 || !ctx) return -1;
    if (memcmp(data, "HBC6", 4) != 0) return -1;

    uint8_t version = data[4];
    if (version != 0x06) return -1;

    size_t offset = 5;
    if (offset + 4 > data_size) return -1;
    
    uint32_t hrt_size = READ_U32(&data[offset]); offset += 4;
    if (hrt_size % 12 != 0) return -1;
    
    ctx->patch_count = hrt_size / 12;
    if (offset + hrt_size > data_size) return -1;

    if (ctx->patch_count > 0) {
        ctx->patches = (HBC6_Patch*)malloc(hrt_size);
        if (!ctx->patches) return -1;
        for (uint32_t i = 0; i < ctx->patch_count; i++) {
            ctx->patches[i].co_index      = READ_U32(&data[offset]); offset += 4;
            ctx->patches[i].offset        = READ_U32(&data[offset]); offset += 4;
            ctx->patches[i].token_id      = READ_U16(&data[offset]); offset += 2;
            ctx->patches[i].orig_ngram_len= READ_U16(&data[offset]); offset += 2;
        }
    } else {
        ctx->patches = NULL;
    }

    if (offset + 4 > data_size) return -1;
    ctx->payload_size = READ_U32(&data[offset]); offset += 4;
    if (offset + ctx->payload_size > data_size) return -1;
    ctx->payload_ptr = &data[offset];

    return 0;
}

void hermes_free_hbc6_context(HBC6Context* ctx) {
    if (ctx && ctx->patches) {
        free(ctx->patches);
        ctx->patches = NULL;
    }
}