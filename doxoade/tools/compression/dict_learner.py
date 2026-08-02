# -*- coding: utf-8 -*-
# doxoade/tools/compression/dict_learner.py
"""
Dict Learner — Aprendizado de dicionários Zstd por extensão/perfil.

Com holdout real e telemetria detalhada.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import zstandard as zstd

from doxoade.tools.source_profile import ext_of, is_source_path
from doxoade.tools.compression.hybrid_codec import (
    get_profile_for_ext,
    encode as hybrid_encode,
)


LEARNER_VERSION = 1

# Requisitos mínimos para cogitar dicionário (REDUZIDOS para melhor cobertura)
MIN_TRAIN_FILES = 8
MIN_TRAIN_BYTES = 32 * 1024
MIN_CORPUS_BYTES_FOR_DICT = 96 * 1024

# Amostragem
MAX_SAMPLE_FILES = 500
MAX_SAMPLE_BYTES = 16 * 1024 * 1024
MIN_FILE_SIZE = 64
MAX_FILE_SIZE = 1_000_000

# Defaults
DEFAULT_TRAIN_LEVEL = 5
DEFAULT_COMPRESS_LEVEL = 19
DEFAULT_DICT_SIZE = 64 * 1024

# ROI guard (REDUZIDO para aceitar mais dicionários que se pagam)
MIN_NET_GAIN_BYTES = 8 * 1024
MIN_PAYBACK_RATIO = 2.0

DictSizeSpec = Union[int, str]


@dataclass
class DictManifest:
    ext: str
    profile: str
    corpus_sha256: str
    dict_sha256: str
    dict_id: int
    dict_size: int
    stored_size: int
    sample_count: int
    trained_bytes: int
    train_level: int
    compress_level: int
    learner_version: int
    member_path: str
    decision: str = "pending"
    roi: Optional[dict] = None
    telemetry: Optional[dict] = None  # Métricas detalhadas


_DICT_OBJECT_CACHE: Dict[str, zstd.ZstdCompressionDict] = {}


def dict_cache_dir(project_root: Path) -> Path:
    return project_root / ".doxoade" / "compression" / "dictionaries"


def safe_ext(ext: str) -> str:
    return ext.lstrip(".").lower() or "noext"


def calculate_entropy(data: bytes) -> float:
    """
    Calcula entropia de Shannon em bits por byte.
    Arquivos com entropia alta (>7.5) são difíceis de comprimir.
    """
    if not data:
        return 0.0
    
    freq = [0] * 256
    for byte in data:
        freq[byte] += 1
    
    length = len(data)
    entropy = 0.0
    
    for count in freq:
        if count > 0:
            p = count / length
            entropy -= p * math.log2(p)
    
    return entropy


def choose_dict_size(corpus_bytes: int, spec: DictSizeSpec = "auto") -> int:
    """Escolhe tamanho de dicionário por tamanho do corpus."""
    if isinstance(spec, int):
        return max(1024, int(spec))

    s = str(spec).strip().lower()

    if s.isdigit():
        return max(1024, int(s))

    if s.endswith("k"):
        try:
            return max(1024, int(float(s[:-1]) * 1024))
        except Exception:
            pass

    if s.endswith("kb"):
        try:
            return max(1024, int(float(s[:-2]) * 1024))
        except Exception:
            pass

    # auto
    if corpus_bytes < 1_000_000:
        return 16 * 1024
    if corpus_bytes < 5_000_000:
        return 32 * 1024
    if corpus_bytes < 25_000_000:
        return 64 * 1024
    if corpus_bytes < 200_000_000:
        return 112 * 1024

    return 256 * 1024


def make_corpus_hash(
    project_root: Path,
    files: List[Path],
    hashes: Dict[Path, str],
) -> str:
    """Hash estável do corpus."""
    h = hashlib.sha256()
    h.update(f"doxoade-dict-learner:{LEARNER_VERSION}".encode("utf-8"))

    try:
        root = project_root.resolve()
    except Exception:
        root = project_root

    for f in sorted(files, key=lambda p: p.as_posix()):
        file_hash = hashes.get(f)
        if not file_hash:
            continue

        try:
            rel = f.resolve().relative_to(root).as_posix()
        except Exception:
            rel = f.as_posix()

        h.update(rel.encode("utf-8", "replace"))
        h.update(file_hash.encode("ascii", "replace"))

        try:
            h.update(str(f.stat().st_size).encode("ascii"))
        except OSError:
            h.update(b"0")

    return h.hexdigest()


def select_top_extensions(
    project_root: Path,
    files: List[Path],
    top_n: int = 3,
) -> List[Tuple[str, dict]]:
    """Seleciona as maiores extensões por bytes totais."""
    stats: Dict[str, dict] = defaultdict(lambda: {"files": [], "bytes": 0})

    for f in files:
        if not is_source_path(str(f)):
            continue

        try:
            size = f.stat().st_size
        except OSError:
            continue

        ext = ext_of(f.name) or ".noext"
        stats[ext]["files"].append(f)
        stats[ext]["bytes"] += size

    ranked = sorted(
        stats.items(),
        key=lambda kv: (kv[1]["bytes"], kv[0]),
        reverse=True,
    )

    return ranked[: max(0, int(top_n))]


def collect_samples(
    files: List[Path],
    seed: str,
) -> Tuple[List[bytes], int]:
    """Coleta amostras determinísticas para treino."""
    rng = random.Random(seed)

    candidates: List[Tuple[int, Path]] = []

    for f in files:
        try:
            st = f.stat()
        except OSError:
            continue

        if st.st_size < MIN_FILE_SIZE:
            continue

        if st.st_size > MAX_FILE_SIZE:
            continue

        candidates.append((st.st_size, f))

    candidates.sort(key=lambda item: item[1].as_posix())
    rng.shuffle(candidates)

    samples: List[bytes] = []
    total = 0

    for _, f in candidates:
        try:
            data = f.read_bytes()
        except OSError:
            continue

        if not data:
            continue

        samples.append(data)
        total += len(data)

        if len(samples) >= MAX_SAMPLE_FILES:
            break

        if total >= MAX_SAMPLE_BYTES:
            break

    return samples, total


def _split_train_validation(samples: List[bytes]) -> Tuple[List[bytes], List[bytes]]:
    """
    HOLDOUT REAL: separa 70% para treino e 30% para validação.
    Isso evita superestimação do ROI.
    """
    if len(samples) < 24:
        # Poucas amostras: usa todas para treino e validação
        return samples, samples

    split = int(len(samples) * 0.7)
    train_samples = samples[:split]
    validation_samples = samples[split:]

    if not validation_samples:
        validation_samples = train_samples

    return train_samples, validation_samples


def _compressor(
    level: int,
    dict_data: Optional[zstd.ZstdCompressionDict] = None,
) -> zstd.ZstdCompressor:
    kwargs = {
        "level": level,
        "write_checksum": True,
        "write_content_size": True,
    }

    if dict_data is not None:
        kwargs["dict_data"] = dict_data

    try:
        return zstd.ZstdCompressor(threads=os.cpu_count() or 1, **kwargs)
    except TypeError:
        return zstd.ZstdCompressor(**kwargs)


def compress_bytes(
    data: bytes,
    level: int = DEFAULT_COMPRESS_LEVEL,
    dict_data: Optional[zstd.ZstdCompressionDict] = None,
) -> bytes:
    return _compressor(level=level, dict_data=dict_data).compress(data)


def decompress_bytes(
    data: bytes,
    dict_data: Optional[zstd.ZstdCompressionDict] = None,
) -> bytes:
    if dict_data is not None:
        return zstd.ZstdDecompressor(dict_data=dict_data).decompress(data)

    return zstd.ZstdDecompressor().decompress(data)


def compress_dict_for_storage(
    dict_bytes: bytes,
    level: int = DEFAULT_COMPRESS_LEVEL,
) -> bytes:
    """Comprime o próprio dicionário para armazenar no backup."""
    return compress_bytes(dict_bytes, level=level, dict_data=None)


def decompress_dict_bytes(stored_dict_bytes: bytes) -> bytes:
    """Descomprime um dicionário armazenado como .dict.zst."""
    return decompress_bytes(stored_dict_bytes, dict_data=None)


def decompress_file_with_stored_dict(
    compressed_data: bytes,
    stored_dict_bytes: bytes,
) -> bytes:
    """Usado no restore."""
    raw_dict = decompress_dict_bytes(stored_dict_bytes)
    dct = zstd.ZstdCompressionDict(raw_dict)
    return decompress_bytes(compressed_data, dict_data=dct)


def get_dict_object(raw_dict_path: Path) -> zstd.ZstdCompressionDict:
    """Cacheia objetos ZstdCompressionDict em memória."""
    key = str(raw_dict_path)

    if key not in _DICT_OBJECT_CACHE:
        _DICT_OBJECT_CACHE[key] = zstd.ZstdCompressionDict(
            raw_dict_path.read_bytes()
        )

    return _DICT_OBJECT_CACHE[key]


def train_zstd_dictionary(
    samples: List[bytes],
    dict_size: int,
    train_level: int,
    threads: int,
) -> Optional[zstd.ZstdCompressionDict]:
    if not samples:
        return None

    try:
        return zstd.train_dictionary(
            dict_size,
            samples,
            level=train_level,
            threads=threads,
        )
    except TypeError:
        try:
            return zstd.train_dictionary(dict_size, samples)
        except Exception:
            return None
    except Exception:
        return None


def _extract_dict_id(dct: zstd.ZstdCompressionDict) -> int:
    for name in ("dictid", "dict_id"):
        fn = getattr(dct, name, None)
        if callable(fn):
            try:
                return int(fn())
            except Exception:
                pass
    return 0


def _baseline_compressed_size(
    data: bytes,
    profile: str,
    level: int,
) -> int:
    """Baseline é o melhor modo SEM dicionário."""
    if profile == "none":
        return len(compress_bytes(data, level=level))

    try:
        transformed, _ = hybrid_encode(data, profile)
    except Exception:
        transformed = data

    return len(compress_bytes(transformed, level=level))


def evaluate_dictionary_roi(
    samples: List[bytes],
    dict_bytes: bytes,
    stored_dict_bytes: bytes,
    corpus_bytes: int,
    profile: str,
    level: int = DEFAULT_COMPRESS_LEVEL,
    min_net_gain: int = MIN_NET_GAIN_BYTES,
    min_payback_ratio: float = MIN_PAYBACK_RATIO,
) -> dict:
    """
    Avalia se o dicionário se paga usando HOLDOUT REAL.
    Retorna métricas detalhadas para telemetria.
    """
    sample_original = sum(len(s) for s in samples)

    baseline = 0
    with_dict = 0

    dct = zstd.ZstdCompressionDict(dict_bytes)

    # Calcula entropia média das amostras
    entropies = [calculate_entropy(s) for s in samples]
    avg_entropy = sum(entropies) / len(entropies) if entropies else 0.0
    max_entropy = max(entropies) if entropies else 0.0

    for s in samples:
        baseline += _baseline_compressed_size(s, profile, level)
        with_dict += len(compress_bytes(s, level=level, dict_data=dct))

    sample_savings = baseline - with_dict

    gain_rate = sample_savings / max(1, sample_original)
    estimated_gross = int(corpus_bytes * gain_rate)

    overhead = len(stored_dict_bytes)
    estimated_net = estimated_gross - overhead

    payback_ratio = estimated_gross / max(1, overhead)

    # Compressão média por arquivo
    avg_baseline_per_file = baseline / max(1, len(samples))
    avg_dict_per_file = with_dict / max(1, len(samples))

    use = bool(
        sample_savings > 0
        and estimated_net >= min_net_gain
        and payback_ratio >= min_payback_ratio
    )

    return {
        "sample_count": len(samples),
        "sample_original_bytes": sample_original,
        "sample_baseline_bytes": baseline,
        "sample_with_dict_bytes": with_dict,
        "sample_savings_bytes": sample_savings,
        "sample_savings_rate": float(sample_savings / max(1, sample_original)),
        "gain_rate": float(gain_rate),
        "corpus_bytes": int(corpus_bytes),
        "estimated_gross_savings_bytes": int(estimated_gross),
        "dict_raw_bytes": len(dict_bytes),
        "dict_stored_bytes": overhead,
        "estimated_net_savings_bytes": int(estimated_net),
        "payback_ratio": float(payback_ratio),
        "min_net_gain_bytes": int(min_net_gain),
        "min_payback_ratio": float(min_payback_ratio),
        "avg_entropy": float(avg_entropy),
        "max_entropy": float(max_entropy),
        "avg_baseline_per_file": float(avg_baseline_per_file),
        "avg_dict_per_file": float(avg_dict_per_file),
        "use": use,
    }


def load_or_train_extension_dict(
    project_root: Path,
    ext: str,
    files: List[Path],
    hashes: Dict[Path, str],
    corpus_bytes: int,
    dict_size: DictSizeSpec = "auto",
    train_level: int = DEFAULT_TRAIN_LEVEL,
    compress_level: int = DEFAULT_COMPRESS_LEVEL,
    force: bool = False,
    roi_guard: bool = True,
) -> Tuple[Optional[DictManifest], Optional[Path], Optional[bytes]]:
    """
    Carrega dicionário cacheado ou treina novo com HOLDOUT REAL.
    """
    profile = get_profile_for_ext(ext)

    if corpus_bytes < MIN_CORPUS_BYTES_FOR_DICT:
        return None, None, None

    corpus_sha = make_corpus_hash(project_root, files, hashes)

    cache = dict_cache_dir(project_root)
    cache.mkdir(parents=True, exist_ok=True)

    base = f"{safe_ext(ext)}_{corpus_sha[:16]}"

    manifest_path = cache / f"{base}.json"
    raw_dict_path = cache / f"{base}.dict"
    stored_dict_path = cache / f"{base}.dict.zst"

    # Cache hit
    if not force and manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = DictManifest(**data)

            if manifest.decision == "skip":
                return manifest, None, None

            if (
                manifest.decision == "use"
                and raw_dict_path.exists()
                and stored_dict_path.exists()
            ):
                return (
                    manifest,
                    raw_dict_path,
                    stored_dict_path.read_bytes(),
                )
        except Exception:
            # cache corrompido: retreina
            pass

    samples, trained_bytes = collect_samples(files, corpus_sha)

    if len(samples) < MIN_TRAIN_FILES or trained_bytes < MIN_TRAIN_BYTES:
        return None, None, None

    # HOLDOUT REAL: separa treino e validação
    train_samples, validation_samples = _split_train_validation(samples)

    chosen_size = choose_dict_size(corpus_bytes, dict_size)
    threads = os.cpu_count() or 1

    # Treina com 70% das amostras
    dct = train_zstd_dictionary(
        samples=train_samples,
        dict_size=chosen_size,
        train_level=train_level,
        threads=threads,
    )

    if dct is None:
        return None, None, None

    dict_bytes = dct.as_bytes()
    stored_dict_bytes = compress_dict_for_storage(
        dict_bytes,
        level=compress_level,
    )

    dict_sha = hashlib.sha256(dict_bytes).hexdigest()
    dict_id = _extract_dict_id(dct)

    member_path = f"__doxoade/dicts/{dict_sha}.dict.zst"

    # Avalia ROI nos 30% de validação (HOLDOUT)
    roi = evaluate_dictionary_roi(
        samples=validation_samples,
        dict_bytes=dict_bytes,
        stored_dict_bytes=stored_dict_bytes,
        corpus_bytes=corpus_bytes,
        profile=profile,
        level=compress_level,
    )

    decision = "use" if (not roi_guard or roi.get("use")) else "skip"

    # Telemetria detalhada
    telemetry = {
        "file_count": len(files),
        "corpus_bytes": corpus_bytes,
        "trained_on_samples": len(train_samples),
        "validated_on_samples": len(validation_samples),
        "trained_bytes": trained_bytes,
        "dict_size_chosen": chosen_size,
        "avg_entropy_all": roi.get("avg_entropy", 0.0),
        "max_entropy_all": roi.get("max_entropy", 0.0),
    }

    manifest = DictManifest(
        ext=ext,
        profile=profile,
        corpus_sha256=corpus_sha,
        dict_sha256=dict_sha,
        dict_id=dict_id,
        dict_size=len(dict_bytes),
        stored_size=len(stored_dict_bytes),
        sample_count=len(samples),
        trained_bytes=trained_bytes,
        train_level=train_level,
        compress_level=compress_level,
        learner_version=LEARNER_VERSION,
        member_path=member_path,
        decision=decision,
        roi=roi,
        telemetry=telemetry,
    )

    raw_dict_path.write_bytes(dict_bytes)
    stored_dict_path.write_bytes(stored_dict_bytes)
    manifest_path.write_text(
        json.dumps(asdict(manifest), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if decision == "use":
        return manifest, raw_dict_path, stored_dict_bytes

    return manifest, None, None


def prepare_dictionaries(
    project_root: Path,
    files: List[Path],
    hashes: Dict[Path, str],
    top_n: int = 3,
    dict_size: DictSizeSpec = "auto",
    train_level: int = DEFAULT_TRAIN_LEVEL,
    compress_level: int = DEFAULT_COMPRESS_LEVEL,
    force: bool = False,
    roi_guard: bool = True,
) -> dict:
    """Prepara dicionários para o backup."""
    top = select_top_extensions(project_root, files, top_n=top_n)

    by_ext: Dict[str, Tuple[DictManifest, Path]] = {}
    members: Dict[str, bytes] = {}
    manifests: List[dict] = []
    top_info: List[Tuple[str, int, int]] = []

    for ext, info in top:
        corpus_bytes = int(info.get("bytes", 0))
        file_list = info.get("files", [])

        top_info.append((ext, corpus_bytes, len(file_list)))

        manifest, raw_path, stored_bytes = load_or_train_extension_dict(
            project_root=project_root,
            ext=ext,
            files=file_list,
            hashes=hashes,
            corpus_bytes=corpus_bytes,
            dict_size=dict_size,
            train_level=train_level,
            compress_level=compress_level,
            force=force,
            roi_guard=roi_guard,
        )

        if manifest is not None:
            manifests.append(asdict(manifest))

        if (
            manifest is not None
            and manifest.decision == "use"
            and raw_path is not None
            and stored_bytes is not None
        ):
            by_ext[ext] = (manifest, raw_path)
            members[manifest.member_path] = stored_bytes

    return {
        "by_ext": by_ext,
        "members": members,
        "manifests": manifests,
        "top": top_info,
    }


def compress_file_for_backup(
    raw: bytes,
    ext: str,
    compress_mode: str,
    compress_level: int,
    dictionaries: Dict[str, Tuple[DictManifest, Path]],
) -> Tuple[bytes, dict]:
    """Função principal para o engine chamar por arquivo."""
    profile = get_profile_for_ext(ext)

    mode = (compress_mode or "auto").lower()

    # Learned / Hybrid / Auto com dicionário
    if mode in ("auto", "hybrid", "learned"):
        item = dictionaries.get(ext)

        if item is not None:
            manifest, raw_dict_path = item
            dict_obj = get_dict_object(raw_dict_path)

            compressed = compress_bytes(
                raw,
                level=compress_level,
                dict_data=dict_obj,
            )

            codec_meta = {
                "codec": "zstd+dict",
                "ext": ext,
                "profile": profile,
                "dict_sha256": manifest.dict_sha256,
                "dict_member": manifest.member_path,
                "dict_id": manifest.dict_id,
                "dict_compressed": True,
                "zstd_level": compress_level,
                "learner_version": manifest.learner_version,
            }

            return compressed, codec_meta

        # learned sem dicionário válido cai para plain
        if mode == "learned":
            compressed = compress_bytes(raw, level=compress_level)
            codec_meta = {
                "codec": "zstd",
                "profile": profile,
                "zstd_level": compress_level,
            }
            return compressed, codec_meta

    # Static / fallback hybrid
    if mode in ("auto", "hybrid", "static"):
        try:
            transformed, meta = hybrid_encode(raw, profile)
        except Exception:
            transformed = raw
            meta = {"profile": profile}

        compressed = compress_bytes(transformed, level=compress_level)

        codec_meta = {
            "codec": "hybrid-static",
            "zstd_level": compress_level,
            **meta,
        }

        return compressed, codec_meta

    # plain
    compressed = compress_bytes(raw, level=compress_level)

    codec_meta = {
        "codec": "zstd",
        "profile": profile,
        "zstd_level": compress_level,
    }

    return compressed, codec_meta