# -*- coding: utf-8 -*-
# doxoade/tools/lua_systems/khonsu/khonsu_init.py
"""
🌙 KHONSU INIT BUILDER — Construtor de Inits de Alta Performance e Dual-Snapshot.
Orquestra a montagem, otimização AOT e instalação de inits para máquina e humano.
"""
from __future__ import annotations
import os
import shutil
import time
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Union

from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
from doxoade.commands.lite_xl_systems.lite_xl_init_builder import LiteXLInitBuilder
from .khonsu_opt import KhonsuOptimizer


class KhonsuInitBuilder:
    """🌙 Forjador de inits otimizados AOT com suporte a Dual-Snapshot."""

    @classmethod
    def build_sovereign_init(cls, opt_mode: str = "bytecode") -> Tuple[Union[bytes, str], str, Dict[str, Any]]:
        """
        Gera o código-fonte humano E o artefato de máquina otimizado.
        Returns: (artefato_otimizado, fonte_humano_dev, metricas)
        """
        # 1. Gera o código-fonte humano soberano completo
        raw_source = LiteXLInitBuilder.generate_sovereign_init()

        # 2. Submete o código ao otimizador Khonsu
        force_text = (opt_mode == "text" or opt_mode == "minified")
        optimized_artifact, metrics = KhonsuOptimizer.optimize(raw_source, force_text=force_text)

        return optimized_artifact, raw_source, metrics

    @classmethod
    def install_to_environment(
        cls,
        target_mode: str = "production",
        opt_mode: str = "bytecode",
        save_dev_mirror: bool = True
    ) -> Dict[str, Any]:
        """
        Instala o init otimizado no diretório alvo (production, sandbox ou test).
        Grava o init.lua compilado e o init.lua.dev legível.
        """
        if target_mode == "sandbox":
            deploy_dir = LiteXLPaths.get_sandbox_dir()
        elif target_mode == "test":
            deploy_dir = LiteXLPaths.get_user_dir() / ".doxoade" / "test_deploy"
        else:
            deploy_dir = LiteXLPaths.get_user_dir()

        deploy_dir.mkdir(parents=True, exist_ok=True)
        init_dest = deploy_dir / "init.lua"
        dev_mirror_dest = deploy_dir / "init.lua.dev"

        # 1. Compila os artefatos
        opt_artifact, dev_source, metrics = cls.build_sovereign_init(opt_mode=opt_mode)

        # Se for modo test/sandbox, anexa os hooks forenses
        if target_mode in ("test", "sandbox"):
            hooks_file = Path(__file__).resolve().parent.parent.parent.parent / "commands" / "lite_xl_systems" / "template" / "chaos_hooks.lua"
            if hooks_file.exists():
                hooks_code = hooks_file.read_text(encoding="utf-8")
                dev_source = dev_source + "\n\n-- 🛡️ HOOKS DE TELEMETRIA FORENSE\n" + hooks_code
                opt_artifact, metrics = KhonsuOptimizer.optimize(dev_source, force_text=(opt_mode == "text"))

        # 2. Gravação do binário/texto de máquina em init.lua
        if isinstance(opt_artifact, bytes):
            with open(init_dest, "wb") as f:
                f.write(opt_artifact)
        else:
            init_dest.write_text(opt_artifact, encoding="utf-8")

        # 3. Gravação do espelho legível do desenvolvedor (Dual-Snapshot)
        if save_dev_mirror:
            dev_mirror_dest.write_text(dev_source, encoding="utf-8")

        return {
            "success": True,
            "target_mode": target_mode,
            "opt_mode": metrics["mode"],
            "init_path": init_dest,
            "dev_mirror_path": dev_mirror_dest if save_dev_mirror else None,
            "metrics": metrics
        }
