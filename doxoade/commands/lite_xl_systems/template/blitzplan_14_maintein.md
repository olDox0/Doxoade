O relatório de **`leap_sys`** no `Projeto SysUtils` comprova que a reorganização foi concluída com sucesso: todos os 10 arquivos agora utilizam os caminhos canônicos `leap_sys.leap_engine` e `leap_sys.leap_platform.leap_windows`, sem dependências residuais da pasta pai.

Seguindo o padrão dos seus documentos de engenharia (**ProDeNov 1.2.1** e **PASC-6.1**), estruturamos o **Blitzplan de Integração do Sistema de Notas (DoxNotes)** para garantir que o acesso às suas anotações seja instantâneo, resiliente e **com tolerância zero a falhas ou perda de dados**.

---

# 📜 BLITZPLAN — DOXNOTES: INTEGRAÇÃO SOBERANA DE NOTAS NA IDE (V22.0)
**Módulo Alvo:** `doxoade/commands/lite_xl_systems/template/14_doxnote_panel.lua`  
**Armazenamento Conectado:** `.doxoade/note/*.md` e `.doxoade/note/.pote.md`  
**Protocolo:** ProDeNov 1.2.1 | PASC-6.1 (Zero-Freeze & Single-Thread Safe)  
**Panteões Mobilizados:** Hades (Persistência), Hermes (Sincronia), Apolo (UX/Atalhos) e Ma'at (Integridade de Dados)  
**Teto por Arquivo:** `< 50 KB`

---

## 1. Contexto e Diagnóstico Profundo (W5 / 5 Perguntas)

* **O quê (What):**  
  Integrar o ecossistema de anotações do Doxoade diretamente no Lite XL / Doxly, fornecendo:
  1. **Seletor Rápido de Notas (`Alt+N`):** Paleta fuzzy que lista todas as notas `.md` existentes e permite criar novas notas instantaneamente se o nome não existir.
  2. **O Pote Scratchpad (`Alt+P`):** Split retrátil à direita com o arquivo `.pote.md` (rascunho rápido, auto-save contínuo).
  3. **Visão Consolidada de Agenda (`Alt+A`):** Buffer virtual dinâmico agrupando tarefas vencidas (`[!]`), de hoje (`[*]`) e futuras (`[>]`), mantendo estrita paridade com a sintaxe do `agenda.py` (`[ ] YYYY-MM-DD #id Descrição`).
  4. **Sincronização Não-Bloqueante com Ferramentas Externas:** Recarga automática caso a nota seja alterada fora da IDE (via `doxoade note` no terminal ou `SoftClub Notes` em GUI).
* **Quem (Who):** O desenvolvedor, precisando consultar requisitos, tarefas pendentes e documentações de arquitetura enquanto codifica, sem alternar de janela.
* **Onde (Where):**  
  * `doxoade/commands/lite_xl_systems/template/14_doxnote_panel.lua` (Template modular da IDE).
  * Repositório de notas: `.doxoade/note/*.md` e `.doxoade/note/.pote.md`.
* **Quando (When):** Em runtime contínuo, acionado por atalhos globais rápidos de 1 toque (`Alt+N`, `Alt+P`, `Alt+A`).
* **Por quê (Why):** Evitar *context switching* para o terminal ou editores externos para checar notas essenciais.
* **Origem & Consequências:** A fragmentação anterior exigia abrir outro terminal para rodar `doxoade note`. A integração nativa transforma a IDE em um centro unificado de código e documentação.

---

## 2. Taxonomia de Falhas & Salvaguardas ("Para Não Ter Falhas")

Para blindar o sistema contra travamentos de interface, deadlocks ou corrupção de arquivos:

