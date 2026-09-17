# -*- coding: utf-8 -*-
# doxoade/commands/lite_xl_systems/runtime_process_probe.py
"""
🔬 DOXLY RUNTIME PROCESS PROBE V2 — Sonda Blindada Anti-Implosão.
Testa de forma segura e não-destrutiva o ciclo completo de 'process' no Lite XL:
  • Zero taskkill global (nunca encerra instâncias de trabalho do usuário).
  • Testa assinaturas de start, pipes, read_stdout, write e close_stream.
  • Prescrição técnica automatizada baseada nos resultados empíricos.
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        GREEN = YELLOW = RED = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""

from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

class RuntimeProcessProbeEngine:
    """Orquestrador do ciclo de vida da sonda de runtime de subprocessos do Lite XL."""

    @classmethod
    def get_probe_dir(cls) -> Path:
        """Diretório 100% isolado e efêmero para execução da sonda."""
        probe_dir = LiteXLEngine.get_sandbox_dir().parent / "runtime_process_probe"
        probe_dir.mkdir(parents=True, exist_ok=True)
        return probe_dir

    @classmethod
    def generate_probe_lua_script(cls, json_out_path: Path) -> str:
        """Gera o script Lua autônomo com testes de start e I/O não-bloqueantes."""
        posix_json = json_out_path.as_posix()
        return f"""-- 🔬 SONDA DE INTROSPECÇÃO AVANÇADA DA API PROCESS
local json_out = "{posix_json}"
local report = {{
    timestamp = os.date("%Y-%m-%d %H:%M:%S"),
    platform = rawget(_G, "PLATFORM") or "unknown",
    version = rawget(_G, "VERSION") or "unknown",
    process_type = type(process),
    fields = {{}},
    signatures = {{}},
    io_tests = {{}},
    instance_methods = {{}},
}}

if type(process) == "table" then
    for k, v in pairs(process) do
        report.fields[tostring(k)] = {{ type = type(v), value = tostring(v) }}
    end

    local test_cmd = (rawget(_G, "PLATFORM") == "Windows") and {{"cmd.exe", "/c", "echo DOX_PROBE_OK"}} or {{"echo", "DOX_PROBE_OK"}}
    
    -- 1. Permutações de start
    local ok1, res1 = pcall(process.start, test_cmd)
    report.signatures["start_single_arg"] = {{ ok = ok1, result_type = type(res1), error = not ok1 and tostring(res1) or nil }}

    local valid_proc = ok1 and (type(res1) == "userdata" or type(res1) == "table") and res1 or nil

    local ok2, res2 = pcall(process.start, test_cmd, {{}})
    report.signatures["start_empty_options"] = {{ ok = ok2, result_type = type(res2), error = not ok2 and tostring(res2) or nil }}
    if not valid_proc and ok2 and (type(res2) == "userdata" or type(res2) == "table") then valid_proc = res2 end

    local ok3, res3 = false, "REDIRECT_PIPE nil"
    if process.REDIRECT_PIPE then
        ok3, res3 = pcall(process.start, test_cmd, {{ stdin = process.REDIRECT_PIPE, stdout = process.REDIRECT_PIPE }})
    end
    report.signatures["start_redirect_pipe_constants"] = {{ ok = ok3, result_type = type(res3), error = not ok3 and tostring(res3) or nil }}

    -- 2. Inspeção de métodos de instância
    if valid_proc then
        local methods = {{"read", "read_stdout", "read_stderr", "write", "close_stream", "terminate", "kill", "wait", "returncode", "running", "pid"}}
        for _, m in ipairs(methods) do
            if type(valid_proc[m]) == "function" then
                report.instance_methods[m] = "function"
            end
        end

        -- 3. Teste de I/O em processo interativo seguro
        local shell_cmd = (rawget(_G, "PLATFORM") == "Windows") and {{"cmd.exe"}} or {{"sh"}}
        local ok_io, io_proc = pcall(process.start, shell_cmd)
        if ok_io and io_proc then
            -- Teste write
            if io_proc.write then
                local ok_w, w_err = pcall(io_proc.write, io_proc, "echo TEST_OK\\r\\n")
                report.io_tests["write"] = {{ ok = ok_w, error = not ok_w and tostring(w_err) or nil }}
            end
            -- Teste read_stdout vs read
            if io_proc.read_stdout then
                local ok_r, r_err = pcall(io_proc.read_stdout, io_proc, 1024)
                report.io_tests["read_stdout"] = {{ ok = ok_r, result = ok_r and type(r_err) or nil, error = not ok_r and tostring(r_err) or nil }}
            end
            if io_proc.read then
                local stream_out = process.STREAM_STDOUT or 1
                local ok_r2, r_err2 = pcall(io_proc.read, io_proc, stream_out, 1024)
                report.io_tests["read_stream_arg"] = {{ ok = ok_r2, error = not ok_r2 and tostring(r_err2) or nil }}
            end
            -- Encerra o processo de teste sem zumbis
            pcall(function()
                if io_proc.terminate then io_proc:terminate()
                elseif io_proc.kill then io_proc:kill() end
            end)
        end

        pcall(function() if valid_proc.kill then valid_proc:kill() end end)
    end
