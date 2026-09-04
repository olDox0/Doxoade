# doxoade\docs\Protocols\ProDeNov.md
# PROTOCOLO DE DESENVOLVIMENTO NOVISSIMO / ProDeNov
## Glossario:
singular; plural com repetição ex: S. Ss.
Sistema - S./Ss.

## Desenvolvimento:
este é o novo protocolo simplificado e sucinto de desenvolveimento do doxoade. basicamente outros protocolos são muito estenço e detalhados desnecessariamente, então protocolo Novissimo vai lidar com esta direção.
1. planejamento: o planejarmento deve se basear no contexto da implementação, ouseja Sistema operacional, ferramentas usadas no contexto, como python 3.12, e objetivo e compatibilidade.
  1.0. seguir o protocolo ProDeNov obrigatoriamente. a interpretação caso não implicita deve ser feita a decisão por parte do leitor, e a viabilidade da aplicação do protocolo pode ser questionado para critica construtiva e evoulução continua.
  1.1. faça brainstoming do que é desejado e depois analise de viabilidade, manutenção e escalabilidade posteriormente
  1.2. tasklist de features e checklist de implementação, revisão, plano A á C e implementação. 
   1.2.1. os sistemas devem ter na sua implementação, dito capitulo, deve ter na parte do capitulo um pano A e B no minimo, pois caso haja falha, tera um plano B, isso aumenta a segurança da implementação.
  1.3. revisão de regressão deve ser colocada na tasklist e checklist.
  1.4. prazo e prioridade do sistema(automatico ou manual).
2. placeholders: deve se estabelecer o que sera usado e preparar os placeholder naqual é o esboço do sistema, neste sera estabilicido os seguintes elementos:
  2.1. os arquivos com seus objetivos, obs: limite de 50kb. os arquivos devem ter o seguinte modelo:
    2.1.1. o comentario com o local relativo ao projeto, exemplo pratico # RAIZ/DIRETORIO/ARQUIVO.xyz . outro exemplo real: "# doxoade/commands/lite_xl_systems/template/03_tab_colors.lua"
    2.1.2. depois do anterior deve colocar o docstrings com o objetivo arquivo e especificações exemplo: """ Interface CLI para Orquestração, Diag. Forense, Verificação de Templates e Reinício. """
    2.1.3.  imports, neste sera colocado os imports que seram usados naquele arquivo.
        2.1.3.1. obs: em database não se usa o sqlite, se delega a um arquivo para este fim por razões de segurança.
    2.1.4. esboço de funções. neste sera esboçado funções, nestas sera explicado sua atividade no docstring e sera desenhado um fluxo
    2.1.4. Integração, dependendo se já existir delegações na arquitetura existente, vai ser necessario adaptar ou adequar.
3. questões tecnicas: elaborarei sobre tecnicidades chatas aqui
  3.1. recomenda-se usar o que esta estabilicido com mais prioridade, se possivel delegue funções ao o que já existe e tem aquele fim.
    3.1.1. se existe uma lib padrão que já cumpri aquela tarefa, use-a. só não use se o escopo ou regras não permir.
    3.1.2. dependendo do objetivo vai ser preciso criar camadas de orquestão para inter-operabilidade.
    3.1.3. num onjetivo complexo, vai ser preciso desenvolver sistemas complexos ou delegar sistemas complexos
    3.1.4. sistema de diagnostico é fundamental em qualquer sistema, ele deve responder sobre: onde?, o que?, quem?, quando?, quanto? e porque? estas perguntas são essencias em diagnostico.
4. Situações reais
  4.1. Caso o prazo não permitir o sistema estiver estavel o suficiente, pode-se não seguir o protocolo
    4.1.1. se o sistema funciona naquele contexto limitado, pode-se cosidera-lo pronto temporariamente até a proxima revisão.
  4.2. Caso o dev não estejá com a capacidade de desenvolveimento com segurança no momento, não desenvolva no periodo, ou só planeje.
    4.2.1. Esta regra é por questões de segurança contra regressões.
5. Recomendações:
  5.1. É recomendado colocar notas tecnicas sobre problemas, é importante, é necessario colocar informações sobre o problema. pode-se colocar no codigo em docstring o erro se necessario.
  5.2. Recomenda-se fortemente que lide com o tratamento de exceptions para que falhas sejam bem informadas e previstas para que o deve não fique a ver navios com relação a erros.
