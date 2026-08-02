# -*- coding: utf-8 -*-
# doxoade/commands/backup_systems/backup_engine.py
"""
Backup Engine v3.0 — SAP/Strap + Ignore soberano + fail-graceful + Learned Compression.

Mudanças principais:
- Pipeline em duas fases: scan/hash -> preparação de dicionários -> compressão.
- Dicionários Zstd por extensão/perfil com ROI guard via dict_learner.
- Restore correto usando codec_meta, não extractall bruto.
- Container .tar.gz externo (leve) + membros internos em Zstd/Zstd+dict.
- Estatísticas separadas para skipped, unchanged, compressed, dict overhead.
"""

import asyncio
import fnmatch
import io
import os
import stat
import tarfile
import time
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

import zstandard as zstd

from .backup_metadata import (
    BackupMetadata,
    FileManifest,
    compute_file_hash,
    load_previous_metadata,
)
from doxoade.tools.source_profile import is_source_path, ext_of
from doxoade.tools.compression import hybrid_codec

try:
    from doxoade.tools.compression import dict_learner
    DICT_LEARNER_ERROR = None
except Exception as e:
    dict_learner = None
    DICT_LEARNER_ERROR = e

try:
    from doxoade.tools.async_log_systems.async_echo import echout, drain
except Exception:
    def echout(*a, **k):
        print(*a)

    def drain():
        pass


# ============================================================================
# Configurações
# ============================================================================

PITSTOP_INTERVAL = 1000
HASH_CHUNK_SIZE = 8192

DEFAULT_COMPRESS_LEVEL = 19
DEFAULT_DICT_TOP = 3
DEFAULT_DICT_SIZE = "auto"

# Gzip externo leve: serve principalmente para comprimir os headers do tar,
# já que os membros internos estão em Zstd.
TAR_GZ_LEVEL = 3

VALID_COMPRESS_MODES = {
    "auto",
    "plain",
    "static",
    "learned",
    "hybrid",
}


# Piso de segurança: cobre o ruído óbvio mesmo se o pyproject não tiver ignore.
HARDCODED_IGNORE = [
    # VCS / IDE
    ".git/",
    ".hg/",
    ".svn/",
    ".idea/",
    ".vscode/",
    ".swp",

    # Python
    "__pycache__/",
    "pycache/",
    ".py[cod]",
    "$py.class",
    ".egg-info/",
    ".egg",
    "build/",
    "dist/",
    ".eggs/",

    # venvs
    "venv/",
    ".venv/",
    "env/",
    ".env/",

    # Doxoade / artefatos / caches
    ".doxoade/",
    ".doxoade_cache/",
    "w64devkit/",
    "nppBackup/",
    "recovery_zone/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",

    # ruído diverso
    "node_modules/",
    ".log",
    ".bak",
    ".old",
    "*.tmp",
    "tmp/",
    "pytest_temp_dir/",
    ".dox_agent_workspace/",

    # SO
    "Thumbs.db",
    "desktop.ini",
    ".DS_Store",
]


# ============================================================================
# Matcher de ignore
# ============================================================================

def _compile_patterns(patterns: List[str]) -> List[Tuple[str, str]]:
    """
    Pré-compila padrões na semântica documentada:

    - com '*' ou '?' ou '[...]' -> glob
    - com '/'                   -> prefixo de diretório
    - com '/' no final          -> igualdade de componente
    - solta                     -> substring de componente
    """
    out: List[Tuple[str, str]] = []

    for e in patterns:
        e = str(e).strip()
        if not e:
            continue

        star = ("*" in e) or ("?" in e) or (("[" in e) and ("]" in e))
        e2 = e.rstrip("/")
        donly = e.endswith("/")
        slash = "/" in e2

        if star:
            kind = "glob"
        elif slash:
            kind = "prefix"
        elif donly:
            kind = "cmpeq"
        else:
            kind = "compsub"

        out.append((kind, e2))

    return out


def _match_one(rel: str, comps: List[str], kind: str, e2: str) -> bool:
    if kind == "glob":
        return fnmatch.fnmatch(rel, e2) or fnmatch.fnmatch(comps[-1], e2)

    if kind == "prefix":
        return rel == e2 or rel.startswith(e2 + "/")

    if kind == "cmpeq":
        return e2 in comps

    # compsub
    return any(e2 in c for c in comps)


