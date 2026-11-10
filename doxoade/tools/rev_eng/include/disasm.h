#ifndef DISASM_H
#define DISASM_H

#include "file_reader.h"
#include "decoder.h"
#include "decoder_backend.h"
#include "pre_ir.h"

typedef enum {
    CF_NONE = 0, CF_JMP, CF_JCC, CF_CALL, CF_RET,
} ControlFlowType;

typedef struct {
    uint32_t    count;
    DecodedInsn *insns;
} InsnList;

int disasm_collect(const FileReader *fr, uint64_t offset, uint64_t length,
                   uint64_t va_base, DecoderBackend backend,
                   InsnList *out, char *err_buf, size_t err_buf_size);

ControlFlowType insn_control_flow(const DecodedInsn *insn, uint64_t *target_va);

int disasm_range(const FileReader *fr, uint64_t offset, uint64_t length,
                 uint64_t va_base, DecoderBackend backend, const PreIR *ir,
                 FILE *out, char *err_buf, size_t err_buf_size);

int disasm_text_section(const FileReader *fr, const PreIR *ir,
                        DecoderBackend backend,
                        FILE *out, char *err_buf, size_t err_buf_size);

#endif
