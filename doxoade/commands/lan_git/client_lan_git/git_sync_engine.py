# doxoade\commands\lan_git\client_lan_git\git_sync_engine.py
""" Módulo Motor de Sincronização LAN Git com Suporte a Nomes de Repositórios com Espaços.
Codifica URLs em conformidade com RFC-3986 (quote/unquote). """

import os
import sys
import shutil
import subprocess
import traceback
import tempfile
from urllib.parse import quote
from typing import Tuple, Optional
import click

from doxoade.commands.lan_git.discovery_lan_git.manifest_lan_git import GitManifest
from doxoade.commands.lan_git.client_lan_git.lan_git_comparator import LANComparator, SyncStatus
from doxoade.commands.lan_git.transport_lan_git.git_bundle_stream import GitBundleClient


class GitSyncEngine:
    """Executa as operações de Git Fetch/Pull com sanitização estrita de URLs."""

    REMOTE_NAME = "lan-peer"

    @classmethod
    def verify_sync_integrity(cls, repo_path: str, remote_manifest: GitManifest) -> bool:
        """Audita se a árvore do repositório local é 100% idêntica à do Host remoto."""
        ok, local_tree = cls._run_git_forensic(repo_path, ["rev-parse", "HEAD^{tree}"])
        if not ok or not local_tree:
            click.secho("  ⚠ [AUDIT] Não foi possível obter o Tree Hash local.", fg="yellow")
            return False

        local_tree_hash = local_tree.strip()
        remote_tree_hash = remote_manifest.tree_hash.strip()

        click.secho("\n--- [AUDITORIA CRIPTOGRÁFICA DE SINCRONIZAÇÃO] ---", fg="cyan", bold=True)
        click.echo(f"  Host Tree Hash   : {remote_tree_hash or 'N/A'}")
        click.echo(f"  Local Tree Hash  : {local_tree_hash}")

        if remote_tree_hash and local_tree_hash == remote_tree_hash:
            click.secho("  ✔ [INTEGRIDADE CONFIRMADA] O cliente está 100% espelhado com o Host.", fg="green", bold=True)
            click.secho("--------------------------------------------------\n", fg="cyan")
            return True
        elif not remote_tree_hash:
            click.secho("  ✔ [PULL OK] Sincronização concluída (Host sem hash de auditoria).", fg="green")
            click.secho("--------------------------------------------------\n", fg="cyan")
            return True
        else:
            click.secho("  ✖ [DIVERGÊNCIA DETECTADA] Os arquivos entre Host e Cliente não coincidem.", fg="red", bold=True)
            click.secho("--------------------------------------------------\n", fg="cyan")
            return False

    @classmethod
    def _run_git_forensic(cls, repo_path: str, args: list) -> Tuple[bool, str, int, str]:
        git_bin = shutil.which("git")
        if not git_bin:
            err_msg = "[CRÍTICO] Executável 'git.exe' não encontrado no PATH do Windows."
            click.secho(f"\n{err_msg}\n", fg="red", bold=True)
            return False, "", -1, err_msg

        full_cmd = ["git", "-C", repo_path] + args
        cmd_str = f"git -C \"{repo_path}\" " + " ".join(args)
        click.secho(f"  [GIT-EXEC] {cmd_str}", fg="cyan")
        sys.stdout.flush()

        try:
            res = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()

            if res.returncode == 0:
                click.secho(f"  ✔ [GIT-OK] (Exit {res.returncode})", fg="green")
                return True, stdout, res.returncode, stderr
            else:
                click.secho(f"  ✖ [GIT-FAIL] Exit Code: {res.returncode}", fg="yellow")
                if stderr:
                    click.secho(f"    [STDERR] {stderr}", fg="red")
                if stdout:
                    click.secho(f"    [STDOUT] {stdout}", fg="white")
                return False, stdout, res.returncode, stderr

        except Exception as e:
            tb = traceback.format_exc()
            click.secho(f"\n  ✖ [EXCEÇÃO NO SUBPROCESS]\n{tb}", fg="red", bold=True)
            return False, "", -1, str(e)

    @classmethod
    def _configure_remote(cls, repo_path: str, remote_url: str) -> Tuple[bool, str]:
        git_dir = os.path.join(repo_path, ".git")

        if not os.path.exists(git_dir):
            click.secho(f"  [INIT] Repositório .git ausente em '{repo_path}'. Inicializando...", fg="yellow")
            ok, out, code, err = cls._run_git_forensic(repo_path, ["init"])
            if not ok:
                return False, f"Falha no 'git init' (Exit {code}): {err or out}"

        ok, remotes, code, err = cls._run_git_forensic(repo_path, ["remote"])
        if not ok:
            return False, f"Falha ao consultar 'git remote' (Exit {code}): {err or remotes}"

        remote_list = remotes.splitlines() if remotes else []

        if cls.REMOTE_NAME in remote_list:
            click.secho(f"  [REMOTE] Atualizando URL do remote '{cls.REMOTE_NAME}' -> {remote_url}", fg="cyan")
            ok, out, code, err = cls._run_git_forensic(repo_path, ["remote", "set-url", cls.REMOTE_NAME, remote_url])
        else:
            click.secho(f"  [REMOTE] Adicionando novo remote '{cls.REMOTE_NAME}' -> {remote_url}", fg="cyan")
            ok, out, code, err = cls._run_git_forensic(repo_path, ["remote", "add", cls.REMOTE_NAME, remote_url])

        if not ok:
            return False, f"Falha ao vincular remote '{cls.REMOTE_NAME}' (Exit {code}): {err or out}"

        return True, "Remote configurado com sucesso."

    @classmethod
    def pull_from_peer(cls, repo_path: str, manifest: GitManifest, force: bool = False, autostash: bool = False, live: bool = False) -> Tuple[bool, str]:
        repo_path = os.path.abspath(repo_path)

        target_branch = "dox-live" if (live or manifest.is_live or manifest.branch == "dox-live") else manifest.branch

        click.secho("\n--- [DIAGNÓSTICO FORENSE DE SINCRONIZAÇÃO] ---", fg="cyan", bold=True)
        click.echo(f"  Diretório Alvo : {repo_path}")
        click.echo(f"  Host Remoto    : {manifest.hostname} ({manifest.ip}:{manifest.port})")
        click.echo(f"  Transporte     : {manifest.transport.upper()}")
        click.echo(f"  Alvo de Sinc   : {target_branch} @ {manifest.short_commit}")
        click.echo(f"  Mensagem       : {manifest.commit_message}")
        if live or manifest.is_live:
            click.secho("  Modo Live      : ATIVO (Espelhamento Direto de Rascunho)", fg="magenta", bold=True)
        click.secho("----------------------------------------------\n", fg="cyan")

        bypass_safety = force or live or manifest.is_live

        status, msg = LANComparator.evaluate_sync(repo_path, manifest, force=bypass_safety)
        click.echo(f"[STATUS AVALIADO] {status.value.upper()}: {msg}")

        if status == SyncStatus.DIRTY_LOCAL and not bypass_safety and not autostash:
            return False, f"[SEGURANÇA] {msg} Use '--force' ou '--live' para espelhar."

        if status == SyncStatus.UP_TO_DATE and not bypass_safety:
            return True, f"[SINCRONIZADO] {msg}"

        ok_head, _, _, _ = cls._run_git_forensic(repo_path, ["rev-parse", "HEAD"])
        has_no_head = not ok_head

        # ⚡ Codificação de URL para suportar pastas com espaços (ex: "Projeto%20SysUtils")
        encoded_repo_name = quote(manifest.repo_name)

        # 1. Tentativa Primária: Smart HTTP (Porta 8080)
        http_url = f"http://{manifest.ip}:8080/{encoded_repo_name}"
        ok, result_msg = cls._pull_via_standard_remote(repo_path, http_url, target_branch, has_no_head=has_no_head, force=bypass_safety, autostash=autostash)
        if ok:
            return True, result_msg

        # 2. Fallback para Git Daemon (Porta 9418)
        click.secho("\n[CONTINGÊNCIA] Tentando porta do Git Daemon (9418)...", fg="yellow", bold=True)
        daemon_url = f"git://{manifest.ip}:{manifest.port}/{manifest.repo_name}"
        return cls._pull_via_standard_remote(repo_path, daemon_url, target_branch, has_no_head=has_no_head, force=bypass_safety, autostash=autostash)

    @classmethod
    def _pull_via_standard_remote(cls, repo_path: str, remote_url: str, branch: str, has_no_head: bool = False, force: bool = False, autostash: bool = False) -> Tuple[bool, str]:
        ok, err = cls._configure_remote(repo_path, remote_url)
        if not ok:
            return False, err

        stashed = False
        if autostash and not has_no_head:
            click.secho("\n[STASH] Guardando alterações de pesquisa locais...", fg="yellow")
            ok_stash, out_stash, _, _ = cls._run_git_forensic(repo_path, ["stash", "push", "-m", "lan_git_autostash"])
            stashed = ("No local changes to save" not in out_stash)

        click.secho(f"\n[FETCH] Puxando objetos do branch '{branch}' via LAN ({remote_url})...", fg="cyan")
        ok, fetch_out, code, fetch_err = cls._run_git_forensic(repo_path, ["fetch", cls.REMOTE_NAME, branch])
        if not ok:
            return False, f"Falha no 'git fetch' (Exit {code}): {fetch_err or fetch_out}"

        # Aplica Reset Hard em caso de novo repositório, force ou live mirror
        if has_no_head or force or branch == "dox-live":
            click.secho(f"\n[APLICAÇÃO] Espelhando estado exato do Host ({cls.REMOTE_NAME}/{branch})...", fg="green", bold=True)
            ok, reset_out, code, reset_err = cls._run_git_forensic(repo_path, ["reset", "--hard", f"{cls.REMOTE_NAME}/{branch}"])
            if not ok:
                return False, f"Falha no Reset Hard (Exit {code}): {reset_err or reset_out}"
            return True, f"Repositório espelhado com sucesso com o Host ({branch} @ {cls.REMOTE_NAME}/{branch})."

        click.secho(f"\n[MERGE] Aplicando Fast-Forward para '{cls.REMOTE_NAME}/{branch}'...", fg="cyan")
        ok, merge_out, code, merge_err = cls._run_git_forensic(repo_path, ["merge", "--ff-only", f"{cls.REMOTE_NAME}/{branch}"])
        if not ok:
            return False, f"Falha no Fast-Forward (Exit {code}): {merge_err or merge_out}"

        if stashed:
            click.secho("\n[STASH-POP] Restaurando alterações de pesquisa locais...", fg="yellow")
            cls._run_git_forensic(repo_path, ["stash", "pop"])

        return True, f"Repositório atualizado com sucesso via LAN: {merge_out}"

    @classmethod
    def _pull_via_bundle(cls, repo_path: str, host_ip: str, port: int, branch: str) -> Tuple[bool, str]:
        with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as tmp:
            tmp_bundle_file = tmp.name

        try:
            ok, err = GitBundleClient.receive_bundle(host_ip, port, tmp_bundle_file)
            if not ok:
                return False, f"Falha no download do bundle: {err}"

            ok, out, code, fetch_err = cls._run_git_forensic(repo_path, ["fetch", tmp_bundle_file, f"{branch}:{branch}"])
            if not ok:
                ok, out, code, merge_err = cls._run_git_forensic(repo_path, ["pull", "--ff-only", tmp_bundle_file, branch])
                if not ok:
                    return False, f"Falha ao aplicar commits do bundle (Exit {code}): {fetch_err or merge_err}"

            return True, "Repositório atualizado com sucesso a partir de Git Bundle validado por SHA-256."
        finally:
            if os.path.exists(tmp_bundle_file):
                try:
                    os.remove(tmp_bundle_file)
                except Exception:
                    pass
