// doxoade/tools/rev_eng/include/file_reader.h
/* file_reader.h — leitura de arquivo com validação de bounds (Degrau 0)
 *
 * Contrato:
 *   - file_reader_open() lê o arquivo inteiro em memória e retorna um handle.
 *   - file_reader_close() libera o handle.
 *   - file_reader_at() retorna ponteiro para `size` bytes em `offset`,
 *     ou NULL se `offset + size` estourar o tamanho do arquivo.
 *   - Nenhuma função crasha em offset inválido: retornam NULL/erro.
 *
 * O handle é opaco: o chamador não deve acessar `data`/`size` diretamente,
 * embora os campos estejam visíveis para inspeção em debug.
 */
#ifndef FILE_READER_H
#define FILE_READER_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint8_t *data;
    size_t   size;
    char    *path;      /* cópia do caminho, para mensagens de erro */
} FileReader;

/* Abre e lê o arquivo inteiro. Retorna 0 em sucesso, -1 em erro
 * (arquivo ausente, sem permissão, vazio, ou malloc falhou).
 * Em caso de erro, preenche `err_buf` (se não-NULL) com mensagem. */
int file_reader_open(const char *path, FileReader *out,
                     char *err_buf, size_t err_buf_size);

/* Libera `data` e `path`. Seguro chamar em handle já fechado. */
void file_reader_close(FileReader *fr);

/* Retorna ponteiro para `size` bytes a partir de `offset`, ou NULL se
 * `offset + size > fr->size` (com proteção contra overflow de size_t).
 * Não aloca; o ponteiro aponta para dentro de `fr->data`. */
const uint8_t *file_reader_at(const FileReader *fr,
                              size_t offset, size_t size);

/* Helpers de leitura little-endian (PE é LE em x86-64).
 * Todos retornam 0 e preenchem `out` em sucesso, -1 se fora de bounds. */
int file_reader_u8 (const FileReader *fr, size_t off, uint8_t  *out);
int file_reader_u16(const FileReader *fr, size_t off, uint16_t *out);
int file_reader_u32(const FileReader *fr, size_t off, uint32_t *out);
int file_reader_u64(const FileReader *fr, size_t off, uint64_t *out);

#endif /* FILE_READER_H */