6. Comunicação:
 6.1. Atualiação de codigo deve seguir serto protocolo:
  6.1.1. Contexto, é preciso contextualizar o problema
  6.1.2. problema, qual o problema, o que?, onde?, quando?, porque?, quem?
  6.1.3. solução, a resposta deve ser breve, o snipped de modificação com referencia do final e começo dos codigos anteriores.
  6.1.4. previsão do resultado.

## Sistemas e conceitos

Blitz Devlopmente: Desenvolvimento baseado em preparo e construção rapida de prototipos, seguindo regras simples de planejamento, planos caso ocorra problemas em cada parte do desenvolvimento. assim uma documentação dita Blitzplan ou Blueprint é feita para auxilio em projetos que exigem mais de um dia de desenvolvimento. Assim é exigido sistemas de diagnsotico para auxiliar em teste em produção. não é tolerado erros ocultos ou falta de dados de erro.
* *Plano*: Blitzplan para preparar o que vai ser feito, é a arquitetura, a documentação que vai fazer as coisas estaveis a longo prazo, ela pode estar no local do sistema mesmo e não necessariamente no docs/ caso o dev ache mais dinamico assim.
* *Requisição*: contexto, O que, onde, quem, quando, quanto, e porque. delegações e resposabilidade das partes. com isso o que vai ser usado, aonde, por quem, quanto vai ser usado, e porque daquele sistema. respostas simples já é bom começo; exemplo simplorio: python 3.12, projeto_x/, uso para devs, pequeno porte, projeto de exemplo.
* *Segurança*: a garantia de que um problema ocorra e tenha reversibilidade, quanto um sistema traz segurança, isso é pefeito e o objetivo da segurança. com isso, um sistema complexo que manipula sistemas sensiveis tem que ser seguro, precisa de segurança
* *Devflow*: é quando o dev pode fazer suas atividade com tranquilidade e segurança mesmo com imprevistos, e com garantias que o trabalho não sera perdido e permanecera escalavel. assim a manutenção tem sua importancia, um codigo que segue os protocolos teram sua criação, desenvolvimento e manutenção adequada.
## Exemplos reais:

´´´python
# doxoade/commands/lite_xl_systems/cmd_lite_xl.py
""" Interface CLI para Orquestração, Diag. Forense, Verificação de Templates e Reinício. """
import os
import re
import sys
import time
import shutil
import subprocess
import click
from datetime import datetime, timedelta
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

@click.group("lite-xl", help="⚡ Gestão, diagnóstico e automação do Lite XL.")
def lite_xl_group():
    """Grupo de comandos do ecossistema Lite XL."""
    pass

