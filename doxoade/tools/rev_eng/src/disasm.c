/* disasm.c — tabela de opcodes e formatação (Fase 3) */
#include "disasm.h"
#include "decoder_backend.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* Nomes de registradores por tamanho */
static const char *regs64[16] = {
    "rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi",
    "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"
};
static const char *regs32[16] = {
    "eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi",
    "r8d", "r9d", "r10d", "r11d", "r12d", "r13d", "r14d", "r15d"
};
static const char *regs16[16] = {
    "ax", "cx", "dx", "bx", "sp", "bp", "si", "di",
    "r8w", "r9w", "r10w", "r11w", "r12w", "r13w", "r14w", "r15w"
};
static const char *regs8[16] = {
    "al", "cl", "dl", "bl", "spl", "bpl", "sil", "dil",
    "r8b", "r9b", "r10b", "r11b", "r12b", "r13b", "r14b", "r15b"
};

static const char *cc_names[16] = {
    "o", "no", "b", "ae", "e", "ne", "be", "a",
    "s", "ns", "p", "np", "l", "ge", "le", "g"
};

static const char *alu_names[8] = {
    "add", "or", "adc", "sbb", "and", "sub", "xor", "cmp"
};

static const char *shift_names[8] = {
    "rol", "ror", "rcl", "rcr", "shl", "shr", "sal", "sar"
};

static const char *group1_names[8] = {
    "add", "or", "adc", "sbb", "and", "sub", "xor", "cmp"
};

static const char *reg_name(uint8_t num, int size)
{
    num &= 15;
    if (size == 8) return regs64[num];
    if (size == 4) return regs32[num];
    if (size == 2) return regs16[num];
    if (size == 1) return regs8[num];
    return "???";
}

/* Busca o símbolo com va <= target (binary search). */
static const char *symbol_lookup(const PreIR *ir, uint64_t target,
                                 uint64_t *out_offset, uint64_t max_offset)
{
    if (ir == NULL || ir->symbols == NULL || ir->symbol_count == 0) return NULL;
    uint32_t lo = 0, hi = ir->symbol_count;
    while (lo < hi) {
        uint32_t mid = (lo + hi) / 2;
        if (ir->symbols[mid].va <= target) lo = mid + 1;
        else hi = mid;
    }
    if (lo == 0) return NULL;
    const SymbolEntry *s = &ir->symbols[lo - 1];
    uint64_t off = target - s->va;
    if (off > max_offset) return NULL;
    *out_offset = off;
    return s->name;
}

/* Formata o operando r/m (registrador se mod=3, memória caso contrário). */
static void fmt_rm(DecodedInsn *insn, int size, const PreIR *ir,
                   char *out, size_t out_size)
{
    if (insn->mod == 3) {
        snprintf(out, out_size, "%s", reg_name(insn->rm, size));
        return;
    }
    const char *ptr = (size == 1) ? "byte ptr " :
                      (size == 2) ? "word ptr " :
                      (size == 4) ? "dword ptr " : "qword ptr ";

    char body[256] = "";
    size_t blen = 0;

    if (insn->has_sib) {
        int base = insn->base, index = insn->index, scale = insn->scale;
        if ((base & 7) == 5 && insn->mod == 0) {
            blen += snprintf(body + blen, sizeof(body) - blen, "0x%x",
                             (uint32_t)insn->disp);
        } else {
            blen += snprintf(body + blen, sizeof(body) - blen, "%s",
                             reg_name(base, 8));
            if ((index & 7) != 4)
                blen += snprintf(body + blen, sizeof(body) - blen,
                                 "+%s*%d", reg_name(index, 8), 1 << scale);
            if (insn->disp) {
                if (insn->disp < 0)
                    blen += snprintf(body + blen, sizeof(body) - blen,
                                     "-0x%x", (unsigned)(-insn->disp));
                else
                    blen += snprintf(body + blen, sizeof(body) - blen,
                                     "+0x%x", (unsigned)insn->disp);
            }
        }
    } else if (insn->mod == 0 && (insn->rm & 7) == 5) {
        uint64_t target = insn->va + insn->length + insn->disp;
        char symbuf[300] = "";
        uint64_t sym_off = 0;
        const char *sym = symbol_lookup(ir, target, &sym_off, 0);
        if (sym) {
            if (sym_off == 0)
                snprintf(symbuf, sizeof(symbuf), " <%s>", sym);
            else
                snprintf(symbuf, sizeof(symbuf), " <%s+0x%llx>", sym,
                         (unsigned long long)sym_off);
        }
        blen += snprintf(body + blen, sizeof(body) - blen,
                         "rip+0x%x (0x%llx)%s",
                         insn->disp, (unsigned long long)target, symbuf);
    } else {
        blen += snprintf(body + blen, sizeof(body) - blen, "%s",
                         reg_name(insn->rm, 8));
        if (insn->disp) {
            if (insn->disp < 0)
                blen += snprintf(body + blen, sizeof(body) - blen,
                                 "-0x%x", (unsigned)(-insn->disp));
            else
                blen += snprintf(body + blen, sizeof(body) - blen,
                                 "+0x%x", (unsigned)insn->disp);
        }
    }
    snprintf(out, out_size, "%s[%s]", ptr, body);
}

