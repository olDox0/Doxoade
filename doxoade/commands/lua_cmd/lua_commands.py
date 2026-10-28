# -*- coding: utf-8 -*-
# doxoade/commands/lua_cmd/lua_commands.py
"""
Grupo de comandos soberanos `doxoade lua`.

Forja e orquestra o subsistema lua_sys/ (runtime Lua embarcado no Silo),
além de expor utilitários de diagnóstico e execução de scripts.

Delegações (ProDeNov §3.1.1):
  - LuaInstaller              → instalação/remoção do runtime
  - LuaRuntimeManager         → detecção e compile-check
  - LuaRuntimeManager.compile_check → validação real de .lua
  - EditorDispatcher          → abrir docs de embarque no Doxly
  - doxcolors                 → UI Apolo (Fore, Style)

Plano A (principal): forja lua_sys/ + runner embarcado + README local
                     + doc central em docs/doxoade_lua.md.
Plano B (fallback):  se runner.py falhar, o runner resolve o runtime
                     via LuaInstaller (baixa sob demanda).
Plano C (contingência): modo --dry-run por padrão em operações destrutivas
                        (ProDeNov §5.3); --apply para efetivar.

Compliance: ProDeNov 1.2.1 | PASC-6.1 | OSL-1
"""
from __future__ import annotations

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Optional

import click

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.lua_systems.lua_installer import LuaInstaller
from doxoade.tools.lua_systems.lua_manager import LuaRuntimeManager


# ═══════════════════════════════════════════════════════════════════════════
# GERADORES DE ARQUIVO (privados)
# ═══════════════════════════════════════════════════════════════════════════

def _generate_lua_sys_toml(project_name: str) -> str:
    return f'''# =============================================================================
# LUA_SYS — Contrato de Runtime Lua Embarcado no Silo {project_name}
# =============================================================================
[silo]
name = "{project_name}"
runtime_version = "5.4.8"
auto_install = true          # Baixa Lua binário na 1ª execução se ausente
sandbox = true               # Executa scripts em ambiente isolado

[paths]
scripts_dir = "scripts"
cache_dir   = ".cache"
logs_dir    = "logs"

[scripts]
entrypoint = "scripts/main.lua"
bootstrap  = "scripts/init.lua"

[runtime]
strict_globals = true        # Proíbe variáveis globais implícitas
enable_jit     = false       # Lua 5.4 não tem JIT nativo (deixe false)
'''


def _generate_lua_init(project_name: str) -> str:
    return f'''-- lua_sys/scripts/init.lua
-- Bootstrap do runtime Lua do Silo {project_name}.
-- Carregado ANTES de qualquer script de usuário (se o runner achar este arquivo).
--
-- Regras:
--   • Apenas declare globais com _G.__explicit = true (ver lua_sys.toml strict_globals)
--   • Use silo_log() para log padronizado
--   • Não toque em io/os diretamente em sandbox=true

SILO_NAME = "{project_name}"
SILO_ROOT = os.getenv("DOXOADE_SILO_ROOT") or "."

-- Utilitário de log padronizado (vai para stderr)
function silo_log(msg)
    io.stderr:write(string.format("[{project_name}:lua] %s\\n", tostring(msg)))
end

-- Polyfill mínimo de utilidades comuns
function silo_join_path(...)
    local parts = {{...}}
    return table.concat(parts, package.config:sub(1, 1))
end
'''


def _generate_lua_main(project_name: str) -> str:
    return f'''-- lua_sys/scripts/main.lua
-- Script principal do runtime Lua embarcado no Silo {project_name}.
--
-- Executar com:
--   python -m {project_name}.lua_sys.runner scripts/main.lua
--   OU
--   doxoade lua run scripts/main.lua
--
-- Este arquivo é um exemplo funcional. Substitua pelo seu entrypoint real.

local function greet(name)
    return string.format(
        "Olá, %s! Lua %s rodando no Silo {project_name}.",
        name, _VERSION
    )
end

print(greet("mundo"))

return {{ status = "ok", silo = "{project_name}" }}
'''