| Vetor de Risco | Causa Potencial | Salvaguarda / Mitigação Ativa |
| :--- | :--- | :--- |
| **`FAIL-NO-DIR`** | `.doxoade/note/` inexistente no projeto alvo | Criação atômica via `system.mkdir` no frame zero de invocação com fallback para a raiz. |
| **`FAIL-SPLIT-COLLAPSE`** | Nó de split à direita ocupado ou fechado | `get_or_create_note_split()` inspeciona o layout da árvore do `core.root_view` e aloca um split lateral de 35% sem deformar o editor principal. |
| **`FAIL-WRITE-CORRUPT`** | Queda abrupta da IDE durante escrita | Escrita atômica segura via arquivo temporário `.tmp_{pid}` + replace no Lua, mantendo o padrão Ma'at. |
| **`FAIL-EXT-CONFLICT`** | Edição concorrente via terminal (`note_cmd.py`) | Verificação de `st_mtime` antes de salvar: se o arquivo foi alterado fora, a IDE recarrega ou solicita confirmação antes de sobrescrever. |
| **`FAIL-TASK-SYNTAX`** | Digitação de tarefa sem ID ou formato inválido | Geração automática de ID alfanumérico único de 5 dígitos (`#a1b2c`) ao salvar uma nova linha que comece com data. |

---

## 3. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Fast-Path Nativo em Lua sem Processos Filhos)
1. **Zero IPC / Zero Latência:**  
   Como todas as notas já são Markdown puro no disco, o Lite XL lê e grava diretamente nos arquivos usando a API nativa `core.open_doc(path)` e `doc:save()`. Não há spawn de processos Python no hotpath de edição.
2. **Navegação Ergonômica:**
   * **`Alt+N` (Seletor / Criador de Notas):**
     * Abre a `core.command_view`.
     * Digitar lista as notas existentes com fuzzy match.
     * Digitar um nome novo e teclar `Enter` cria `nome.md` com cabeçalho padrão e abre no split lateral.
   * **`Alt+P` (O Pote / Scratchpad):**
     * Alterna (toggle) a visibilidade do painel à direita contendo `.pote.md`.
     * Se o painel já estiver aberto e focado, fecha ou devolve o foco para o código principal.
   * **`Alt+A` (Agenda do Dia):**
     * Gera um buffer virtual em memória (tipo `[Agenda Doxoade]`) com as tarefas agrupadas e links de salto direto: teclar `Enter` em uma tarefa salta para o arquivo e linha exatos da nota onde a tarefa foi escrita.

### 🔹 Plano B (Fallback — Abertura em Aba Comum)
* Caso o usuário esteja em um monitor pequeno ou com splits verticais esgotados onde criar mais uma coluna quebraria a geometria do editor: o comando detecta a largura disponível (`view.size.x < 800`) e abre a nota como uma aba comum no nó ativo em vez de dividir a tela.

### 🔹 Plano C (Contingência & Fuga Externa)
* Se houver falha de descritores de arquivo ou permissão restrita, o comando dispõe do comando alternativo `doxoade:open-note-external`, disparando o Notepad++ ou o SoftClub via processo desacoplado sem travar a IDE.

---

## 4. Arquivos Impactados

```text
doxoade/
└── commands/lite_xl_systems/template/
    └── 14_doxnote_panel.lua     # [REFORMULAÇÃO TOTAL] Motor de Splits, Seletor Fuzzy, Pote e Agenda (~28 KB)
```

---

## 5. Matriz de Casos de Teste (DoD - Definition of Done)

| ID do Teste | Entrada / Ação | Comportamento Esperado |
| :--- | :--- | :--- |
| **TC-NOTE-01** | Teclar `Alt+N` com notas existentes | Paleta abre com a lista de notas ordenadas por data de modificação recente. |
| **TC-NOTE-02** | Teclar `Alt+N` e digitar `arquitetura_v2` (inexistente) | Cria `.doxoade/note/arquitetura_v2.md` com data e abre o split à direita. |
| **TC-NOTE-03** | Teclar `Alt+P` (O Pote) | Abre o painel lateral com `.pote.md`. Teclar `Alt+P` novamente fecha o painel e devolve o foco. |
| **TC-NOTE-04** | Escrever `[ ] 2026-10-06 Revisar KVM` e salvar | O sistema detecta o padrão de tarefa e adiciona o `#id` automaticamente. |
| **TC-NOTE-05** | Teclar `Alt+A` (Agenda) | Gera a lista com as tarefas de hoje e pendentes. `Enter` na tarefa abre a nota dona. |
| **TC-NOTE-06** | Modificar a nota pelo terminal (`doxoade note`) | A IDE detecta a mudança e atualiza o buffer em tela sem erros de conflito. |

---

## 6. Próximo Passo

O plano está traçado com todas as salvaguardas contratuais.  
Podemos iniciar a **implementação do código de `14_doxnote_panel.lua`**?
