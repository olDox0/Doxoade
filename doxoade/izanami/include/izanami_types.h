// izanami/include/izanami_types.h
/* ==========================================================================
 * [IZANAMI SYSTEMS] Tipos Primitivos, Protocolos e ABI UEFI 2.x Soberana.
 * Zero bibliotecas externas. Alinhamento rigoroso para arquitetura IA-32 / x86.
 * Em estrita conformidade com o protocolo ProDeNov v2.0.
 * ========================================================================== */

#ifndef IZANAMI_TYPES_H
#define IZANAMI_TYPES_H

/* --------------------------------------------------------------------------
 * 1. Tipos Primitivos da Especificação UEFI
 * -------------------------------------------------------------------------- */
typedef unsigned char      UINT8;
typedef unsigned short     UINT16;
typedef unsigned int       UINT32;
typedef unsigned long long UINT64;

typedef signed char        INT8;
typedef signed short       INT16;
typedef signed int         INT32;
typedef signed long long   INT64;

/* No IA-32 (32-bit), UINTN/INTN tem 4 bytes; em 64-bit tem 8 bytes */
#if defined(__x86_64__) || defined(_M_X64)
    typedef UINT64 UINTN;
    typedef INT64  INTN;
    #define EFIAPI __attribute__((ms_abi))
#else
    typedef UINT32 UINTN;
    typedef INT32  INTN;
    #define EFIAPI __attribute__((cdecl))
#endif

typedef UINT16 CHAR16;
typedef UINT8  BOOLEAN;
typedef void   VOID;
typedef VOID*  EFI_HANDLE;
typedef UINTN  EFI_STATUS;

#define TRUE  1
#define FALSE 0
#define NULL  ((VOID*)0)

/* --------------------------------------------------------------------------
 * 2. Códigos de Status Canônicos do UEFI
 * -------------------------------------------------------------------------- */
#define EFI_SUCCESS               0
#define EFI_ERROR_BIT             ((UINTN)1 << (sizeof(UINTN) * 8 - 1))
#define EFI_LOAD_ERROR            (EFI_ERROR_BIT | 1)
#define EFI_INVALID_PARAMETER     (EFI_ERROR_BIT | 2)
#define EFI_UNSUPPORTED           (EFI_ERROR_BIT | 3)
#define EFI_BAD_BUFFER_SIZE       (EFI_ERROR_BIT | 4)
#define EFI_BUFFER_TOO_SMALL      (EFI_ERROR_BIT | 5)
#define EFI_NOT_READY             (EFI_ERROR_BIT | 6)
#define EFI_DEVICE_ERROR          (EFI_ERROR_BIT | 7)
#define EFI_NOT_FOUND             (EFI_ERROR_BIT | 14)

/* --------------------------------------------------------------------------
 * 3. Cores e Atributos de Vídeo (Simple Text Output)
 * -------------------------------------------------------------------------- */
#define EFI_BLACK                 0x00
#define EFI_BLUE                  0x01
#define EFI_GREEN                 0x02
#define EFI_CYAN                  0x03
#define EFI_RED                   0x04
#define EFI_MAGENTA               0x05
#define EFI_BROWN                 0x06
#define EFI_LIGHTGRAY             0x07
#define EFI_DARKGRAY              0x08
#define EFI_LIGHTBLUE             0x09
#define EFI_LIGHTGREEN            0x0A
#define EFI_LIGHTCYAN             0x0B
#define EFI_LIGHTRED              0x0C
#define EFI_LIGHTMAGENTA          0x0D
#define EFI_YELLOW                0x0E
#define EFI_WHITE                 0x0F

#define EFI_BACKGROUND_BLACK      0x00
#define EFI_BACKGROUND_BLUE       0x10
#define EFI_BACKGROUND_GREEN      0x20
#define EFI_BACKGROUND_CYAN       0x30
#define EFI_BACKGROUND_RED        0x40
#define EFI_BACKGROUND_MAGENTA    0x50
#define EFI_BACKGROUND_BROWN      0x60
#define EFI_BACKGROUND_LIGHTGRAY  0x70

#define EFI_TEXT_ATTR(Foreground, Background) ((Foreground) | ((Background) << 4))

/* --------------------------------------------------------------------------
 * 4. Protocolo de Entrada de Teclado (Simple Text Input)
 * -------------------------------------------------------------------------- */
typedef struct {
    UINT16 ScanCode;
    CHAR16 UnicodeChar;
} EFI_INPUT_KEY;