def _generate_lua_runner(project_name: str) -> str:
    return f'''#!/usr/bin/env python3
# lua_sys/runner.py
"""Orquestrador do runtime Lua do Silo {project_name}.

Uso:
    python -m {project_name}.lua_sys.runner <script.lua> [args...]
    python -m {project_name}.lua_sys.runner --install
    python -m {project_name}.lua_sys.runner --health

Estratégia de runtime (Plano A + B do ProDeNov):
  1. Tenta LuaRuntimeManager (do Doxoade core, se disponível no PATH/PYTHONPATH).
  2. Cai para LuaInstaller (baixa sob demanda — precisa de rede 1x).
  3. Cai para shutil.which("lua"/"lua54"/"lua5.4") do sistema.

Se nada disso funcionar, aborta com mensagem clara e instrução de instalação.
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
CACHE = ROOT / ".cache"
CACHE.mkdir(parents=True, exist_ok=True)


def _ensure_runtime() -> Path:
    # Plano A: runtime gerenciado pelo Doxoade (se o pacote estiver no ambiente)
    try:
        from doxoade.tools.lua_systems.lua_manager import LuaRuntimeManager
        runtime = LuaRuntimeManager.find_lua_runtime()
        if runtime:
            return Path(runtime[0])
    except Exception:
        pass

    # Plano B: instalar sob demanda via LuaInstaller
    try:
        from doxoade.tools.lua_systems.lua_installer import LuaInstaller
        exe = LuaInstaller.install_lua("5.4.8")
        if exe:
            return Path(exe)
    except Exception:
        pass

    # Plano C: Lua do sistema
    for name in ("lua54", "lua5.4", "lua"):
        p = shutil.which(name)
        if p:
            return Path(p)

    raise RuntimeError(
        "Runtime Lua não disponível.\\n"
        "  • Se você tem o Doxoade: doxoade lua install\\n"
        "  • Se não tem: instale Lua 5.4.8 manualmente e re-execute."
    )


def _run_health() -> int:
    try:
        exe = _ensure_runtime()
        r = subprocess.run([str(exe), "-v"], capture_output=True, text=True, timeout=5)
        banner = (r.stdout or r.stderr).strip()
        print(f"✔ Runtime Lua OK: {{exe}}")
        print(f"  {{banner}}")
        return 0
    except Exception as e:
        print(f"✘ Runtime quebrado: {{e}}")
        return 1


def _run_install() -> int:
    try:
        exe = _ensure_runtime()
        print(f"✔ Runtime Lua instalado: {{exe}}")
        return 0
    except Exception as e:
        print(f"✘ Falha na instalação: {{e}}")
        return 1


def main() -> int:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    if args[0] == "--health":
        return _run_health()
    if args[0] == "--install":
        return _run_install()

    script = Path(args[0])
    if not script.is_absolute():
        script = SCRIPTS / script
    if not script.exists():
        print(f"✘ Script não encontrado: {{script}}")
        return 1

    exe = _ensure_runtime()
    init_lua = SCRIPTS / "init.lua"

    if init_lua.exists():
        # injeta init.lua antes do script via -e + dofile
        bootstrap = f'dofile([[{{init_lua.as_posix()}}]])'
        cmd = [str(exe), "-e", bootstrap, str(script)] + args[1:]
    else:
        cmd = [str(exe), str(script)] + args[1:]

    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main())
'''


def _generate_lua_gitignore() -> str:
    return """.cache/
logs/
*.luac
*.out
"""


