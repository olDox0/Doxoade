# -*- coding: utf-8 -*-
# doxoade/tools/emulator_systems/qemu_runner.py
"""
[HÓRUS] QEMU Execution & Telemetry Supervisor v1.0.
Gerencia ciclo de vida, captura serial, traço de CPU e servidor GDB sob diretrizes ProDeNov.
"""

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .qemu_detector import QemuDetector, QemuInfo


@dataclass
class QemuRunConfig:
    """Configuração declarativa para lançamento do emulador."""
    image_path: str
    arch: str = "i386"
    memory_mb: int = 128
    media_type: str = "drive"       # 'drive' (raw HDD), 'fda' (floppy), 'cdrom', 'kernel'
    serial_mode: str = "stdio"      # 'stdio' (Plano A), 'file' (Plano B), 'none'
    serial_log_file: str = "serial.log"
    trace_cpu: bool = False         # Registra int, cpu_reset e guest_errors
    trace_log_file: str = "qemu_trace.log"
    debug_gdb: bool = False         # Ativa servidor GDB em localhost:1234 e congela CPU
    gdb_port: int = 1234
    uefi_rom: Optional[Path] = None
    force_tcg: bool = True          # TCG é obrigatório para trace de CPU determinístico
    dry_run: bool = False           # Salvaguarda: exibe comando sem disparar
    extra_args: List[str] = field(default_factory=list)


@dataclass
class RunResult:
    """Relatório estruturado pós-execução (Auditoria Ma'at)."""
    success: bool
    return_code: int
    command: List[str]
    trace_file: Optional[Path] = None
    serial_file: Optional[Path] = None
    message: str = ""


class QemuRunner:
    """
    Supervisor soberano de execução QEMU.
    Garante integridade de processos, isolamento de pipes e telemetria de falhas.
    """

    def __init__(self, project_root: str = "."):
        self.root = Path(project_root).resolve()

    def build_command(self, cfg: QemuRunConfig) -> List[str]:
        """
        [HEFESTO] Forja o vetor de comando validando integridade de caminhos e flags.
        Garante que argumentos sejam mutuamente compatíveis.
        """
        emu_info: Optional[QemuInfo] = QemuDetector.detect(cfg.arch)
        if not emu_info:
            raise FileNotFoundError(
                f"Emulador para arquitetura '{cfg.arch}' não encontrado. "
                "Execute QemuDetector.detect() para diagnosticar."
            )

        cmd: List[str] = [emu_info.path]

        # 1. Configuração de Memória
        cmd.extend(["-m", f"{cfg.memory_mb}M"])

        # 2. Motor de Execução (Acelerador vs TCG)
        # NOTA: Quando trace_cpu está ativo, TCG é obrigatório para dissecar interrupções
        if cfg.trace_cpu or cfg.force_tcg:
            cmd.extend(["-accel", "tcg"])
        elif emu_info.accel in ["whpx", "kvm"]:
            cmd.extend(["-accel", emu_info.accel])

        # 3. Mídia de Inicialização
        target_path = Path(cfg.image_path)
        if not target_path.is_absolute():
            target_path = self.root / target_path

        target_str = str(target_path)

        if cfg.media_type == "fda":
            cmd.extend(["-fda", target_str])
        elif cfg.media_type == "drive":
            cmd.extend(["-drive", f"file={target_str},format=raw,index=0,media=disk"])
        elif cfg.media_type == "cdrom":
            cmd.extend(["-cdrom", target_str])
        elif cfg.media_type == "kernel":
            cmd.extend(["-kernel", target_str])
        else:
            raise ValueError(f"Tipo de mídia inválido: {cfg.media_type}")

        # 4. Firmware UEFI (se fornecido)
        if cfg.uefi_rom:
            rom_path = Path(cfg.uefi_rom)
            if not rom_path.is_absolute():
                rom_path = self.root / rom_path
            if not rom_path.exists():
                raise FileNotFoundError(f"ROM UEFI não encontrada em: {rom_path}")
            cmd.extend(["-bios", str(rom_path)])

        # 5. Telemetria Serial
        # Plano A: Redirecionamento stdio para leitura imediata
        # Plano B: Gravação contínua em arquivo de log
        if cfg.serial_mode == "stdio":
            cmd.extend(["-serial", "stdio"])
        elif cfg.serial_mode == "file":
            serial_out = self.root / cfg.serial_log_file
            cmd.extend(["-serial", f"file:{serial_out}"])

        # 6. Auditoria e Telemetria de CPU (Hórus)
        if cfg.trace_cpu:
            trace_out = self.root / cfg.trace_log_file
            cmd.extend([
                "-d", "int,cpu_reset,guest_errors",
                "-D", str(trace_out),
                "-no-reboot",
                "-no-shutdown"
            ])

        # 7. Depuração Remota GDB
        if cfg.debug_gdb:
            # -s abre porta TCP:1234, -S paralisa a CPU no primeiro ciclo de clock
            cmd.extend(["-gdb", f"tcp::{cfg.gdb_port}", "-S"])

        # 8. Argumentos Customizados Adicionais
        if cfg.extra_args:
            cmd.extend(cfg.extra_args)

        return cmd

    def run(self, cfg: QemuRunConfig) -> RunResult:
        """
        [RÁ] Dispara e supervisiona o emulador.
        Lida com interrupções do usuário (Ctrl+C), salvaguarda dry-run e coleta de logs.
        """
        try:
            cmd = self.build_command(cfg)
        except Exception as e:
            return RunResult(
                success=False,
                return_code=-1,
                command=[],
                message=f"Falha na validação do comando: {e}"
            )

        # Salvaguarda ProDeNov: Modo Dry-Run não toca o sistema
        if cfg.dry_run:
            return RunResult(
                success=True,
                return_code=0,
                command=cmd,
                message="[DRY-RUN] Comando forjado e validado com sucesso."
            )

        # Verificação de existência da mídia antes do disparo real
        target_path = Path(cfg.image_path)
        if not target_path.is_absolute():
            target_path = self.root / target_path

        if not target_path.exists():
            return RunResult(
                success=False,
                return_code=-1,
                command=cmd,
                message=f"Arquivo de mídia não encontrado: {target_path}"
            )

        trace_log = (self.root / cfg.trace_log_file) if cfg.trace_cpu else None
        serial_log = (self.root / cfg.serial_log_file) if cfg.serial_mode == "file" else None

        # Limpa logs antigos para garantir precisão
        if trace_log and trace_log.exists():
            try:
                trace_log.unlink()
            except Exception:
                pass

        try:
            # Execução direta com repasse de I/O
            proc = subprocess.run(cmd, cwd=str(self.root))
            return RunResult(
                success=(proc.returncode == 0),
                return_code=proc.returncode,
                command=cmd,
                trace_file=trace_log,
                serial_file=serial_log,
                message="Sessão de emulação finalizada normalmente."
            )
        except KeyboardInterrupt:
            return RunResult(
                success=True,
                return_code=130,
                command=cmd,
                trace_file=trace_log,
                serial_file=serial_log,
                message="Emulador encerrado pelo desenvolvedor (SIGINT/Ctrl+C)."
            )
        except Exception as e:
            return RunResult(
                success=False,
                return_code=-1,
                command=cmd,
                trace_file=trace_log,
                serial_file=serial_log,
                message=f"Erro durante execução do QEMU: {e}"
            )
