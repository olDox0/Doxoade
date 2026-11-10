// doxoade\tools\rev_eng\src\decoder.c
/* decoder.c — decodificador x86-64 (Fase 3)
 *
 * Implementa o subset necessário para 40% de cobertura:
 *   - Prefixos legacy (lock, rep, operand-size, address-size, segment)
 *   - REX
 *   - Opcodes de 1 e 2 bytes (0F escape)
 *   - ModR/M + SIB + deslocamento
 *   - Imediatos de 1/2/4/8 bytes
 *   - Relativos (jmp/call)
 *
 * NÃO implementa:
 *   - Opcodes de 3 bytes (0F 38, 0F 3A) — VEX/EVEX, SSE/AVX avançado
 *   - Instruções de string (movs, stos, lods) — usam SI/DI implicitamente
 *   - Prefixos de segmento (FS/GS) — presentes mas ignorados na formatação
 *   - x87 (D8-DF)
 *
 * O decoder é defensivo: toda leitura valida bounds via file_reader_at.
 */
#include "decoder.h"

#include <string.h>
#include <stdio.h>

/* Tabela de tamanhos de operandos por tipo (em bytes) */
static int operand_size(OperandType t, uint8_t rex, uint8_t prefix_opsize)
{
    int w = (rex & 0x08) != 0;  /* REX.W */
    int p66 = (prefix_opsize != 0);
    switch (t) {
        case OP_EB: case OP_GB: case OP_IB: case OP_JB:
        case OP_AL: case OP_CL: case OP_DL: case OP_BL:
        case OP_MB:
            return 1;
        case OP_EW: case OP_GW: case OP_IW: case OP_AX: case OP_CX:
        case OP_DX: case OP_MW:
            return 2;
        case OP_ED: case OP_GD: case OP_ID: case OP_EAX: case OP_ECX:
        case OP_EDX: case OP_MD:
            return 4;
        case OP_EQ: case OP_GQ: case OP_IQ: case OP_MQ:
            return 8;
        case OP_EV: case OP_GV: case OP_IZ: case OP_RAX:
            return w ? 8 : (p66 ? 2 : 4);
        default:
            return 0;
    }
}