static void fmt_operands(const DecodedInsn *insn, const FileReader *fr,
                         const PreIR *ir, char *out, size_t out_size)
{
    out[0] = '\0';
    int w = (insn->rex & 0x08) != 0;
    int p66 = insn->prefix_opsize != 0;
    int reg_sz = w ? 8 : (p66 ? 2 : 4);
    size_t written = 0;

    for (int i = 0; i < insn->num_ops; i++) {
        OperandType t = insn->op[i];
        if (t == OP_NONE) break;
        if (i > 0) written += snprintf(out + written, out_size - written, ", ");

        switch (t) {
            case OP_AL: case OP_CL: case OP_DL: case OP_BL: {
                int idx = (t == OP_AL) ? 0 : (t == OP_CL) ? 1 : (t == OP_DL) ? 2 : 3;
                written += snprintf(out + written, out_size - written, "%s", regs8[idx]);
                break;
            }
            case OP_AX: case OP_CX: case OP_DX: {
                int idx = (t == OP_AX) ? 0 : (t == OP_CX) ? 1 : 2;
                written += snprintf(out + written, out_size - written, "%s", regs16[idx]);
                break;
            }
            case OP_EAX: case OP_ECX: case OP_EDX: {
                int idx = (t == OP_EAX) ? 0 : (t == OP_ECX) ? 1 : 2;
                written += snprintf(out + written, out_size - written, "%s", regs32[idx]);
                break;
            }
            case OP_RAX:
                written += snprintf(out + written, out_size - written, "rax");
                break;
            case OP_1:
                written += snprintf(out + written, out_size - written, "1");
                break;
            case OP_EB: fmt_rm((DecodedInsn*)insn, 1, ir, out + written, out_size - written); written += strlen(out + written); break;
            case OP_EW: fmt_rm((DecodedInsn*)insn, 2, ir, out + written, out_size - written); written += strlen(out + written); break;
            case OP_ED: fmt_rm((DecodedInsn*)insn, 4, ir, out + written, out_size - written); written += strlen(out + written); break;
            case OP_EQ: fmt_rm((DecodedInsn*)insn, 8, ir, out + written, out_size - written); written += strlen(out + written); break;
            case OP_EV: fmt_rm((DecodedInsn*)insn, reg_sz, ir, out + written, out_size - written); written += strlen(out + written); break;
            case OP_MB: fmt_rm((DecodedInsn*)insn, 1, ir, out + written, out_size - written); written += strlen(out + written); break;
            case OP_MW: fmt_rm((DecodedInsn*)insn, 2, ir, out + written, out_size - written); written += strlen(out + written); break;
            case OP_MD: fmt_rm((DecodedInsn*)insn, 4, ir, out + written, out_size - written); written += strlen(out + written); break;
            case OP_MQ: fmt_rm((DecodedInsn*)insn, 8, ir, out + written, out_size - written); written += strlen(out + written); break;
            case OP_GB: written += snprintf(out + written, out_size - written, "%s", reg_name(insn->reg, 1)); break;
            case OP_GW: written += snprintf(out + written, out_size - written, "%s", reg_name(insn->reg, 2)); break;
            case OP_GD: written += snprintf(out + written, out_size - written, "%s", reg_name(insn->reg, 4)); break;
            case OP_GQ: written += snprintf(out + written, out_size - written, "%s", reg_name(insn->reg, 8)); break;
            case OP_GV: written += snprintf(out + written, out_size - written, "%s", reg_name(insn->reg, reg_sz)); break;
            case OP_IZ: case OP_ID: case OP_IQ: case OP_IW: case OP_IB: {
                if (insn->imm_size == 8)
                    written += snprintf(out + written, out_size - written, "0x%llx", (unsigned long long)insn->imm);
                else if (insn->imm_size == 4)
                    written += snprintf(out + written, out_size - written, "0x%x", (uint32_t)insn->imm);
                else if (insn->imm_size == 2)
                    written += snprintf(out + written, out_size - written, "0x%x", (uint16_t)insn->imm);
                else
                    written += snprintf(out + written, out_size - written, "0x%x", (uint8_t)insn->imm);
                break;
            }
            case OP_JB: case OP_JZ: {
                uint64_t target = insn->va + insn->length + insn->imm;
                uint64_t sym_off = 0;
                const char *sym = symbol_lookup(ir, target, &sym_off, 0x1000);
                if (sym) {
                    if (sym_off == 0)
                        written += snprintf(out + written, out_size - written,
                                            "0x%llx <%s>", (unsigned long long)target, sym);
                    else
                        written += snprintf(out + written, out_size - written,
                                            "0x%llx <%s+0x%llx>",
                                            (unsigned long long)target, sym,
                                            (unsigned long long)sym_off);
                } else {
                    written += snprintf(out + written, out_size - written,
                                        "0x%llx", (unsigned long long)target);
                }
                break;
            }
            default:
                written += snprintf(out + written, out_size - written, "<op?>");
                break;
        }
    }
}

