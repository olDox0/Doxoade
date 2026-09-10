# 📜 BLITZPLAN — APRIMORAMENTO DO MOTOR REGRET & SEGURANÇA OPERACIONAL
**Subsistema Alvo:** `doxoade/commands/regret_systems/` & `template/00_header_and_logger.lua`  
**Protocolo de Conformidade:** ProDeNov 1.2.1 (Planos A, B e C | W5 | Limite < 50KB)  
**Data:** 08/09/2026 | **Autor:** Nexus Core / Anúbis & Hefesto

---

## 1. Contexto e Objetivos (W5 / 5 Perguntas)

* **O quê:**
  1. Correção do crash de I/O (`PermissionError: [Errno 13]`) quando o comando `doxoade regret` recebe um **diretório** como alvo em vez de um arquivo único.
  2. Implementação do **Rastreamento Cross-File (Symbol Relocation)** para que símbolos movidos entre arquivos (ou templates irmãos) sejam classificados como `RELOCATED_CROSS_FILE` e não como perda crítica de capacidade (`METHOD_DROPPED`).
  3. Homologação e fechamento de ciclo do hook `RootView:draw` em `00_header_and_logger.lua` (HUD de Boot Report).
* **Quem:** Desenvolvedores e agentes atuando no ambiente Doxoade / Doxly.
* **Onde:** `doxoade/commands/regret_systems/` (`regret_engine.py`, `regret_git_reader.py`, `regret_reporter.py`) e `doxoade/commands/lite_xl_systems/template/00_header_and_logger.lua`.
* **Quando:** Imediatamente, antes de avançar para novas tarefas na IDE Lite XL/Doxly.
* **Por quê:** Executar `doxoade regret <diretorio>` é o fluxo natural do desenvolvedor para auditar subsistemas inteiros (ex: `doxoade/commands/lite_xl_systems/`). O crash bloqueia esse fluxo e a falta de consciência cross-file gera ruído em refatorações saudáveis.
* **Origem & Consequências:** O `regret_engine.py` supôs que `TARGET` seria sempre um arquivo individual e invocou `file_path.read_text()` diretamente. Se não corrigido, o usuário fica restrito a rodar arquivo por arquivo ou depender da detecção global cega.

---

## 2. Taxonomia dos Problemas & Diagnóstico

| ID | Sintoma | Causa Raiz | Impacto |
| :--- | :--- | :--- | :--- |
| **BUG-01** | `PermissionError: [Errno 13]` ao passar pasta | `regret_engine.py:75` faz `file_path.read_text()` em pasta | 🔴 Bloqueante para auditoria de diretórios |
| **GAP-02** | Falso positivo `METHOD_DROPPED` em código migrado | Escopo isolado por arquivo; desconhece adições em arquivos irmãos | 🟡 Ruído de severidade alta em refatorações |
| **CASE-03** | `RootView:draw` ausente em `00_header_and_logger.lua` | HUD de boot foi removido na working tree vs `ORIG_HEAD` | ⚪ Decisão arquitetural pendente |

---

## 3. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Router Polimórfico + Cross-File Reconciliation)
1. **Target Router no `regret_engine.py`:**
   * Se `TARGET` for arquivo: analisa o arquivo único.
   * Se `TARGET` for diretório: delega para coleta recursiva via `doxoade.tools.filesystem` (respeitando `SYSTEM_IGNORES`, `.gitignore` e extensões permitidas: `.lua`, `.py`, `.md`).
   * Se `TARGET` for omitido: mantém o comportamento padrão de ler working-tree vs `ORIG_HEAD` / `-B`.
2. **Cross-File Symbol Reconciliation:**
   * O motor executa em duas passadas:
     * **Passada 1:** Extrai símbolos removidos e adicionados de todos os arquivos do lote auditado.
     * **Passada 2:** Se o símbolo $S$ foi removido de `arquivo_A` mas foi adicionado ou já existe em `arquivo_B` (do mesmo subsistema/módulo), rebaixa a severidade de `ALTA (METHOD_DROPPED)` para `INFO (RELOCATED_CROSS_FILE)`.
3. **Decisão sobre `RootView:draw` em `00_header_and_logger.lua`:**
   * Como o `doxly_khonsu_gate.py` já gerencia o `_DOXOADE_BOOT_REPORT` com log no console e o `10_forensic_engine.lua` já faz a telemetria live do `RootView:draw`, verificar se o HUD visual deve ser restaurado como salvaguarda leve ou formalizado como deprecado.

### 🔹 Plano B (Fallback — Single-File Safe Loop com Ignorância Graciosa)
* Caso a árvore do Git ou de backups esteja inconsistente para varredura cross-file, o motor chaveia para o **modo arquivo-a-arquivo isolado**.
* Se encontrar uma pasta, faz apenas um `glob("*.lua")` / `glob("*.py")` direto e sem análise de dependência cruzada, ignorando diretórios sem travar com `PermissionError`.