@lite_xl_group.command(
    "check-templates",
    help=(
        "Audita individualmente cada arquivo de template .lua com snippets"
        " forenses."
    ),
)
@click.option(
    "--fix",
    "-f",
    is_flag=True,
    help="Simula o autorreparo de templates (DRY-RUN por padrão).",
)
@click.option(
    "--apply",
    "-a",
    is_flag=True,
    help="Aplica as correções no disco (sai do modo Dry-Run).",
)
def cmd_check_templates(fix, apply):
    is_fix_active = fix or apply
    is_dry_run = not apply

    t_dir = LiteXLEngine.get_template_dir()
    click.echo(
        f"\n{Fore.CYAN}{Style.BRIGHT}🧩 AUDITORIA DE TEMPLATES MODULARES LITE"
        f" XL{Style.RESET_ALL}"
    )
    click.echo(f"  {Fore.WHITE}Diretório:{Fore.RESET} {t_dir}\n")

    # ═══════════════════════════════════════════════════════════
    # 1. AUTO-FIX ENGINE (COM DRY-RUN E SNIPPETS DE DIFF)
    # ═══════════════════════════════════════════════════════════
    if is_fix_active:
        fix_report = LiteXLEngine.fix_templates(dry_run=is_dry_run)

        if fix_report["total_fixes"] > 0:
            if is_dry_run:
                click.echo(
                    f"{Fore.YELLOW}{Style.BRIGHT}🔍 [DRY-RUN] PRÉVIA DE"
                    f" AUTORREPARO ({fix_report['total_fixes']} correções"
                    f" propostas):{Style.RESET_ALL}\n"
                )
            else:
                click.echo(
                    f"{Fore.GREEN}{Style.BRIGHT}✔ [APPLY] AUTORREPARO APLICADO"
                    f" COM SUCESSO ({fix_report['total_fixes']} correções"
                    f" gravadas):{Style.RESET_ALL}\n"
                )

            for item in fix_report["fixed_files"]:
                click.echo(
                    f"  {Fore.CYAN}📄 {item['file']}{Fore.RESET} ({item['fixes']}"
                    " reparos):"
                )
                for diff in item["diffs"]:
                    click.echo(
                        f"    {Fore.WHITE}┌─ [{item['file']}:{diff['line']}]"
                        f" → {diff['type']}{Fore.RESET}"
                    )
                    click.echo(f"    {Fore.RED} - {diff['old']}{Fore.RESET}")
                    click.echo(f"    {Fore.GREEN} + {diff['new']}{Fore.RESET}")
                    click.echo(f"    {Fore.WHITE}└{'─' * 60}{Fore.RESET}")
                click.echo()

            if is_dry_run:
                click.echo(
                    f"{Fore.YELLOW}💡 Nenhuma alteração foi gravada no disco."
                    " Execute com --apply para efetivar:{Fore.RESET}"
                )
                click.echo(
                    f"   {Fore.WHITE}doxoade lite-xl check-templates --fix"
                    f" --apply{Fore.RESET}\n"
                )
        elif fix:
            click.echo(
                f"{Fore.GREEN}✔ Nenhum reparo pendente nos"
                f" templates.{Fore.RESET}\n"
            )

    # ═══════════════════════════════════════════════════════════
    # 2. AUDITORIA E SNIPPETS FORENSES DE CÓDIGO
    # ═══════════════════════════════════════════════════════════
    report = LiteXLEngine.verify_templates()
    for fname, data in report["files"].items():
        status_badge = (
            f"{Fore.GREEN}[PASS]{Fore.RESET}"
            if data["status"] == "PASS"
            else f"{Fore.RED}[FAIL]{Fore.RESET}"
        )
        click.echo(
            f"  {status_badge} {Style.BRIGHT}{fname:<35}{Style.RESET_ALL}"
            f" ({data['lines']} linhas)"
        )

        for err in data["errors"]:
            click.echo(f"      {Fore.RED}✖ {err}{Fore.RESET}")

        # Renderização de Snippets Visuais
        for finding in data.get("findings", []):
            if finding.get("snippet"):
                line_no = finding["line"]
                click.echo(
                    f"        {Fore.CYAN}┌─ [{fname}:{line_no}]{Fore.RESET}"
                )
                for ln, is_target, code_text in finding["snippet"]:
                    prefix = f"{Fore.RED}>>{Fore.RESET}" if is_target else "  "
                    click.echo(
                        f"        {prefix} {Fore.YELLOW}{ln:4d} |{Fore.RESET}"
                        f" {code_text}"
                    )
                click.echo(f"        {Fore.CYAN}└{'─' * 50}{Fore.RESET}")

    if report["all_ok"]:
        click.echo(
            f"\n{Fore.GREEN}{Style.BRIGHT}✔ Todos os {report['total_files']}"
            " templates .lua estão 100% íntegros e"
            f" compatíveis!{Style.RESET_ALL}\n"
        )
    else:
        click.echo(
            f"\n{Fore.RED}{Style.BRIGHT}✖ Foram encontrados erros nos"
            f" templates acima.{Style.RESET_ALL}"
        )
        if not is_fix_active:
            click.echo(
                f"{Fore.YELLOW}💡 Dica: Execute 'doxoade lite-xl"
                f" check-templates --fix' para simular o auto-reparo.{Fore.RESET}\n"
            )

@lite_xl_group.command("kill", help="Encerra todos os processos do Lite XL em execução.")
def cmd_kill():
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "lite-xl"], capture_output=True)
    click.echo(f"{Fore.GREEN}✔ Processos do Lite XL encerrados.{Fore.RESET}")


@lite_xl_group.command("restart", help="Salva a sessão, encerra e reinicia com todas as abas e splits preservados.")
@click.argument("target", required=False, default=".")
def cmd_restart(target):
    if LiteXLEngine.is_running():
        try:
            ipc_queue = LiteXLEngine.get_ipc_queue_path()
            with open(ipc_queue, "a", encoding="utf-8") as f:
                f.write("__DOXOADE_GRACEFUL_QUIT__\n")
            time.sleep(0.4)
        except Exception:
            pass

    LiteXLEngine.kill_ghost_processes()
    time.sleep(1.0)

    click.echo(f"{Fore.YELLOW}Reiniciando Lite XL com sessão preservada...{Fore.RESET}")
    native_exe = LiteXLEngine.find_executable()

    if native_exe:
        resolved_path, _, _ = LiteXLEngine.resolve_target_path(target)
        working_dir = str(Path(resolved_path).parent if Path(resolved_path).is_file() else resolved_path)
        subprocess.Popen(
            [str(native_exe), resolved_path],
            cwd=working_dir,
            close_fds=True
        )
        click.echo(f"{Fore.GREEN}✔ Lite XL reiniciado com abas e divisões mantidas:{Fore.RESET} {resolved_path}")
    else:
        click.echo(f"{Fore.RED}✖ Executável lite-xl.exe não encontrado.{Fore.RESET}")


