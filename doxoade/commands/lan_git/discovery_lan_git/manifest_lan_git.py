""" Módulo de Manifesto do Repositório Git Local com Suporte a Live Mirror.
Extrai metadados do Git e gera Shadow Commits em memória (refs/heads/dox-live) para espelhamento sem commit. """

import os
import json
import subprocess
import time
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Tuple, List


DOX_MAGIC_HEADER = "DOX_GIT_SYNC_v1"


@dataclass
class GitManifest:
    magic: str
    protocol_version: str
    hostname: str
    ip: str
    port: int
    transport: str            # "git_daemon" | "http" | "bundle"
    repo_name: str
    branch: str
    head_commit: str
    short_commit: str
    commit_message: str
    is_dirty: bool
    is_live: bool             # Indica se é um espelho ao vivo em memória
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
                timestamp=float(payload.get("timestamp", 0.0))
            )
        except Exception:
            return None


class GitManifestExtractor:
    """Extrai informações e forja Shadow Commits para o modo Live Mirror."""

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
        repo_path = os.path.abspath(repo_path)
        if not os.path.exists(os.path.join(repo_path, ".git")) and not repo_path.endswith(".git"):
            return None

        # 1. Checa status de modificações (dirty)
        ok, status = cls._run_git(repo_path, ["status", "--porcelain"])
        is_dirty = bool(status.strip()) if ok else False

        # 2. Branch e Commit Base
        ok, branch = cls._run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
        if not ok:
            branch = "main"

        ok, head_commit = cls._run_git(repo_path, ["rev-parse", "HEAD"])
        if not ok:
            head_commit = "0" * 40

        commit_msg = ""
        ok, msg = cls._run_git(repo_path, ["log", "-1", "--pretty=%s"])
        if ok:
            commit_msg = msg

        # 3. Se o Modo LIVE estiver ativo, forja um Shadow Commit em memória
        if live:
            # Tenta capturar rascunhos + arquivos novos untracked com 'git stash create -u'
            ok_stash, stash_hash = cls._run_git(repo_path, ["stash", "create", "--include-untracked"])
            if not ok_stash or not stash_hash.strip():
                ok_stash, stash_hash = cls._run_git(repo_path, ["stash", "create"])

            # Se houver alterações em memória, usa o hash do stash; caso contrário, usa o HEAD
            shadow_hash = stash_hash.strip() if (ok_stash and stash_hash.strip()) else head_commit

            # Atualiza a referência efêmera 'refs/heads/dox-live'
            cls._run_git(repo_path, ["update-ref", "refs/heads/dox-live", shadow_hash])

            branch = "dox-live"
            head_commit = shadow_hash
            commit_msg = f"[LIVE-MIRROR] Espelho de rascunho em memória ({len(status.splitlines()) if is_dirty else 0} alterações)"

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
            timestamp=time.time()
        )