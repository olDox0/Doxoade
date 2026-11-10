#ifndef DECODER_H
#define DECODER_H

#include "file_reader.h"
#include <stdint.h>
#include <stddef.h>

typedef enum {
    OP_NONE = 0,
    OP_EB, OP_EW, OP_ED, OP_EQ, OP_EV,
    OP_GB, OP_GW, OP_GD, OP_GQ, OP_GV,
    OP_IB, OP_IW, OP_ID, OP_IQ, OP_IZ,
    OP_JB, OP_JZ,
    OP_AL, OP_CL, OP_DL, OP_BL,
    OP_AX, OP_CX, OP_DX,
    OP_EAX, OP_ECX, OP_EDX, OP_RAX,
    OP_1,
    OP_MB, OP_MW, OP_MD, OP_MQ,
} OperandType;

typedef struct {
    uint64_t offset;
    uint64_t va;
    char     mnemonic[32];
    char     op_str[128];
    uint8_t  length;
    uint8_t  prefix_lock;
    uint8_t  prefix_rep;
    uint8_t  prefix_seg;
    uint8_t  prefix_opsize;
    uint8_t  prefix_addrsize;
    uint8_t  rex;
    uint16_t opcode;
    uint8_t  opcode_len;
    uint8_t  modrm;
    uint8_t  mod;
    uint8_t  reg;
    uint8_t  rm;
    uint8_t  sib;
    uint8_t  has_sib;
    uint8_t  scale;
    uint8_t  index;
    uint8_t  base;
    uint8_t  has_modrm;
    int32_t  disp;
    uint8_t  disp_size;
    int64_t  imm;
    uint8_t  imm_size;
    OperandType op[3];
    uint8_t     num_ops;
} DecodedInsn;

int decode_one(const FileReader *fr, uint64_t offset,
               DecodedInsn *out,
               char *err_buf, size_t err_buf_size);

#endif