@lite_xl_group.command("diagnose", help="Realiza auditoria forense do init.lua e templates.")
def cmd_diagnose():
    init_file = LiteXLEngine.get_init_lua_path()
    err_file = LiteXLEngine.get_error_txt_path()
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🩺 DIAGNÓSTICO FORENSE DO INIT.LUA{Style.RESET_ALL}")
    click.echo(f"  {Fore.WHITE}Alvo:{Fore.RESET} {init_file}\n")

    if err_file.exists():
        click.echo(f"{Fore.RED}{Style.BRIGHT}⚠ CRASH REPORT DETECTADO (error.txt):{Style.RESET_ALL}")
        click.echo(err_file.read_text(encoding="utf-8", errors="replace"))

    report = LiteXLEngine.diagnose_init_file(init_file)
    if not report["exists"]:
        click.echo(f"{Fore.RED}✖ Arquivo init.lua não encontrado.{Fore.RESET}")
        return

    if report["errors"]:
        click.echo(f"{Fore.RED}{Style.BRIGHT}✖ ERROS CRÍTICOS DETECTADOS ({len(report['errors'])}):{Style.RESET_ALL}")
        for err in report["errors"]:
            click.echo(f"  {Fore.RED}• {err}{Fore.RESET}")
    else:
        click.echo(f"{Fore.GREEN}✔ Sintaxe, escapes e módulos 100% validados!{Fore.RESET}")

    if report["checks"]:
        click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}✔ CHECAGENS DE INTEGRIDADE:{Style.RESET_ALL}")
        for c in report["checks"]:
            click.echo(f"  {Fore.GREEN}•{Fore.RESET} {c}")

    click.echo()


def parse_traceback(traceback_text, message=""):
    """Extrai informações estruturadas do traceback OU da mensagem."""
    lines = traceback_text.strip().split('\n') if traceback_text else []
    culprit_file = None
    culprit_line = 0
    culprit_name = "core"
    frames = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        frames.append(line)
        if line.startswith('[C]:') or line.startswith('[STRING') or 'core/init.lua' in line.lower():
            continue
        match = re.search(r'([a-zA-Z]:\\[^:\n]+|\/[^:\n]+):(\d+)', line)
        if match:
            fpath = match.group(1)
            fline = int(match.group(2))
            fname = fpath.replace('\\', '/')
            if 'program files' in fname.lower() and 'data/core' in fname.lower():
                continue
            if 'plugins/' in fname.lower() or 'plugins\\' in fname.lower():
                plug_match = re.search(r'plugins[/\\]([^/\\]+)', fname, re.IGNORECASE)
                culprit_name = plug_match.group(1) if plug_match else fname.split('/')[-1]
            elif 'init.lua' in fname.lower():
                culprit_name = "user_init"
            else:
                culprit_name = fname.split('/')[-1]
            culprit_file = fpath
            culprit_line = fline
            break

    # Fallback na mensagem se o traceback não revelou o arquivo
    if not culprit_file and message:
        match = re.search(r'([a-zA-Z]:\\[^:\n]+|\/[^:\n]+):(\d+)', message)
        if match:
            culprit_file = match.group(1)
            culprit_line = int(match.group(2))
            fname = culprit_file.replace('\\', '/')
            culprit_name = fname.split('/')[-1]

    return {
        "file": culprit_file,
        "line": culprit_line,
        "name": culprit_name,
        "frames": frames,
    }


def render_snippet(file_path, line_no):
    """Renderiza snippet do código fonte."""
    if not file_path:
        return
    target = Path(file_path)
    if not target.exists() or not target.is_file():
        return
    try:
        src_lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(0, line_no - 3)
        end = min(len(src_lines), line_no + 2)
        click.echo(f"    {Fore.CYAN}┌─ [{target.name}:{line_no}]{Fore.RESET}")
        for idx in range(start, end):
            ln = idx + 1
            prefix = f"{Fore.RED}>>{Fore.RESET}" if ln == line_no else "  "
            click.echo(f"    {prefix} {Fore.YELLOW}{ln:4d} |{Fore.RESET} {src_lines[idx]}")
        click.echo(f"    {Fore.CYAN}└────────────────────────────────────{Fore.RESET}")
    except Exception:
        pass

´´´