#define SCAN_NULL       0x00
#define SCAN_UP         0x01
#define SCAN_DOWN       0x02
#define SCAN_RIGHT      0x03
#define SCAN_LEFT       0x04
#define SCAN_HOME       0x05
#define SCAN_END        0x06
#define SCAN_INSERT     0x07
#define SCAN_DELETE     0x08
#define SCAN_PAGE_UP    0x09
#define SCAN_PAGE_DOWN  0x0A
#define SCAN_ESC        0x17

struct _EFI_SIMPLE_TEXT_INPUT_PROTOCOL;

typedef EFI_STATUS (EFIAPI *EFI_INPUT_RESET)(
    struct _EFI_SIMPLE_TEXT_INPUT_PROTOCOL *This,
    BOOLEAN ExtendedVerification
);

typedef EFI_STATUS (EFIAPI *EFI_INPUT_READ_KEY)(
    struct _EFI_SIMPLE_TEXT_INPUT_PROTOCOL *This,
    EFI_INPUT_KEY *Key
);

typedef struct _EFI_SIMPLE_TEXT_INPUT_PROTOCOL {
    EFI_INPUT_RESET    Reset;
    EFI_INPUT_READ_KEY ReadKeyStroke;
    VOID              *WaitForKey;
} EFI_SIMPLE_TEXT_INPUT_PROTOCOL;

/* --------------------------------------------------------------------------
 * 5. Protocolo de Saída de Texto (Simple Text Output)
 * -------------------------------------------------------------------------- */
struct _EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL;

typedef EFI_STATUS (EFIAPI *EFI_TEXT_RESET)(
    struct _EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
    BOOLEAN ExtendedVerification
);

typedef EFI_STATUS (EFIAPI *EFI_TEXT_STRING)(
    struct _EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
    const CHAR16 *String
);

typedef EFI_STATUS (EFIAPI *EFI_TEXT_TEST_STRING)(
    struct _EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
    const CHAR16 *String
);

typedef EFI_STATUS (EFIAPI *EFI_TEXT_QUERY_MODE)(
    struct _EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
    UINTN ModeNumber,
    UINTN *Columns,
    UINTN *Rows
);

typedef EFI_STATUS (EFIAPI *EFI_TEXT_SET_MODE)(
    struct _EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
    UINTN ModeNumber
);

typedef EFI_STATUS (EFIAPI *EFI_TEXT_SET_ATTRIBUTE)(
    struct _EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
    UINTN Attribute
);

typedef EFI_STATUS (EFIAPI *EFI_TEXT_CLEAR_SCREEN)(
    struct _EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This
);

typedef EFI_STATUS (EFIAPI *EFI_TEXT_SET_CURSOR_POSITION)(
    struct _EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
    UINTN Column,
    UINTN Row
);

typedef EFI_STATUS (EFIAPI *EFI_TEXT_ENABLE_CURSOR)(
    struct _EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
    BOOLEAN Visible
);

typedef struct {
    INT32   MaxMode;
    INT32   Mode;
    INT32   Attribute;
    INT32   CursorColumn;
    INT32   CursorRow;
    BOOLEAN CursorVisible;
} SIMPLE_TEXT_OUTPUT_MODE;

typedef struct _EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL {
    EFI_TEXT_RESET                Reset;
    EFI_TEXT_STRING               OutputString;
    EFI_TEXT_TEST_STRING          TestString;
    EFI_TEXT_QUERY_MODE           QueryMode;
    EFI_TEXT_SET_MODE             SetMode;
    EFI_TEXT_SET_ATTRIBUTE        SetAttribute;
    EFI_TEXT_CLEAR_SCREEN         ClearScreen;
    EFI_TEXT_SET_CURSOR_POSITION  SetCursorPosition;
    EFI_TEXT_ENABLE_CURSOR        EnableCursor;
    SIMPLE_TEXT_OUTPUT_MODE      *Mode;
} EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL;

/* --------------------------------------------------------------------------
 * 6. Cabeçalho de Tabela Padrão (24 bytes)
 * -------------------------------------------------------------------------- */
typedef struct {
    UINT64 Signature;
    UINT32 Revision;
    UINT32 HeaderSize;
    UINT32 CRC32;
    UINT32 Reserved;
} EFI_TABLE_HEADER;

/* --------------------------------------------------------------------------
 * 7. Serviços de Tempo de Execução (Runtime Services)
 * -------------------------------------------------------------------------- */