def _is_excluded(rel_posix: str, comps: List[str], compiled: List[Tuple[str, str]]) -> bool:
    return any(_match_one(rel_posix, comps, k, e2) for k, e2 in compiled)


def _load_toml_ignores(project_root: Path) -> List[str]:
    """Lê [tool.doxoade].ignore do pyproject.toml (fail-graceful)."""
    toml_path = project_root / "pyproject.toml"

    if not toml_path.exists():
        return []

    try:
        try:
            import tomllib
            with open(toml_path, "rb") as f:
                data = tomllib.load(f)
        except ImportError:
            import toml
            data = toml.load(str(toml_path))
    except Exception as e:
        echout(
            f"   ⚠️  pyproject.toml ilegível ({type(e).name}); "
            f"ignore do toml não aplicado",
            level="warn",
        )
        return []

    raw = (data.get("tool", {}) or {}).get("doxoade", {}) or {}
    ign = raw.get("ignore", []) or []
    return [str(p).strip() for p in ign if str(p).strip()]


# ============================================================================
# Engine
# ============================================================================

class BackupEngineStrap:
    """Motor de backup com ignore soberano, fail-graceful e compressão aprendida."""

    def __init__(self, project_root: Path, backup_dir: Path):
        self.project_root = Path(project_root).resolve()
        self.backup_dir = Path(backup_dir).resolve()
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self.tar = None
        self.manifests: List[FileManifest] = []
        self.previous_meta: Optional[BackupMetadata] = None
        self._t0 = 0.0

        self.stats = self._new_stats()

        self._ext_excluded: Dict[str, int] = {}
        self._paths_by_rel: Dict[str, Path] = {}
        self._hashes_by_rel: Dict[str, str] = {}

        self.include_all = False
        self.compress_mode = "auto"
        self.compress_level = DEFAULT_COMPRESS_LEVEL
        self.dict_top = DEFAULT_DICT_TOP
        self.dict_size = DEFAULT_DICT_SIZE
        self.retrain_dict = False
        self.roi_guard = True
        self.prep: Optional[dict] = None

    def _new_stats(self) -> dict:
        return {
            "scanned": 0,
            "hashed": 0,
            "compressed": 0,
            "skipped": 0,
            "unchanged": 0,
            "pitstops": 0,
            "ignore_patterns": 0,
            "dict_members": 0,
            "dict_bytes": 0,
        }

    # ------------------------------------------------------------------------
    # Ignore
    # ------------------------------------------------------------------------

    def _build_compiled(self):
        toml_pats = _load_toml_ignores(self.project_root)

        # Nunca fazer backup do próprio diretório de backups.
        try:
            if str(self.backup_dir).startswith(str(self.project_root)):
                rel = self.backup_dir.relative_to(self.project_root).as_posix()
                toml_pats.append(rel + "/")
        except Exception:
            pass

        self.stats["ignore_patterns"] = len(HARDCODED_IGNORE) + len(toml_pats)
        return _compile_patterns(list(HARDCODED_IGNORE) + toml_pats), len(toml_pats)

    # ------------------------------------------------------------------------
    # Orquestração principal
    # ------------------------------------------------------------------------

    async def create_backup(
        self,
        delta: bool = False,
        include_all: bool = False,
        compress_mode: str = "auto",
        compress_level: int = DEFAULT_COMPRESS_LEVEL,
        dict_top: int = DEFAULT_DICT_TOP,
        dict_size: str = DEFAULT_DICT_SIZE,
        retrain_dict: bool = False,
        roi_guard: bool = True,
    ) -> Optional[BackupMetadata]:
        """
        Cria backup.

        Modos de compressão:
        - auto:    igual hybrid
        - plain:   zstd puro
        - static:  hybrid-static + zstd
        - learned: zstd+dict se houver; senão plain
        - hybrid:  zstd+dict se pagar; senão static
        """
        # Configuração da run
        self.include_all = bool(include_all)

        self.compress_mode = str(compress_mode or "auto").lower()
        if self.compress_mode not in VALID_COMPRESS_MODES:
            self.compress_mode = "auto"

        self.compress_level = int(compress_level)
        self.dict_top = int(dict_top)
        self.dict_size = dict_size
        self.retrain_dict = bool(retrain_dict)
        self.roi_guard = bool(roi_guard)

        # Estado
        self.stats = self._new_stats()
        self._ext_excluded = {}
        self._paths_by_rel = {}
        self._hashes_by_rel = {}
        self.manifests = []
        self.prep = None

        compiled, n_toml = self._build_compiled()

        self._t0 = time.perf_counter()
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_id = f"backup_{timestamp}"

        # Container .tar.gz com gzip leve sobre membros internos Zstd.
        backup_path = self.backup_dir / f"{backup_id}.tar.gz"

        self.previous_meta = load_previous_metadata(self.backup_dir) if delta else None

        echout("🚀 Iniciando Backup Engine v3.0")
        echout(f"   📦 Projeto: {self.project_root.name}")
        echout(f"   🎯 Destino: {backup_path.name}")
        echout(f"   🔄 Modo   : {'DELTA' if delta else 'COMPLETO'}")
        echout(
            "   🎯 Escopo : "
            f"{'TUDO (--all)' if self.include_all else 'SÓ FONTE (código/config/texto)'}"
        )
        echout(
            f"   🧹 Ignore : {n_toml} padrões do pyproject.toml + "
            f"{len(HARDCODED_IGNORE)} internos "
            f"({self.stats['ignore_patterns']} ativos)"
        )
        echout(f"   🗜️  Compress: {self.compress_mode} | level={self.compress_level}")
        echout(
            f"   📚 Dicionário: top={self.dict_top} | size={self.dict_size} | "
            f"retrain={self.retrain_dict} | roi_guard={self.roi_guard}"
        )
        echout("")

        if dict_learner is None and self.compress_mode in ("auto", "hybrid", "learned"):
            echout(
                "   ⚠️  dict_learner indisponível; "
                "compressão aprendida desativada para esta execução.",
                level="warn",
            )
            if DICT_LEARNER_ERROR is not None:
                echout(f"      Erro de import: {DICT_LEARNER_ERROR}", level="warn")

        # Fase 1: scan + hash
        candidate_manifests = await self._scan_and_hash(compiled)

        if not candidate_manifests:
            echout("   ⏭️  Nenhuma fonte alterada — snapshot descartado (sem tar/meta).")
            return None

        # Fase 2: preparação de dicionários
        self.prep = self._prepare_dictionaries(candidate_manifests)
        self._print_dict_plan()

        # Fase 3: escrita do tar + compressão dos arquivos
        try:
            with tarfile.open(
                backup_path,
                "w:gz",
                compresslevel=TAR_GZ_LEVEL,
                format=tarfile.GNU_FORMAT,
            ) as tar:
                self.tar = tar

                # 3.1. Dicionários usados entram antes dos arquivos.
                for member_path, data in self.prep.get("members", {}).items():
                    self._add_bytes_to_tar(member_path, data, int(time.time()))
                    self.stats["dict_members"] += 1
                    self.stats["dict_bytes"] += len(data)

                # 3.2. Arquivos do backup.
                for manifest in candidate_manifests:
                    path = self._paths_by_rel.get(manifest.path)
                    if path is None:
                        continue

                    try:
                        raw = await asyncio.to_thread(path.read_bytes)
                        ext = ext_of(manifest.path)

                        compressed, codec_meta = self._compress_file(raw, ext)

                        self._add_bytes_to_tar(
                            manifest.path,
                            compressed,
                            int(manifest.mtime),
                        )

                        manifest.codec_meta = codec_meta
                        self.manifests.append(manifest)
                        self.stats["compressed"] += 1

                        if self.stats["compressed"] % PITSTOP_INTERVAL == 0:
                            self.stats["pitstops"] += 1
                            echout(
                                f"   🛑 [PITSTOP {self.stats['pitstops']}] "
                                f"{self.stats['compressed']} gravados"
                            )

                    except (PermissionError, OSError, FileNotFoundError):
                        manifest.included = False
                        self.stats["skipped"] += 1

        finally:
            self.tar = None
            drain()

        # Ma'at: se nada sobreviveu, descarta o tar.
        if not self.manifests:
            try:
                backup_path.unlink()
            except OSError:
                pass
            echout("   ⏭️  Nenhum arquivo pôde ser gravado — snapshot descartado.")
            return None

        metadata = self._build_metadata(backup_id, backup_path, delta)

        (self.backup_dir / f"{backup_id}.meta.json").write_text(
            metadata.to_json(),
            encoding="utf-8",
        )

        self._print_final_report(metadata, backup_path)
        return metadata

    # ------------------------------------------------------------------------
    # Fase 1: scan + hash
    # ------------------------------------------------------------------------

    async def _scan_and_hash(self, compiled) -> List[FileManifest]:
        """
        Varre o projeto com poda de árvore e já calcula hash dos arquivos.

        Retorna apenas os manifests que devem ser comprimidos:
        - full: todos os fontes válidos
        - delta: somente os alterados
        """
        manifests: List[FileManifest] = []

        prev_by_path: Dict[str, FileManifest] = {}
        if self.previous_meta:
            prev_by_path = {p.path: p for p in self.previous_meta.files}

        for root, dirs, files in os.walk(
            self.project_root,
            topdown=True,
            followlinks=False,
        ):
            rel_root = Path(root).relative_to(self.project_root)

            # Poda de diretórios ignorados.
            kept = []
            for d in dirs:
                drel = rel_root.joinpath(d).as_posix()
                if _is_excluded(drel, drel.split("/"), compiled):
                    continue
                kept.append(d)
            dirs[:] = kept

            for f in files:
                # BPC0: só fonte, salvo --all.
                if not self.include_all and not is_source_path(f):
                    ex = ext_of(f) or "<none>"
                    self._ext_excluded[ex] = self._ext_excluded.get(ex, 0) + 1
                    continue

                frel = rel_root.joinpath(f).as_posix()
                if _is_excluded(frel, frel.split("/"), compiled):
                    continue

                full = Path(root) / f

                try:
                    st = full.stat()
                except (PermissionError, OSError, FileNotFoundError):
                    self.stats["skipped"] += 1
                    continue

                if not stat.S_ISREG(st.st_mode):
                    continue

                self.stats["scanned"] += 1

                h = await asyncio.to_thread(compute_file_hash, full, HASH_CHUNK_SIZE)
                if h is None:
                    self.stats["skipped"] += 1
                    continue

                self.stats["hashed"] += 1

                manifest = FileManifest(
                    path=frel,
                    size=st.st_size,
                    mtime=st.st_mtime,
                    sha256=h,
                    included=True,
                )

                # Delta: se inalterado, não entra no novo tar.
                prev = prev_by_path.get(frel)
                if prev and prev.sha256 == h and prev.size == manifest.size:
                    manifest.included = False
                    self.stats["unchanged"] += 1
                    continue

                self._paths_by_rel[frel] = full
                self._hashes_by_rel[frel] = h
                manifests.append(manifest)

                if self.stats["scanned"] % 100 == 0:
                    echout(f"   📂 Scanner: {self.stats['scanned']} coletados")

        return manifests

    # ------------------------------------------------------------------------
    # Fase 2: dicionários
    # ------------------------------------------------------------------------

    def _prepare_dictionaries(self, manifests: List[FileManifest]) -> dict:
        """
        Prepara dicionários por extensão usando dict_learner.

        Se dict_learner não estiver disponível ou modo não usar dicionário,
        retorna estrutura vazia.
        """
        empty = {
            "by_ext": {},
            "members": {},
            "manifests": [],
            "top": [],
        }

        if dict_learner is None:
            return empty

        if self.compress_mode not in ("auto", "hybrid", "learned"):
            return empty

        files = [self._paths_by_rel[m.path] for m in manifests]
        hashes = {
            self._paths_by_rel[m.path]: self._hashes_by_rel[m.path]
            for m in manifests
        }

        try:
            return dict_learner.prepare_dictionaries(
                project_root=self.project_root,
                files=files,
                hashes=hashes,
                top_n=self.dict_top,
                dict_size=self.dict_size,
                compress_level=self.compress_level,
                force=self.retrain_dict,
                roi_guard=self.roi_guard,
            )
        except Exception as e:
            echout(
                f"   ⚠️  Falha ao preparar dicionários ({type(e).__name__}: {e}); "
                f"seguindo sem compressão aprendida.",
                level="warn",
            )
            return empty

    def _print_dict_plan(self):
        if not self.prep:
            return

        top = self.prep.get("top", [])
        manifests = self.prep.get("manifests", [])

        if top:
            echout("   📚 Candidatos a dicionário (top extensões):")
            for ext, corpus_bytes, count in top:
                echout(
                    f"      - {ext:<8} | {count:>4} arquivos | "
                    f"{corpus_bytes / 1024 / 1024:.2f} MB"
                )

        if manifests:
            echout("   🧠 ROI dos dicionários:")
            for m in manifests:
                roi = m.get("roi") or {}
                decision = m.get("decision", "pending")
                stored = float(m.get("stored_size", 0) or 0)
                net = float(roi.get("estimated_net_savings_bytes", 0) or 0)
                payback = float(roi.get("payback_ratio", 0) or 0)

                icon = "✅" if decision == "use" else "⏭️"
                echout(
                    f"      {icon} {m.get('ext', '?'):<8} | "
                    f"dict={stored / 1024:.1f} KB | "
                    f"net={net / 1024:.1f} KB | "
                    f"payback={payback:.1f}x | "
                    f"{decision}"
                )
        else:
            echout("   📚 Nenhum dicionário treinado/avaliado.")

        echout("")

    # ------------------------------------------------------------------------
    # Fase 3: compressão de arquivo
    # ------------------------------------------------------------------------

    def _compress_file(self, raw: bytes, ext: str) -> Tuple[bytes, dict]:
        """
        Comprime um arquivo segundo o modo configurado.

        Se dict_learner existir, delega a ele.
        Senão, usa fallback static/plain.
        """
        if dict_learner is not None and self.prep is not None:
            return dict_learner.compress_file_for_backup(
                raw=raw,
                ext=ext,
                compress_mode=self.compress_mode,
                compress_level=self.compress_level,
                dictionaries=self.prep.get("by_ext", {}),
            )

        # Fallback sem dict_learner.
        profile = hybrid_codec.get_profile_for_ext(ext)

        if self.compress_mode in ("auto", "hybrid", "static"):
            try:
                transformed, meta = hybrid_codec.encode(raw, profile)
            except Exception:
                transformed = raw
                meta = {"profile": profile}

            cctx = zstd.ZstdCompressor(level=self.compress_level)
            compressed = cctx.compress(transformed)

            codec_meta = {
                "codec": "hybrid-static",
                "zstd_level": self.compress_level,
                **meta,
            }
            return compressed, codec_meta

        cctx = zstd.ZstdCompressor(level=self.compress_level)
        compressed = cctx.compress(raw)

        codec_meta = {
            "codec": "zstd",
            "profile": profile,
            "zstd_level": self.compress_level,
        }
        return compressed, codec_meta

    def _add_bytes_to_tar(self, name: str, data: bytes, mtime: int):
        """Adiciona um membro binário ao tar atual."""
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        info.mtime = int(mtime)

        # Metadata determinístico e menor.
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""

        self.tar.addfile(info, io.BytesIO(data))

    # ------------------------------------------------------------------------
    # Metadados + relatório
    # ------------------------------------------------------------------------

    def _build_metadata(
        self,
        backup_id: str,
        backup_path: Path,
        delta: bool,
    ) -> BackupMetadata:
        included = self.manifests

        total = (
            len(included)
            + self.stats.get("skipped", 0)
            + self.stats.get("unchanged", 0)
        )

        comp_size = backup_path.stat().st_size
        raw_size = sum(m.size for m in included)

        ext_in = Counter(ext_of(m.path) or "<none>" for m in included)

        # ------------------------------------------------------------------
        # Telemetria agregada por extensão
        # ------------------------------------------------------------------
        telemetry = {
            "by_extension": {},
            "codec_usage": Counter(),
            "total_tar_members": len(included) + self.stats.get("dict_members", 0),
            "estimated_tar_header_overhead_bytes": (
                len(included) + self.stats.get("dict_members", 0) + 1
            ) * 512,
        }

        ext_stats: dict = defaultdict(lambda: {
            "count": 0,
            "original_bytes": 0,
        })

        codec_usage = telemetry["codec_usage"]

        for m in included:
            ext = ext_of(m.path) or "<none>"
            ext_stats[ext]["count"] += 1
            ext_stats[ext]["original_bytes"] += m.size

            codec = (m.codec_meta or {}).get("codec", "unknown")
            codec_usage[codec] += 1

        telemetry["by_extension"] = dict(ext_stats)
        telemetry["codec_usage"] = dict(codec_usage)

        # ------------------------------------------------------------------
        # Montagem do BackupMetadata
        # ------------------------------------------------------------------
        kwargs = {}
        fields = getattr(BackupMetadata, "__dataclass_fields__", {})

        if "compression_mode" in fields:
            kwargs["compression_mode"] = self.compress_mode

        if "dictionaries" in fields:
            kwargs["dictionaries"] = (
                self.prep.get("manifests", []) if self.prep else []
            )

        if "telemetry" in fields:
            kwargs["telemetry"] = telemetry

        return BackupMetadata(
            backup_id=backup_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            backup_type="delta" if delta and self.previous_meta else "full",
            parent_backup_id=(
                self.previous_meta.backup_id if self.previous_meta else None
            ),
            project_root=str(self.project_root),
            total_files=total,
            included_files=len(included),
            total_size_bytes=raw_size,
            compressed_size_bytes=comp_size,
            compression_ratio=(comp_size / raw_size) if raw_size else 0,
            files=included,
            ext_excluded=dict(self._ext_excluded),
            ext_included=dict(ext_in),
            **kwargs,
        )

    def _print_final_report(self, metadata: BackupMetadata, backup_path: Path):
        elapsed = time.perf_counter() - self._t0
        drain()

        echout("")
        echout("=" * 70)
        echout("✅ BACKUP CONCLUÍDO")
        echout("=" * 70)
        echout(f"   📦 ID       : {metadata.backup_id}")
        echout(f"   🔄 Tipo     : {metadata.backup_type.upper()}")
        echout(f"   📊 Incluídos : {metadata.included_files}/{metadata.total_files}")
        echout(
            f"   ⏭️  Pulados  : {self.stats['skipped']} "
            f"(permissão/IO) | "
            f"inalterados: {self.stats.get('unchanged', 0)}"
        )
        echout(f"   💾 Tamanho  : {metadata.compressed_size_bytes / 1024 / 1024:.2f} MB")
        echout(f"   📈 Ratio    : {metadata.compression_ratio:.2%}")
        echout(f"   ⏱️  Tempo    : {elapsed:.2f}s")
        echout(f"   🛑 Pitstops : {self.stats['pitstops']}")
        echout(f"   🧹 Ignore   : {self.stats['ignore_patterns']} padrões ativos")
        echout(f"   🗜️  Modo     : {self.compress_mode} | level={self.compress_level}")

        container = "tar.gz" if str(backup_path).endswith(".tar.gz") else "tar"
        echout(f"   🧰 Container : {container}")

        if self.prep:
            used = [
                m for m in self.prep.get("manifests", [])
                if m.get("decision") == "use"
            ]
            if used:
                echout("   📚 Dicionários usados:")
                for m in used:
                    roi = m.get("roi") or {}
                    net = float(roi.get("estimated_net_savings_bytes", 0) or 0)
                    payback = float(roi.get("payback_ratio", 0) or 0)
                    echout(
                        f"      - {m.get('ext', '?'):<8} | "
                        f"{float(m.get('stored_size', 0)) / 1024:.1f} KB | "
                        f"net={net / 1024:.1f} KB | "
                        f"payback={payback:.1f}x"
                    )
            else:
                echout("   📚 Nenhum dicionário entrou no backup (ROI não pagou).")

        echout(f"   📍 Local    : {backup_path}")
        echout("=" * 70)

        if self.manifests:
            top = sorted(self.manifests, key=lambda m: m.size, reverse=True)[:8]
            echout("   📦 Maiores incluídos:")
            for m in top:
                echout(f"        {m.size / 1024:>8.1f} KB  {m.path}")

            if len(self.manifests) <= 20:
                echout("   📄 Todos os incluídos (≤20):")
                for m in sorted(self.manifests, key=lambda m: m.path):
                    echout(f"        {m.path}")

        if self._ext_excluded:
            ex_top = sorted(self._ext_excluded.items(), key=lambda kv: -kv[1])[:10]
            barr = ", ".join(f"{e}×{n}" for e, n in ex_top)
            echout(f"   🚫 Barrados por extensão (top): {barr}")

    # ------------------------------------------------------------------------
    # Utilitários públicos
    # ------------------------------------------------------------------------

    def list_backups(self) -> List[BackupMetadata]:
        backups: List[BackupMetadata] = []
        for mp in sorted(self.backup_dir.glob("backup_*.meta.json"), reverse=True):
            with open(mp, "r", encoding="utf-8") as f:
                backups.append(BackupMetadata.from_json(f.read()))
        return backups

    def restore_backup(self, backup_id: str, target_dir=None) -> BackupMetadata:
        """
        Restaura backup corretamente, aplicando decode por codec_meta.

        Nunca usa extractall bruto.
        """
        target_dir = Path(target_dir) if target_dir else self.project_root

        meta_path = self.backup_dir / f"{backup_id}.meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Backup {backup_id} não encontrado")

        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = BackupMetadata.from_json(f.read())

        # Prefere o novo container .tar.gz, aceita .tar legado.
        backup_path = self.backup_dir / f"{backup_id}.tar.gz"
        if not backup_path.exists():
            backup_path = self.backup_dir / f"{backup_id}.tar"

        if not backup_path.exists():
            raise FileNotFoundError(f"Arquivo de backup para {backup_id} não encontrado")

        echout(f"🔄 Restaurando backup {backup_id}...")

        mode = "r:gz" if backup_path.name.endswith(".tar.gz") else "r"
        restored = 0

        with tarfile.open(backup_path, mode) as tar:
            for manifest in metadata.files:
                if not manifest.included:
                    continue

                target_path = target_dir / manifest.path

                try:
                    self._restore_member(
                        tar=tar,
                        member_name=manifest.path,
                        target_path=target_path,
                        codec_meta=manifest.codec_meta,
                    )
                    restored += 1
                except KeyError:
                    echout(
                        f"   ⚠️  Membro não encontrado no tar: {manifest.path}",
                        level="warn",
                    )
                except Exception as e:
                    echout(
                        f"   ⚠️  Falha ao restaurar {manifest.path}: {e}",
                        level="warn",
                    )

        echout(f"✅ Backup restaurado: {restored} arquivos")
        return metadata

    def _restore_member(
        self,
        tar: tarfile.TarFile,
        member_name: str,
        target_path: Path,
        codec_meta: Optional[dict],
    ):
        """
        Restaura um membro aplicando o codec correto.

        Suporta:
        - zstd+dict
        - zstd puro
        - hybrid-static legado
        """
        compressed_data = tar.extractfile(member_name).read()
        codec = (codec_meta or {}).get("codec", "hybrid-static")

        if codec == "zstd+dict":
            dict_sha = codec_meta.get("dict_sha256")
            dict_member = codec_meta.get(
                "dict_member",
                f"__doxoade/dicts/{dict_sha}.dict.zst",
            )

            stored_dict_bytes = tar.extractfile(dict_member).read()

            # Dicionário armazenado como .dict.zst.
            raw_dict_bytes = zstd.ZstdDecompressor().decompress(stored_dict_bytes)
            dct = zstd.ZstdCompressionDict(raw_dict_bytes)

            dctx = zstd.ZstdDecompressor(dict_data=dct)
            raw_data = dctx.decompress(compressed_data)

        elif codec == "zstd":
            dctx = zstd.ZstdDecompressor()
            raw_data = dctx.decompress(compressed_data)

        else:
            # Legado: hybrid-static + zstd.
            dctx = zstd.ZstdDecompressor()
            transformed_data = dctx.decompress(compressed_data)
            raw_data = hybrid_codec.decode(
                transformed_data,
                codec_meta or {"profile": "none"},
            )

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(raw_data)