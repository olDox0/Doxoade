// doxoade/tools/rev_eng/include/pe_parser.h
/* pe_parser.h — parser PE32/PE32+ mínimo (Degrau 0)
 *
 * Escopo: ler MZ, PE header, seções e imports. Preencher PreIR.
 * Fora de escopo (por enquanto): relocations, exports, TLS, resources,
 * certificados, debug directory.
 *
 * Contrato:
 *   - pe_parse() preenche `out` (PreIR) e retorna 0 em sucesso.
 *   - Em erro, retorna -1 e preenche `err_buf` com mensagem.
 *   - Em sucesso, o chamador é responsável por chamar pre_ir_free(&out).
 *   - Em erro, `out` fica zerado (seguro chamar pre_ir_free mesmo assim).
 */
#ifndef PE_PARSER_H
#define PE_PARSER_H

#include "file_reader.h"
#include "pre_ir.h"

/* Parseia o arquivo em `fr` e preenche `out`.
 * Retorna 0 em sucesso, -1 em erro (com mensagem em `err_buf`). */
int pe_parse(const FileReader *fr, PreIR *out,
             char *err_buf, size_t err_buf_size);

#endif /* PE_PARSER_H */