int decode_one(const FileReader *fr, uint64_t offset,
               DecodedInsn *out, char *err_buf, size_t err_buf_size)
{
    if (fr == NULL || out == NULL) return -1;
    memset(out, 0, sizeof(*out));
    out->offset = offset;

    uint8_t *p = NULL;
    size_t remain = (offset < fr->size) ? (fr->size - offset) : 0;
    if (remain == 0) {
        snprintf(err_buf, err_buf_size, "offset fora do arquivo");
        return -1;
    }
    p = fr->data + offset;

    uint64_t i = 0;

    /* 1. Prefixos legacy (até 4) */
    for (int n = 0; n < 4 && i < remain; n++) {
        uint8_t b = p[i];
        if (b == 0xF0) { out->prefix_lock = 1; i++; continue; }
        if (b == 0xF3) { out->prefix_rep = 1; i++; continue; }
        if (b == 0xF2) { out->prefix_rep = 2; i++; continue; }
        if (b == 0x66) { out->prefix_opsize = 1; i++; continue; }
        if (b == 0x67) { out->prefix_addrsize = 1; i++; continue; }
        if (b == 0x2E || b == 0x36 || b == 0x3E ||
            b == 0x26 || b == 0x64 || b == 0x65) {
            out->prefix_seg = b; i++; continue;
        }
        break;
    }

    /* 2. REX (só se o próximo byte estiver na faixa 40-4F) */
    if (i < remain && (p[i] & 0xF0) == 0x40) {
        out->rex = p[i];
        i++;
    }

    /* 3. Opcode (1 ou 2 bytes; 0F escape) */
    if (i >= remain) {
        snprintf(err_buf, err_buf_size, "opcode truncado");
        return -1;
    }
    uint8_t b0 = p[i++];
    out->opcode = b0;
    out->opcode_len = 1;

    if (b0 == 0x0F) {
        if (i >= remain) {
            snprintf(err_buf, err_buf_size, "opcode 0F truncado");
            return -1;
        }
        uint8_t b1 = p[i++];
        out->opcode = (uint16_t)((0x0F << 8) | b1);
        out->opcode_len = 2;
    }

    /* 4. ModR/M e SIB (quando aplicável) */
    /* A tabela de opcodes decide se a instrução tem ModR/M.
     * Por enquanto, decodificamos o ModR/M se o opcode estiver nas
     * faixas conhecidas que usam ModR/M. Isso é uma simplificação:
     * o ideal é uma tabela de has_modrm por opcode, mas para o
     * primeiro protótipo usamos heurística. */
    int needs_modrm = 0;
    if (out->opcode_len == 1) {
        uint8_t op = (uint8_t)out->opcode;
        /* ALU ops (00-3D), exceto as de imediato direto (04,05,0C,0D,...) */
        if (op <= 0x3D && (op & 7) < 4) needs_modrm = 1;
        /* 50-5F: push/pop reg (sem modrm) */
        /* 63: movsxd */
        if (op == 0x63) needs_modrm = 1;
        /* 80-8F: groups + mov + lea + pop */
        if (op >= 0x80 && op <= 0x8F) needs_modrm = 1;
        /* 90: nop */
        /* C0-C1: shifts group 2 */
        if (op == 0xC0 || op == 0xC1) needs_modrm = 1;
        /* C6-C7: mov imm */
        if (op == 0xC6 || op == 0xC7) needs_modrm = 1;
        /* D0-D3: shifts group 2 */
        if (op >= 0xD0 && op <= 0xD3) needs_modrm = 1;
        /* F6-F7: group 3 */
        if (op == 0xF6 || op == 0xF7) needs_modrm = 1;
        /* FE-FF: groups 4/5 */
        if (op == 0xFE || op == 0xFF) needs_modrm = 1;
    } else {
        /* 0F xx */
        uint8_t op1 = (uint8_t)(out->opcode & 0xFF);
        /* 0F 1F: nop Ev */
        if (op1 == 0x1F) needs_modrm = 1;
        /* 0F 40-4F: cmovcc */
        if (op1 >= 0x40 && op1 <= 0x4F) needs_modrm = 1;
        /* 0F 90-9F: setcc */
        if (op1 >= 0x90 && op1 <= 0x9F) needs_modrm = 1;
        /* 0F AF: imul */
        if (op1 == 0xAF) needs_modrm = 1;
        /* 0F B6/B7/BE/BF: movzx/movsx */
        if (op1 == 0xB6 || op1 == 0xB7 || op1 == 0xBE || op1 == 0xBF) needs_modrm = 1;
    }

    if (needs_modrm) {
        if (i >= remain) {
            snprintf(err_buf, err_buf_size, "ModR/M truncado");
            return -1;
        }
        out->has_modrm = 1;
        out->modrm = p[i++];
        out->mod = (out->modrm >> 6) & 3;
        out->reg = (out->modrm >> 3) & 7;
        out->rm  = out->modrm & 7;

        /* REX.R, REX.B estendem reg e rm */
        if (out->rex & 0x04) out->reg |= 8;  /* REX.R */
        if (out->rex & 0x01) out->rm  |= 8;  /* REX.B */

        /* SIB: presente se mod != 11 e rm == 100 (4) */
        if (out->mod != 3 && (out->rm & 7) == 4) {
            if (i >= remain) {
                snprintf(err_buf, err_buf_size, "SIB truncado");
                return -1;
            }
            out->has_sib = 1;
            out->sib = p[i++];
            out->scale = (out->sib >> 6) & 3;
            out->index = ((out->sib >> 3) & 7) | ((out->rex & 0x02) ? 8 : 0);
            out->base  = (out->sib & 7) | ((out->rex & 0x01) ? 8 : 0);
        }

        /* Deslocamento */
        if (out->mod == 1) {
            /* disp8 */
            if (i >= remain) { snprintf(err_buf, err_buf_size, "disp8 truncado"); return -1; }
            out->disp = (int8_t)p[i++];
            out->disp_size = 1;
        } else if (out->mod == 2) {
            /* disp32 */
            if (i + 4 > remain) { snprintf(err_buf, err_buf_size, "disp32 truncado"); return -1; }
            int32_t d;
            memcpy(&d, p + i, 4);
            out->disp = d;
            out->disp_size = 4;
            i += 4;
        } else if (out->mod == 0) {
            /* RIP-relative: mod=00, rm=101 (ou 13) */
            if ((out->rm & 7) == 5) {
                if (i + 4 > remain) { snprintf(err_buf, err_buf_size, "RIP disp32 truncado"); return -1; }
                int32_t d;
                memcpy(&d, p + i, 4);
                out->disp = d;
                out->disp_size = 4;
                i += 4;
            }
            /* mod=00, rm=100 (SIB): sem disp, mas SIB precisa de base != 5
             * ou disp32 se base == 5 */
            if (out->has_sib && (out->base & 7) == 5) {
                if (i + 4 > remain) { snprintf(err_buf, err_buf_size, "SIB disp32 truncado"); return -1; }
                int32_t d;
                memcpy(&d, p + i, 4);
                out->disp = d;
                out->disp_size = 4;
                i += 4;
            }
        }
    }

    /* 5. Imediato (depende do opcode) */
    /* Simplificação para 40%: detectamos imediato pela faixa do opcode.
     * O ideal é uma tabela de imm_size por opcode. */
    int imm_sz = 0;
    if (out->opcode_len == 1) {
        uint8_t op = (uint8_t)out->opcode;
        /* 04, 0C, 14, 1C, 24, 2C, 34, 3C: AL, Ib */
        if (op <= 0x3C && (op & 7) == 4) imm_sz = 1;
        /* 05, 0D, 15, 1D, 25, 2D, 35, 3D: rAX, Iz */
        else if (op <= 0x3D && (op & 7) == 5) {
            imm_sz = (out->rex & 0x08) ? 4 : (out->prefix_opsize ? 2 : 4);
        }
        /* 68: push imm32 */
        else if (op == 0x68) imm_sz = (out->prefix_opsize ? 2 : 4);
        /* 6A: push imm8 */
        else if (op == 0x6A) imm_sz = 1;
        /* 70-7F: jcc rel8 */
        else if (op >= 0x70 && op <= 0x7F) imm_sz = 1;
        /* 80, 82, 83: group 1, imm8 */
        else if (op == 0x80 || op == 0x82 || op == 0x83) imm_sz = 1;
        /* 81: group 1, imm32 */
        else if (op == 0x81) imm_sz = (out->rex & 0x08) ? 4 : (out->prefix_opsize ? 2 : 4);
        /* B0-B7: mov r8, imm8 */
        else if (op >= 0xB0 && op <= 0xB7) imm_sz = 1;
        /* B8-BF: mov r32/64, imm */
        else if (op >= 0xB8 && op <= 0xBF) imm_sz = (out->rex & 0x08) ? 8 : (out->prefix_opsize ? 2 : 4);
        /* C0, C1: shifts com imm8 */
        else if (op == 0xC0 || op == 0xC1) imm_sz = 1;
        /* C6, C7: mov imm */
        else if (op == 0xC6) imm_sz = 1;
        else if (op == 0xC7) imm_sz = (out->rex & 0x08) ? 4 : (out->prefix_opsize ? 2 : 4);
        /* E8, E9: call/jmp rel32 */
        else if (op == 0xE8 || op == 0xE9) imm_sz = 4;
        /* EB: jmp rel8 */
        else if (op == 0xEB) imm_sz = 1;
        /* F6: group 3, test tem imm8 */
        else if (op == 0xF6) imm_sz = 1;
        /* F7: group 3, test tem imm32 */
        else if (op == 0xF7) imm_sz = (out->rex & 0x08) ? 4 : (out->prefix_opsize ? 2 : 4);
    } else {
        uint8_t op1 = (uint8_t)(out->opcode & 0xFF);
        /* 0F 80-8F: jcc rel32 */
        if (op1 >= 0x80 && op1 <= 0x8F) imm_sz = 4;
    }

    if (imm_sz > 0) {
        if (i + imm_sz > remain) {
            snprintf(err_buf, err_buf_size, "imediato truncado");
            return -1;
        }
        int64_t v = 0;
        if (imm_sz == 1) v = (int8_t)p[i];
        else if (imm_sz == 2) { int16_t x; memcpy(&x, p + i, 2); v = x; }
        else if (imm_sz == 4) { int32_t x; memcpy(&x, p + i, 4); v = x; }
        else if (imm_sz == 8) { int64_t x; memcpy(&x, p + i, 8); v = x; }
        out->imm = v;
        out->imm_size = imm_sz;
        i += imm_sz;
    }

    out->length = (uint8_t)i;
    return (int)i;
}
