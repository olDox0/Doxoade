# doxoade/commands/init.py
import os
import sys
import subprocess
import re
import click
from doxoade.tools.doxcolors import Fore, Style
# Importa as ferramentas necessárias do módulo compartilhado
from ..shared_tools import (
    ExecutionLogger,
    _run_git_command
)
#init(autoreset=True)
__version__ = "34.0 Alfa"
@click.command('init')
@click.pass_context
@click.argument('project_name', required=False)
@click.option('--remote', help="URL do repositório Git remoto para publicação automática.")
def init(ctx, project_name, remote):
    """Cria a estrutura de um novo projeto e, opcionalmente, o publica no GitHub."""
    arguments = ctx.params
    path = '.' # O comando 'init' opera a partir do diretório atual
    with ExecutionLogger('init', path, arguments) as logger:
        click.echo(Fore.CYAN + "--- [INIT] Assistente de Criação de Novo Projeto ---")
        if not project_name:
            project_name = click.prompt("Qual é o nome do seu novo projeto?")
        
        if not re.match(r'^[a-zA-Z0-9_-]+$', project_name):
            msg = "O nome do projeto deve conter apenas letras, números, hífens e underscores."
            logger.add_finding('error', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}")
            sys.exit(1)
        
        project_path = os.path.abspath(project_name)
        if os.path.exists(project_path):
            msg = f"O diretório '{project_path}' já existe."
            logger.add_finding('error', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}")
            sys.exit(1)
            
        original_dir = os.getcwd()
        
        try:
            # --- LÓGICA DE CRIAÇÃO LOCAL ---
            click.echo(f"   > Criando a estrutura do projeto em: {project_path}")
            os.makedirs(project_path)
            
            click.echo("   > Criando ambiente virtual 'venv'...")
            subprocess.run([sys.executable, "-m", "venv", os.path.join(project_path, "venv")], check=True, capture_output=True)
            click.echo("   > Criando arquivo .gitignore...")
            gitignore_content = (f"# {project_name} .gitignore\n\nvenv/\n__pycache__/\n*.py[cod]\nbuild/\ndist/\n*.egg-info/\n.vscode/\n.idea/\n.env\n\n# --- Arquivos de Cache do Python ---\n\n__pycache__/\n*.py[cod]\n*.pyc\n*.pyo\n*.pyd\n\n# --- Arquivos de Ambiente Virtual ---\n\nvenv/\n.venv/\nenv/\n.env\n\n# --- Arquivos de Build e Distribuição (para PyInstaller) ---\n\nbuild/\ndist/\n*.egg-info/\n*.spec\n\n# --- ARQUIVOS SENSÍVEIS E DE USUÁRIO (NUNCA COMPARTILHAR) ---\n\n*.json\n*.log\n*.old\n*.txt\n*.bkp\n*.bak\n*.dox\n*.nppBackup\n\nExemplo/\ntmp/\n\n# --- Arquivos de Configuração de IDE ---\n\n.vscode/\n.idea/\n\n# --- Arquivos de sistema do Windows ---\n\ndesktop.ini\nThumbs.db\n# --- BACKUPS E ARQUIVOS TEMPORÁRIOS ---\n\nVers/\n\n*.mak\n*.log\n\n# --- Doxoade cache files\n\n.doxoade_cache/\n.dox_agent_workspace/\n.dox_lab/\ndoxoade/opt/\n\n# Exceções (Auto-fixed pelo Doxoade)\n\n!requirements.txt\n")
            with open(os.path.join(project_path, ".gitignore"), "w", encoding="utf-8") as f: f.write(gitignore_content)
            
            click.echo("   > Criando arquivo requirements.txt...")
            with open(os.path.join(project_path, "requirements.txt"), "w", encoding="utf-8") as f: f.write("# Adicione suas dependências aqui\n")
            
            click.echo("   > Criando arquivo indentity.md inicial...")
            indentity_md_content = (f"---\n\n# 📄 Relatório Universal de Delimitação de Escopo e Decisão\n\n## 1️⃣ Existência do {project_name} (POR QUÊ?)\n\n**Objetivo:** evitar projetos que não deveriam existir.\n\n1. Qual problema real {project_name} resolve?\n2. O que acontece se {project_name} **não** existir?\n3. Qual é o custo atual do problema (tempo, erro, dinheiro, energia)?\n4. Este problema é:\n\n   * recorrente\n   * crítico\n   * ou apenas incômodo?\n5. {project_name} elimina o problema ou apenas o desloca?\n6. Qual decisão {project_name} precisa tornar óbvia?\n\n> Se não há decisão clara, não há {project_name}.\n\n---\n\n## 2️⃣ Usuário Real (QUEM?)\n\n**Objetivo:** impedir design para “usuário imaginário”.\n\n7. Quem usa {project_name}?\n8. Quem **não** deve usá-lo?\n9. Qual o nível técnico mínimo esperado do usuário?\n10. O {project_name} é usado:\n\n    * interativamente\n    * automaticamente\n    * ambos?\n11. O que o usuário **mais erra hoje**?\n12. O {project_name} reduz esse erro ou só o mascara?\n\n---\n\n## 3️⃣ Escopo Funcional (O QUÊ?)\n\n**Objetivo:** cortar excesso antes de nascer.\n\n13. O que {project_name} **DEVE** fazer obrigatoriamente?\n14. O que ele **PODE** fazer, mas não é essencial?\n15. O que ele **NUNCA** deve fazer?\n16. O {project_name}:\n\n    * executa ações\n    * orquestra ações\n    * valida decisões\n    * apenas informa?\n17. Ele toma decisões ou apenas expõe opções?\n18. O que acontece se ele falhar?\n\n---\n\n## 4️⃣ Fronteiras Claras (ATÉ ONDE?)\n\n**Objetivo:** impedir expansão infinita.\n\n19. O que fica explicitamente fora do {project_name}?\n20. O {project_name} substitui algo existente ou apenas integra?\n21. Em que ponto ele deve **parar e falhar**, em vez de continuar?\n22. Ele corrige problemas ou apenas detecta?\n23. O {project_name} conhece o ambiente ou é neutro?\n24. Quais problemas **não são responsabilidade** de {project_name}?\n\n---\n\n## 5️⃣ Arquitetura Mental (COMO PENSAR?)\n\n**Objetivo:** alinhar visão e estrutura.\n\n25. {project_name} é mais parecido com:\n\n    * ferramenta\n    * serviço\n    * plataforma\n    * biblioteca\n    * produto?\n26. Ele deve ser:\n\n    * fechado e previsível\n    * extensível\n27. Como ele cresce?\n\n    * código direto\n    * plugins\n    * configuração\n28. O que é pior:\n\n    * não fazer algo\n    * fazer algo errado?\n29. O {project_name} deve otimizar para:\n\n    * segurança\n    * velocidade\n    * clareza\n    * flexibilidade?\n\n---\n\n## 6️⃣ Qualidade e Risco (COM QUE CUIDADO?)\n\n**Objetivo:** evitar fragilidade invisível.\n\n30. Qual erro é inaceitável?\n31. Onde o {project_name} **pode** errar?\n32. Qual falha deve aparecer o mais cedo possível?\n33. O {project_name} precisa ser:\n\n    * determinístico\n    * tolerante a falhas\n    * autoexplicativo?\n34. Como ele comunica erro?\n35. O erro gera aprendizado ou confusão?\n\n---\n\n## 7️⃣ Evolução Controlada (FUTURO)\n\n**Objetivo:** permitir crescimento sem perda de identidade.\n\n36. Qual é o limite máximo de complexidade aceitável?\n37. Quando uma funcionalidade deve virar {project_name} separado?\n38. O que, se entrar, corrompe o {project_name}?\n39. O que deve permanecer estável por anos?\n40. O que pode ser descartável?\n\n---\n\n## 8️⃣ Critério de Sucesso (COMO SABER?)\n\n**Objetivo:** impedir desenvolvimento eterno.\n\n41. Como saber que o {project_name} deu certo?\n42. Qual métrica simples indica sucesso?\n43. O que melhora imediatamente quando ele é usado?\n44. Quando você pararia de trabalhar nele?\n45. O que você aceita **não resolver**?\n\n---\n\n## 9️⃣ Pergunta Final (a mais importante)\n\n46. Se você tivesse que explicar {project_name} em **uma frase técnica**, qual seria?\n\n> Se não cabe em uma frase clara, o escopo ainda está errado.\n\n---\n\n## 🧠 Regra de Ouro\n\n> **Projeto bom não é o que faz tudo.\n> É o que sabe exatamente o que não faz.**\n\n---\n")
            with open(os.path.join(project_path, "indentity.md"), "w", encoding="utf-8") as f: f.write(indentity_md_content)
            
            click.echo("   > Criando arquivo main.py inicial...")
            main_py_content = (f"def main():\n    print(\"Bem-vindo ao {project_name}!\")\n\nif __name__ == '__main__':\n    main()\n")
            with open(os.path.join(project_path, "main.py"), "w", encoding="utf-8") as f: f.write(main_py_content)
            click.echo("   > Inicializando repositório Git...")
            os.chdir(project_path)
            if not _run_git_command(['init', '-b', 'main']):
                logger.add_finding('error', "Falha ao inicializar o repositório Git.")
                sys.exit(1)
            click.echo(Fore.GREEN + "\n[OK] Estrutura local do projeto criada com sucesso!")
            # --- LÓGICA DE PUBLICAÇÃO AUTOMÁTICA ---
            if remote:
                click.echo(Fore.CYAN + "\n--- Publicando projeto no repositório remoto ---")
                
                click.echo(f"   > Adicionando remote 'origin' -> {remote}")
                if not _run_git_command(['remote', 'add', 'origin', remote]):
                    logger.add_finding('error', "Falha ao adicionar o remote Git.")
                    sys.exit(1)
                
                click.echo("   > Adicionando todos os arquivos ao Git (git add .)...")
                if not _run_git_command(['add', '.']):
                    logger.add_finding('error', "Falha ao executar 'git add .'.")
                    sys.exit(1)
                commit_message = f"Commit inicial: Estrutura do projeto {project_name}"
                click.echo(f"   > Criando commit inicial com a mensagem: '{commit_message}'...")
                if not _run_git_command(['commit', '-m', commit_message]):
                    logger.add_finding('error', "Falha ao executar 'git commit'.")
                    sys.exit(1)
                click.echo("   > Enviando para o branch 'main' no remote 'origin' (git push)...")
                if not _run_git_command(['push', '--set-upstream', 'origin', 'main']):
                    click.echo(Fore.RED + "[ALERTA] Push rejeitado. Tentando reconciliação automática...")
                    pull_success = _run_git_command([
                        'pull', 'origin', 'main',
                        '--rebase',
                        '--allow-unrelated-histories'
                    ])

                    if pull_success:
                        click.echo(Fore.GREEN + "   > [OK] Históricos reconciliados. Tentando push novamente...")
                        if not _run_git_command(['push', '--set-upstream', 'origin', 'main']):
                            msg = "Falha final no push após reconciliação automática."
                            logger.add_finding('error', msg)
                            click.echo(Fore.RED + f"[ERRO] {msg}")
                            sys.exit(1)
                    else:
                        msg = "Falha ao reconciliar com o remoto. Verifique conflitos e permissões do repositório."
                        logger.add_finding('error', msg)
                        click.echo(Fore.RED + f"[ERRO] {msg}")
                        sys.exit(1)
                click.echo(Fore.GREEN + "\n[OK] Projeto publicado com sucesso!")
                click.echo(Style.BRIGHT + f"   > Veja seu repositório em: {remote}")
            
            else:
                click.echo(Fore.YELLOW + "\nLembrete: Este é um projeto local. Para publicá-lo mais tarde, use 'doxoade git-new'.")

            # Pós-init: abre automaticamente um shell com venv e elevação (best effort).
            click.echo(Fore.CYAN + "\n--- Ativação automática do ambiente (venv-up --admin) ---")
            try:
                os.chdir(project_path)
                launch_result = subprocess.run(
                    ['doxoade', 'venv-up', '--admin'],
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                if launch_result.returncode == 0:
                    click.echo(Fore.GREEN + "[OK] Solicitação de shell administrativo enviada com sucesso.")
                else:
                    click.echo(Fore.YELLOW + "[AVISO] Não foi possível iniciar 'doxoade venv-up --admin' automaticamente.")
                    logger.add_finding('warning', 'Falha ao executar venv-up --admin automaticamente.')
            except Exception as launch_error:
                click.echo(Fore.YELLOW + f"[AVISO] Falha ao disparar venv-up automático: {launch_error}")
                logger.add_finding('warning', f"Falha ao disparar venv-up automático: {launch_error}")
        except Exception as e:
            logger.add_finding('fatal_error', f"Ocorreu um erro inesperado durante a inicialização: {e}")
            click.echo(Fore.RED + f"[ERRO] Ocorreu um erro inesperado: {e}")
        finally:
            os.chdir(original_dir)
