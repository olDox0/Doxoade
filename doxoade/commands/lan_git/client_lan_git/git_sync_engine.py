# doxoade/commands/lan_git/client_lan_git/git_sync_engine.py
# Orquestrador do Fetch/Pull e controle do git remote
""" Módulo Motor de Sincronização LAN Git com Telemetria e Fallback Automático.
Suporta protocolo nativo git:// com contingência transparente para Smart HTTP. """

import os
import sys
import shutil
import subprocess
import traceback
import tempfile
from typing import Tuple, Optional
import click

from doxoade.commands.lan_git.discovery_lan_git.manifest_lan_git import GitManifest
from doxoade.commands.lan_git.client_lan_git.lan_git_comparator import LANComparator, SyncStatus
from doxoade.commands.lan_git.transport_lan_git.git_bundle_stream import GitBundleClient


class GitSyncEngine:
    """Executa as operações de Git Fetch/Pull com resiliência multicamadas."""

    REMOTE_NAME = "lan-peer"

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
    def pull_from_peer(cls, repo_path: str, manifest: GitManifest) -> Tuple[bool, str]:
        repo_path = os.path.abspath(repo_path)

        click.secho("\n--- [DIAGNÓSTICO FORENSE DE SINCRONIZAÇÃO] ---", fg="cyan", bold=True)
        click.echo(f"  Diretório Alvo : {repo_path}")
        click.echo(f"  Host Remoto    : {manifest.hostname} ({manifest.ip}:{manifest.port})")
        click.echo(f"  Transporte     : {manifest.transport.upper()}")
        click.echo(f"  Commit Remoto  : {manifest.short_commit} ({manifest.commit_message})")
        click.secho("----------------------------------------------\n", fg="cyan")

        status, msg = LANComparator.evaluate_sync(repo_path, manifest)
        click.echo(f"[STATUS AVALIADO] {status.value.upper()}: {msg}")

        if status == SyncStatus.DIRTY_LOCAL:
            return False, f"[SEGURANÇA] {msg} Faça commit ou stash antes de atualizar."
        if status == SyncStatus.UP_TO_DATE:
            return True, f"[SINCRONIZADO] {msg}"

        is_uninit = (status == SyncStatus.UNINITIALIZED)

        # Tentativa 1: Transporte Primário Anunciado (Plano A: git://)
        if manifest.transport == "git_daemon":
            remote_url = f"git://{manifest.ip}:{manifest.port}/{manifest.repo_name}"
            ok, result_msg = cls._pull_via_standard_remote(repo_path, remote_url, manifest.branch, is_uninitialized=is_uninit)
            if ok:
                return True, result_msg

            # Fallback Automático: Se o git:// der erro no Windows, tenta Smart HTTP (Plano B)
            click.secho("\n[CONTINGÊNCIA] Falha no protocolo git://. Tentando Plano B via Smart HTTP...", fg="yellow", bold=True)
            fallback_http_url = f"http://{manifest.ip}:8080/{manifest.repo_name}"
            return cls._pull_via_standard_remote(repo_path, fallback_http_url, manifest.branch, is_uninitialized=is_uninit)

        elif manifest.transport == "http":
            remote_url = f"http://{manifest.ip}:{manifest.port}/{manifest.repo_name}"
            return cls._pull_via_standard_remote(repo_path, remote_url, manifest.branch, is_uninitialized=is_uninit)

        elif manifest.transport == "bundle":
            return cls._pull_via_bundle(repo_path, manifest.ip, manifest.port, manifest.branch)

        return False, f"Transporte desconhecido: {manifest.transport}"

    @classmethod
    def _pull_via_standard_remote(cls, repo_path: str, remote_url: str, branch: str, is_uninitialized: bool = False) -> Tuple[bool, str]:
        ok, err = cls._configure_remote(repo_path, remote_url)
        if not ok:
            return False, err

        click.secho(f"\n[FETCH] Puxando objetos do branch '{branch}' via LAN ({remote_url})...", fg="cyan")
        ok, fetch_out, code, fetch_err = cls._run_git_forensic(repo_path, ["fetch", cls.REMOTE_NAME, branch])
        if not ok:
            return False, f"Falha no 'git fetch' (Exit {code}): {fetch_err or fetch_out}"

        if is_uninitialized:
            click.secho(f"\n[CHECKOUT] Configurando branch local '{branch}'...", fg="cyan")
            ok, out, code, err = cls._run_git_forensic(repo_path, ["checkout", "-B", branch, f"{cls.REMOTE_NAME}/{branch}"])
            if not ok:
                return False, f"Falha no 'git checkout' inicial (Exit {code}): {err or out}"
            return True, f"Repositório inicializado e sincronizado com sucesso (Branch: {branch})."

        click.secho(f"\n[MERGE] Aplicando Fast-Forward para '{cls.REMOTE_NAME}/{branch}'...", fg="cyan")
        ok, merge_out, code, merge_err = cls._run_git_forensic(repo_path, ["merge", "--ff-only", f"{cls.REMOTE_NAME}/{branch}"])
        if not ok:
            return False, f"Falha no Fast-Forward (Exit {code}): {merge_err or merge_out}"

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