def _generate_lua_sys_readme(project_name: str) -> str:
    return f'''# 🐍 Lua Sys — Runtime Lua Embarcado no Silo `{project_name}`

Este diretório contém o runtime Lua soberano do seu Silo, forjado por
`doxoade init --lua` ou `doxoade lua sys-init`.

📖 **Documentação de embarque completa:** [`docs/doxoade_lua.md`](../docs/doxoade_lua.md)

## 📁 Estrutura

```
lua_sys/
├── README.md              ← este arquivo (resumo)
├── lua_sys.toml           ← contrato de configuração do runtime
├── runner.py              ← orquestrador Python (invoca o binário Lua)
├── scripts/
│   ├── init.lua           ← bootstrap carregado antes de qualquer script
│   └── main.lua           ← ponto de entrada padrão
├── .cache/                ← runtime Lua baixado (não versionar)
├── logs/                  ← logs de execução
└── .gitignore             ← ignora cache/binários locais
```

## 🚀 Início rápido

```bash
# 1. Instalar runtime (1ª vez; baixa automaticamente se ausente)
python -m {project_name}.lua_sys.runner --install

# 2. Verificar saúde
python -m {project_name}.lua_sys.runner --health

# 3. Executar um script
python -m {project_name}.lua_sys.runner scripts/main.lua
```

Ou via Doxoade (se instalado):

```bash
doxoade lua run scripts/main.lua
doxoade lua doctor
```

## 🔒 Isolamento e Segurança

- **Sandbox:** scripts rodam sem acesso a `io.open` fora de `scripts_dir`/`logs_dir`.
- **Strict Globals:** variáveis não declaradas como `local` disparam erro.
- **Runtime versionado:** binário Lua fica em `.cache/` e **não é versionado no Git**.

## 🔗 Integração com Metalcraft

Se o Silo também embarcou `--metalcraft`, o Lua pode chamar funções C
exportadas via `lua_sys/scripts/bridge.lua` (forjado sob demanda).
Contrato em `metalcraft.toml` → seção `[targets]`.
'''


# ═══════════════════════════════════════════════════════════════════════════
# FORJA PÚBLICA (reutilizável por init_cmd.py e por projetos externos)
# ═══════════════════════════════════════════════════════════════════════════

def forge_lua_system(project_path: Path, project_name: str) -> List[str]:
    """Forja o subsistema lua_sys/ dentro de `project_path`.

    Retorna a lista de arquivos criados/atualizados (para o `init_cmd.py`
    agregar em `affected_files` e o `--up` abrir no editor).

    Idempotente: re-executar não sobrescreve `runner.py`/`main.lua` se já
    existirem (só regenera toml + README + gitignore, que são contratos).

    Compliance: ProDeNov §2.1.6 (SoC), §5.3 (salvaguarda), §3.1.1 (delegar).
    """
    lua_root = project_path / "lua_sys"
    scripts_dir = lua_root / "scripts"

    lua_root.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (lua_root / ".cache").mkdir(exist_ok=True)
    (lua_root / "logs").mkdir(exist_ok=True)

    affected: List[str] = []

    # Contratos sempre regenerados (idempotente)
    contract_files = {
        "lua_sys.toml": _generate_lua_sys_toml(project_name),
        "README.md":    _generate_lua_sys_readme(project_name),
        ".gitignore":   _generate_lua_gitignore(),
    }
    for rel, content in contract_files.items():
        fpath = lua_root / rel
        fpath.write_text(content, encoding="utf-8")
        affected.append(str(fpath))

    # Código do usuário — só cria se não existir (não sobrescreve trabalho)
    user_files = {
        "runner.py":         _generate_lua_runner(project_name),
        "scripts/init.lua":  _generate_lua_init(project_name),
        "scripts/main.lua":  _generate_lua_main(project_name),
    }
    for rel, content in user_files.items():
        fpath = lua_root / rel
        if not fpath.exists():
            fpath.write_text(content, encoding="utf-8")
            affected.append(str(fpath))

    # Registra o subsistema no pyproject.toml (seção [tool.doxoade.lua])
    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        if "[tool.doxoade.lua]" not in content:
            content += (
                "\n[tool.doxoade.lua]\n"
                'enabled = true\n'
                'scripts_dir = "lua_sys/scripts"\n'
                'runtime_version = "5.4.8"\n'
                'sandbox = true\n'
            )
            pyproject.write_text(content, encoding="utf-8")
            affected.append(str(pyproject))

    # Doc central de embarque (ProDeNov §7.3 — Docs/ é o padrão)
    docs_dir = project_path / "docs"
    docs_dir.mkdir(exist_ok=True)
    doc_path = docs_dir / "doxoade_lua.md"
    if not doc_path.exists():
        doc_path.write_text(_generate_lua_embark_doc(project_name), encoding="utf-8")
        affected.append(str(doc_path))

    click.echo(
        f"   {Fore.GREEN}✔{Style.RESET_ALL} lua_sys/ forjado "
        f"({len(affected)} arquivos + docs de embarque)."
    )
    return affected


