[33m384d171[m[33m ([m[1;36mHEAD[m[33m -> [m[1;32mmain[m[33m)[m olDox222 : Alfa 66.40 : 2025.12.24.a :   ■  Refatoração : Modularização do shared_tools em doxoade.tools (Git, FS, Analysis, Logger)
[33m9c9d56d[m[33m ([m[1;31morigin/main[m[33m, [m[1;31morigin/HEAD[m[33m)[m olDox222 : Alfa 66.37 : 2025.12.24.a  ■  MaxTelemetry : Aprimoramento para monitorar uso de recursos de programas terceiros em python, agora suporta a analise de filhos no doxoade run, o dito Tree Monitoring e o Execution-In-Process, infelizmente com exec ouseja brecha de segurança se não for tratado corretamente.  ■  Run : Corrigido --flow --internal para dados de processamento consultaveis sem erro na exibição do processamento.  ■  Run --flow : Melhoria na exibição dos dados de leitura sob a execução com uma Text User Interface um pouco melhor
[33m398eedc[m olDox222 : Alfa 66.30 : 2025.12.22.a : ■ Sync - Agora com sincronização git (git push) mais inteligente e segura para não causar regressões acidentais vindas do desenvolvimento entre sistemas diferentes, sync --safe. ■ Canon-Regression - Avançando com o Sistema Scaffolding Anti-Regressão; ● Tripe (QA-Integrated): cobertura de testes automatizados, Snapshots, e teste de regressão.  ■ Check - Correção do problema gravissimo no sistema de identificação nos aspectos gerais de todos os niveis; ● Adicionado _run_style_probe; ● Adicionada função de ignorar a analise de style por padrão no check, alem de opção --exclude; ● Sistema de Prioridade e Filtragem para exibição dos problemas para o usuario - _print_summary; Correção de retrosseços acidentais; Verificação dos arquivos de sondagem e varredura no doxoade/probes/, cobertura com pytest foi feita.  ■ Search - Sistema Nexus de cruzamento de dados, agora o search é mais inteligente ao pesquisar os dados obtidos no uso do doxoade(Precisa ser melhorado).  ■ Sistema MaxTelemetry para armazenar dados de uso de recursos naqual o doxoade faz, CPU, RAM, DISCO.  ■ Alfagold Ouroborus - Sistema de treinamento de IA com melhoria de 25-40% da velocidade de treinamento com o uso de Lookup Table, que basicamente é um tabelamento de pre-calculo que é carregado nas memorias L1 e L2 da CPU; ● Alem de Otimização matematica do Adam para calcular vies como escalar antes de processar matrizes - Scalar Bias Correction: Calcular Aceleração Angular fora da matriz; ● In-Place Operations: Usar *= e += para não alocar memória nova; ● Otimização de Raiz: Evitar g**2 (lento) e usar g*g (rápido); ● Aumento do batch para 128; Documentação - Atualizada, Relatório Técnicos melhores para o Alfagold; ● Modificação do True Batching para usar Pre-Allocated Master Cache para combater gargalo de acesso da ram no accumulate_grad isto gerou um resultado bizzaramente rapido, CPU N2808 usada em 200%, os dois nucleos usados em totalidade, windows todo travado, não ironicamente, o que éra 4 Horas de treino com 100 epocas com 1000 Amostras agora é 5 Minutos.  ■ Nota - veja que se o homem chegou na lua com 1MHz, 72kb, 4kb RAM, 16bits, 55W e inteface de Calculadora(DSKY) o segredo não é performace nem memoria, é um projeto que consiga conceber seus proprios problemas e resolvelos com o tempo e suporte seus proprios erros e aprenda com eles ou pelos menos os documente.
[33m239d1cc[m Alfa 65.47 : 2025.12.17.b - Correções de regressões acidentais. atualizações ainda em andamento
[33m01b9e52[m Alfa 65.47 : 2025.12.17.a - Correções de regressões acidentais. atualizações ainda em andamento
[33m22b132c[m Merge branch 'main' of https://github.com/olDox0/Doxoade
[33m5c5d824[m olDox222 : Alfa 65.45 : 2025.12.16.a - Brain - Pickle removido por questões de segurança identificados pelo security(bandit), agora é usado o json; foram feitos asDocumentações e Roadmap de P&D da IA prototipo. Security - Correção e aprimoramento do comando, fora adicionado niveis de analise, correção da analise para ser limitada deacordo com configuração do toml; Hardening completo: Security Clean Sweep (0 High/Medium); dezenas de problemas relevantes foram corrigidos no doxoade, o security foi usado; Documentação atualizada com Protocolo Aegis e Hardening de Segurança. Check - Aprimoramento do dicionario de abdução de imports no STDLIB_MODULES, agora com math e random. History - Aprimoramento para dados mais ricos e cruzamento de dados com o doxoade search atraves de --incidents; agora a pesquisa mais flexivel e modos como --limit delimite de exibição; --unsolved para mostrar questões não exclarecidas.
[33m0f565f1[m olDox222 : Alfa 65.13 : 2025.12.15.a - Rescue - Correção na escolha do editor no termux. Ide - configura o json do micro para que alt + d divida a tela no meio para dois arquivos.
[33m42495c7[m Merge branch 'main' of https://github.com/olDox0/Doxoade
[33mb511298[m Resolvendo conflitos manualmente em brain.py e core.py
[33mdf73519[m olDox222 : Alfa 65.15 : 2025.12.14 - Brain - Ouroboros IA (Experimental Self-Learning AI)
[33mf009749[m olDox222 : Alfa 65.10 : 2025.12.14.b - Brain - Sistema de raciocinio dedutivo (Sherlock) para codigo baseado no DPLL (Davis-Putnam-Logemann-Loveland). Resolução da contaminhação de contexto. Novo sistema de critica (critic.py) de resultado no modo consult, ele julga se o resultado e favoravel. Escreve codigo com LSTM e , os sistemas auxiliam se o resultado é favoravel. # Experimental
[33m3cbfaaa[m merge test
[33mcd614ad[m olDox222 : Alfa 65.00 : 2025.12.14.a - Brain - Sistema de inteligencia artificial em fase de experimentação para geração de codigo (AlfaGold). #Experimenteal
[33m3e58936[m olDox222 : Alfa 65.00 : 2025.12.14.a - Brain - Sistema de inteligencia artificial em fase de experimentação para geração de codigo (AlfaGold). #Experimenteal
[33m7bb0ec5[m olDox222 : Alfa 65.00 : 2025.12.14.a - Brain - Sistema de inteligencia artificial em fase de experimentação para geração de codigo (AlfaGold). #Experimenteal
[33m20dcd80[m olDox222 : Alfa 64.60 : 2025.12.11.a - Brain - Novo comando experimental de treino e uso de uma pequinissima rede neural, utiliza numpy. Ainda esta em dase experimental. o objetivo final é auxiliar o usuario com o codigo e resolução de problemas
[33m871deff[m olDox222 : Alfa 64.50 : 2025.12.10.d - webcheck, Scaffold - Suporte para nicegui. Risk - Aprimoramento da analise de gerenciamento de risco em projetos. Correção no install.py em andamento.
[33m74c146d[m olDox222 : Alfa 64.33 : 2025.12.10.c - Risk - Implementação do cálculo de risco baseado no Estado Atual do projeto, ignorando histórico irrelevante. #2
[33m597a442[m olDox222 : Alfa 64.23 : 2025.12.10.b - Risk - Implementação do Sistema de Gestão de Risco (Risk Management). calcula estabilidade e dívida técnica real. #1 prototipo
[33m15a342b[m olDox222 : Alfa 64.18 : 2025.12.10.a - Pedia - Adição dos volumes de Transição, Estratégia, Conhecimento e Glossário à Doxoadepédia.
[33m5b7aa20[m olDox222 : Alfa 64.15 : 2025.12.9.c - Health - O comando health agora usa ferramentas internas para análise estática e respeita o ambiente do usuário para cobertura, eliminando a injeção de dependências no requirements.txt de projetos terceiros.
[33m1232cd0[m olDox222 : Alfa 64.05 : 2025.12.09.b - check - refatoração inicial, do filter_and_inject_findings e tags. #1
[33md4ea330[m olDox222 : Alfa 64.00 : 2025.12.09.a - Security Suite Final - Implementação da arquitetura 'Batteries Included'. O Doxoade agora utiliza suas próprias ferramentas de segurança (Bandit/Safety) localizadas via heurística de path, permitindo auditar qualquer projeto sem poluir o ambiente alvo.
[33m53d23c7[m olDox222 : Alfa 63.81 : 2025.12.08.c - Run - run foi reparado e funciona localmente em projetos isolados corretamente.
[33m5c00254[m olDox222 : Alfa 63.80 : 2025.12.08.b - Flow - Hardening do Visualizador: Proteção contra crash em variáveis inescrutáveis (NumPy/Enum) e filtros de performance para bibliotecas.
[33mc07866c[m olDox222 : Alfa 63.70 : 2025.12.8.a - Security Hardening - Migração para SHA256 e sanitização de shell=True no doxoade maestro.
[33m61ab493[m olDox222 : Alfa 63.60 : 2025.12.15.h - Test Mapper - Ferramenta de mapeamento de cobertura lógica (Código vs Testes) e identificação de órfãos.
[33md1ca865[m olDox222 : Alfa 63.50 : 2025.12.07.d - Deepcheck - Aprimoramento e polimento MPoT.
[33mdcef0cd[m olDox222 : Alfa 63.55 : 2025.12.15.d - Deepcheck - Implementação de análise semântica de fluxo de dados (Data Flow Analysis), validação de contratos de IO e detecção de Dead Params.
[33mfe41022[m olDox222 : Alfa 63.45 : 2025.12.07.c - Search: Implementação completa do indexador persistente, busca semântica, fuzzy matching e análise de impacto integrada. #2 Funcional em teste
[33mf12a3a3[m olDox222 : Alfa 63.30 : 2025.12.07.b - Search: Comando para pesquisa em função, codigo, comentario e git. #1 Estado inicial - fundação
[33m5e84652[m olDox222 : Alfa 63.25 : 2025.12.07.a - Pedia: reparação dos problemas de exibição. Nova função timeline (chronos) para fazer historico de atividade do usuario.
[33m977b65d[m olDox222 : Alfa 63.10 : 2025.12.06.h - Lab AST V2 - Integração nativa com Git para detecção automática de mudanças estruturais (Wrap Try/Except) no workflow do usuário.
[33mb1b4088[m olDox222 : Alfa 63.10 : 2025.12.06.h - Lab AST V2 - Integração nativa com Git para detecção automática de mudanças estruturais (Wrap Try/Except) no workflow do usuário.
[33m83553c8[m Teste AST inicial
[33m377f009[m olDox222 : Alfa 63.00 : 2025.12.06.g - AST Lab - Prova de Conceito do aprendizado estrutural (WRAP TRY_EXCEPT) via de árvores sintáticas. #1
[33mc99273c[m olDox222 : Alfa 62.97 : 2025.12.06.f - genesis - Correção do fix. #3 em testes
[33mf7bb953[m olDox222 : Alfa 62.96 : 2025.12.06.e - genesis - Correção do fix. #2 em testes
[33m9462811[m Merge branch 'main' of https://github.com/olDox0/Doxoade
[33m4e31e37[m olDox222 : Alfa 62.95 : 2025.12.06.e - genesis - Correção do fix. #1 em testes
[33m1ac4998[m olDox222 : Alfa 62.95 : 2025.12.06.e - Pedia - Documentação dw politicas e o plano R0. Documetação em estado avançado
[33m6b4d2fb[m olDox222 : Alfa 62.90 : 2025.12.06.d - Pedia - Catalogação de conceitos via glossario, e incidentes com mais dados
[33mbbfbde9[m olDox222 : Alfa 62.86 : 2025.12.06.c - Pedia - Catalogação Histórica - Setembro á Novembro de 2025. Catalogação de incidentes e timeline
[33m98868dc[m olDox222 : Alfa 62.83 : 2025.12.06.b - Pedia - Aumento da cobertura da catalogação para o pedia - Infraestrutura e DevOps
[33m57296d7[m olDox222 : Alfa 62.80 : 2025.12.06.a - Pedia - Aumento da cobertura da catalogação para o pedia - Timeline, Protocolos e Sistema da Era genesis
[33m4bd639e[m olDox222 : Alfa 62.70 : 2025.12.05.d - Flow - Visualização e analise de execução e performace de programas, um alias de doxoade run --flow. correções de self-run. #5 Finalizado
[33m23de24a[m olDox222 : Alfa 62.60 : 2025.12.05.c - Genesis - Sonda XRef para integridade entre arquivos estabiliza shared_tools com lazy imports. Correção na exibição. #4 Finalizalçao
[33m19f9792[m olDox222 : Alfa 62.53 : 2025.12.05.b - Gênesis - Refatoração completa dos motores Learning e Fixer para arquitetura modular baseada em estratégias (MPoT Compliance). #3 funcional
[33m80e44bc[m olDox222 : Alfa 62.51 : 2025.12.05.a - Gênesis - Refatoração completa dos motores Learning e Fixer para arquitetura modular baseada em estratégias (MPoT Compliance). #2 funcional
[33mfa8c095[m olDox222 : Alfa 62.50 : 2025.12.05.a - Gênesis - Refatoração completa dos motores Learning e Fixer para arquitetura modular baseada em estratégias (MPoT Compliance). #1 Em teste
[33m35fee2a[m olDox222 : Alfa 62.50 : 2025.12.04.f - Impact Analysis V3 Final - Geração de gráficos Mermaid (-g) e métricas de estabilidade.
[33m92d6cea[m olDox222 : Alfa 62.30 : 2025.12.04.d - Impact Analysis V2 - Implementação de rastreamento profundo (-t), detecção de uso de funções e correção de heurística de Dead Code. #1 em testes
[33mc85f225[m olDox222 : Alfa 62.20 : 2025.12.04.c - UI Update - Renderizador Markdown com paleta 'High Contrast' (Colorama EX) para melhor legibilidade em terminais Windows/Termux.
[33m5f9bd0a[m olDox222 : Alfa 62.10 : 2025.12.04.b - Pedia - Documentação Híbrida (JSON/MD) com listagem responsiva e volumes técnicos.
[33me45e352[m olDox222 : Alfa 62.00 : 2025.12.04.a - Android Sync - Implementação de exportação/importação segura entre Termux e Android Storage.
[33m7ef7ecb[m olDox222 : Alfa 61.25 : 2025.12.03.s - Merge - Comando para gerenciar conflitos de merge, o usuario pode escolher resolver ou selecionar opções do doxoade merge. #2 finalização
[33m6689583[m olDox222 : Alfa 61.17 : 2025.12.03.o - Merge - Testamdo mudança no main #1
[33m9036f1e[m olDox222 : Alfa 61.12 : 2025.12.03.o - Ide - escolha de editores no termux #7 finalizando
[33m37e52cd[m olDox222 : Alfa 61.11 : 2025.12.03.n - Ide - escolha de editores no termux #6 finalizando
[33m6e89cce[m olDox222 : Alfa 61.10 : 2025.12.03.m - Ide - escolha de editores no termux #5 finalizando
[33m22eb0e9[m olDox222 : Alfa 61.07 : 2025.12.03.k - Ide - Comando para interface de programação para termux. #3 teste no termux
[33m1a2f834[m olDox222 : Alfa 61.01 : 2025.12.03.j - Ide - Comando para interface de programação para termux. #2 funcional no windows
[33m5088a30[m olDox222 : Alfa 61.00 : 2025.12.03.i - Ide - Comando para interface de programação para termux. #1 em fase de testes
[33m6ebd5ff[m olDox222 : Alfa 60.95 : 2025.12.02.h - Test System - Implementação do comando 'test' unificado e limpeza de testes legados (reset da suite).
[33m486aadc[m olDox222 : Alfa 60:90 : 2025.12.02.g - Run - Refatoração MPoT para o run e testes unitarios (Unit Tests)
[33m706e4d7[m olDox222 : Alfa 60.80 : 2025.12.02.f - Verilog - Novo comando para diagnostico de sintaxe usando (iverilog g2012 - SystemVerilog), falta implementação de funções de aprendizado com genesis, diagnosticos mais legiveis, diagnosticos focados num aspecto - #1 em fases de teste
[33m1e27b3b[m olDox222 : Alfa 60.70 : 2025.12.02.e - Lazarus - Implementação de Análise Forense (Smart Context) para comparação entre código quebrado e o estável antes do crash.
[33maa078bf[m olDox222 : Alfa 60.64 : 2025.12.02.d - Lazarus - Sistema de deadlock completo e funcional
[33m99d3596[m olDox222 : Alfa 60.62 : 2025.12.02.c - Lazarus - Corrigindo __init__. e preparando git para segundo teste. #2 Correção
[33m0a532e5[m olDox222 : Alfa 60.61 : 2025.12.02.b - Lazarus - Sistema de Deadlock e Diagnosticos Fatais que analisa e diagnostica o porque o sistema interno do doxoade quebrou. Wrapper anti crash. Rescue para analisar traceback do crash e exibir diagnostico via terceiros. Sistema póstume em arquivo json para Genesis aprender sobre o erro. O sistema sujere correção baseada no git de uma versão estavel. #1 Teste
[33m53f93cb[m olDox222 : Alfa 60.55 : 2025.12.02.a - Pedia - Restruturação para maior flexibilidade, e diferentes catalogos de informações
[33mc75c217[m olDox222 : Alfa 60.50 : 2025.12.01.h - Style - Novo comando que analisa o ptojeto baseado no the power of ten da nasa mas adaptado. - documentação interna para auxiliar desenvolvedores
[33m55716e2[m Merge branch 'main' of https://github.com/olDox0/Doxoade - Resolução de conflito Gênese V14 (Local)
[33ma4a6d33[m olDox222 : Alfa 60.46 : 2025.12.01.g - genesis - check agora com --clones para identicar funções duplicadas(dry), ele ignora @click.group() - #2 Funcionando
[33md9ccd5f[m olDox222 : Alfa 60.45 : 2025.12.01.e - genesis - check agora com --clones para identicar funções duplicadas(dry), ele ignora @click.group() - #1 Em Teste
[33m74c1acc[m olDox222 : Alfa 60.50 : 2025.11.30.e - Clone Probe Integrado e Check Refatorado
[33mfa8c4f4[m olDox222 : Alfa 60.40 : 2025.11.30.d - Maestro - novos comandos FIND_LINE_NUMBER e DELETE_BLOCK_TREE
[33m45faccf[m olDox222 : Alfa 60.32 : 2025.11.30.c - Limpeza do github
[33m8fc578e[m olDox222 : Alfa 60.31 : 2025.11.30.b - doxoade mestre - aprimoramento da programação dos arquivos de automação .dox, verbosos e novos comandos, manipulação de arquivos, fluxo de controle e suporte a batch
[33m986ec56[m olDox222 : Alfa 60.30 : 2025.11.30.a - doxoade mestre - aprimoramento da programação dos arquivos de automação .dox, verbosos e novos comandos, manipulação de arquivos, fluxo de controle e suporte a batch
[33m875cf4b[m olDox222 : Alfa 60.25 : 2025.11.29.a - Novo comando maestro para programar e automatizar atividades no doxoade com arquivo.dox, check por mais informações no pedia
[33m2271f7b[m olDox222 : Alfa 60.05 : 2025.11.28.e - doxoade pedia - Nova forma de pesquisa para comentarios. Corrigido - Agora o pedia ignoara os arquivos do ignore do pyproject.toml
[33me7de5a1[m olDox222 : Alfa 60.00 : 2025.11.28.d - doxoade pedia - Novo comando com conhecimento do doxoade embutido na forma de artigos num arquivo json.
[33m0a9f2dc[m olDox222 : Alfa 59.95 : 2025.11.28.c - sistema de noqa (No Quality Assurance). e sistema de notas para comentarios rastreaveis, indicadores para desenvolvedores.
[33meda174f[m olDox222 : Alfa 59.87 : 2025.11.28.b - telemetria temporal, para identificação do tempo de execução, medir tempo de execução.
[33m3642495[m olDox222 : Alfa 59.85 : 2025.11.28.a - Genesis - Agora detecta Code Smells, aprende correções a fins com o template flexivel, naturalmente.
[33m05d88f8[m olDox222 : Alfa 59.80 : 2025.11.27.a - Novo comando para modificação de arquivo via CLI, moddify, com funções add em linha individual e multi-linha, remove para remover linhas, replace para subtituir textos, show para exibir linha ou linhas.
[33mc63f6fe[m olDox222 : Alfa 59.65 : 2025.11.26.b - Genesis - aprendizado ocorre mesmo em runtime
[33m24b1ccb[m olDox222 : Alfa 59.65 : 2025.11.26.b - Genesis - aprendizado ocorre mesmo em runtime
[33mf659005[m olDox222 : Alfa 59.60 : 2025.11.26.a - Genesis - refatoração leve, Atualização em fixer.py, learning.py e check.py - hotfix no shared_tools - teste de aprendizado flexivel
[33mc67f015[m olDox222 : Alfa 59.51 : 2025.11.25.c - Genesis - refatoração leve no check para learning.py, funções de aprendizado movidos. Commit de teste de aprendizado
[33m5ef0813[m olDox222 : Alfa 59.40 : 2025.11.25.b - Run - Correção e simplificação do doxoade run, para funcionar com input e codigos simplorios
[33md1b5f1f[m olDox222 : Alfa 59.35 : 2025.11.25.a - setup-health - hotfix e correções no setup-health, corrigido a instalação essencial do pyflakes
[33med12f60[m olDox22 : Alfa 59.30 : 2025.11.24.b - Check - correção do check --fix, agora conserta os problemas identificados de forma não destrutiva, comenta as linhas e modificar-as mas sempre deixado a versão original comenda para fins de reversibilidade.
[33mcad3f6d[m olDox222 : Alfa 59.05 : 2025.11.24.a - Health - Hotfix do bug de Nonetype na chamada do pytest para testagem sem arquivos de teste
[33m1c078c8[m Alfa 59.00 : 2025.11.23.d - Debug - comando de debugagem, e --gen-test para fazer testes para pytest com mais dinamismo: em fase de testes. Run - --flow --internal para analise de visual trace profiler interno nos comandos do doxoade
[33m9568796[m Alfa 58.61 : 2025.11.23.c - Run - Nova função --flow para analise de gargalos e rastreio do funcionanmento de arquivos.pt : Correções minimas
[33m2e7bc5b[m olDox222 : Alfa 58.60 : 2025.11.23.b - Run - Nova função --flow para analise de gargalos e rastreio do funcionanmento de arquivos.pt : Base completa
[33m277181f[m olDox222 : Alfa 58.30 : 2025.11.23.a - Rewind - Novo comando para voltar arquivos no tempo com o git, para uma versão anterior do arquivo especificado
[33ma715d36[m olDox222 : Alfa 58.00 : 2025.11.22.l - Check - Atualizado check e run para identificar e catalogar problemas fatais, trace, back e afins
[33m7a51cac[m olDox222 : Alfa 57.70 : 2025.11.22.k - Genesis - Implementado nova função de abdução e indentificação do erro da falta de imports importantes
[33mb2a7527[m olDox22 : Alfa 57.20 : 2025.11.22.j - Correções - Novo instaler.sh para termux - #1 testagem
[33mbfa5a18[m Alfa 57.00 : 2025.11.22.i - Correções - Correção de entry_points e nomenclatura para termux - Teste
[33m323f6e9[m Alfa 56.81 : 2025.11.22.h - Genesis - Sistema de catalogagem, aprendendo e consolidando novos templates no check - 6# Consolidação
[33m8fdc96f[m Alfa 56.80 : 2025.11.22.g - Genesis - Sistema de catalogagem, aprendendo e consolidando novos templates no check - 5# Consolidação
[33mfa33a00[m Alfa 56.75 : 2025.11.22.f - Genesis - Sistema de catalogagem, aprendendo e consolidando novos templates - 4# Compreender Correções
[33mc5ad96a[m Alfa 56.75 : 2025.11.22.e - Genesis - Sistema de catalogagem, aprendendo e consolidando novos templates - 3# Compreender Erro
[33mcfb5b53[m olDox222 : Alfa 56.70 : 2025.11.22.a - Genesis - Sistema de catalogagem, adição de mais templates de aprendizado
[33m1570880[m olDox222 : Alfa 56.65 : 2025.11.21.ak - Genesis - Sistema de catalogagem, check e save estaveis
[33m9182f17[m olDox222 : Alfa 56.60 : 2025.11.21.aj - Genesis - Sistema de catalogagem, check cataloga questões, save aprende (algoritmo de raciocinio de indução) e salva-as no DB
[33m760cc8d[m olDox222 : Alfa 56.50 : 2025.11.21.ai - Genesis - Sistema de catalogagem agora baseado em template de inferencia - completo
[33m3968645[m olDox222 : Alfa 56.13 : 2025.11.21.ah - Genesis - Sistema de catalogagem agora baseado em template de inferencia - Novas correções de funções quebradas - #22 Aprendendo Correção
[33m98a85cd[m olDox222 : Alfa 56.13 : 2025.11.21.ag - Genesis - Sistema de catalogagem agora baseado em template de inferencia - Novas correções de funções quebradas, commit força do para testes - #21 Aprendendo Erro
[33m74c2af1[m olDox222 : Alfa 56.13 : 2025.11.21.ac - Genesis - Sistema de catalogagem agora baseado em template de inferencia - Novas correções de funções quebradas - #17 Aprendendo Erro
[33mb3d57a5[m olDox222 : Alfa 56.10 : 2025.11.21.ab - Genesis - Sistema de catalogagem agora baseado em template de inferencia - Novas correções de funções quebradas - #16 Aprendendo Correção
[33me4315d2[m olDox222 : Alfa 55.94 : 2025.11.21.z - Genesis - Sistema de catalogagem agora baseado em template de inferencia - correções de funções quebradas - #14 Aprendendo Correção
[33m60ebf6f[m olDox222 : Alfa 55.93 : 2025.11.21.x - Genesis - Sistema de catalogagem agora baseado em template de inferencia - correções de funções quebradas - #12 Aprendendo Reparo
[33mb3ed8bc[m olDox222 : Alfa 55.90 : 2025.11.21.t - Genesis - Sistema de catalogagem agora baseado em template de inferencia - Testando correções para o DB - #9 Aprendendo save
[33m7ea6440[m olDox222 : Alfa 55.86 : 2025.11.21.o - Genesis - Sistema de catalogagem agora baseado em template de inferencia - Testando Novas correções - #4 Testando Erro
[33m2bb938e[m olDox222 : Alfa 55.83 : 2025.11.21.n - Genesis - Sistema de catalogagem agora baseado em template de inferencia - Testando correções - #3 Testando Correção
[33mc9383b3[m olDox222 : Alfa 55.80 : 2025.11.21.l - Genesis - Sistema de catalogagem agora baseado em template de inferencia - Fazendo debugagem - #1 Testando Correção
[33mb534f06[m Alfa 55.73: 2025.11.21.j - Genesis - Sistema de catalogagem agora baseado em template de inferencia - #2 Testando Reparo
[33m46a1dab[m Alfa 55.70: 2025.11.21.i - Genesis - Sistema de catalogagem agora baseado em template de inferencia - #3 Testando Reparo
[33m36240b8[m olDox222 : Alfa 55.67: 2025.11.21.g - Genesis - Sistema de catalogagem agora baseado em template de inferencia - #2 Testando Erro
[33m57eadfb[m Alfa 55.65: 2025.11.21.f - Genesis - Sistema de catalogagem agora baseado em template de inferencia - #3 Testando Reparo
[33m99ea16d[m Alfa 55.60: 2025.11.21.c - Genesis - Sistema de catalogagem agora baseado em template de inferencia - #1 Testando Save
[33m04ce969[m Alfa 55.20: 2025.11.21 - doxoade history - Otimização do check no commit inteligente do save
[33m50de255[m Alfa 55.00: 2025.11.21 - doxoade history - Sistema de catalogagem (history) esta com base pronta
[33m2bf437a[m Alfa 54.2 : 2025.11.20 - Testagem de aprendizado no Sistema de catalogagem #3 - CORREÇÃO
[33md3bb207[m Alfa 53.9 : 2025.11.20 - Testagem de aprendizado no Sistema de catalogagem #3 - CORREÇÃO
[33m43c0e10[m Alfa 53.6 : 2025.11.20 - Testagem de aprendizado no Sistema de catalogagem #3 - CORREÇÃO
[33m2cdabb2[m Alfa 53.3 : 2025.11.20 - Testagem de aprendizado no Sistema de catalogagem #3 - REPARO
[33m4f62702[m Alfa 53.0 : 2025.11.20 - Testagem de aprendizado no Sistema de catalogagem #3 - Correção
[33m2bc51d2[m Alfa 53.0 : 2025.11.20 - Testagem de aprendizado no Sistema de catalogagem #3 - Correção
[33m68f2c57[m Alfa 52.5 : 2025.11.20 - Testagem de aprendizado no Sistema de catalogagem #2 - Erro
[33m0e6e4a0[m Alfa 52.48 : 2025.11.20 - Testagem de aprendizado no Sistema de catalogagem #3 - Correção
[33mf3b6dcf[m Alfa 52.46 : 2025.11.20 - Testagem de aprendizado no Sistema de catalogagem #3 - Correção
[33m5c22175[m Alfa 52.46 : 2025.11.19 - Testagem de aprendizado no Sistema de catalogagem #3
[33m94d360e[m Alfa 52.46 : 2025.11.19 - Testagem de aprendizado no Sistema de catalogagem #2
[33m8e4affd[m Alfa 52.46 : 2025.11.19 - Testagem de aprendizado no Sistema de catalogagem #2
[33mda7a8ae[m Alfa 52.43 : 2025.11.19 - Sistema basico de catalogagem de problemas e soluções
[33mf95f11f[m Alfa 52.4 : 2025.11.19 - doxoade history, Testagem das funções. #3 - Correção do Erro proposital
[33m0bf2381[m Alfa 52.2 : 2025.11.19 - doxoade history, Testagem das funções. #3 - Correção do Erro proposital
[33m827a096[m Alfa 52.0 : 2025.11.19 - doxoade history, Testagem das funções. #2 - Erro proposital
[33m0a95890[m Alfa 51.7 : 2025.11.19 - doxoade history, Testagem das funções. #3 - Correção do Erro proposital
[33m8c9e553[m Alfa 51.5 : 2025.11.19 - doxoade history, Testagem das funções. #3 - Correção do Erro proposital
[33m5b036ff[m Alfa 51.0 : 2025.11.19 - doxoade history, Testagem das funções. #3 - Correção do Erro proposital
[33meee3132[m Alfa 50.1 : 2025.11.19 - doxoade history, Testagem das funções. #1 - Save
[33mc60408f[m Alfa 50.05 : 2025.11.19 - doxoade history, Testagem das funções. #1 - Save
[33m5ce17e2[m Alfa 50.0 : 2025.11.19 - doxoade history, Testagem das funções. #1 - Save
[33m9c076cb[m Alfa 49.9 : 2025.11.19 - doxoade history, Testagem das funções. #1 - Save
[33m98d2621[m Alfa 49.8 : 2025.11.19 - doxoade history, Testagem das funções. #1 - Save
[33m1bb4f17[m Alfa 49.8 : 2025.11.19 - doxoade history, Testagem das funções. #1 - Save
[33mfda8492[m Alfa 49.6 : 2025.11.19 - doxoade history, Testagem das funções. #1 - Save
[33m7b62f91[m Alfa 49.4 : 2025.11.19 - doxoade history, Testagem das funções. #1 - Save
[33mec2d4d5[m Alfa 49.3 : 2025.11.19 - doxoade history, Testagem das funções. #2 - Erro proposital
[33mc8c724c[m Alfa 49.2 : 2025.11.19 - doxoade history, Testagem das funções. #1 - Save
[33m59908c7[m Alfa 48.9 : 2025.11.19 - doxoade history, db-query - Correção no save. #1 - Save
[33m06a20b0[m Alfa 48.73 : 2025.11.19 - doxoade history - Correção no save. #1 - Save
[33m1ae1432[m Alfa 48.65 : 2025.11.19 - doxoade history - Correção no save. #20
[33mabe57f1[m Alfa 48.64 : 2025.11.19 - doxoade history - Correção no save. #18
[33ma2865b7[m Alfa 48.61 : 2025.11.18 - doxoade history - Correção no save. #17
[33mdc507b2[m Alfa 48.57 : 2025.11.18 - doxoade history - Testando identificação de problemas. #12
[33m6213b66[m Alfa 48.56 : 2025.11.18 - doxoade history - Testando identificação de problemas. #11
[33m3d1cd9f[m Alfa 48.54 : 2025.11.18 - Testando funcionalidades para doxoade history para identificação e aprendizado com erros orientando ao git. #10
[33m1b1d3ea[m Alfa 48.50 : 2025.11.18 - Testando funcionalidades para doxoade history para identificação e aprendizado com erros orientando ao git. #7
[33m8e23ab5[m Alfa 48.45 : 2025.11.18 - Testando funcionalidades para doxoade history para identificação e aprendizado com erros orientando ao git. #5
[33m7afbd65[m Alfa 48.42 : 2025.11.18 - Testando funcionalidades para doxoade history para identificação e aprendizado com erros orientando ao git. #4
[33mf51c7f3[m Alfa 48.4 : 2025.11.18 - Testando funcionalidades para doxoade history para identificação e aprendizado com erros orientando ao git. #2
[33ma970faa[m Alfa 48.3 : 2025.11.18 - Testando funcionalidades para doxoade history para identificação e aprendizado com erros orientando ao git.
[33md8e1846[m Alfa 48.0 : 2025.11.18 - Testando Nova funcionalidades para doxoade history, check e save feram modificados. Aprimoramento do deeocheck, agora com --verbose, e aprimoramento do global-health. Novo comando para comparação entre arquivo, o doxoade mirror.
[33m6c85119[m Alfa 46.2 : 2025.11.16 - Comando doxoade venv-up para abrir terminal no venv pelo explorer, runer e terminal. Retrocesso nas função --trace do run para fazer função independente futura 'trace' para rastreio aovivo do funcionamento de programas
[33m2c3a082[m Alfa 46.0 : 2025.11.16 - Doxoade python, arquivos de instalação do python de forma independente, install.sh, install-python.bat e install-python.sh
[33m56cc3b2[m Alfa 45.7 : 2025.11.15 - Aprimoramento do  global-health. Correções no impact_analysis. !!Novo comando de instalação do python, base não finalizada e não independente!!
[33m98dff22[m Alfa 45.5 : 2025.11.15 - impact-analysis, Rastreio de dependencias de funções
[33m7e0878b[m Alfa 45.38 : 2025.11.15 - Correções nas dependecias e toml para android-termux #6
[33me2fc86e[m Alfa 45.37 : 2025.11.15 - Correções nas dependecias e toml para android-termux #5
[33m9692a2b[m Alfa 45.36 : 2025.11.15 - Correções nas dependecias e toml para android-termux #4
[33m2c274ec[m Alfa 45.35 : 2025.11.15 - Correções nas dependecias e toml #3
[33mefe91ec[m build: Ignora o diretório de cache do doxoade
[33med464ea[m Alfa 45.33 : 2025.11.15 - Correções de dependecias #2
[33m83965a2[m Alfa 45.32 : 2025.11.15 - Correções de dependecias
[33mf9a0a45[m Alfa 45.31 : 2025.11.15 - Correções no toml
[33m9935e7d[m Alfa 45.3 : 2025.11.15 - Correções no db, check, dashboard
[33m9bb6787[m Alfa 45.0 : 2025.11.14 - Diff compara commits direntes, Check refatorado
[33medce1cc[m Alfa 44.0 : 2025.11.13B - comparação do codigo commitado e atual
[33mc166fac[m Alfa 43.7 : 2025.11.13A - Snippet do codigo estavel para comparação com codigo erroneo
[33m1eebd55[m Alfa 43.4 - Sistema anti-regressão estabelecido
[33me9c8bb1[m feat: Adicionar fixtures de teste de regressão
[33m584ddf8[m Alfa 43 - Sistema anti-regressão basico
[33md0ce350[m Alfa 42.5 - Cobertura pytest, Implantação do Sapiens, Database, Dashboard, e Canone
[33maeafa91[m Alfa 41.2 - Correções e aprimoramento do Check, Self-test, Health, Rebuild e Global-health
[33md54317d[m Alfa 40.2 - Aumento da cobertura do pytest no doxoade
[33m36b5bab[m Alfa 40 - Correção do check, implementação do self-test
[33mecd9d42[m correções sobre as refatoração recente parte 1 - Alfa 39.8
[33m085ba79[m Alfa 39.7 - Correção do optimize, e check
[33mc5572be[m Correções no check, e shared tools - Alfa 39.5
[33m149dce5[m Correções em tutorial, clear e install - Alfa 39
[33m0e34007[m Instalação universal install.py parte 4 e correçoes
[33m10bf122[m Concluído Projeto Fênix com instalador universal e correções parte 2
[33m7d536cf[m Instalação universal install.py parte 3 e correçoes
[33mae627ff[m Instalação universal install.py parte 2 e correçoes
[33mfa90b62[m doxoade intelligence - 37.2 Alfa Revisado
[33m7db861d[m Atualizada a documentação README para a V2.0
[33m05d512d[m Atualizada a documentação README do doxoade
[33m6818054[m Atualizada a documentação README do doxoade
[33m061e7a5[m Pequena Correção no doctor - 35.81 Alfa Phoenix
[33m6488419[m Arquitetura final: Runner simples e remoção do check de ambiente
[33mcc6f7c7[m Estabilização do uso multiplataforma, e doctor - 35.8 Alfa Phoenix
[33ma306e10[m Finalizado Runner Inteligente com exceção para o Doctor
[33mdfe166a[m Runner Inteligente para portabilidade universal
[33m4bc9b6b[m script de instalaçãol para Linux
[33m4d1ab3d[m Correções no doctor
[33m1e6f28c[m Teste sob o save refatorado
[33m004f154[m Corrigido .gitignore parte 2
[33mdbfe6a1[m Corrigido .gitignore e restaurado o doxoade.bat
[33m01fece1[m Limpeza de arquivos ignorados
[33m1a529f3[m Teste: Commitando arquivo ignorado
[33mcb5b91f[m Estrutura completa do projeto com plugins e runner - 35.5 Alfa Phoenix
[33m6e574b3[m Avançando com a refatoração e correções - 35.5 Alfa Phoenix
[33mdda1e9c[m Avançando com a refatoração
[33m8d835bd[m Avanço da refatoração: Apicheck, Deep check... - Alfa 35
[33m9204496[m Refatoração do comando health e optimize - Alfa 33
[33m91c5ac1[m refatoração via modularização, e melhoramento do deepcheck
[33ma0ad23a[m 31.3 Alfa - Iniciando Refatoração
[33m7591e4f[m Alfa 30.2 - correção no run --trace
[33m3639e7f[m Alfa 30.1 - Nova função Doxoade optimize
[33m8058d11[m Alfa 26 - Correção e aprimoramento do run
[33ma5e4133[m Atualização do run, com modo gravaçao --trace
[33m078c1fc[m Novas funções kvcheck para arquivos .kv e Encoding para codificação de arquivos
[33m4dfd356[m Correção e aprimoramento do log, e guicheck
[33m8310034[m Correção e aprimoramento do log, e guicheck
[33m66656d7[m Atualização do guicheck para analise sob kivy
[33m7930956[m Correção do na função de ignorar pastas, do .doxoaderc
[33mfb2da6a[m fix: Corrige o .gitignore e adiciona o requirements.txt
[33ma085017[m Nova funcionalidade, deepcheck
[33mfac497b[m Aprimoramento do doxoade log
[33m2120cc8[m Correção e bugs no doxoade health
[33mdd3e9c6[m Doxoade Init teve automação aprimorado
[33m99d6817[m Atualização do README
[33m8565301[m Versão final do Dashboard e correções de bugs
[33md9c51e6[m Doxoade doctor - Diagnostico de ambiente
[33m6ecd679[m Atualização de correção e aprimoramento do doxoade health
[33m84a18f5[m doxoade tutorial atualizado com funções de aprendizado e gamificação
[33mb190d01[m tutorial aprimorado. pro-noob friendly
[33m979362a[m Guicheck aprimorado: Analise detalhadas e exatas
[33m05e0e55[m Correções no def run com relação ao doxoade auto e exibição
[33m70a4f61[m Atualização. doxoade tutorial, README, e --help
[33md6d3ee3[m Atualização. doxoade tutorial e afins
[33m2f34673[m Atualização. Adição do Git-New.
[33m3f1b463[m Correção do README
[33m00be7e2[m Atualização. Adição do Git-New.
[33mfe62c7e[m Teste
[33m4d09798[m Limpeza parte 3
[33m742e627[m Commit inicial: Repositório recriado com .gitignore forçado
[33mdd42796[m Commit inicial: Versão final e limpa do doxoade
