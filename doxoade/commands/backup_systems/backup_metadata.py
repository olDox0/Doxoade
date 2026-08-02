# -*- coding: utf-8 -*-
# doxoade/commands/backup_systems/backup_metadata.py
"""
Backup Metadata — Estrutura de metadados para cada backup.
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

@dataclass
class FileManifest:
    """Manifest de um arquivo no backup."""
    path: str
    size: int
    mtime: float
    sha256: str
    included: bool  # False se é delta e arquivo não mudou
    codec_meta: dict = None
    
@dataclass
class BackupMetadata:
    """Metadados completos de um backup."""
    backup_id: str
    timestamp: str
    backup_type: str
    parent_backup_id: Optional[str]
    project_root: str
    total_files: int
    included_files: int
    total_size_bytes: int
    compressed_size_bytes: int
    compression_ratio: float
    files: List[FileManifest]
    ext_excluded: dict = None
    ext_included: dict = None
    compression_mode: str = "auto"
    dictionaries: List[dict] = None
    telemetry: dict = None  # NOVO: métricas agregadas
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'BackupMetadata':
        data = json.loads(json_str)
        files = [FileManifest(**f) for f in data.pop('files', [])]
        return cls(**data, files=files)

def compute_file_hash(path: Path, chunk_size: int = 8192) -> str:
    """
    SHA256 em chunks. Ma'at/PASC-6: NUNCA levanta por arquivo ilegível.
    PermissionError/OSError (arquivo travado pelo SO, antivírus, junction
    quebrada) vira None — o caller marca o arquivo como pulado e o backup
    segue. Um backup não morre por causa de um arquivo.
    """
    sha256 = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                sha256.update(chunk)
    except (PermissionError, OSError):
        return None
    return sha256.hexdigest()

def load_previous_metadata(backup_dir: Path) -> Optional[BackupMetadata]:
    """Carrega metadados do backup mais recente."""
    backups = sorted(backup_dir.glob('backup_*.meta.json'), reverse=True)
    if not backups:
        return None
    with open(backups[0], 'r', encoding='utf-8') as f:
        return BackupMetadata.from_json(f.read())
        
def _restore_file(tar_member, tar_file, target_path, codec_meta):
    """Restaura um arquivo aplicando o codec correto."""
    import zstandard as zstd
    from . import hybrid_codec

    codec = (codec_meta or {}).get("codec", "hybrid-static")
    compressed_data = tar_file.extractfile(tar_member).read()

    if codec == "zstd+dict":
        dict_sha = codec_meta.get("dict_sha256")
        dict_member = codec_meta.get(
            "dict_member",
            f"__doxoade/dicts/{dict_sha}.dict.zst",
        )

        stored_dict_bytes = tar_file.extractfile(dict_member).read()
        raw_dict_bytes = zstd.ZstdDecompressor().decompress(stored_dict_bytes)
        dct = zstd.ZstdCompressionDict(raw_dict_bytes)

        dctx = zstd.ZstdDecompressor(dict_data=dct)
        raw_data = dctx.decompress(compressed_data)

    elif codec == "zstd":
        dctx = zstd.ZstdDecompressor()
        raw_data = dctx.decompress(compressed_data)

    else:
        dctx = zstd.ZstdDecompressor()
        transformed_data = dctx.decompress(compressed_data)
        raw_data = hybrid_codec.decode(
            transformed_data,
            codec_meta or {"profile": "none"},
        )

    Path(target_path).parent.mkdir(parents=True, exist_ok=True)

    with open(target_path, "wb") as f:
        f.write(raw_data)