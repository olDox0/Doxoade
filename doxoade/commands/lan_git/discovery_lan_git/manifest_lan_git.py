# doxoade/commands/lan_git/discovery_lan_git/manifest_lan_git.py
# Serializador e Validador do Payload de Anúncio
""" Módulo de Manifesto do Repositório Git Local.
Coleta metadados do Git e empacota no formato padrão do Doxoade LAN Git. """

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
    timestamp: float

    def to_json(self) -> str:
        """Serializa o manifesto em JSON minificado para tráfego UDP."""
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
                timestamp=float(payload.get("timestamp", 0.0))
            )
        except Exception:
            return None


class GitManifestExtractor:
    """Extrai informações seguras do repositório Git local via CLI."""

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
            if res.returncode == 0:
                return True, res.stdout.strip()
            return False, res.stderr.strip()
        except Exception as e:
            return False, str(e)

    @classmethod
    def extract(cls, repo_path: str, host_ip: str, port: int = 9418, transport: str = "git_daemon") -> Optional[GitManifest]:
        repo_path = os.path.abspath(repo_path)
        if not os.path.exists(os.path.join(repo_path, ".git")) and not repo_path.endswith(".git"):
            return None

        # 1. Branch atual
        ok, branch = cls._run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
        if not ok:
            branch = "main"

        # 2. Hash do Commit HEAD
        ok, head_commit = cls._run_git(repo_path, ["rev-parse", "HEAD"])
        if not ok:
            head_commit = "0" * 40

        # 3. Hash curto
        short_commit = head_commit[:7]

        # 4. Mensagem do último commit
        ok, msg = cls._run_git(repo_path, ["log", "-1", "--pretty=%s"])
        commit_msg = msg if ok else ""

        # 5. Status dirty (alterações não commitadas)
        ok, status = cls._run_git(repo_path, ["status", "--porcelain"])
        is_dirty = bool(status.strip()) if ok else False

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
            timestamp=time.time()
        )