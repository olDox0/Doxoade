/* doctor.h — self-diagnóstico e pre-flight do doxreveng
 *
 * doctor_run:   self-test completo (build, parser, decoder, CFG, symbols)
 * preflight_run: guarda rápida antes de operações pesadas
 *                (valida que o alvo tem o que a operação precisa)
 */
#ifndef DOCTOR_H
#define DOCTOR_H

#include "decoder_backend.h"

/* Executa o diagnóstico. `target` é um binário PE para testar;
 * se NULL, usa testes internos mínimos.
 * Retorna 0 se todos os testes passaram, 1 se algum falhou. */
int doctor_run(const char *target);

/* Valida pré-condições para `operation` ("parse", "disasm" ou "cfg").
 * Rápido — não decodifica o .text inteiro.
 * `backend` é o backend que será usado na operação.
 * Retorna 0 se OK, 1 se falha (mensagem em stderr). */
int preflight_run(const char *path, const char *operation,
                  DecoderBackend backend);

#endif /* DOCTOR_H */
