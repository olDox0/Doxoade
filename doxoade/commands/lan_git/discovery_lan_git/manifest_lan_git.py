""" Módulo de Manifesto do Repositório Git Local com Detecção de Mudanças Reais.
Só forja Shadow Commits quando arquivos forem de fato salvos/alterados. """

import os
import json
import subprocess
import time
import hashlib
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Tuple, List


DOX_MAGIC_HEADER = "DOX_GIT_SYNC_v1"

# Cache em memória para evitar criar commits desnecessários se nada mudou
_LAST_DIRTY_SIGNATURE: str = ""
_LAST_SHADOW_HASH: str = ""


@dataclass
class GitManifest:
    magic: str
    protocol_version: str
    hostname: str
    ip: str
    port: int
    transport: str
    repo_name: str
    branch: str
    head_commit: str
    short_commit: str
    commit_message: str
    is_dirty: bool
    is_live: bool
    dirty_count: int
    timestamp: float

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    def to_bytes(self) -> bytes:
        return self.to_json().encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> Optional["GitManifest"]:
        try:
            payload = json.loads(data.decode("utf-8"))
            if payload.get("magic") != DOX_MAGIC_HEADER:
                return None
            return cls(
                magic=payload["magic"],
                protocol_version=payload.get("protocol_version", "1.0"),
                hostname=payload.get("hostname", "Unknown"),
                ip=payload["ip"],
                port=int(payload["port"]),
                transport=payload.get("transport", "git_daemon"),
                repo_name=payload["repo_name"],
                branch=payload["branch"],
                head_commit=payload["head_commit"],
                short_commit=payload["short_commit"],
                commit_message=payload.get("commit_message", ""),
                is_dirty=bool(payload.get("is_dirty", False)),
                is_live=bool(payload.get("is_live", False)),
                dirty_count=int(payload.get("dirty_count", 0)),
                timestamp=float(payload.get("timestamp", 0.0))
            )
        except Exception:
            return None


class GitManifestExtractor:
    """Extrai metadados com debouncing de Shadow Commits."""

    @staticmethod
    def _run_git(repo_dir: str, args: list) -> Tuple[bool, str]:
        try:
            res = subprocess.run(
                ["git", "-C", repo_dir] + args,
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            return (res.returncode == 0), res.stdout.strip()
        except Exception as e:
            return False, str(e)

    @classmethod
    def extract(cls, repo_path: str, host_ip: str, port: int = 9418, transport: str = "git_daemon", live: bool = False) -> Optional[GitManifest]:
        global _LAST_DIRTY_SIGNATURE, _LAST_SHADOW_HASH

        repo_path = os.path.abspath(repo_path)
        if not os.path.exists(os.path.join(repo_path, ".git")) and not repo_path.endswith(".git"):
            return None

        # 1. Checa status das modificações
        ok, status = cls._run_git(repo_path, ["status", "--porcelain"])
        raw_status = status.strip() if ok else ""
        dirty_lines = raw_status.splitlines() if raw_status else []
        is_dirty = len(dirty_lines) > 0

        # 2. Hash base do HEAD
        ok, head_commit = cls._run_git(repo_path, ["rev-parse", "HEAD"])
        if not ok:
            head_commit = "0" * 40

        ok, branch = cls._run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
        if not ok:
            branch = "main"

        commit_msg = ""
        ok, msg = cls._run_git(repo_path, ["log", "-1", "--pretty=%s"])
        if ok:
            commit_msg = msg

        # 3. Modo Live Mirror Inteligente (Só cria novo commit se houver alteração real)
        if live:
            # Assinatura de integridade: status dos arquivos + HEAD atual
            current_sig = hashlib.sha256(f"{head_commit}_{raw_status}".encode("utf-8")).hexdigest()

            if current_sig != _LAST_DIRTY_SIGNATURE or not _LAST_SHADOW_HASH:
                # Mudança real detectada no editor: forja novo Shadow Commit
                if is_dirty:
                    ok_stash, stash_hash = cls._run_git(repo_path, ["stash", "create", "--include-untracked"])
                    if not ok_stash or not stash_hash.strip():
                        ok_stash, stash_hash = cls._run_git(repo_path, ["stash", "create"])
                    shadow_hash = stash_hash.strip() if (ok_stash and stash_hash.strip()) else head_commit
                else:
                    shadow_hash = head_commit

                _LAST_DIRTY_SIGNATURE = current_sig
                _LAST_SHADOW_HASH = shadow_hash
                cls._run_git(repo_path, ["update-ref", "refs/heads/dox-live", shadow_hash])
            else:
                # Reaproveita o shadow commit anterior (sem spam no loop)
                shadow_hash = _LAST_SHADOW_HASH

            branch = "dox-live"
            head_commit = shadow_hash
            commit_msg = f"[LIVE-MIRROR] Rascunho em memória ({len(dirty_lines)} arquivo(s) modificado(s))"

        short_commit = head_commit[:7]
        repo_name = os.path.basename(repo_path)
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]

        import socket
        hostname = socket.gethostname()

        return GitManifest(
            magic=DOX_MAGIC_HEADER,
            protocol_version="1.0",
            hostname=hostname,
            ip=host_ip,
            port=port,
            transport=transport,
            repo_name=repo_name,
            branch=branch,
            head_commit=head_commit,
            short_commit=short_commit,
            commit_message=commit_msg,
            is_dirty=is_dirty,
            is_live=live,
            dirty_count=len(dirty_lines),
            timestamp=time.time()
        )