static int fmt_insn(DecodedInsn *insn, const FileReader *fr,
                    const PreIR *ir, char *out, size_t out_size)
{
    /* Caminho Capstone: mnemonic + op_str já formatados. */
    if (insn->mnemonic[0] != '\0') {
        if (insn->op_str[0] != '\0')
            snprintf(out, out_size, "%s %s", insn->mnemonic, insn->op_str);
        else
            snprintf(out, out_size, "%s", insn->mnemonic);

        /* Anotação de símbolos para alvo RIP-relative. */
        if (insn->has_rip_target && ir != NULL) {
            uint64_t sym_off = 0;
            const char *sym = symbol_lookup(ir, insn->rip_target, &sym_off, 0);
            if (sym) {
                size_t len = strlen(out);
                if (sym_off == 0)
                    snprintf(out + len, out_size - len, " <%s>", sym);
                else
                    snprintf(out + len, out_size - len,
                             " <%s+0x%llx>", sym,
                             (unsigned long long)sym_off);
            }
        }
        return 0;
    }

    /* Caminho nativo: tabela de opcodes. */
    char mnemo[32] = "";
    char operands[128] = "";

    uint8_t op1 = insn->opcode_len == 1 ? (uint8_t)insn->opcode : 0;
    uint8_t op2 = insn->opcode_len == 2 ? (uint8_t)(insn->opcode & 0xFF) : 0;

    if (insn->opcode_len == 1) {
        if (op1 <= 0x3D && (op1 & 7) < 6) {
            int idx = op1 >> 3;
            int var = op1 & 7;
            snprintf(mnemo, sizeof(mnemo), "%s", alu_names[idx]);
            insn->num_ops = 2;
            if (var == 0) { insn->op[0] = OP_EB; insn->op[1] = OP_GB; }
            else if (var == 1) { insn->op[0] = OP_EV; insn->op[1] = OP_GV; }
            else if (var == 2) { insn->op[0] = OP_GB; insn->op[1] = OP_EB; }
            else if (var == 3) { insn->op[0] = OP_GV; insn->op[1] = OP_EV; }
            else if (var == 4) { insn->op[0] = OP_AL; insn->op[1] = OP_IB; }
            else if (var == 5) { insn->op[0] = OP_EAX; insn->op[1] = OP_IZ; }
        }
        else if (op1 == 0x63) { snprintf(mnemo, sizeof(mnemo), "movsxd"); insn->op[0] = OP_GV; insn->op[1] = OP_ED; insn->num_ops = 2; }
        else if (op1 == 0x68) { snprintf(mnemo, sizeof(mnemo), "push"); insn->op[0] = OP_IZ; insn->num_ops = 1; }
        else if (op1 == 0x6A) { snprintf(mnemo, sizeof(mnemo), "push"); insn->op[0] = OP_IB; insn->num_ops = 1; }
        else if (op1 >= 0x50 && op1 <= 0x57) { snprintf(mnemo, sizeof(mnemo), "push"); insn->op[0] = OP_GV; insn->reg = (op1 - 0x50) | ((insn->rex & 0x01) ? 8 : 0); insn->num_ops = 1; insn->prefix_opsize = 0; insn->rex |= 0x08; }
        else if (op1 >= 0x58 && op1 <= 0x5F) { snprintf(mnemo, sizeof(mnemo), "pop"); insn->op[0] = OP_GV; insn->reg = (op1 - 0x58) | ((insn->rex & 0x01) ? 8 : 0); insn->num_ops = 1; insn->prefix_opsize = 0; insn->rex |= 0x08; }
        else if (op1 == 0x80 || op1 == 0x81 || op1 == 0x82 || op1 == 0x83) {
            int grp = insn->reg & 7;
            snprintf(mnemo, sizeof(mnemo), "%s", group1_names[grp]);
            insn->op[0] = (op1 == 0x80 || op1 == 0x82) ? OP_EB : OP_EV;
            insn->op[1] = (op1 == 0x81) ? OP_IZ : OP_IB;
            insn->num_ops = 2;
        }
        else if (op1 == 0x84) { snprintf(mnemo, sizeof(mnemo), "test"); insn->op[0] = OP_EB; insn->op[1] = OP_GB; insn->num_ops = 2; }
        else if (op1 == 0x85) { snprintf(mnemo, sizeof(mnemo), "test"); insn->op[0] = OP_EV; insn->op[1] = OP_GV; insn->num_ops = 2; }
        else if (op1 == 0x88) { snprintf(mnemo, sizeof(mnemo), "mov"); insn->op[0] = OP_EB; insn->op[1] = OP_GB; insn->num_ops = 2; }
        else if (op1 == 0x89) { snprintf(mnemo, sizeof(mnemo), "mov"); insn->op[0] = OP_EV; insn->op[1] = OP_GV; insn->num_ops = 2; }
        else if (op1 == 0x8A) { snprintf(mnemo, sizeof(mnemo), "mov"); insn->op[0] = OP_GB; insn->op[1] = OP_EB; insn->num_ops = 2; }
        else if (op1 == 0x8B) { snprintf(mnemo, sizeof(mnemo), "mov"); insn->op[0] = OP_GV; insn->op[1] = OP_EV; insn->num_ops = 2; }
        else if (op1 == 0x8D) { snprintf(mnemo, sizeof(mnemo), "lea"); insn->op[0] = OP_GV; insn->op[1] = OP_EV; insn->num_ops = 2; }
        else if (op1 == 0x8F) { snprintf(mnemo, sizeof(mnemo), "pop"); insn->op[0] = OP_EV; insn->num_ops = 1; }
        else if (op1 == 0x90) { snprintf(mnemo, sizeof(mnemo), "nop"); insn->num_ops = 0; }
        else if (op1 == 0x98) { snprintf(mnemo, sizeof(mnemo), "cbw"); insn->num_ops = 0; }
        else if (op1 == 0x99) { snprintf(mnemo, sizeof(mnemo), "cwd"); insn->num_ops = 0; }
        else if (op1 >= 0xB0 && op1 <= 0xB7) { snprintf(mnemo, sizeof(mnemo), "mov"); insn->op[0] = OP_GB; insn->op[1] = OP_IB; insn->reg = (op1 - 0xB0) | ((insn->rex & 0x01) ? 8 : 0); insn->num_ops = 2; }
        else if (op1 >= 0xB8 && op1 <= 0xBF) { snprintf(mnemo, sizeof(mnemo), "mov"); insn->op[0] = OP_GV; insn->op[1] = OP_IZ; insn->reg = (op1 - 0xB8) | ((insn->rex & 0x01) ? 8 : 0); insn->num_ops = 2; }
        else if (op1 == 0xC0) { snprintf(mnemo, sizeof(mnemo), "%s", shift_names[insn->reg & 7]); insn->op[0] = OP_EB; insn->op[1] = OP_IB; insn->num_ops = 2; }
        else if (op1 == 0xC1) { snprintf(mnemo, sizeof(mnemo), "%s", shift_names[insn->reg & 7]); insn->op[0] = OP_EV; insn->op[1] = OP_IB; insn->num_ops = 2; }
        else if (op1 == 0xC3) { snprintf(mnemo, sizeof(mnemo), "ret"); insn->num_ops = 0; }
        else if (op1 == 0xC6) { snprintf(mnemo, sizeof(mnemo), "mov"); insn->op[0] = OP_EB; insn->op[1] = OP_IB; insn->num_ops = 2; }
        else if (op1 == 0xC7) { snprintf(mnemo, sizeof(mnemo), "mov"); insn->op[0] = OP_EV; insn->op[1] = OP_IZ; insn->num_ops = 2; }
        else if (op1 == 0xC9) { snprintf(mnemo, sizeof(mnemo), "leave"); insn->num_ops = 0; }
        else if (op1 == 0xCC) { snprintf(mnemo, sizeof(mnemo), "int3"); insn->num_ops = 0; }
        else if (op1 == 0xD0) { snprintf(mnemo, sizeof(mnemo), "%s", shift_names[insn->reg & 7]); insn->op[0] = OP_EB; insn->op[1] = OP_1; insn->num_ops = 2; }
        else if (op1 == 0xD1) { snprintf(mnemo, sizeof(mnemo), "%s", shift_names[insn->reg & 7]); insn->op[0] = OP_EV; insn->op[1] = OP_1; insn->num_ops = 2; }
        else if (op1 == 0xD2) { snprintf(mnemo, sizeof(mnemo), "%s", shift_names[insn->reg & 7]); insn->op[0] = OP_EB; insn->op[1] = OP_CL; insn->num_ops = 2; }
        else if (op1 == 0xD3) { snprintf(mnemo, sizeof(mnemo), "%s", shift_names[insn->reg & 7]); insn->op[0] = OP_EV; insn->op[1] = OP_CL; insn->num_ops = 2; }
        else if (op1 == 0xE8) { snprintf(mnemo, sizeof(mnemo), "call"); insn->op[0] = OP_JZ; insn->num_ops = 1; }
        else if (op1 == 0xE9) { snprintf(mnemo, sizeof(mnemo), "jmp"); insn->op[0] = OP_JZ; insn->num_ops = 1; }
        else if (op1 >= 0x70 && op1 <= 0x7F) { snprintf(mnemo, sizeof(mnemo), "j%s", cc_names[op1 & 0xF]); insn->op[0] = OP_JB; insn->num_ops = 1; }
        else if (op1 == 0xEB) { snprintf(mnemo, sizeof(mnemo), "jmp"); insn->op[0] = OP_JB; insn->num_ops = 1; }
        else if (op1 == 0xF4) { snprintf(mnemo, sizeof(mnemo), "hlt"); insn->num_ops = 0; }
        else if (op1 == 0xF6) { snprintf(mnemo, sizeof(mnemo), "test"); insn->op[0] = OP_EB; insn->op[1] = OP_IB; insn->num_ops = 2; }
        else if (op1 == 0xF7) { snprintf(mnemo, sizeof(mnemo), "test"); insn->op[0] = OP_EV; insn->op[1] = OP_IZ; insn->num_ops = 2; }
        else if (op1 == 0xFE) { snprintf(mnemo, sizeof(mnemo), "inc"); insn->op[0] = OP_EB; insn->num_ops = 1; }
        else if (op1 == 0xFF) {
            int grp = insn->reg & 7;
            if (grp == 0) { snprintf(mnemo, sizeof(mnemo), "inc"); insn->op[0] = OP_EV; insn->num_ops = 1; }
            else if (grp == 1) { snprintf(mnemo, sizeof(mnemo), "dec"); insn->op[0] = OP_EV; insn->num_ops = 1; }
            else if (grp == 2) { snprintf(mnemo, sizeof(mnemo), "call"); insn->op[0] = OP_EV; insn->num_ops = 1; }
            else if (grp == 4) { snprintf(mnemo, sizeof(mnemo), "jmp"); insn->op[0] = OP_EV; insn->num_ops = 1; }
            else if (grp == 6) { snprintf(mnemo, sizeof(mnemo), "push"); insn->op[0] = OP_EV; insn->num_ops = 1; }
        }
        else if (op1 == 0xFC) { snprintf(mnemo, sizeof(mnemo), "cld"); insn->num_ops = 0; }
        else if (op1 == 0xFD) { snprintf(mnemo, sizeof(mnemo), "std"); insn->num_ops = 0; }
        else { snprintf(mnemo, sizeof(mnemo), "db 0x%02x", op1); insn->num_ops = 0; }
    }
    else {
        if (op2 == 0x05) { snprintf(mnemo, sizeof(mnemo), "syscall"); insn->num_ops = 0; }
        else if (op2 == 0x0B) { snprintf(mnemo, sizeof(mnemo), "ud2"); insn->num_ops = 0; }
        else if (op2 == 0x1F) { snprintf(mnemo, sizeof(mnemo), "nop"); insn->op[0] = OP_EV; insn->num_ops = 1; }
        else if (op2 >= 0x40 && op2 <= 0x4F) { snprintf(mnemo, sizeof(mnemo), "cmov%s", cc_names[op2 & 0xF]); insn->op[0] = OP_GV; insn->op[1] = OP_EV; insn->num_ops = 2; }
        else if (op2 >= 0x80 && op2 <= 0x8F) { snprintf(mnemo, sizeof(mnemo), "j%s", cc_names[op2 & 0xF]); insn->op[0] = OP_JZ; insn->num_ops = 1; }
        else if (op2 >= 0x90 && op2 <= 0x9F) { snprintf(mnemo, sizeof(mnemo), "set%s", cc_names[op2 & 0xF]); insn->op[0] = OP_EB; insn->num_ops = 1; }
        else if (op2 == 0xA2) { snprintf(mnemo, sizeof(mnemo), "cpuid"); insn->num_ops = 0; }
        else if (op2 == 0xAF) { snprintf(mnemo, sizeof(mnemo), "imul"); insn->op[0] = OP_GV; insn->op[1] = OP_EV; insn->num_ops = 2; }
        else if (op2 == 0xB6) { snprintf(mnemo, sizeof(mnemo), "movzx"); insn->op[0] = OP_GV; insn->op[1] = OP_EB; insn->num_ops = 2; }
        else if (op2 == 0xB7) { snprintf(mnemo, sizeof(mnemo), "movzx"); insn->op[0] = OP_GV; insn->op[1] = OP_EW; insn->num_ops = 2; }
        else if (op2 == 0xBE) { snprintf(mnemo, sizeof(mnemo), "movsx"); insn->op[0] = OP_GV; insn->op[1] = OP_EB; insn->num_ops = 2; }
        else if (op2 == 0xBF) { snprintf(mnemo, sizeof(mnemo), "movsx"); insn->op[0] = OP_GV; insn->op[1] = OP_EW; insn->num_ops = 2; }
        else if (op2 == 0x31) { snprintf(mnemo, sizeof(mnemo), "rdtsc"); insn->num_ops = 0; }
        else { snprintf(mnemo, sizeof(mnemo), "db 0x0f, 0x%02x", op2); insn->num_ops = 0; }
    }

    fmt_operands(insn, fr, ir, operands, sizeof(operands));
    if (operands[0]) snprintf(out, out_size, "%s %s", mnemo, operands);
    else snprintf(out, out_size, "%s", mnemo);
    return 0;
}