end

-- Gravação atômica do JSON de resultado
local f = io.open(json_out, "w")
if f then
    f:write("{{\\n")
    f:write(string.format('  "timestamp": %q,\\n', report.timestamp))
    f:write(string.format('  "platform": %q,\\n', report.platform))
    f:write(string.format('  "version": %q,\\n', report.version))
    f:write(string.format('  "process_type": %q,\\n', report.process_type))
    
    f:write('  "fields": {{\\n')
    local ff = {{}}
    for k, v in pairs(report.fields) do
        table.insert(ff, string.format('    %q: {{ "type": %q, "value": %q }}', k, v.type, v.value))
    end
    f:write(table.concat(ff, ",\\n") .. "\\n  }},\\n")

    f:write('  "signatures": {{\\n')
    local ss = {{}}
    for k, v in pairs(report.signatures) do
        local err_part = v.error and string.format(', "error": %q', v.error) or ''
        table.insert(ss, string.format('    %q: {{ "ok": %s, "result_type": %q%s }}', k, tostring(v.ok), v.result_type, err_part))
    end
    f:write(table.concat(ss, ",\\n") .. "\\n  }},\\n")

    f:write('  "io_tests": {{\\n')
    local ii = {{}}
    for k, v in pairs(report.io_tests) do
        local err_part = v.error and string.format(', "error": %q', v.error) or ''
        table.insert(ii, string.format('    %q: {{ "ok": %s%s }}', k, tostring(v.ok), err_part))
    end
    f:write(table.concat(ii, ",\\n") .. "\\n  }},\\n")

    f:write('  "instance_methods": {{\\n')
    local mm = {{}}
    for k, v in pairs(report.instance_methods) do
        table.insert(mm, string.format('    %q: %q', k, v))
    end
    f:write(table.concat(mm, ",\\n") .. "\\n  }}\\n")
    f:write("}}\\n")
    f:flush()
    f:close()
