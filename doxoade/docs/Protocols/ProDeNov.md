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
    3.1.4. sistema de diagnostico é fundamental em qualquer sistema, ele deve responder sobre: onde?, o que?, quem?, quando?, quanto? porque? origem? e consequencias estas perguntas são essencias em diagnostico.
4. Situações reais
  4.1. Caso o prazo não permitir o sistema estiver estavel o suficiente, pode-se não seguir o protocolo
    4.1.1. se o sistema funciona naquele contexto limitado, pode-se cosidera-lo pronto temporariamente até a proxima revisão.
  4.2. Caso o dev não estejá com a capacidade de desenvolveimento com segurança no momento, não desenvolva no periodo, ou só planeje.
    4.2.1. Esta regra é por questões de segurança contra regressões.
5. Recomendações:
  5.1. É recomendado colocar notas tecnicas sobre problemas, é importante, é necessario colocar informações sobre o problema. pode-se colocar no codigo em docstring o erro se necessario.
  5.2. Recomenda-se fortemente que lide com o tratamento de exceptions para que falhas sejam bem informadas e previstas para que o deve não fique a ver navios com relação a erros.
  5.3. recomenda-se salvaguardas --dry-run por padrão caso o comando ou sistema manipule questões excepcionais para o workflow, features essencial e UX.
  5.4. mecanismos para verificar a integridade dos dados é essencial. recomendase um err table para fazer previsão de problemas e já ter uma solução em mente; maior exemplo desta tecnica é o doxoade typhon
  5.5. antes de comitar faça revisão vendo o diff para lidar com regressões da melhor forma.
  5.6. para não ficar preso num development hell, deve testar cada implementação adequadamente, com calma, um passo de cada vez. fazer um blitzplan é bastante recomendado, e fazer roteiro para teste e implementação é adequado.
6. Comunicação:
 6.1. Atualiação de codigo deve seguir serto protocolo:
  6.1.1. Contexto, é preciso contextualizar o problema
  6.1.2. problema, qual o problema, o que?, onde?, quando?, porque?, quem? origem? e consequencias
  6.1.3. solução, a resposta deve ser breve, o snipped de modificação com referencia do final e começo dos codigos anteriores.
  6.1.4. previsão do resultado.
  6.1.5. citações devem ser mencionadas no codigo por razões eticas e de responsabilidade com a comunidade dev. então um comentario como: # solução de github.com/fulano/projeto ou """ fix https://site.com/exemplo/123 """

## Sistemas e conceitos

Blitz Devlopmente: Desenvolvimento baseado em preparo e construção rapida de prototipos, seguindo regras simples de planejamento, planos caso ocorra problemas em cada parte do desenvolvimento. assim uma documentação dita Blitzplan ou Blueprint é feita para auxilio em projetos que exigem mais de um dia de desenvolvimento. Assim é exigido sistemas de diagnsotico para auxiliar em teste em produção. não é tolerado erros ocultos ou falta de dados de erro.
* *Plano*:       Blitzplan para preparar o que vai ser feito, é a arquitetura, a documentação que vai fazer as coisas estaveis a longo prazo, ela pode estar no local do sistema mesmo e não necessariamente no docs/ caso o dev ache mais dinamico assim.
* *Requisição*:  contexto, O que, onde, quem, quando, quanto, porque, origem e consequencias. delegações e resposabilidade das partes. com isso o que vai ser usado, aonde, por quem, quanto vai ser usado, e porque daquele sistema. respostas simples já é bom começo; exemplo simplorio: python 3.12, projeto_x/, uso para devs, pequeno porte, projeto de exemplo.
* *Segurança*:   a garantia de que um problema ocorra e tenha reversibilidade, quanto um sistema traz segurança, isso é pefeito e o objetivo da segurança. com isso, um sistema complexo que manipula sistemas sensiveis tem que ser seguro, precisa de segurança
* *Devflow*:     é quando o dev pode fazer suas atividade com tranquilidade e segurança mesmo com imprevistos, e com garantias que o trabalho não sera perdido e permanecera escalavel. assim a manutenção tem sua importancia, um codigo que segue os protocolos teram sua criação, desenvolvimento e manutenção adequada.
* *os porques*:  qual o problema, o que?, onde?, quando?, porque?, quem? origem? e consequencias
* *Preservação*: é importante dados de registro e historico por preservação e investigações com segurança.
* *roteiro*:     roteiro de implementação e testagem(RIT/Ritual) -> avaliação -> sistema de diagnostico/testagem -> implementação.

