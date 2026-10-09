# -*- coding: utf-8 -*-
# doxoade/tools/emulator_systems/disk_forge.py
"""
[HEFESTO] Disk Forge v1.0 — Forjador Soberano de Mídias UEFI / ESP.
Gera imagens particionadas MBR/ESP com FAT16 nativo e árvore /EFI/BOOT/ em Python puro.
Em total conformidade com o protocolo ProDeNov (Art. 2 e 3).
"""

import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DiskForgeConfig:
    """Configuração da imagem de disco EFI."""
    output_image: str = "uefi_disk.img"
    kernel_payload: Optional[Path] = None
    arch: str = "ia32"          # 'ia32' (Bay Trail N2808) ou 'x64'
    disk_size_mb: int = 32      # Tamanho total da imagem
    volume_label: str = "DOX_ESP"
    dry_run: bool = False


@dataclass
class DiskForgeResult:
    """Relatório da forja de imagem."""
    success: bool
    output_path: Path
    size_bytes: int
    target_efi_name: str
    message: str = ""


class DiskForge:
    """
    Forjador autônomo de sistemas de arquivos FAT16 com partição MBR ESP (0xEF).
    Zero dependências de utilitários de sistema (mtools, parted ou privilégio root).
    """

    SECTOR_SIZE = 512
    PARTITION_START_LBA = 2048   # Alinhamento padrão de 1 MB (2048 * 512)
    SECTORS_PER_CLUSTER = 4      # Cluster de 2 KB
    ROOT_ENTRIES = 512           # 512 entradas de diretório raiz (32 setores)

    def __init__(self, project_root: str = "."):
        self.root = Path(project_root).resolve()

    def forge_uefi(self, cfg: DiskForgeConfig) -> DiskForgeResult:
        """
        [HEFESTO] Forja imagem particionada contendo /EFI/BOOT/BOOT{ARCH}.EFI.
        """
        out_path = Path(cfg.output_image)
        if not out_path.is_absolute():
            out_path = self.root / out_path

        efi_binary_name = "BOOTIA32.EFI" if cfg.arch.lower() == "ia32" else "BOOTX64.EFI"

        # Leitura do payload do kernel
        payload_data = b""
        if cfg.kernel_payload:
            k_path = Path(cfg.kernel_payload)
            if not k_path.is_absolute():
                k_path = self.root / k_path
            if not k_path.exists():
                return DiskForgeResult(
                    success=False,
                    output_path=out_path,
                    size_bytes=0,
                    target_efi_name=efi_binary_name,
                    message=f"Kernel payload não encontrado: {k_path}"
                )
            payload_data = k_path.read_bytes()
        else:
            # Stub de fallback (executável EFI nulo para validação de boot)
            payload_data = b"DOXOADE_EFI_STUB\x00"

        total_bytes = cfg.disk_size_mb * 1024 * 1024
        total_sectors = total_bytes // self.SECTOR_SIZE

        if total_sectors <= self.PARTITION_START_LBA + 1024:
            return DiskForgeResult(
                success=False,
                output_path=out_path,
                size_bytes=0,
                target_efi_name=efi_binary_name,
                message="Tamanho de disco insuficiente para partição ESP."
            )

        if cfg.dry_run:
            return DiskForgeResult(
                success=True,
                output_path=out_path,
                size_bytes=total_bytes,
                target_efi_name=efi_binary_name,
                message="[DRY-RUN] Simulação de forja de partição concluída."
            )

        # -----------------------------------------------------------------
        # 1. Estruturação dos dados e alocação FAT16
        # -----------------------------------------------------------------
        part_sectors = total_sectors - self.PARTITION_START_LBA
        reserved_sectors = 4
        num_fats = 2
        root_dir_sectors = (self.ROOT_ENTRIES * 32) // self.SECTOR_SIZE  # 32 setores

        # Cálculo de setores da FAT
        data_sectors_approx = part_sectors - (reserved_sectors + root_dir_sectors)
        clusters_approx = data_sectors_approx // self.SECTORS_PER_CLUSTER
        sectors_per_fat = math.ceil((clusters_approx * 2) / self.SECTOR_SIZE)

        # -----------------------------------------------------------------
        # 2. Montagem do MBR (LBA 0)
        # -----------------------------------------------------------------
        mbr = bytearray(self.SECTOR_SIZE)
        # Assinatura de código inicial nula
        mbr[0:3] = b"\xEB\x5E\x90"
        
        # Entrada 1 da Tabela de Partição MBR (Offset 446 / 0x1BE)
        # Flags: 0x80 (Bootável), Tipo: 0xEF (EFI System Partition)
        part_entry = struct.pack(
            "<B3sB3sII",
            0x80,                      # Status ativo
            b"\x00\x02\x00",           # CHS inicial
            0xEF,                      # Tipo ESP (0xEF)
            b"\xFF\xFF\xFF",           # CHS final
            self.PARTITION_START_LBA,  # LBA inicial
            part_sectors               # Setores totais
        )
        mbr[0x1BE:0x1BE + 16] = part_entry
        mbr[510:512] = b"\x55\xAA"

        # -----------------------------------------------------------------
        # 3. Montagem do VBR / BPB FAT16 (LBA 2048)
        # -----------------------------------------------------------------
        vbr = bytearray(self.SECTOR_SIZE)
        vbr[0:3] = b"\xEB\x3C\x90"
        vbr[3:11] = b"DOXOADE "
        struct.pack_into(
            "<HBHBHHBHHHII",
            vbr, 11,
            self.SECTOR_SIZE,
            self.SECTORS_PER_CLUSTER,
            reserved_sectors,
            num_fats,
            self.ROOT_ENTRIES,
            0 if part_sectors > 65535 else part_sectors,
            0xF8,                      # Mídia Fixed Disk
            sectors_per_fat,
            63,                        # Sectors per track
            255,                       # Heads (NumHeads)
            self.PARTITION_START_LBA,  # Hidden sectors
            part_sectors if part_sectors > 65535 else 0
        )
        # Extended BPB
        struct.pack_into("<BBBI11s8s", vbr, 36, 0x80, 0, 0x29, 0x12345678, b"DOX_ESP    ", b"FAT16   ")
        vbr[510:512] = b"\x55\xAA"