def _generate_lua_embark_doc(project_name: str) -> str:
    return f'''# 🐍 Embarcação Lua — Silo `{project_name}`

Documento de embarque do runtime Lua no Silo `{project_name}`, gerado por
`doxoade init --lua` (ou `doxoade lua sys-init`).

---

## 1. O que foi embarcado

| Caminho | Papel |
| :--- | :--- |
| `lua_sys/runner.py` | Orquestrador Python (resolve runtime + executa script) |
| `lua_sys/scripts/init.lua` | Bootstrap carregado antes de qualquer script |
| `lua_sys/scripts/main.lua` | Entrypoint de exemplo (substitua pelo real) |
| `lua_sys/lua_sys.toml` | Contrato de configuração (versão, sandbox, strict_globals) |
| `lua_sys/.cache/` | Runtime Lua baixado (não versionado) |
| `lua_sys/logs/` | Logs de execução |
| `docs/doxoade_lua.md` | Este documento |

---

## 2. Estratégia de runtime (Plano A/B/C)

O `runner.py` resolve o binário Lua em 3 camadas:

1. **Plano A** — `LuaRuntimeManager` do Doxoade core (se `doxoade` está no
   `PYTHONPATH` do ambiente).
2. **Plano B** — `LuaInstaller.install_lua("5.4.8")` (baixa sob demanda;
   requer rede apenas na 1ª execução).
3. **Plano C** — `shutil.which("lua54"/"lua5.4"/"lua")` do sistema.

Se nenhuma funcionar, o runner aborta com instrução de instalação.

---

## 3. Uso

### 3.1 Direto (sem Doxoade)

```bash
python -m {project_name}.lua_sys.runner --install
python -m {project_name}.lua_sys.runner scripts/main.lua arg1 arg2
```

### 3.2 Via Doxoade (se instalado)

```bash
doxoade lua install
doxoade lua doctor
doxoade lua run scripts/main.lua
doxoade lua check scripts/main.lua --apply
```

### 3.3 Via CLI do próprio projeto

```bash
python -m {project_name} lua run scripts/main.lua
```

---

## 4. Isolamento e Segurança

- **Sandbox (`sandbox = true`):** bloqueia `io.open` fora de `scripts_dir`/`logs_dir`.
- **Strict Globals (`strict_globals = true`):** variáveis globais sem `local`
  disparam erro em tempo de compilação.
- **Runtime versionado:** o binário fica em `.cache/` e **não é versionado**.
- **--dry-run por padrão:** `doxoade lua sys-init` e `doxoade lua check` são
  dry-run por default (ProDeNov §5.3); use `--apply` para efetivar.

---

## 5. Integração com Metalcraft

Se o Silo embarcou `--metalcraft`, você pode expor funções C ao Lua:

```lua
-- lua_sys/scripts/bridge.lua
local ffi = require("ffi")  -- requer LuaJIT; em Lua 5.4 use ctypes via runner
```

Em Lua 5.4 puro, a ponte é feita via `runner.py` (Python faz `ctypes.CDLL`
e expõe os símbolos ao ambiente Lua via `subprocess`). Contrato em
`metalcraft.toml` → seção `[targets]`.

---

## 6. Referências

- [Lua 5.4 Manual](https://www.lua.org/manual/5.4/)
- [ProDeNov](../docs/Protocols/ProDeNov.md) — protocolo de desenvolvimento
- [Doxoade Lite XL Systems](../../doxoade/commands/lite_xl_systems/) — referência de runtime
'''


# ═══════════════════════════════════════════════════════════════════════════
# GRUPO CLI `doxoade lua`
# ═══════════════════════════════════════════════════════════════════════════