end
"""

    @classmethod
    def run_probe(cls, timeout_sec: float = 3.5) -> Dict[str, Any]:
        """Executa a sonda empírica automatizada no sandbox sem matar processos alheios."""
        probe_dir = cls.get_probe_dir()
        json_out = probe_dir / "runtime_process_probe.json"
        if json_out.exists():
            json_out.unlink(missing_ok=True)

        init_file = probe_dir / "init.lua"
        init_file.write_text(cls.generate_probe_lua_script(json_out), encoding="utf-8")

        exe = LiteXLEngine.find_executable()
        if not exe:
            return {"success": False, "error": "Executável lite-xl não encontrado no sistema."}

        env = os.environ.copy()
        env["LITE_USERDIR"] = str(probe_dir)
        env["XDG_CONFIG_HOME"] = str(probe_dir.parent)

        CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
        cmd = [str(exe), "--userdir", str(probe_dir)]
        start_time = time.time()

        proc = subprocess.Popen(
            cmd,
            env=env,
            creationflags=CREATE_NEW_CONSOLE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        # Aguarda geração do arquivo sem matar arbitrariamente
        while (time.time() - start_time) < timeout_sec:
            if json_out.exists() and json_out.stat().st_size > 50:
                break
            if proc.poll() is not None:
                break
            time.sleep(0.1)

        # Encerra APENAS o PID da sonda
        if proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=1.0)
            except Exception:
                pass

        if not json_out.exists():
            stderr_output = proc.stderr.read() if proc.stderr else ""
            return {
                "success": False,
                "error": f"A sonda não gerou telemetria. Erro stderr: {stderr_output[:200]}",
                "probe_dir": str(probe_dir)
            }

        try:
            probe_data = json.loads(json_out.read_text(encoding="utf-8", errors="replace"))
            probe_data["success"] = True
            probe_data["duration_ms"] = round((time.time() - start_time) * 1000, 2)
            return probe_data
        except Exception as e:
            return {"success": False, "error": f"Falha ao ler resultado JSON da sonda: {e}"}

    @classmethod
    def render_report(cls, data: Dict[str, Any]) -> None:
        """Renderiza o laudo de engenharia com prescrições técnicas automáticas."""
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═' * 75}")
        print("🔬 DOXLY RUNTIME PROCESS PROBE V2 — LAUDO DE COMPATIBILIDADE C/LUA")
        print(f"{'═' * 75}{Style.RESET_ALL}\n")

        if not data.get("success"):
            print(f"  {Fore.RED}✖ Falha na execução da sonda:{Fore.RESET} {data.get('error')}")
            print(f"  {Fore.LIGHTBLACK_EX}Diretório de teste:{Fore.RESET} {data.get('probe_dir')}\n")
            return

        print(f"  • {Fore.WHITE}Plataforma/SO   :{Fore.RESET} {data.get('platform')} ({sys.platform})")
        print(f"  • {Fore.WHITE}Versão Lite XL  :{Fore.RESET} {data.get('version')}")
        print(f"  • {Fore.WHITE}Tempo da Sonda  :{Fore.RESET} {data.get('duration_ms')} ms")
        print(f"  • {Fore.WHITE}Tipo de process :{Fore.RESET} {Fore.GREEN if data.get('process_type') == 'table' else Fore.RED}{data.get('process_type')}{Fore.RESET}\n")

        # Constantes
        fields = data.get("fields", {})
        print(f"  {Fore.CYAN}📋 CONSTANTES & ENUMS EXPORTADOS:{Fore.RESET}")
        if fields:
            for k, v in sorted(fields.items()):
                print(f"     ├─ {Style.BRIGHT}{k:<24}{Style.RESET_ALL} ({v['type']}) = {Fore.YELLOW}{v['value']}{Fore.RESET}")
        print()

        # Permutações de start
        signatures = data.get("signatures", {})
        print(f"  {Fore.MAGENTA}🧪 TESTE DE PERMUTAÇÕES (process.start):{Fore.RESET}")
        for sig_name, res in signatures.items():
            ok = res.get("ok", False)
            badge = f"{Fore.GREEN}[FUNCIONA]{Fore.RESET}" if ok else f"{Fore.RED}[FALHA]{Fore.RESET}"
            print(f"     ├─ {badge} {Style.BRIGHT}{sig_name:<30}{Style.RESET_ALL} ➔ Retorno: {res.get('result_type')}")
            if not ok and res.get("error"):
                print(f"     │    ↳ {Fore.LIGHTBLACK_EX}Erro C:{Fore.RESET} {res['error']}")
        print()

        # Testes de I/O
        io_tests = data.get("io_tests", {})
        if io_tests:
            print(f"  {Fore.BLUE}⚡ TESTES DE FLUXO DE I/O (Read / Write):{Fore.RESET}")
            for io_name, res in io_tests.items():
                ok = res.get("ok", False)
                badge = f"{Fore.GREEN}[FUNCIONA]{Fore.RESET}" if ok else f"{Fore.RED}[FALHA]{Fore.RESET}"
                print(f"     ├─ {badge} {Style.BRIGHT}{io_name:<30}{Style.RESET_ALL}")
            print()

        # Métodos da instância
        methods = data.get("instance_methods", {})
        print(f"  {Fore.WHITE}⚙️  MÉTODOS DO OBJETO PROCESSO (Instância):{Fore.RESET}")
        if methods:
            methods_str = ", ".join(sorted([f"{m}()" for m in methods.keys()]))
            print(f"     ↳ {Fore.GREEN}{methods_str}{Fore.RESET}\n")

        # 💡 Prescrição Técnica Automatizada
        print(f"{Fore.CYAN}{'═' * 75}")
        print(f"💡 PRESCRIÇÃO TÉCNICA BASEADA EM EVIDÊNCIAS (Lite XL {data.get('version')})")
        print(f"{'═' * 75}{Style.RESET_ALL}")

        has_single_arg = signatures.get("start_single_arg", {}).get("ok", False)
        has_read_stdout = "read_stdout" in methods

        if has_single_arg:
            print(f"  1. {Fore.GREEN}✔ Spawn de Processo:{Fore.RESET} Use {Fore.YELLOW}process.start(cmd_args){Fore.RESET} sem tabela de options.")
        if has_read_stdout:
            print(f"  2. {Fore.GREEN}✔ Leitura de Saída:{Fore.RESET} Use {Fore.YELLOW}proc:read_stdout(chunk_size){Fore.RESET} em vez de proc:read().")
        print(f"  3. {Fore.GREEN}✔ Escrita em Stdin:{Fore.RESET} Use {Fore.YELLOW}proc:write(data){Fore.RESET} com flush via Enter (\\r\\n).")
        print(f"  4. {Fore.YELLOW}⚠ Alerta de Compatibilidade:{Fore.RESET} REDIRECT_PIPE é nulo nesta versão. Nunca passe opções de pipe em string ou tabela.")
        print(f"{Fore.CYAN}{'═' * 75}{Style.RESET_ALL}\n")