typedef enum {
    EfiResetCold,
    EfiResetWarm,
    EfiResetShutdown,
    EfiResetPlatformSpecific
} EFI_RESET_TYPE;

typedef VOID (EFIAPI *EFI_RESET_SYSTEM)(
    EFI_RESET_TYPE ResetType,
    EFI_STATUS ResetStatus,
    UINTN DataSize,
    VOID *ResetData
);

typedef struct {
    EFI_TABLE_HEADER  Hdr;
    VOID             *GetTime;
    VOID             *SetTime;
    VOID             *GetWakeupTime;
    VOID             *SetWakeupTime;
    VOID             *SetVirtualAddressMap;
    VOID             *ConvertPointer;
    VOID             *GetVariable;
    VOID             *GetNextVariableName;
    VOID             *SetVariable;
    VOID             *GetNextHighMonotonicCount;
    EFI_RESET_SYSTEM  ResetSystem;
    VOID             *UpdateCapsule;
    VOID             *QueryCapsuleCapabilities;
    VOID             *QueryVariableInfo;
} EFI_RUNTIME_SERVICES;

/* --------------------------------------------------------------------------
 * 8. Serviços de Inicialização Canônicos (Boot Services - Ordem Exata UEFI 2.x)
 * -------------------------------------------------------------------------- */
typedef EFI_STATUS (EFIAPI *EFI_STALL)(
    UINTN Microseconds
);

typedef struct {
    EFI_TABLE_HEADER Hdr;

    /* Task Priority Services */
    VOID *RaiseTPL;
    VOID *RestoreTPL;

    /* Memory Services */
    VOID *AllocatePages;
    VOID *FreePages;
    VOID *GetMemoryMap;
    VOID *AllocatePool;
    VOID *FreePool;

    /* Event & Timer Services */
    VOID *CreateEvent;
    VOID *SetTimer;
    VOID *WaitForEvent;
    VOID *SignalEvent;
    VOID *CloseEvent;
    VOID *CheckEvent;

    /* Protocol Handler Services */
    VOID *InstallProtocolInterface;
    VOID *ReinstallProtocolInterface;
    VOID *UninstallProtocolInterface;
    VOID *HandleProtocol;
    VOID *Reserved;
    VOID *RegisterProtocolNotify;
    VOID *LocateHandle;
    VOID *LocateDevicePath;
    VOID *InstallConfigurationTable;

    /* Image Services */
    VOID *LoadImage;
    VOID *StartImage;
    VOID *Exit;
    VOID *UnloadImage;
    VOID *ExitBootServices;

    /* Miscellaneous Services */
    VOID      *GetNextMonotonicCount;
    EFI_STALL  Stall;
    VOID      *SetWatchdogTimer;

    /* Driver Support Services */
    VOID *ConnectController;
    VOID *DisconnectController;

    /* Open / Close Protocol Services */
    VOID *OpenProtocol;
    VOID *CloseProtocol;
    VOID *OpenProtocolInformation;

    /* Library Services */
    VOID *ProtocolsPerHandle;
    VOID *LocateHandleBuffer;
    VOID *LocateProtocol;
    VOID *InstallMultipleProtocolInterfaces;
    VOID *UninstallMultipleProtocolInterfaces;

    /* 32-bit CRC / Memory Ops */
    VOID *CalculateCrc32;
    VOID *CopyMem;
    VOID *SetMem;
    VOID *CreateEventEx;
} EFI_BOOT_SERVICES;

/* --------------------------------------------------------------------------
 * 9. Tabela Mestra do Sistema (EFI System Table)
 * -------------------------------------------------------------------------- */
typedef struct {
    EFI_TABLE_HEADER                 Hdr;
    CHAR16                          *FirmwareVendor;
    UINT32                           FirmwareRevision;
    EFI_HANDLE                       ConsoleInHandle;
    EFI_SIMPLE_TEXT_INPUT_PROTOCOL  *ConIn;
    EFI_HANDLE                       ConsoleOutHandle;
    EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *ConOut;
    EFI_HANDLE                       StandardErrorHandle;
    EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *StdErr;
    EFI_RUNTIME_SERVICES            *RuntimeServices;
    EFI_BOOT_SERVICES               *BootServices;
    UINTN                            NumberOfTableEntries;
    VOID                            *ConfigurationTable;
} EFI_SYSTEM_TABLE;

#endif /* IZANAMI_TYPES_H */