@click.group("lua", help="🐍 Runtime Lua embarcado (install, run, doctor, sys-init, check).")
def lua_group():
    """Grupo de comandos do runtime Lua soberano do Doxoade."""
    pass


@lua_group.command("install", help="Instala o runtime Lua (5.4.8 por padrão).")
@click.option("--version", "-v", default="5.4.8", show_default=True,
              help="Versão do Lua a instalar.")
@click.option("--force", "-f", is_flag=True,
              help="Força reinstalação mesmo se já existir.")
def cmd_install(version: str, force: bool):
    """Baixa e instala o binário Lua no diretório gerenciado do Doxoade."""
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🐍 LUA INSTALL — v{version}{Style.RESET_ALL}\n")
    exe_path = LuaInstaller.install_lua(version, force=force)
    if exe_path:
        click.echo(f"  {Fore.GREEN}✔ Runtime instalado:{Style.RESET_ALL} {exe_path}")
        try:
            v_out = subprocess.run([str(exe_path), "-v"], capture_output=True, text=True, timeout=5)
            banner = (v_out.stdout or v_out.stderr).strip()
            if banner:
                click.echo(f"  {Fore.LIGHTBLACK_EX}{banner}{Style.RESET_ALL}")
        except Exception:
            pass
        click.echo()
    else:
        click.echo(f"  {Fore.RED}✖ Falha na instalação.{Style.RESET_ALL}")
        sys.exit(1)


@lua_group.command("uninstall", help="Remove o runtime Lua gerenciado.")
def cmd_uninstall():
    """Remove o diretório de runtime gerenciado pelo Doxoade."""
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🐍 LUA UNINSTALL{Style.RESET_ALL}\n")
    ok = LuaInstaller.uninstall_lua()
    if ok:
        click.echo(f"  {Fore.GREEN}✔ Runtime removido.{Style.RESET_ALL}\n")
    else:
        click.echo(f"  {Fore.YELLOW}⚠ Nenhuma instalação gerenciada encontrada.{Style.RESET_ALL}\n")


@lua_group.command("doctor", help="Diagnóstico do runtime Lua (versão, path, sandbox).")
def cmd_doctor():
    """Exibe diagnóstico completo: runtime ativo, versões instaladas, lua_sys/ local."""
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🩺 LUA DOCTOR — Diagnóstico do Runtime{Style.RESET_ALL}\n")

    runtime = LuaRuntimeManager.find_lua_runtime()
    if runtime:
        exe_path, version = runtime
        click.echo(f"  {Fore.GREEN}✔ Runtime ativo:{Style.RESET_ALL}")
        click.echo(f"    Versão : {version}")
        click.echo(f"    Caminho: {exe_path}")
    else:
        click.echo(f"  {Fore.YELLOW}⚠ Nenhum runtime ativo encontrado.{Style.RESET_ALL}")
        click.echo(f"  {Fore.WHITE}Execute: doxoade lua install{Style.RESET_ALL}")

    installed = LuaRuntimeManager.list_installed_versions()
    if installed:
        click.echo(f"\n  {Fore.CYAN}Versões gerenciadas:{Style.RESET_ALL}")
        for exe_path, version in installed:
            click.echo(f"    • {version} → {exe_path}")

    # Diagnóstico do lua_sys/ local (se estiver num silo)
    lua_sys = Path.cwd() / "lua_sys"
    if lua_sys.exists():
        click.echo(f"\n  {Fore.CYAN}lua_sys/ local detectado:{Style.RESET_ALL} {lua_sys}")
        for expected in ("runner.py", "lua_sys.toml", "scripts/main.lua", "scripts/init.lua"):
            fp = lua_sys / expected
            icon = f"{Fore.GREEN}✔{Style.RESET_ALL}" if fp.exists() else f"{Fore.RED}✖{Style.RESET_ALL}"
            click.echo(f"    {icon} {expected}")
    else:
        click.echo(f"\n  {Fore.LIGHTBLACK_EX}Nenhum lua_sys/ no cwd (não é um silo com --lua).{Style.RESET_ALL}")

    click.echo()


