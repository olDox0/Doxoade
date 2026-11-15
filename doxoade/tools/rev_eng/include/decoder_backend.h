/* decoder_backend.h — interface de backend plugável para decodificação
 *
 * Permite alternar entre o decoder nativo (aprendizado) e o Capstone
 * (cobertura total, dependência opcional via HAVE_CAPSTONE).
 */
#ifndef DECODER_BACKEND_H
#define DECODER_BACKEND_H

#include "decoder.h"
#include "file_reader.h"
#include <stdint.h>

typedef enum {
    BACKEND_NATIVE   = 0,
    BACKEND_CAPSTONE = 1,
} DecoderBackend;

typedef enum {
    DECODE_MODE_32 = 0,
    DECODE_MODE_64 = 1,
} DecodeMode;

int decode_one_backend(DecoderBackend backend, DecodeMode mode,
                       const FileReader *fr, uint64_t offset, uint64_t va,
                       DecodedInsn *out,
                       char *err_buf, size_t err_buf_size);

#endif
