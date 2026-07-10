// doxoade/tools/hermes_systems/native/hermes_hbc6_patches.h
#pragma once
#include <Python.h>
#include <stdint.h>

#pragma pack(push, 1) // 🚀 GARANTE 12 BYTES EXATOS NO DISCO E NA RAM
typedef struct {
    uint32_t co_index;
    uint32_t offset;
    uint16_t token_id;
    uint16_t orig_ngram_len;
} HBC6_Patch;
#pragma pack(pop)

typedef struct {
    HBC6_Patch* patches;
    uint32_t patch_count;
    const uint8_t* payload_ptr;
    uint32_t payload_size;
} HBC6Context;

// Protótipos
int hermes_parse_hbc6_header(const uint8_t* data, size_t data_size, HBC6Context* ctx);
void hermes_free_hbc6_context(HBC6Context* ctx);
PyObject* hermes_apply_hbc6_patches(PyObject* code_obj, HBC6_Patch* patches, int patch_count);
