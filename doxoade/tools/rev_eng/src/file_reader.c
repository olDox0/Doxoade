// doxoade/tools/rev_eng/src/file_reader.c
/* file_reader.c — leitura de arquivo com validação de bounds (Degrau 0)
 *
 * Regra de ouro: nenhum offset/tamanho vindo do arquivo é confiável.
 * Toda leitura passa por file_reader_at(), que valida bounds.
 */
#include "file_reader.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Copia até `dst_size-1` chars de `src` para `dst`, sempre NUL-terminando. */
static void safe_strcpy(char *dst, const char *src, size_t dst_size)
{
    if (dst == NULL || dst_size == 0) return;
    if (src == NULL) { dst[0] = '\0'; return; }
    size_t n = strlen(src);
    if (n >= dst_size) n = dst_size - 1;
    memcpy(dst, src, n);
    dst[n] = '\0';
}

int file_reader_open(const char *path, FileReader *out,
                     char *err_buf, size_t err_buf_size)
{
    if (out == NULL) return -1;
    out->data = NULL;
    out->size = 0;
    out->path = NULL;

    if (path == NULL) {
        if (err_buf) safe_strcpy(err_buf, "path NULL", err_buf_size);
        return -1;
    }

    FILE *f = fopen(path, "rb");
    if (f == NULL) {
        if (err_buf) safe_strcpy(err_buf, "fopen falhou", err_buf_size);
        return -1;
    }

    /* Determina tamanho via fseek/ftell (portátil em binário). */
    if (fseek(f, 0, SEEK_END) != 0) {
        if (err_buf) safe_strcpy(err_buf, "fseek END falhou", err_buf_size);
        fclose(f);
        return -1;
    }
    long sz = ftell(f);
    if (sz < 0) {
        if (err_buf) safe_strcpy(err_buf, "ftell falhou", err_buf_size);
        fclose(f);
        return -1;
    }
    if (sz == 0) {
        if (err_buf) safe_strcpy(err_buf, "arquivo vazio", err_buf_size);
        fclose(f);
        return -1;
    }
    if (fseek(f, 0, SEEK_SET) != 0) {
        if (err_buf) safe_strcpy(err_buf, "fseek SET falhou", err_buf_size);
        fclose(f);
        return -1;
    }

    uint8_t *buf = (uint8_t *)malloc((size_t)sz);
    if (buf == NULL) {
        if (err_buf) safe_strcpy(err_buf, "malloc falhou", err_buf_size);
        fclose(f);
        return -1;
    }

    size_t got = fread(buf, 1, (size_t)sz, f);
    fclose(f);
    if (got != (size_t)sz) {
        free(buf);
        if (err_buf) safe_strcpy(err_buf, "fread incompleto", err_buf_size);
        return -1;
    }

    out->data = buf;
    out->size = (size_t)sz;

    /* Cópia do path para mensagens de erro posteriores. */
    size_t plen = strlen(path);
    out->path = (char *)malloc(plen + 1);
    if (out->path == NULL) {
        free(out->data);
        out->data = NULL;
        out->size = 0;
        if (err_buf) safe_strcpy(err_buf, "malloc path falhou", err_buf_size);
        return -1;
    }
    memcpy(out->path, path, plen + 1);

    return 0;
}

void file_reader_close(FileReader *fr)
{
    if (fr == NULL) return;
    free(fr->data);
    free(fr->path);
    fr->data = NULL;
    fr->size = 0;
    fr->path = NULL;
}

const uint8_t *file_reader_at(const FileReader *fr,
                              size_t offset, size_t size)
{
    if (fr == NULL || fr->data == NULL) return NULL;
    /* Proteção contra overflow de size_t: se offset + size < offset,
     * houve wrap. */
    if (offset > fr->size) return NULL;
    if (size > fr->size - offset) return NULL;
    return fr->data + offset;
}

/* Helpers LE. Todos usam file_reader_at para validação. */

int file_reader_u8(const FileReader *fr, size_t off, uint8_t *out)
{
    const uint8_t *p = file_reader_at(fr, off, 1);
    if (p == NULL || out == NULL) return -1;
    *out = p[0];
    return 0;
}

int file_reader_u16(const FileReader *fr, size_t off, uint16_t *out)
{
    const uint8_t *p = file_reader_at(fr, off, 2);
    if (p == NULL || out == NULL) return -1;
    *out = (uint16_t)p[0] | ((uint16_t)p[1] << 8);
    return 0;
}

int file_reader_u32(const FileReader *fr, size_t off, uint32_t *out)
{
    const uint8_t *p = file_reader_at(fr, off, 4);
    if (p == NULL || out == NULL) return -1;
    *out =  (uint32_t)p[0]
         | ((uint32_t)p[1] << 8)
         | ((uint32_t)p[2] << 16)
         | ((uint32_t)p[3] << 24);
    return 0;
}

int file_reader_u64(const FileReader *fr, size_t off, uint64_t *out)
{
    const uint8_t *p = file_reader_at(fr, off, 8);
    if (p == NULL || out == NULL) return -1;
    uint64_t v = 0;
    for (int i = 7; i >= 0; i--) {
        v = (v << 8) | p[i];
    }
    *out = v;
    return 0;
}