### 🔹 Plano C (Contingência & Rollback)
* Se qualquer alteração no `regret_engine.py` causar instabilidade:
  * Reverter imediatamente o arquivo alterado via `git checkout -- doxoade/commands/regret_systems/regret_engine.py`.
  * Usar a flag `-d / --dump` para salvar trechos detectados no `.doxoade/dumppot.txt` para auditoria manual.

---

## 4. Arquivos Impactados e Limites de Tamanho (< 50KB)

```
doxoade/commands/regret_systems/
├── regret_engine.py         # Router de diretório + coletor em lote + cross-file pass (~15KB)
├── regret_git_reader.py     # Resolução de arquivos da working tree e revisões git (~12KB)
└── regret_reporter.py       # Renderização da badge RELOCATED_CROSS_FILE (~14KB)

doxoade/commands/lite_xl_systems/template/
└── 00_header_and_logger.lua # Avaliação do HUD RootView:draw (~14KB)
```
*Todos os arquivos estão rigorosamente abaixo do teto de 50KB do ProDeNov.*

---

## 5. Especificação Técnica dos Patches

### 5.1. Target Router no `regret_engine.py`
Substituir a chamada cega `file_path.read_text()` por um despachante de alvos:

```python
def resolve_audit_targets(target_path: Optional[Path]) -> List[Path]:
    """Resolve se o alvo é arquivo único, diretório ou working tree completa."""
    if target_path is None:
        return get_changed_files_from_git_or_backup()

    target = Path(target_path).resolve()
    if not target.exists():
        raise FileNotFoundError(f"Alvo inexistente: {target}")

    if target.is_file():
        return [target]

    if target.is_dir():
        # Coleta industrial respeitando extensões permitidas
        allowed_exts = {".lua", ".py", ".md", ".toml"}
        collected = []
        for root, dirs, files in os.walk(target):
            # Filtra pastas de quarentena/ignore do Doxoade
            dirs[:] = [d for d in dirs if d not in SYSTEM_IGNORES and not d.startswith(".")]
            for f in files:
                p = Path(root) / f
                if p.suffix.lower() in allowed_exts:
                    collected.append(p)
        return sorted(collected)

    return []
```

### 5.2. Lógica de Reconciliação Cross-File
Antes de emitir o veredito por arquivo:

```python
# Mapeia símbolos adicionados globalmente na rodada
global_added_symbols = {
    sym.name: (file_path, sym)
    for file_path, diff in batch_diffs.items()
    for sym in diff.added_symbols
}

for file_path, diff in batch_diffs.items():
    for dropped_sym in list(diff.dropped_symbols):
        if dropped_sym.name in global_added_symbols:
            dest_file, _ = global_added_symbols[dropped_sym.name]
            diff.dropped_symbols.remove(dropped_sym)
            diff.relocated_symbols.append({
                "symbol": dropped_sym.name,
                "from": file_path.name,
                "to": dest_file.name,
            })
```

---

## 6. Tasklist & Checklist de Execução

- [ ] **Fase 1: Correção do Bug de Diretório (`regret_engine.py`)**
  - [ ] Implementar verificação `is_dir()` e coleta recursiva de arquivos.
  - [ ] Tratar `PermissionError` e `FileNotFoundError` com mensagens claras no padrão Apolo.
  - [ ] Testar no terminal: `doxoade regret doxoade/commands/lite_xl_systems` (deve rodar sem crash).

- [ ] **Fase 2: Motor de Reconciliação Cross-File**
  - [ ] Criar estrutura intermediária de agregação de símbolos por lote auditado.
  - [ ] Rebaixar falsos positivos de realocação para `RELOCATED_CROSS_FILE`.
  - [ ] Adicionar suporte no `regret_reporter.py` para exibir a badge informativa.

- [ ] **Fase 3: Deliberação sobre `RootView:draw` em `00_header_and_logger.lua`**
  - [ ] Inspecionar se o OSD banner de boot ainda é necessário ou se o console já supre a informação.
  - [ ] Se necessário: reinserir o hook com proteção anti-recursão.
  - [ ] Se redundante: validar que o pipeline de deploy Typhon o reconhece como estável.

- [ ] **Fase 4: Homologação e Fechamento**
  - [ ] Rodar `doxoade doxly check-templates` (garantir que continua 30/30 e 82/82 PASS).
  - [ ] Rodar `doxoade regret` limpo contra `ORIG_HEAD` e contra o backup.
  - [ ] Registrar resultado antes de iniciar o próximo ciclo de desenvolvimento na IDE.

---

**Plano delineado e fundamentado.** Posso proceder com a aplicação cirúrgica da **Fase 1** (correção de diretório no `regret_engine.py`)?
