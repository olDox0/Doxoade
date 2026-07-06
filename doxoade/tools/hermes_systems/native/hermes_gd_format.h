// doxoade/tools/hermes_systems/native/hermes_gd_format.h
#pragma pack(push, 1) // Garante que não haja padding do compilador

#define HGD1_MAGIC "HGD1"

// Entrada de índice (8 bytes)
typedef struct {
    uint32_t offset;  // Offset em bytes a partir do início do arquivo
    uint32_t length;  // Tamanho do pattern em bytes
} HGD1_Entry;

// Header do Dicionário Global
typedef struct {
    char magic[4];        // "HGD1"
    uint32_t version;     // 0x01
    uint16_t count;       // Número de tokens no dicionário
    uint16_t base_token;  // O code point base (ex: 0xE000)
    uint8_t reserved[24]; // Alinhamento para 32 bytes
    HGD1_Entry entries[]; // Array flexível (C99) de 'count' elementos
} HGD1_Header;

#pragma pack(pop)