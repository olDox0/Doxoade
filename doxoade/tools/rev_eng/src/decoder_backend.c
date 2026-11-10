/* decoder_backend.c — implementação da interface de backend */
#include "decoder_backend.h"

#include <stdio.h>
#include <string.h>

#ifdef HAVE_CAPSTONE
#include <capstone/capstone.h>
#include <capstone/x86.h>

/* Traduz um cs_insn (Capstone) para DecodedInsn (nosso formato). */
static int translate_capstone(const cs_insn *ci, uint64_t offset, uint64_t va,
                              DecodedInsn *out)
{
    memset(out, 0, sizeof(*out));
    out->offset = offset;
    out->va = va;
    out->length = (uint8_t)ci->size;

    /* Mnemônico e string de operandos — o Capstone já formata (Intel). */
    strncpy(out->mnemonic, ci->mnemonic, sizeof(out->mnemonic) - 1);
    strncpy(out->op_str, ci->op_str, sizeof(out->op_str) - 1);

    /* Preencher opcode (para CF) — o Capstone não expõe o opcode bruto
     * diretamente, mas cs_x86.encoding tem o campo. */
    if (ci->detail && ci->id != 0) {
        const cs_x86 *x86 = &ci->detail->x86;
        /* opcode_len/opcode: bytes do opcode em ci->bytes após os prefixos.
         * Usamos o primeiro byte pós-prefixos como "opcode" para CF. */
        uint8_t opcode_len = x86->opcode[0];
        if (opcode_len > 0) {
            out->opcode_len = 1;
            out->opcode = x86->opcode[1];
            if (opcode_len == 2) {
                out->opcode_len = 2;
                out->opcode = ((uint16_t)0x0F << 8) | x86->opcode[2];
            }
        }

        /* Imediato (para jcc/call/jmp relativo). */
        for (int i = 0; i < x86->op_count; i++) {
            const cs_x86_op *op = &x86->operands[i];
            if (op->type == X86_OP_IMM) {
                out->imm = op->imm;
                out->imm_size = (op->size > 0) ? op->size : 4;
                break;
            }
        }
    }

    return (int)out->length;
}
#endif /* HAVE_CAPSTONE */

int decode_one_backend(DecoderBackend backend,
                       const FileReader *fr, uint64_t offset, uint64_t va,
                       DecodedInsn *out,
                       char *err_buf, size_t err_buf_size)
{
    if (backend == BACKEND_NATIVE) {
        int n = decode_one(fr, offset, out, err_buf, err_buf_size);
        if (n > 0) out->va = va;
        return n;
    }

#ifdef HAVE_CAPSTONE
    if (backend == BACKEND_CAPSTONE) {
        static csh handle = 0;
        if (handle == 0) {
            if (cs_open(CS_ARCH_X86, CS_MODE_64, &handle) != CS_ERR_OK) {
                snprintf(err_buf, err_buf_size, "cs_open falhou");
                return -1;
            }
            cs_option(handle, CS_OPT_DETAIL, CS_OPT_ON);
            cs_option(handle, CS_OPT_SYNTAX, CS_OPT_SYNTAX_INTEL);
        }

        size_t max_bytes = (offset < fr->size) ? (fr->size - offset) : 0;
        if (max_bytes > 15) max_bytes = 15;  /* tamanho máximo de uma instrução x86-64 */
        if (max_bytes == 0) {
            snprintf(err_buf, err_buf_size, "offset fora do arquivo");
            return -1;
        }

        cs_insn *ci = cs_malloc(handle);
        if (ci == NULL) {
            snprintf(err_buf, err_buf_size, "cs_malloc falhou");
            return -1;
        }

        const uint8_t *code = fr->data + offset;
        size_t code_size = max_bytes;
        uint64_t address = va;
        int n = 0;
        if (cs_disasm_iter(handle, &code, &code_size, &address, ci)) {
            n = translate_capstone(ci, offset, va, out);
        } else {
            snprintf(err_buf, err_buf_size, "cs_disasm_iter falhou");
        }
        cs_free(ci, 1);
        return (n > 0) ? n : -1;
    }
#else
    if (backend == BACKEND_CAPSTONE) {
        snprintf(err_buf, err_buf_size,
                 "backend Capstone não compilado (defina HAVE_CAPSTONE)");
        return -1;
    }
#endif

    snprintf(err_buf, err_buf_size, "backend desconhecido");
    return -1;
}
