PC-A Amaranth



PC-B Bluebaby


(venv) C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade>doxoade lan-git pull --live

   [*] Fundição Alvo: gordian_test
   🛡️  [SOTÉRIA] Auditando 1 fontes...
      💉 Vacinando módulos...
      🛡️ Sotéria integrada — 3 fontes

   [*] Fundição Alvo: stress_test
   🛡️  [SOTÉRIA] Auditando 1 fontes...
      💉 Vacinando módulos...
      🛡️ Sotéria integrada — 3 fontes

   [*] Fundição Alvo: soteria_scribe_advance
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: vls_scanner
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: hermes_async_log
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: async_log
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: hermes_bridge_soteria
      ⚡ [BYPASS] Sotéria desativada.
      🐍 Python.h detectado — include: C:\Users\Victor Alexandre\AppData\Local\Programs\Python\Python312\Include
      🔗 Python lib: python312.lib
[HERMES-LOGGER] ✔ Logger assíncrono inicializado
[INFO] [0.241ms] Hermes Diagnostic hooks instalados
[INFO] [0.266ms] Hermes Async Logger inicializado
  ✔ [HERMES v2] Bridge C já compilado (Cache Hit).
Procurando o repositório na rede local...
Sincronizando com 'DESKTOP-SVKLRJ1' (192.168.18.52)...
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" branch --show-current
  ✔ [GIT-OK] (Exit 0)
Sincronizando com 'DESKTOP-SVKLRJ1' (192.168.18.52)...
  [RAMIFICAÇÃO] Branch de trabalho ativo: 'main'

--- [DIAGNÓSTICO FORENSE DE SINCRONIZAÇÃO] ---
  Diretório Alvo : C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade
  Host Remoto    : DESKTOP-SVKLRJ1 (192.168.18.52:9418)
  Transporte     : GIT_DAEMON
  Alvo de Sinc   : dox-live @ debebeb
  Mensagem       : [LIVE-MIRROR] Rascunho com 6 arquivo(s) modificado(s)
  Modo Live      : ATIVO (Espelhamento Direto de Rascunho)
----------------------------------------------

[STATUS AVALIADO] FAST_FORWARD: Atualização disponível: [debebeb] [LIVE-MIRROR] Rascunho com 6 arquivo(s) modificado(s)
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" rev-parse HEAD
  ✔ [GIT-OK] (Exit 0)
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" remote
  ✔ [GIT-OK] (Exit 0)
  [REMOTE] Atualizando URL do remote 'lan-peer' -> http://192.168.18.52:8080/doxoade
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" remote set-url lan-peer http://192.168.18.52:8080/doxoade
  ✔ [GIT-OK] (Exit 0)

