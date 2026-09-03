# doxoade/commands/lan_git/discovery_lan_git/manifest_lan_git.py
import os
import json
import subprocess
import hashlib
import tempfile
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Tuple, List

DOX_MAGIC_HEADER = "DOX_GIT_SYNC_v1"
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
    tree_hash: str          # 🛡️ Árvore Merkle para auditoria de integridade
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
                tree_hash=payload.get("tree_hash", ""),
                is_dirty=bool(payload.get("is_dirty", False)),
                is_live=bool(payload.get("is_live", False)),
                dirty_count=int(payload.get("dirty_count", 0)),
                timestamp=float(payload.get("timestamp", 0.0))
            )
        except Exception:
            return None


class GitManifestExtractor:
    @staticmethod
    def _run_git(repo_dir: str, args: list, env: Optional[dict] = None) -> Tuple[bool, str]:
        try:
            merged_env = os.environ.copy()
            if env:
                merged_env.update(env)
            res = subprocess.run(
                ["git", "-C", repo_dir] + args,
                capture_output=True,
                text=True,
                timeout=10,
                env=merged_env,
                check=False
            )
            return (res.returncode == 0), res.stdout.strip()
        except Exception as e:
            return False, str(e)

    @classmethod
    def _forge_shadow_commit(cls, repo_path: str, head_commit: str) -> Tuple[str, str]:
        """
        Gera um Shadow Commit real contendo 100% dos arquivos novos e modificados,
        utilizando um índice temporário sem alterar o workspace do desenvolvedor.
        """
        temp_index = os.path.join(repo_path, ".git", "dox_shadow_index")
        env = {"GIT_INDEX_FILE": temp_index}

        try:
            # 1. Carrega o estado atual da HEAD no índice temporário
            cls._run_git(repo_path, ["read-tree", head_commit], env=env)
            # 2. Adiciona todas as modificações e pastas novas (respeitando .gitignore)
            cls._run_git(repo_path, ["add", "-A"], env=env)
            # 3. Grava a árvore de objetos completa
            ok, tree_hash = cls._run_git(repo_path, ["write-tree"], env=env)
            if not ok or not tree_hash:
                return head_commit, ""
            
            # 4. Cria um commit apontando para a árvore com todos os arquivos novos
            msg = "[LIVE-MIRROR] Espelhamento de Rascunho com Arquivos Novos"
            parent_arg = ["-p", head_commit] if head_commit and head_commit != ("0"*40) else []
            ok, commit_hash = cls._run_git(repo_path, ["commit-tree", tree_hash] + parent_arg + ["-m", msg], env=env)
            
            if ok and commit_hash:
                cls._run_git(repo_path, ["update-ref", "refs/heads/dox-live", commit_hash.strip()])
                return commit_hash.strip(), tree_hash.strip()
        finally:
            if os.path.exists(temp_index):
                try:
                    os.remove(temp_index)
                except Exception:
                    pass
        return head_commit, ""

    @classmethod
    def extract(cls, repo_path: str, host_ip: str, port: int = 9418, transport: str = "git_daemon", live: bool = False) -> Optional[GitManifest]:
        global _LAST_DIRTY_SIGNATURE, _LAST_SHADOW_HASH
        repo_path = os.path.abspath(repo_path)
        if not os.path.exists(os.path.join(repo_path, ".git")) and not repo_path.endswith(".git"):
            return None

        ok, status = cls._run_git(repo_path, ["status", "--porcelain"])
        raw_status = status.strip() if ok else ""
        dirty_lines = raw_status.splitlines() if raw_status else []
        is_dirty = len(dirty_lines) > 0

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

        tree_hash = ""
        if live:
            current_sig = hashlib.sha256(f"{head_commit}_{raw_status}".encode("utf-8")).hexdigest()
            if current_sig != _LAST_DIRTY_SIGNATURE or not _LAST_SHADOW_HASH:
                shadow_hash, tree_hash = cls._forge_shadow_commit(repo_path, head_commit)
                _LAST_DIRTY_SIGNATURE = current_sig
                _LAST_SHADOW_HASH = shadow_hash
            else:
                shadow_hash = _LAST_SHADOW_HASH
            
            target_commit = shadow_hash
            target_branch = "dox-live"
            commit_msg = f"[LIVE-MIRROR] Rascunho com {len(dirty_lines)} arquivo(s) modificado(s)"
        else:
            target_commit = head_commit
            target_branch = branch
            ok, th = cls._run_git(repo_path, ["rev-parse", "HEAD^{tree}"])
            tree_hash = th if ok else ""

        try:
            import socket
            hostname = socket.gethostname()
        except Exception:
            hostname = "DoxoadeHost"

        return GitManifest(
            magic=DOX_MAGIC_HEADER,
            protocol_version="1.0",
            hostname=hostname,
            ip=host_ip,
            port=port,
            transport=transport,
            repo_name=os.path.basename(repo_path),
            branch=target_branch,
            head_commit=target_commit,
            short_commit=target_commit[:7],
            commit_message=commit_msg,
            tree_hash=tree_hash,
            is_dirty=is_dirty,
            is_live=live,
            dirty_count=len(dirty_lines),
            timestamp=os.path.getmtime(repo_path)
        )