## Sistemas

VULCAN:
 * **:

TYPHON: Sistema de diagnostico e triangulação de dados. doxoade typhon apresentou o conteito de rastreamento de problemas, posteriorment no doxly foi aprofundado o sistema para um sistema de testagem, diagnostico com profundidade para sistemas complexos.
 * *Rastreabilidade*: este é extremamente importante para ter um horizonte da profundidade de um problema.
 * *Caos*: Sistema de testagem para avaliar o diagnostico de problemas, para que respondam: onde? quando? o que? quem? porque? origem? e consequencia com isso é possivel triangular o problema para facilitar o resolução deste
 * *Diagnostico*: o diagnostico de problemas deve fornecer os dados do problema, o alastro, W5, e afins.
 
DOXLY: IDE naqual o doxoade adotou para usar em produção do doxoade e de outros projetos. dotada de integrações e sistemas de apoio para desenvolvimento rapido de prototipos, reparação rapida, flexibilidade e outras atividades.
 * *Automação*:
 * *Workflow*:

## Exemplos reais:

´´´python
# -*- coding: utf-8 -*-
# doxoade/commands/lite_xl_systems/cmd_typhon_deploy.py
"""
Comandos CLI para o Typhon Deploy Engine v2.0.
Separação clara entre PRODUCTION, SANDBOX e TEST modes com Launch Automático.
"""
import click
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from .typhon_deploy import TyphonDeployEngine

@click.group("deploy", help="🐉 Pipeline de deploy com separação produção/testes.")
def deploy_group():
    """Grupo de comandos de deploy Typhon."""
    pass

@deploy_group.command("status", help="Mostra status de todos os modos de deploy.")
@click.option("--mode", "-m", type=click.Choice(["production", "sandbox", "test"]), help="Modo específico.")
def cmd_status(mode):
    """Exibe status completo dos modos de deploy."""
    TyphonDeployEngine.print_status(mode)

@deploy_group.command("production", help="Deploy em PRODUÇÃO (com backup e launch automático).")
@click.option("--force", "-f", is_flag=True, help="Força deploy mesmo com warnings.")
@click.option("--launch/--no-launch", "-l/-nl", default=True, help="Lança o Lite XL após deploy (Padrão: True).")
def cmd_deploy_production(force, launch):
    """Deploy seguro em produção com backup e lançamento automático."""
    print(f"\n{Fore.GREEN}{Style.BRIGHT}🟢 DEPLOY PRODUCTION{Style.RESET_ALL}\n")
    result = TyphonDeployEngine.deploy("production", force=force)
    if result["success"]:
        print(f"\n{Fore.GREEN}✔ Deploy de produção concluído com sucesso!{Fore.RESET}")
        if result["backup"]:
            print(f"{Fore.CYAN}💾 Backup de segurança: {result['backup'].name}{Fore.RESET}")
        if launch:
            print()
            TyphonDeployEngine.launch("production", exorcise=False)
    else:
        print(f"\n{Fore.RED}✖ Deploy falhou: {result['error']}{Fore.RESET}")
        if result["backup"]:
            print(f"{Fore.YELLOW}🔄 Rollback automático executado.{Fore.RESET}")

@deploy_group.command("sandbox", help="Deploy em SANDBOX (isolamento total + launch automático).")
@click.option("--launch/--no-launch", "-l/-nl", default=True, help="Lança o Lite XL após deploy (Padrão: True).")
@click.option("--exorcise", is_flag=True, default=False, help="Mata instâncias antigas de sandbox.")
def cmd_deploy_sandbox(launch, exorcise):
    """Deploy isolado no sandbox sem interferir na produção."""
    print(f"\n{Fore.BLUE}{Style.BRIGHT}🔵 DEPLOY SANDBOX{Style.RESET_ALL}\n")
    result = TyphonDeployEngine.deploy("sandbox")
    if result["success"]:
        print(f"\n{Fore.GREEN}✔ Deploy de sandbox concluído!{Fore.RESET}")
        print(f"{Fore.LIGHTBLACK_EX}   Diretório isolado: {result['init'].parent}{Fore.RESET}")
        if launch:
            print()
            TyphonDeployEngine.launch("sandbox", exorcise=exorcise)
    else:
        print(f"\n{Fore.RED}✖ Deploy falhou: {result['error']}{Fore.RESET}")

´´´