[FETCH] Puxando objetos do branch 'dox-live' via LAN (http://192.168.18.52:8080/doxoade)...
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" fetch lan-peer dox-live
  ✔ [GIT-OK] (Exit 0)
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" branch --show-current
  ✔ [GIT-OK] (Exit 0)

  [LIVE] Recebendo rascunho em memória e preparando fusão...
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" branch -f dox-live-sync lan-peer/dox-live
  ✔ [GIT-OK] (Exit 0)
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" checkout main
  ✔ [GIT-OK] (Exit 0)
  [INFO] Incorporando alterações recebidas em 'main'...
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" merge dox-live-sync --no-edit --no-ff
  ✖ [GIT-FAIL] Exit Code: 1
    [STDOUT] Auto-merging doxoade/commands/lite_xl_systems/template/07_keymaps_and_help.lua
CONFLICT (content): Merge conflict in doxoade/commands/lite_xl_systems/template/07_keymaps_and_help.lua
Auto-merging doxoade/commands/lite_xl_systems/template/13_toolbar_doxoade.lua
CONFLICT (content): Merge conflict in doxoade/commands/lite_xl_systems/template/13_toolbar_doxoade.lua
Automatic merge failed; fix conflicts and then commit the result.

  ⚠ [DIVERGÊNCIA DETECTADA NO LIVE-SYNC]
  O rascunho do Host diverge do histórico atual de 'main'.
  🛡️ [AUTO-PROTEÇÃO] Abortando a fusão para evitar marcadores de conflito em arquivos de código...
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" merge --abort
  ✔ [GIT-OK] (Exit 0)
  ✔ Branch 'main' restaurado e 100% íntegro.

  💡 Para testar o rascunho do Host em isolamento sem afetar o 'main':
     git checkout dox-live-sync
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" branch --show-current
  ✔ [GIT-OK] (Exit 0)

  ✔ [BRANCH ATIVO] Seu repositório está no branch: 'main'.

(venv) C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade>doxoade doxly setup -f

   [*] Fundição Alvo: gordian_test
   🛡️  [SOTÉRIA] Auditando 1 fontes...
      💉 Vacinando módulos...
      🛡️ Sotéria integrada — 3 fontes

   [*] Fundição Alvo: stress_test
   🛡️  [SOTÉRIA] Auditando 1 fontes...
      💉 Vacinando módulos...
      🛡️ Sotéria integrada — 3 fontes

   [*] Fundição Alvo: soteria_scribe_advance
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: vls_scanner
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: hermes_async_log
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: async_log
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: hermes_bridge_soteria
      ⚡ [BYPASS] Sotéria desativada.
      🐍 Python.h detectado — include: C:\Users\Victor Alexandre\AppData\Local\Programs\Python\Python312\Include
      🔗 Python lib: python312.lib
[HERMES-LOGGER] ✔ Logger assíncrono inicializado
[INFO] [0.262ms] Hermes Diagnostic hooks instalados
[INFO] [0.288ms] Hermes Async Logger inicializado
  ✔ [HERMES v2] Bridge C já compilado (Cache Hit).
  Templates compilados (37 templates + 0 probes): C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade\doxoade\commands\lite_xl_systems\template

✔ Configuração Modular montada com sucesso em: Configuração soberana instalada e validada em C:\Users\Victor Alexandre\.config\lite-xl\init.lua
  Templates compilados (37 módulos): C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade\doxoade\commands\lite_xl_systems\template
  Backup salvo em: Configuração soberana instalada e validada em C:\Users\Victor Alexandre\.config\lite-xl\init.lua.bak

🚀 Recursos ativos:
  • Matriz de abas coloridas e texto em branco
  • Highlight de seleção global entre splits
  • Fundo de cor para #HEX e {R, G, B}

💡 Execute 'doxoade lite-xl restart' para iniciar limpo.


(venv) C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade>doxoade lan-git pull --force

   [*] Fundição Alvo: gordian_test
   🛡️  [SOTÉRIA] Auditando 1 fontes...
      💉 Vacinando módulos...
      🛡️ Sotéria integrada — 3 fontes

   [*] Fundição Alvo: stress_test
   🛡️  [SOTÉRIA] Auditando 1 fontes...
      💉 Vacinando módulos...
      🛡️ Sotéria integrada — 3 fontes

   [*] Fundição Alvo: soteria_scribe_advance
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: vls_scanner
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: hermes_async_log
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: async_log
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: hermes_bridge_soteria
      ⚡ [BYPASS] Sotéria desativada.
      🐍 Python.h detectado — include: C:\Users\Victor Alexandre\AppData\Local\Programs\Python\Python312\Include
      🔗 Python lib: python312.lib
[HERMES-LOGGER] ✔ Logger assíncrono inicializado
[INFO]  ✔ [HERMES v2] Bridge C já compilado (Cache Hit).
 [1.215ms] Hermes Diagnostic hooks instalados
[INFO] [1.246ms] Hermes Async Logger inicializado
Procurando o repositório na rede local...
Sincronizando com 'DESKTOP-SVKLRJ1' (192.168.18.52)...
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" branch --show-current
  ✔ [GIT-OK] (Exit 0)
Sincronizando com 'DESKTOP-SVKLRJ1' (192.168.18.52)...
  [RAMIFICAÇÃO] Branch de trabalho ativo: 'main'

--- [DIAGNÓSTICO FORENSE DE SINCRONIZAÇÃO] ---
  Diretório Alvo : C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade
  Host Remoto    : DESKTOP-SVKLRJ1 (192.168.18.52:9418)
  Transporte     : GIT_DAEMON
  Alvo de Sinc   : dox-live @ 3ed9039
  Mensagem       : [LIVE-MIRROR] Rascunho com 6 arquivo(s) modificado(s)
  Modo Live      : ATIVO (Espelhamento Direto de Rascunho)
----------------------------------------------

[STATUS AVALIADO] FAST_FORWARD: Atualização disponível: [3ed9039] [LIVE-MIRROR] Rascunho com 6 arquivo(s) modificado(s)
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" rev-parse HEAD
  ✔ [GIT-OK] (Exit 0)
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" remote
  ✔ [GIT-OK] (Exit 0)
  [REMOTE] Atualizando URL do remote 'lan-peer' -> http://192.168.18.52:8080/doxoade
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" remote set-url lan-peer http://192.168.18.52:8080/doxoade
  ✔ [GIT-OK] (Exit 0)

[FETCH] Puxando objetos do branch 'dox-live' via LAN (http://192.168.18.52:8080/doxoade)...
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" fetch lan-peer dox-live
  ✔ [GIT-OK] (Exit 0)
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" branch --show-current
  ✔ [GIT-OK] (Exit 0)
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" checkout main
  ✔ [GIT-OK] (Exit 0)

✔ [SUCESSO] Rascunho de rede recebido em 'lan-peer/dox-live'. Seu branch ativo 'main' permanece protegido.
  ✔ [BRANCH] Você está no branch original: 'main'.

(venv) C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade>doxoade doxly setup -f

   [*] Fundição Alvo: gordian_test
   🛡️  [SOTÉRIA] Auditando 1 fontes...
      💉 Vacinando módulos...
      🛡️ Sotéria integrada — 3 fontes

   [*] Fundição Alvo: stress_test
   🛡️  [SOTÉRIA] Auditando 1 fontes...
      💉 Vacinando módulos...
      🛡️ Sotéria integrada — 3 fontes

   [*] Fundição Alvo: soteria_scribe_advance
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: vls_scanner
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: hermes_async_log
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: async_log
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: hermes_bridge_soteria
      ⚡ [BYPASS] Sotéria desativada.
      🐍 Python.h detectado — include: C:\Users\Victor Alexandre\AppData\Local\Programs\Python\Python312\Include
      🔗 Python lib: python312.lib
[HERMES-LOGGER] ✔ Logger assíncrono inicializado
[INFO] [0.810ms] Hermes Diagnostic hooks instalados
[INFO] [0.839ms] Hermes Async Logger inicializado
  ✔ [HERMES v2] Bridge C já compilado (Cache Hit).
  Templates compilados (37 templates + 0 probes): C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade\doxoade\commands\lite_xl_systems\template

✔ Configuração Modular montada com sucesso em: Configuração soberana instalada e validada em C:\Users\Victor Alexandre\.config\lite-xl\init.lua
  Templates compilados (37 módulos): C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade\doxoade\commands\lite_xl_systems\template
  Backup salvo em: Configuração soberana instalada e validada em C:\Users\Victor Alexandre\.config\lite-xl\init.lua.bak

🚀 Recursos ativos:
  • Matriz de abas coloridas e texto em branco
  • Highlight de seleção global entre splits
  • Fundo de cor para #HEX e {R, G, B}

💡 Execute 'doxoade lite-xl restart' para iniciar limpo.


(venv) C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade>doxoade doxly log

   [*] Fundição Alvo: gordian_test
   🛡️  [SOTÉRIA] Auditando 1 fontes...
      💉 Vacinando módulos...
      🛡️ Sotéria integrada — 3 fontes

   [*] Fundição Alvo: stress_test
   🛡️  [SOTÉRIA] Auditando 1 fontes...
      💉 Vacinando módulos...
      🛡️ Sotéria integrada — 3 fontes

   [*] Fundição Alvo: soteria_scribe_advance
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: vls_scanner
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: hermes_async_log
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: async_log
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: hermes_bridge_soteria
      ⚡ [BYPASS] Sotéria desativada.
      🐍 Python.h detectado — include: C:\Users\Victor Alexandre\AppData\Local\Programs\Python\Python312\Include
      🔗 Python lib: python312.lib
[HERMES-LOGGER] ✔ Logger assíncrono inicializado
[INFO] [0.971ms] Hermes Diagnostic hooks instalados
[INFO] [1.006ms] Hermes Async Logger inicializado
  ✔ [HERMES v2] Bridge C já compilado (Cache Hit).

📜 DOXLY LOG VIEWER — MODO [PRODUCTION]
  Diretório: C:\Users\Victor Alexandre\.config\lite-xl
Exibindo as últimas 40 linha(s):

  [15:58:17] [CMD] ⚡ Disparado: 'doc:set-cursor'
  [15:58:19] [CMD] ⚡ Disparado: 'doxoade:note-shared-menu'
  [15:58:19] [CMD] ⚡ Disparado: 'doxoade:note-shared-menu'
  [15:59:25] HOOKS_INIT: Hooks forenses ativos com I/O em buffer (Zero-Freeze).
  [15:59:25] [BOOT] === SOVEREIGN BOOT OK ===
  [15:59:25] [INFO] 👻 [PHANTO_CRISIS] Core V2.1 Strict-Safe inicializado.
  [15:59:25] [INFO] 💾 [HADES LOCK] Auto-save de sessão ativo (on-quit + 30s + anti-loop).
  [15:59:25] [INFO] 💾 [HADES LOCK] Auto-save de sessão ativo (on-quit + 15s + debounced).
  [15:59:25] [INFO] 🚀 [03b] MOTOR NOTEPAD++ V5 (cor por todo o bloco + resolver autônomo).
  [15:59:25] [INFO] 🦅 [CHRONOS V3] Telemetria temporal e Ring Buffer de 120s ativos.
  [15:59:25] [INFO] === SOVEREIGN BOOT OK ===
  [15:59:25] [INFO] 🏛️ [16] Open Editors Dock Engine registrado e pronto.
  [15:59:25] [INFO] 🌙 [KHONSU V2] Governador Adaptativo de Frame ativo (Pilar 2).
  [15:59:25] [INFO] 🟢 [DOXOADE] Docstrings Python injetadas com sucesso!
  [15:59:25] [INFO] Opening project "doxoade" from directory C:\Users\Victor Alexandre\Documents\doxoade_proj
  [15:59:26] [INFO] 👻 [PHANTO_CRISIS] Core V2.0 armado. Isolamento atômico ativo.
  [15:59:26] HOOKS_INIT: Hooks forenses ativos com I/O em buffer (Zero-Freeze).
  [15:59:26] [BOOT] === SOVEREIGN BOOT OK ===
  [15:59:26] [INFO] 👻 [PHANTO_CRISIS] Core V2.1 Strict-Safe inicializado.
  [15:59:26] [INFO] 💾 [HADES LOCK] Auto-save de sessão ativo (on-quit + 30s + anti-loop).
  [15:59:26] [INFO] 💾 [HADES LOCK] Auto-save de sessão ativo (on-quit + 15s + debounced).
  [15:59:26] [INFO] 🦅 [CHRONOS V3] Telemetria temporal e Ring Buffer de 120s ativos.
  [15:59:26] [INFO] === SOVEREIGN BOOT OK ===
  [15:59:26] [INFO] 🏛️ [16] Open Editors Dock Engine registrado e pronto.
  [15:59:26] [INFO] 🌙 [KHONSU V2] Governador Adaptativo de Frame ativo (Pilar 2).
  [15:59:26] [INFO] ✔ Sessão Soberana restaurada sem duplicações.
  [15:59:26] [INFO] ✔ Sessão Soberana restaurada sem duplicações.
  [15:59:26] [INFO] 👻 [PHANTO_CRISIS] Core V2.1 Strict-Safe inicializado.
  [15:59:26] [INFO] 💾 [HADES LOCK] Auto-save de sessão ativo (on-quit + 30s + anti-loop).
  [15:59:26] [INFO] 💾 [HADES LOCK] Auto-save de sessão ativo (on-quit + 15s + debounced).
  [15:59:26] [INFO] 🦅 [CHRONOS V3] Telemetria temporal e Ring Buffer de 120s ativos.
  [15:59:26] [INFO] === SOVEREIGN BOOT OK ===
  [15:59:26] [INFO] 🏛️ [16] Open Editors Dock Engine registrado e pronto.
  [15:59:26] [INFO] 🌙 [KHONSU V2] Governador Adaptativo de Frame ativo (Pilar 2).
  [15:59:26] [INFO] ✔ Sessão Soberana restaurada sem duplicações.
  [15:59:26] [INFO] ✔ Sessão Soberana restaurada sem duplicações.
  [15:59:26] [INFO] 🟢 [DOXOADE] Syntax Python sobrescrito com docstrings verdes!
  [15:59:35] [CMD] ⚡ Disparado: 'doxoade:note-shared-menu'
  [15:59:26] [INFO] 🟢 [DOXOADE] Syntax Python sobrescrito com docstrings verdes!
  [15:59:35] [CMD] ⚡ Disparado: 'doxoade:note-shared-menu'


(venv) C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade>:: de problema de too many synbols, não fui infromado muito bem
(venv) C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade>:: por alguma razão o shared não funciona aqui.::
(venv) C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade>
(venv) C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade>:: push do notes não foi enviado, não chegou aqui
(venv) C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade>doxoade lan-git note --daemon

   [*] Fundição Alvo: gordian_test
   🛡️  [SOTÉRIA] Auditando 1 fontes...
      💉 Vacinando módulos...
      🛡️ Sotéria integrada — 3 fontes

   [*] Fundição Alvo: stress_test
   🛡️  [SOTÉRIA] Auditando 1 fontes...
      💉 Vacinando módulos...
      🛡️ Sotéria integrada — 3 fontes

   [*] Fundição Alvo: soteria_scribe_advance
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: vls_scanner
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: hermes_async_log
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: async_log
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: hermes_bridge_soteria
      ⚡ [BYPASS] Sotéria desativada.
      🐍 Python.h detectado — include: C:\Users\Victor Alexandre\AppData\Local\Programs\Python\Python312\Include
      🔗 Python lib: python312.lib
[HERMES-LOGGER] ✔ Logger assíncrono inicializado
[INFO] [0.320ms] Hermes Diagnostic hooks instalados
[INFO] [0.379ms] Hermes Async Logger inicializado
  ✔ [HERMES v2] Bridge C já compilado (Cache Hit).

                                           [SYSTEM CRASH DETECTED]                                      

______________________________________________________________________________________________________________
                                             [RELATÓRIO SOB ERRO]                                       

  🆔 ID EVENTO   : 611368D2             📅 HORÁRIO : 2026-09-20 16:09:57
  🚀 INVOCAÇÃO   : doxoade              🚪 EXIT CODE : 1

  ■ CAUSA RAIZ (Necropsia de Sistema):
    STATUS : Símbolo Indefinido
    LAUDO  : Uso de variável ou função que não existe. (NameError: name 'Path' is not defined)

  ■ CENA DO CRIME (Triangulação de Código):
    ALVO FONTE  : cli_lan_git.py | COORDENADA: C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade\doxoade\commands\lan_git\cli_lan_git.py:677
         675 |
         676 | # 🌍 Caminho Global Canônico: ~/.doxoade/shared_notes.md
     >>  677 | home = Path.home()
         678 | global_dir = home / ".doxoade"
         679 | global_dir.mkdir(parents=True, exist_ok=True)

  ■ CADEIA DE ENVOLVIMENTO (Anatomia da Queda):
    [0] [PY] ↳ cmd_note                  (cli_lan_git.py:677)
         675 |
         676 | # 🌍 Caminho Global Canônico: ~/.doxoade/shared_notes.md
     >>  677 | home = Path.home()
         678 | global_dir = home / ".doxoade"
         679 | global_dir.mkdir(parents=True, exist_ok=True)

______________________________________________________________________________________________________________
                                           [OPÇÕES DE INTERVENÇÃO]                                      


  1.  [GIT]  Reverter cli_lan_git.py                      2.  [EDIT] Abrir no Doxly (Lite XL) Linha 677
  3.  [INFO] Ver logs brutos                              4.  [DEBUG] Diagnóstico Pipeline
  5.  [IO]    Analisar Dados e Memória                    6.  [CODE]  Console Interativo
  7.  [HORUS] Ver Timeline NSR (Shadow)                   0.  [EXIT] Encerrar sessão
  8.  [FIX]  Dry-Run da Correção (Anúbis)

  Sua decisão (ex: 34): 3

______________________________________________________________________________________________________________

  ■ [BRUTE LOG] Soteria Engine:


--- [ INÍCIO DO LOG BRUTO ] ---
Traceback (most recent call last):
  File "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade\doxoade\commands\lan_git\cli_lan_git.py", line 677, in cmd_note
    home = Path.home()
           ^^^^
NameError: name 'Path' is not defined

--- [ FIM DO LOG ] ---

______________________________________________________________________________________________________________

(venv) C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade>doxoade lan-git pull --force

   [*] Fundição Alvo: gordian_test
   🛡️  [SOTÉRIA] Auditando 1 fontes...
      💉 Vacinando módulos...
      🛡️ Sotéria integrada — 3 fontes

   [*] Fundição Alvo: stress_test
   🛡️  [SOTÉRIA] Auditando 1 fontes...
      💉 Vacinando módulos...
      🛡️ Sotéria integrada — 3 fontes

   [*] Fundição Alvo: soteria_scribe_advance
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: vls_scanner
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: hermes_async_log
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: async_log
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: hermes_bridge_soteria
      ⚡ [BYPASS] Sotéria desativada.
      🐍 Python.h detectado — include: C:\Users\Victor Alexandre\AppData\Local\Programs\Python\Python312\Include
      🔗 Python lib: python312.lib
[HERMES-LOGGER] ✔ Logger assíncrono inicializado
[INFO] [0.276ms] Hermes Diagnostic hooks instalados
  ✔ [HERMES v2] Bridge C já compilado (Cache Hit).
[INFO] [0.322ms] Hermes Async Logger inicializado
Procurando o repositório na rede local...
Sincronizando com 'DESKTOP-SVKLRJ1' (192.168.18.52)...
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" branch --show-current
  ✔ [GIT-OK] (Exit 0)
Sincronizando com 'DESKTOP-SVKLRJ1' (192.168.18.52)...
  [RAMIFICAÇÃO] Branch de trabalho ativo: 'main'

--- [DIAGNÓSTICO FORENSE DE SINCRONIZAÇÃO] ---
  Diretório Alvo : C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade
  Host Remoto    : DESKTOP-SVKLRJ1 (192.168.18.52:9418)
  Transporte     : GIT_DAEMON
  Alvo de Sinc   : dox-live @ 691b16d
  Mensagem       : [LIVE-MIRROR] Rascunho com 6 arquivo(s) modificado(s)
  Modo Live      : ATIVO (Espelhamento Direto de Rascunho)
----------------------------------------------

[STATUS AVALIADO] FAST_FORWARD: Atualização disponível: [691b16d] [LIVE-MIRROR] Rascunho com 6 arquivo(s) modificado(s)
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" rev-parse HEAD
  ✔ [GIT-OK] (Exit 0)
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" remote
  ✔ [GIT-OK] (Exit 0)
  [REMOTE] Atualizando URL do remote 'lan-peer' -> http://192.168.18.52:8080/doxoade
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" remote set-url lan-peer http://192.168.18.52:8080/doxoade
  ✔ [GIT-OK] (Exit 0)

[FETCH] Puxando objetos do branch 'dox-live' via LAN (http://192.168.18.52:8080/doxoade)...
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" fetch lan-peer dox-live
  ✔ [GIT-OK] (Exit 0)
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" branch --show-current
  ✔ [GIT-OK] (Exit 0)
  [GIT-EXEC] git -C "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade" checkout main
  ✔ [GIT-OK] (Exit 0)

✔ [SUCESSO] Rascunho de rede recebido em 'lan-peer/dox-live'. Seu branch ativo 'main' permanece protegido.
  ✔ [BRANCH] Você está no branch original: 'main'.

(venv) C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade>doxoade lan-git note --daemon

   [*] Fundição Alvo: gordian_test
   🛡️  [SOTÉRIA] Auditando 1 fontes...
      💉 Vacinando módulos...
      🛡️ Sotéria integrada — 3 fontes

   [*] Fundição Alvo: stress_test
   🛡️  [SOTÉRIA] Auditando 1 fontes...
      💉 Vacinando módulos...
      🛡️ Sotéria integrada — 3 fontes

   [*] Fundição Alvo: soteria_scribe_advance
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: vls_scanner
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: hermes_async_log
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: async_log
      ⚡ [BYPASS] Sotéria desativada.

   [*] Fundição Alvo: hermes_bridge_soteria
      ⚡ [BYPASS] Sotéria desativada.
      🐍 Python.h detectado — include: C:\Users\Victor Alexandre\AppData\Local\Programs\Python\Python312\Include
      🔗 Python lib: python312.lib
[HERMES-LOGGER] ✔ Logger assíncrono inicializado
[INFO] [0.272ms] Hermes Diagnostic hooks instalados
[INFO] [0.318ms] Hermes Async Logger inicializado
  ✔ [HERMES v2] Bridge C já compilado (Cache Hit).

                                           [SYSTEM CRASH DETECTED]                                      

______________________________________________________________________________________________________________
                                             [RELATÓRIO SOB ERRO]                                       

  🆔 ID EVENTO   : 611368D2             📅 HORÁRIO : 2026-09-20 16:12:12
  🚀 INVOCAÇÃO   : doxoade              🚪 EXIT CODE : 1

  ■ CAUSA RAIZ (Necropsia de Sistema):
    STATUS : Símbolo Indefinido
    LAUDO  : Uso de variável ou função que não existe. (NameError: name 'Path' is not defined)

  ■ CENA DO CRIME (Triangulação de Código):
    ALVO FONTE  : cli_lan_git.py | COORDENADA: C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade\doxoade\commands\lan_git\cli_lan_git.py:677
         675 |
         676 | # 🌍 Caminho Global Canônico: ~/.doxoade/shared_notes.md
     >>  677 | home = Path.home()
         678 | global_dir = home / ".doxoade"
         679 | global_dir.mkdir(parents=True, exist_ok=True)

  ■ CADEIA DE ENVOLVIMENTO (Anatomia da Queda):
    [0] [PY] ↳ cmd_note                  (cli_lan_git.py:677)
         675 |
         676 | # 🌍 Caminho Global Canônico: ~/.doxoade/shared_notes.md
     >>  677 | home = Path.home()
         678 | global_dir = home / ".doxoade"
         679 | global_dir.mkdir(parents=True, exist_ok=True)

______________________________________________________________________________________________________________
                                           [OPÇÕES DE INTERVENÇÃO]                                      


  1.  [GIT]  Reverter cli_lan_git.py                      2.  [EDIT] Abrir no Doxly (Lite XL) Linha 677
  3.  [INFO] Ver logs brutos                              4.  [DEBUG] Diagnóstico Pipeline
  5.  [IO]    Analisar Dados e Memória                    6.  [CODE]  Console Interativo
  7.  [HORUS] Ver Timeline NSR (Shadow)                   0.  [EXIT] Encerrar sessão
  8.  [FIX]  Dry-Run da Correção (Anúbis)

  Sua decisão (ex: 34): 3

______________________________________________________________________________________________________________

  ■ [BRUTE LOG] Soteria Engine:


--- [ INÍCIO DO LOG BRUTO ] ---
Traceback (most recent call last):
  File "C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade\doxoade\commands\lan_git\cli_lan_git.py", line 677, in cmd_note
    home = Path.home()
           ^^^^
NameError: name 'Path' is not defined

--- [ FIM DO LOG ] ---

______________________________________________________________________________________________________________

(venv) C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade>:: isso confirma que a sincronização não esta sincronizando corretamente, porque eu corrigi este problema
(venv) C:\Users\Victor Alexandre\Documents\doxoade_proj\doxoade>