/* ===== disasm_collect ===== */

int disasm_collect(const FileReader *fr, uint64_t offset, uint64_t length,
                   uint64_t va_base, DecoderBackend backend,
                   InsnList *out, char *err_buf, size_t err_buf_size)
{
    if (out == NULL) return -1;
    out->count = 0;
    out->insns = NULL;

    uint64_t end = offset + length;
    if (end > fr->size) end = fr->size;

    uint32_t cap = 0;
    uint64_t pos = offset;
    while (pos < end) {
        DecodedInsn tmp;
        int n = decode_one_backend(backend, fr, pos, va_base + pos, &tmp,
                                   err_buf, err_buf_size);
        if (n <= 0 || pos + n > end) n = 1;
        cap++;
        pos += n;
    }
    if (cap == 0) return 0;

    DecodedInsn *arr = (DecodedInsn *)calloc(cap, sizeof(DecodedInsn));
    if (arr == NULL) {
        snprintf(err_buf, err_buf_size, "calloc insns falhou");
        return -1;
    }

    uint32_t written = 0;
    pos = offset;
    while (pos < end && written < cap) {
        DecodedInsn insn;
        int n = decode_one_backend(backend, fr, pos, va_base + pos, &insn,
                                   err_buf, err_buf_size);
        if (n <= 0 || pos + n > end) {
            memset(&insn, 0, sizeof(insn));
            insn.offset = pos;
            insn.va = va_base + pos;
            insn.length = 1;
            insn.opcode = fr->data[pos];
            insn.opcode_len = 1;
        }
        insn.offset = pos;
        insn.va = va_base + pos;
        arr[written++] = insn;
        pos += insn.length;
    }

    out->count = written;
    out->insns = arr;
    return 0;
}