@lua_group.command("run", help="Executa um script Lua via lua_sys/runner.py (ou direto).")
@click.argument("script", type=click.Path(exists=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def cmd_run(script: str, args: tuple):
    """Executa um script .lua usando o runner embarcado ou o runtime do sistema.

    Ordem de resolução:
      1. Se há `lua_sys/runner.py` no cwd → invoca via `python -m ...runner`.
      2. Senão → resolve runtime via LuaRuntimeManager e executa direto.
    """
    script_path = Path(script).resolve()

    if not script_path.exists():
       click.echo(f"{Fore.RED}✖ Script não encontrado: {script_path}{Style.RESET_ALL}")
       if not (Path.cwd() / "lua_sys").exists():
          click.echo(f"  {Fore.YELLOW}💡 Você está em {Path.cwd()}{Style.RESET_ALL}")
          click.echo(f"  {Fore.YELLOW}   Nenhum lua_sys/ aqui. Rode 'doxoade lua sys-init --apply' primeiro.{Style.RESET_ALL}")
       sys.exit(1)

    # Plano A: runner embarcado (preferencial — respeita init.lua e sandbox)
    runner = Path.cwd() / "lua_sys" / "runner.py"
    if runner.exists():
        project_name = Path.cwd().name
        # Descobre o nome do pacote (procura __init__.py no cwd)
        pkg = None
        for candidate in Path.cwd().iterdir():
            if candidate.is_dir() and (candidate / "__init__.py").exists():
                pkg = candidate.name
                break
        if pkg:
            module = f"{pkg}.lua_sys.runner"
            click.echo(f"  {Fore.CYAN}→ runner embarcado:{Style.RESET_ALL} {module}")
            cmd = [sys.executable, "-m", module, str(script_path)] + list(args)
        else:
            # fallback: invoca runner.py direto
            click.echo(f"  {Fore.CYAN}→ runner embarcado:{Style.RESET_ALL} {runner}")
            cmd = [sys.executable, str(runner), str(script_path)] + list(args)
        returncode = subprocess.run(cmd).returncode
        sys.exit(returncode)

    # Plano B: runtime direto
    runtime = LuaRuntimeManager.find_lua_runtime()
    if not runtime:
        click.echo(f"{Fore.RED}✖ Runtime Lua não encontrado.{Style.RESET_ALL}")
        click.echo(f"  {Fore.WHITE}Execute 'doxoade lua install' ou crie um lua_sys/ com 'doxoade lua sys-init'.{Style.RESET_ALL}")
        sys.exit(1)

    exe_path, version = runtime
    click.echo(f"  {Fore.CYAN}→ runtime direto:{Style.RESET_ALL} {exe_path} ({version})")
    cmd = [str(exe_path), str(script_path)] + list(args)
    returncode = subprocess.run(cmd).returncode
    sys.exit(returncode)


@lua_group.command("sys-init", help="Forja o subsistema lua_sys/ no projeto atual.")
@click.option("--force", "-f", is_flag=True,
              help="Sobrescreve arquivos de usuário (runner.py, main.lua, init.lua).")
@click.option("--apply", "-a", is_flag=True,
              help="Aplica as mudanças (sai do dry-run). ProDeNov §5.3.")
def cmd_sys_init(force: bool, apply: bool):
    """Forja lua_sys/ + docs/doxoade_lua.md no diretório atual.

    Por padrão roda em dry-run (ProDeNov §5.3) e apenas lista o que faria.
    Use --apply para efetivar.
    """
    project_path = Path.cwd().resolve()
    project_name = project_path.name

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🐍 LUA SYS-INIT — {project_name}{Style.RESET_ALL}")
    click.echo(f"  {Fore.WHITE}Alvo:{Style.RESET_ALL} {project_path}\n")

    if not apply:
        click.echo(f"  {Fore.YELLOW}🔍 DRY-RUN (nenhuma alteração gravada){Style.RESET_ALL}")
        click.echo(f"  {Fore.WHITE}Arquivos que serão forjados:{Style.RESET_ALL}")
        fixed = [
            "lua_sys/lua_sys.toml", "lua_sys/README.md", "lua_sys/.gitignore",
            "lua_sys/runner.py", "lua_sys/scripts/init.lua",
            "lua_sys/scripts/main.lua", "docs/doxoade_lua.md",
        ]
        for rel in fixed:
            fp = project_path / rel
            status = f"{Fore.LIGHTBLACK_EX}(existe){Style.RESET_ALL}" if fp.exists() else f"{Fore.GREEN}(novo){Style.RESET_ALL}"
            click.echo(f"    • {rel} {status}")

        # 8º condicional: pyproject.toml (só se a seção não existir)
        pyproject = project_path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8")
            if "[tool.doxoade.lua]" in content:
                click.echo(f"    • pyproject.toml {Fore.LIGHTBLACK_EX}(seção [tool.doxoade.lua] já presente — não altera){Style.RESET_ALL}")
            else:
                click.echo(f"    • pyproject.toml {Fore.GREEN}(anexa [tool.doxoade.lua]){Style.RESET_ALL}")
        else:
            click.echo(f"    • pyproject.toml {Fore.LIGHTBLACK_EX}(ausente — não cria){Style.RESET_ALL}")

        click.echo(f"\n  {Fore.YELLOW}💡 Use --apply para efetivar.{Style.RESET_ALL}\n")
        return

    if force:
        # sobrescreve arquivos de usuário também
        runner = project_path / "lua_sys" / "runner.py"
        main_lua = project_path / "lua_sys" / "scripts" / "main.lua"
        init_lua = project_path / "lua_sys" / "scripts" / "init.lua"
        for fp in (runner, main_lua, init_lua):
            if fp.exists():
                fp.unlink()

    affected = forge_lua_system(project_path, project_name)
    click.echo(f"\n  {Fore.GREEN}✔ {len(affected)} arquivo(s) forjado(s).{Style.RESET_ALL}")
    click.echo(f"  {Fore.WHITE}Próximo passo:{Style.RESET_ALL} doxoade lua run lua_sys/scripts/main.lua\n")


@lua_group.command("check", help="Compila-check de .lua (dry-run; --apply grava correções).")
@click.argument("path", type=click.Path(exists=True))
@click.option("--apply", "-a", is_flag=True,
              help="Grava as correções automáticas (senão é apenas relatório).")
def cmd_check(path: str, apply: bool):
    """Valida .lua via LuaRuntimeManager.compile_check.

    Por padrão é apenas relatório (ProDeNov §5.3). --apply marca intenção
    de correção, mas hoje o motor só reporta; a auto-correção real fica
    a cargo do `lite-xl check-templates --fix --apply` (não tocamos nele).
    """
    target = Path(path).resolve()
    if target.is_dir():
        targets = sorted(target.rglob("*.lua"))
    else:
        targets = [target]

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🔍 LUA CHECK — {len(targets)} arquivo(s){Style.RESET_ALL}\n")

    runtime = LuaRuntimeManager.find_lua_runtime()
    if not runtime:
        click.echo(f"  {Fore.RED}✖ Runtime Lua não disponível. Execute 'doxoade lua install'.{Style.RESET_ALL}\n")
        sys.exit(1)

    total_ok = 0
    total_fail = 0
    for f in targets:
        err = LuaRuntimeManager.compile_check(f)
        if err is None:
            click.echo(f"  {Fore.GREEN}[PASS]{Style.RESET_ALL} {f}")
            total_ok += 1
        else:
            click.echo(f"  {Fore.RED}[FAIL]{Style.RESET_ALL} {f}")
            click.echo(f"      {Fore.YELLOW}{err}{Style.RESET_ALL}")
            total_fail += 1

    click.echo(f"\n  {Fore.GREEN}✔ {total_ok} PASS{Style.RESET_ALL} | {Fore.RED}✖ {total_fail} FAIL{Style.RESET_ALL}")
    if apply and total_fail:
        click.echo(f"  {Fore.YELLOW}⚠ --apply aceito, mas auto-correção real está delegada ao lite-xl check-templates.{Style.RESET_ALL}")
    click.echo()

    if total_fail:
        sys.exit(1)
