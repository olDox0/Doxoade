# 📜 AUDIT v1 — Status, Decisões e Lições

**Documento:** `doxoade/docs/Blitzplans/audit_v1_status.md`
**Data:** 2026-10-29
**Contexto:** Módulo `intelligence` — subcomando `audit` (corte 1)
**Status:** Operacional (diff literal). v1.1 (inteligência por extensão) pendente.

---

## 1. O que o `audit` faz

**Comando:** `doxoade intelligence audit <dossie.xml> [arquivo.py]`

**Função:** Compara o CDATA de cada `<file>` no dossiê XML (gerado por `intelligence --ai-export`) com o conteúdo do arquivo original no disco, usando diff unified.

**Objetivo:** Detectar:
- **Divergências literais** (o XML não reflete o disco).
- **Bug de CDATA** (se o XML tem `]]]]><![CDATA[>`).
- **Truncamento** (XML corrompido).
- **Minificação agressiva** (C/C++ com flags que quebram).

---

## 2. Decisões travadas (v1.0)

| # | Decisão |
|:---|:---|
| 1 | `intelligence` **não** registra flags no XML (por enquanto). |
| 2 | `audit` **só faz o diff** (não reaplica minificação). |
| 3 | `audit` **inteligente por extensão** (C/C++ ≠ Python). |
| 4 | `audit` **não ignora** linhas em branco (mostra o que está lá). |
| 5 | Exit 1 **só** para Python (com `--strict` opcional). |
| 6 | Nota por extensão **antes** do diff. |
| 7 | Veredito por extensão **só** se houver divergência. |
| 8 | `--strict` default **off**. |

---

## 3. Arquivos tocados

| Arquivo | Responsabilidade |
|:---|:---|
| `intelligence.py` | Grupo `intelligence` (scan, `--ai-export`, `--analyze`). |
| `intelligence_audit.py` | Subcomando `audit` (diff literal, v1.1). |
| `intelligence_utils.py` | `VALID_EXTS`, `get_ignore_spec`, `get_god_glossary`, etc. |
| `intelligence_engine.py` | `analyze_file_chief` (extração de metadados). |
| `intelligence_truncation.py` | `TruncationChecker`, `verify_dossier_integrity`. |
| `intelligence.toml` | Configuração (ignore patterns). |

---

## 4. O que funciona (validado)

| Feature | Status | Onde testamos |
|:---|:---|:---|
| Parse do XML (CDATA cru via ET + correção inline) | ✅ | Doxoade + Tianzun |
| Diff literal XML↔disco (unified) | ✅ | Doxoade + Tianzun |
| `--summary` (só resumo) | ✅ | Doxoade |
| `--filter removed/added` | ✅ | Doxoade |
| `--only-diff` | ✅ | Doxoade |
| `-U/--context` (linhas de contexto) | ✅ | Doxoade |
| `file_path` (filtro por arquivo) | ✅ | Doxoade |
| Exit code 1 se divergência (Python) | ✅ | Tianzun (10 arquivos) |
| Tolerância a XML antigo (`<ma'at>`, CDATA bugado) | ✅ | Doxoade |
| Diff em C/C++ (mostra linhas em branco removidas) | ✅ | Tianzun |

---

## 5. O que falta (v1.1)

| Item | Status |
|:---|:---|
| `_classify_diff` (whitespace/comments/code) | ❌ |
| `_diff_literal` com `note` + `classification` | ❌ |
| `_render_report` com veredito por extensão | ❌ |
| `_emit_exit_code` inteligente (Python + C/C++ código real) | ❌ |
| `--strict` no `audit` | ❌ |
| Remover `--filter` duplicado | ⚠️ |

---

## 6. Lições aprendidas

### 6.1 — Arquivo errado, função errada

**O `_emit_exit_code` foi adicionado no `intelligence.py` (grupo) em vez do `intelligence_audit.py` (subcomando).** **Isso causou `NameError: Dict`** (o `intelligence.py` não importa `Dict`) **e `TypeError: intelligence() got unexpected keyword 'strict'`** (o grupo não aceita `strict`).

**Lição:** **o `audit` é um **subcomando** separado. **Funções do `audit` ficam no `intelligence_audit.py`.**

### 6.2 — `--filter` duplicado

**O `--filter` foi adicionado duas vezes.** **O Click emite warning, mas não quebra.** **Lição:** **verificar duplicatas no `@click.option`.**

### 6.3 — `intelligence.py` não importa `Dict`

**O `intelligence.py` usa `Dict`?** **Só se o `_emit_exit_code` for adicionado lá.** **Lição:** **se for adicionar `Dict`, importar `from typing import Dict`.**

### 6.4 — O `mody` é uma ferramenta separada

**O `mody_patch.py` e `mody_triangulation.py` são o **aplicador de patches**. **O `audit` é o **verificador**. **Não misturar.**

---

## 7. Próximos passos

### 7.1 — Fechar o v1.1

1. Aplicar `_classify_diff` no `intelligence_audit.py`.
2. Atualizar `_diff_literal` (com `note` + `classification`).
3. Atualizar `_render_report` (veredito por extensão + nota antes do diff).
4. Adicionar `_emit_exit_code` no `intelligence_audit.py`.
5. Adicionar `--strict` no `audit`.
6. Remover `--filter` duplicado.
7. Testar no Tianzun.

### 7.2 — Validação no Tianzun

```cmd
doxoade intelligence audit chief_dossier_llm.xml