ControlFlowType insn_control_flow(const DecodedInsn *insn, uint64_t *target_va)
{
    if (target_va) *target_va = 0;

    /* --- Caminho Capstone: usa mnemônico, imm absoluto --- */
    if (insn->mnemonic[0] != '\0') {
        const char *m = insn->mnemonic;

        /* ret, retf, retn */
        if (m[0] == 'r' && m[1] == 'e' && m[2] == 't') return CF_RET;

        /* call, callq — Capstone normaliza o alvo para absoluto */
        if (m[0] == 'c' && m[1] == 'a' && m[2] == 'l' && m[3] == 'l') {
            if (insn->imm_size > 0 && target_va) *target_va = (uint64_t)insn->imm;
            return CF_CALL;
        }

        /* jmp — Capstone normaliza o alvo para absoluto */
        if (m[0] == 'j' && m[1] == 'm' && m[2] == 'p') {
            if (insn->imm_size > 0 && target_va) *target_va = (uint64_t)insn->imm;
            return CF_JMP;
        }

        /* jcc (je, jne, jl, jg, jbe, ja, jz, jnz, ...) */
        if (m[0] == 'j') {
            if (insn->imm_size > 0 && target_va) *target_va = (uint64_t)insn->imm;
            return CF_JCC;
        }

        return CF_NONE;
    }

    /* --- Caminho nativo: opcode + relativo --- */
    if (insn->opcode_len == 1) {
        uint8_t op = (uint8_t)insn->opcode;
        if (op >= 0x70 && op <= 0x7F) {
            if (target_va) *target_va = insn->va + insn->length + (uint64_t)insn->imm;
            return CF_JCC;
        }
        if (op == 0xEB || op == 0xE9) {
            if (target_va) *target_va = insn->va + insn->length + (uint64_t)insn->imm;
            return CF_JMP;
        }
        if (op == 0xE8) {
            if (target_va) *target_va = insn->va + insn->length + (uint64_t)insn->imm;
            return CF_CALL;
        }
        if (op == 0xC3 || op == 0xC2 || op == 0xCB || op == 0xCA) return CF_RET;
        if (op == 0xFF) {
            int grp = insn->reg & 7;
            if (grp == 4) return CF_JMP;
            if (grp == 2) return CF_CALL;
        }
    } else {
        uint8_t op2 = (uint8_t)(insn->opcode & 0xFF);
        if (op2 >= 0x80 && op2 <= 0x8F) {
            if (target_va) *target_va = insn->va + insn->length + (uint64_t)insn->imm;
            return CF_JCC;
        }
    }
    return CF_NONE;
}

