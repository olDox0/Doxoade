# -*- coding: utf-8 -*-
# doxoade/commands/check_systems/checkshot.py
"""
CheckShot — Snapshot isolado para validar conteúdo em memória via `doxoade check`.

Usado pelo mody_patch para análise de dry-run: cria um mini-projeto em
.doxoade/checkshot/<sid>/, escreve o conteúdo modificado, roda o check
em modo JSON, retorna os findings estruturados e limpa o snapshot.

Princípios:
  - Zero efeito colateral no projeto real (sandbox isolado).
  - Reutiliza o motor `doxoade check` (single source of truth).
  - JSON estruturado → fácil de renderizar, testar e integrar com IA.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CheckShotResult:
    """Resultado estruturado de uma execução do CheckShot."""
    success: bool
    exit_code: int
    summary: Dict[str, int] = field(default_factory=dict)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    raw_stdout: str = ""
    raw_stderr: str = ""
    snapshot_dir: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def total_findings(self) -> int:
        return len(self.findings)

    @property
    def critical_count(self) -> int:
        return sum(
            1 for f in self.findings
            if str(f.get("severity", "")).upper() in ("CRITICAL", "ERROR")
        )


class CheckShot:
    """
    Executa `doxoade check` em conteúdo isolado, sem tocar no projeto real.

    Fluxo:
      1. Cria .doxoade/checkshot/<sid>/ com pyproject.toml mínimo.
      2. Escreve o arquivo-alvo com o conteúdo modificado.
      3. Invoca `python -m doxoade check <file> --format json --no-cache -t`.
      4. Faz parse do JSON e retorna CheckShotResult.
      5. Remove o snapshot (a menos que keep=True).
    """

    DEFAULT_TIMEOUT = 60

    def __init__(self, project_root: Path, keep: bool = False):
        self.project_root = Path(project_root).resolve()
        self.keep = keep
        self._snapshot_dir: Optional[Path] = None
        self._session_id: Optional[str] = None

    # ------------------------------------------------------------------ #
    #  Ciclo de vida
    # ------------------------------------------------------------------ #
    def _create_snapshot(self, rel_path: str) -> Path:
        self._session_id = uuid.uuid4().hex[:12]
        base = self.project_root / ".doxoade" / "checkshot" / self._session_id
        base.mkdir(parents=True, exist_ok=True)

        # pyproject mínimo para o check encontrar um project_root válido.
        (base / "pyproject.toml").write_text(
            '[project]\nname = "checkshot"\nversion = "0.0.0"\n'
            '[tool.doxoade]\nsource_dir = "."\nignore = []\n',
            encoding="utf-8",
        )

        target = base / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        self._snapshot_dir = base
        return target

    def _cleanup(self) -> None:
        if self.keep or not self._snapshot_dir:
            return
        try:
            shutil.rmtree(self._snapshot_dir, ignore_errors=True)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  Execução
    # ------------------------------------------------------------------ #
    def analyze(
        self,
        modified_content: str,
        rel_path: str,
        extra_args: Optional[List[str]] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> CheckShotResult:
        """
        Valida `modified_content` como se fosse `rel_path` do projeto.

        :param modified_content: Conteúdo (já patcheado) a ser verificado.
        :param rel_path: Caminho relativo do arquivo (ex: 'src/foo.py').
        :param extra_args: Args extras para o check (ex: ['-s'] para security).
        :param timeout: Timeout em segundos.
        """
        rel_path = rel_path.replace("\\", "/").lstrip("/")
        if not rel_path:
            return CheckShotResult(
                success=False, exit_code=-1,
                error="rel_path vazio",
            )

        try:
            target = self._create_snapshot(rel_path)
            target.write_text(modified_content, encoding="utf-8")
        except Exception as e:
            self._cleanup()
            return CheckShotResult(
                success=False, exit_code=-1,
                error=f"Falha ao criar snapshot: {e}",
            )

        cmd = [
            sys.executable, "-m", "doxoade", "check",
            str(target),
            "--format", "json",
            "--no-cache",
            "--fast",
        ]
        if extra_args:
            cmd.extend(extra_args)

        env = os.environ.copy()
        # Evita que o rescue interativo atrapalhe em CI/dry-run.
        env["DOXOADE_MODE"] = "direct"
        env["DOXOADE_RESCUE"] = "0"

        result = CheckShotResult(success=False, exit_code=-1,
                                 snapshot_dir=str(self._snapshot_dir))
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self._snapshot_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env,
            )
            result.exit_code = proc.returncode
            result.raw_stdout = proc.stdout or ""
            result.raw_stderr = proc.stderr or ""

            payload = self._extract_json(result.raw_stdout)
            if payload is None:
                # check não produziu JSON (ex: crash antes do output).
                if proc.returncode == 0:
                    result.success = True
                else:
                    result.error = (
                        result.raw_stderr.strip().splitlines()[-1]
                        if result.raw_stderr.strip() else
                        f"check saiu com código {proc.returncode} sem JSON"
                    )
            else:
                result.success = True
                result.summary = payload.get("summary", {}) or {}
                result.findings = payload.get("findings", []) or []

        except subprocess.TimeoutExpired:
            result.error = f"check excedeu {timeout}s"
        except FileNotFoundError:
            result.error = "Python/doxoade não encontrado no PATH"
        except Exception as e:
            result.error = f"Erro ao invocar check: {e}"
        finally:
            self._cleanup()

        return result

    @staticmethod
    def _extract_json(stdout: str) -> Optional[Dict[str, Any]]:
        """
        Extrai o JSON do check mesmo que haja linhas de log antes.
        Estratégia: encontra o primeiro '{' e tenta decodificar dali em diante.
        """
        if not stdout:
            return None
        idx = stdout.find("{")
        if idx < 0:
            return None
        try:
            decoder = json.JSONDecoder()
            data, _ = decoder.raw_decode(stdout[idx:])
            if isinstance(data, dict):
                return data
        except Exception:
            return None
        return None