# -----------------------------------------------------------------
        # 4. Alocação de Clusters e Diretórios (/EFI/BOOT/BOOTxx.EFI)
        # Cluster 2 = /EFI
        # Cluster 3 = /EFI/BOOT
        # Cluster 4..N = Dados do binário EFI
        # -----------------------------------------------------------------
        cluster_bytes = self.SECTORS_PER_CLUSTER * self.SECTOR_SIZE
        payload_clusters = math.ceil(len(payload_data) / cluster_bytes) or 1

        # Construção da FAT (Tabela de Alocação)
        fat = bytearray(sectors_per_fat * self.SECTOR_SIZE)
        struct.pack_into("<H", fat, 0, 0xFFF8)  # ID de mídia
        struct.pack_into("<H", fat, 2, 0xFFFF)  # Reservado
        struct.pack_into("<H", fat, 4, 0xFFFF)  # Cluster 2 (EOF do dir /EFI)
        struct.pack_into("<H", fat, 6, 0xFFFF)  # Cluster 3 (EOF do dir /EFI/BOOT)

        # Encadeamento dos clusters do arquivo EFI
        start_payload_cluster = 4
        for i in range(payload_clusters):
            c_num = start_payload_cluster + i
            next_val = 0xFFFF if i == (payload_clusters - 1) else (c_num + 1)
            struct.pack_into("<H", fat, c_num * 2, next_val)

        # Função auxiliar blindada para empacotar entrada FAT (32 bytes exatos)
        def pack_dir_entry(buf: bytearray, offset: int, name_11s: bytes, attr: int, fst_clus: int, size: int = 0):
            struct.pack_into(
                "<11sBBBHHHHHHHI",
                buf, offset,
                name_11s,
                attr,
                0, 0,       # NTRes, CrtTimeTenth
                0, 0, 0,    # CrtTime, CrtDate, LstAccDate
                0,          # FstClusHI (0 em FAT16)
                0, 0,       # WrtTime, WrtDate
                fst_clus,   # FstClusLO
                size        # FileSize (4 bytes)
            )

        # Diretório Raiz
        root_dir = bytearray(root_dir_sectors * self.SECTOR_SIZE)
        root_dir[0:11] = b"DOX_ESP    "
        root_dir[11] = 0x08  # Volume ID
        # Entrada para pasta /EFI (Cluster 2)
        pack_dir_entry(root_dir, 32, b"EFI        ", 0x10, 2, 0)

        # Cluster 2: Conteúdo de /EFI
        efi_dir_cluster = bytearray(cluster_bytes)
        pack_dir_entry(efi_dir_cluster, 0,  b".          ", 0x10, 2, 0)
        pack_dir_entry(efi_dir_cluster, 32, b"..         ", 0x10, 0, 0)
        # Entrada para subpasta /EFI/BOOT (Cluster 3)
        pack_dir_entry(efi_dir_cluster, 64, b"BOOT       ", 0x10, 3, 0)

        # Cluster 3: Conteúdo de /EFI/BOOT
        boot_dir_cluster = bytearray(cluster_bytes)
        pack_dir_entry(boot_dir_cluster, 0,  b".          ", 0x10, 3, 0)
        pack_dir_entry(boot_dir_cluster, 32, b"..         ", 0x10, 2, 0)

        # Formata o nome 8.3 do arquivo EFI (ex: 'BOOTIA32EFI')
        efi_83_name = f"{efi_binary_name.split('.')[0]:<8}{efi_binary_name.split('.')[1]:<3}".encode("ascii")
        # Entrada para o arquivo executável EFI (Cluster 4..N)
        pack_dir_entry(boot_dir_cluster, 64, efi_83_name, 0x20, start_payload_cluster, len(payload_data))

        # Preenchimento do payload do arquivo
        payload_aligned = payload_data + b"\x00" * (payload_clusters * cluster_bytes - len(payload_data))

        # -----------------------------------------------------------------
        # 5. Gravação Soberana no Disco
        # -----------------------------------------------------------------
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            # LBA 0: MBR
            f.write(mbr)
            # Preenche até o LBA 2048 (1 MB de alinhamento)
            f.write(b"\x00" * (self.PARTITION_START_LBA * self.SECTOR_SIZE - len(mbr)))
            
            # Início da Partição ESP:
            # 1. VBR
            f.write(vbr)
            f.write(b"\x00" * ((reserved_sectors - 1) * self.SECTOR_SIZE))
            
            # 2. FAT 1 e FAT 2
            f.write(fat)
            f.write(fat)
            
            # 3. Diretório Raiz
            f.write(root_dir)
            
            # 4. Dados de Clusters
            f.write(efi_dir_cluster)     # Cluster 2 (/EFI)
            f.write(boot_dir_cluster)    # Cluster 3 (/EFI/BOOT)
            f.write(payload_aligned)     # Clusters 4..N (Payload)
            
            # 5. Preenchimento final até o tamanho total da imagem
            current_pos = f.tell()
            if current_pos < total_bytes:
                f.write(b"\x00" * (total_bytes - current_pos))

        return DiskForgeResult(
            success=True,
            output_path=out_path,
            size_bytes=total_bytes,
            target_efi_name=efi_binary_name,
            message=f"Imagem UEFI forjada: {out_path.name} ({cfg.disk_size_mb} MB) contendo /EFI/BOOT/{efi_binary_name}"
        )