int disasm_range(const FileReader *fr, uint64_t offset, uint64_t length,
                 uint64_t va_base, DecoderBackend backend, const PreIR *ir,
                 FILE *out, char *err_buf, size_t err_buf_size)
{
    uint64_t end = offset + length;
    if (end > fr->size) end = fr->size;
    uint64_t pos = offset;
    int count = 0;

    while (pos < end) {
        DecodedInsn insn;
        int n = decode_one_backend(backend, fr, pos, va_base + pos, &insn,
                                   err_buf, err_buf_size);
        if (n <= 0 || pos + n > end) {
            uint8_t b = fr->data[pos];
            fprintf(out, "%016llx: %02x                       db 0x%02x\n",
                    (unsigned long long)(va_base + pos), b, b);
            pos++;
            continue;
        }
        insn.va = va_base + pos;
        char text[256];
        fmt_insn(&insn, fr, ir, text, sizeof(text));
        fprintf(out, "%016llx: ", (unsigned long long)insn.va);
        for (int i = 0; i < n && i < 8; i++) fprintf(out, "%02x ", fr->data[pos+i]);
        for (int i = n; i < 8; i++) fprintf(out, "   ");
        fprintf(out, "  %s\n", text);
        pos += n;
        count++;
    }
    return count;
}

int disasm_text_section(const FileReader *fr, const PreIR *ir,
                        DecoderBackend backend,
                        FILE *out, char *err_buf, size_t err_buf_size)
{
    for (uint32_t i = 0; i < ir->section_count; i++) {
        const SectionEntry *s = &ir->sections[i];
        if (strcmp(s->name, ".text") == 0) {
            uint64_t va_base = ir->image_base + s->va - s->raw_offset;
            return disasm_range(fr, s->raw_offset, s->raw_size, va_base,
                                backend, ir, out, err_buf, err_buf_size);
        }
    }
    snprintf(err_buf, err_buf_size, "seção .text não encontrada");
    return -1;
}
