# 📜 BLITZPLAN — MODO CANÔNICO SOBERANO & STAGING PIPELINE (DOXLY V23.0)

**Protocolo:** ProDeNov 1.2.1 | PASC-6.1 (Zero-Freeze) | W5 (5 Perguntas)
**Panteões Mobilizados:** Hades (Persistência/Backups), Ma'at (Invariantes de Integridade),
Anúbis (Auditoria/Rollback), Apolo (UX do HUD), Hórus (Observabilidade)
**Data:** 07/11/2026 | **Teto de Arquivo:** `< 50 KB` por módulo
**Status:** PLANEJAMENTO — Fase 1 e 2 apenas. Implementação em ciclos subsequentes.

---

## 1. Contexto e Diagnóstico (W5 — As 5 Perguntas)

### O quê (What)
Reestruturação do pipeline de deploy do Doxly para introduzir uma **camada de
staging isolada** entre o ambiente de testes e o editor canônico (produção),
com **promoção explícita**, **backups rotativos** e **rollback granular**,
eliminando o risco de perda do ambiente de trabalho do desenvolvedor durante
ciclos de teste.

### Quem (Who)
- **Desenvolvedor do Doxoade** — usa o Doxly como IDE principal para resolver
  problemas reais enquanto desenvolve.
- **Sistemas de Deploy** — `typhon_deploy.py`, `cmd_typhon_deploy.py`,
  `lite_xl_paths.py`.
- **HUD Frameless** — `13d_frameless_hud.lua` (chip `[⚡ PROMOTE]`).
- **Backup Engine** — novo, sob `TyphonDeployEngine`.

### Onde (Where)
```
~/.config/lite-xl/                                 ← CANONICAL (default do .exe)
├── init.lua                                       ← estável, só muda via promote
├── session.lua / workspace/                       ← sessão do usuário (intocada)
└── .doxoade/
    ├── staging/init.lua                           ← NOVO: candidato
    ├── backups/canonical/*.lua.bak                ← NOVO: backups rotativos
    └── test_deploy/, sandbox/                     ← existentes

doxoade/commands/lite_xl_systems/
├── lite_xl_paths.py                              ← +3 métodos
├── typhon_deploy.py                              ← +5 métodos, +modo "staging"
└── cmd_typhon_deploy.py                          ← +deploy staging, promote, rollback-canone
```

### Quando (When)
- **Hoje**: `.exe` sem flag abre `~/.config/lite-xl/`. `deploy production`
  escreve direto ali. Testar = arriscar perder tudo.
- **Fase 1**: infraestrutura adicionada (sem mudança de comportamento).
- **Fase 2**: `deploy staging` introduzido; `deploy production` mantém compatibilidade.
- **Fase 3** (futura): HUD button + session isolation + `production` → alias de `promote`.

### Quanto (How much)
- **Fase 1**: ~120 linhas Python, 3 arquivos, zero regressão.
- **Fase 2**: ~180 linhas Python, 2 arquivos, backwards compatible.
- **Backups**: rotação de 20 snapshots (~10 MB máximo).
- **Latência de promote**: < 200ms (I/O síncrono, não bloqueante).

### Por quê (Why)
Três incidentes em 48h provam o problema:
1. `deploy production -f` (AOT acidental) → 40min perdidos para diagnosticar.
2. Deploy com `_close_enough` quebrado → `error.txt` gerado a cada frame.
3. `deploy test` sobrescreveu `user_settings.lua` de produção por engano
   de flag.

Sem staging, **qualquer iteração de sistema é uma aposta**: você não sabe se
o canonical vai voltar intacto. O modo canônico é pré-requisito para que o
Doxly seja *usable* como IDE primária (não só playground).

### Origem & Consequências (Origin & Consequences)
- **Origem**: Doxly nasceu como ambiente de teste, não como IDE de produção.
  `init.lua` único servia tanto para canonical quanto para deployment.
- **Consequências**: cada deploy é "tudo ou nada". Falhas silenciosas
  requerem intervenção manual, e o editor fica inutilizável enquanto se debuga.
- **Solução**: staging pipeline separa "testar" de "promover" — o desenvolvedor
  sempre tem um editor funcionando no canonical enquanto investiga o staging.

---

## 2. Taxonomia de Complexidade (Regras 0.0 – 0.4 ProDeNov)

| Vetor | Classificação | Mitigação |
| :--- | :---: | :--- |
| **0.0 Thirdparty (Lite XL)** | Baixa | Não modifica core do Lite XL; `init.lua` é só lua puro. |
| **0.1 Devflow** | Baixa | `deploy production` mantém comportamento atual (compatível). |
| **0.2 Rabbit Hole** | Média | Não tenta virtualizar; usa diretórios + hashes. |
| **0.3 Sensibilidade (Sessão)** | **Crítica** | Session do canonical intocada; staging tem session próprio. |
| **0.4 Revisitar** | Baixa | Cada fase é atômica e testável isoladamente. |

---

## 3. Arquitetura da Solução

```
┌────────────────────────────────────────────────────────────────────┐
│                    FLUXO CANÔNICO DE PRODUÇÃO                      │
└────────────────────────────────────────────────────────────────────┘

  DEV EDITA TEMPLATES
         │
         ▼
  doxoade doxly deploy staging -f --no-khonsu
         │
         ├──► .doxoade/staging/init.lua   ← CANDIDATO
         │
         ▼
  doxoade doxly deploy staging --launch-test
         │
         ├──► Abre Lite XL em modo staging (via --userdir)
         ├──► Session isolada (não toca canonical)
         │
         ▼
  DEV VALIDA MANUALMENTE
         │
         ├─── ✅ Staging estável
         │
         ▼
  doxoade doxly deploy promote
         │
         ├──► 1. Backup canonical → .doxoade/backups/canonical/
         ├──► 2. Copy staging/init.lua → canonical/init.lua
         ├──► 3. Atualiza fingerprint
         │
         ▼
  CANONICAL ATUALIZADO ──► próximo `.exe` abre o novo init
         │
         ├─── ❌ Algo quebrou
         │
         ▼
  doxoade doxly deploy rollback-canone
         │
         ├──► 1. Backup do canonical ATUAL (reversível)
         ├──► 2. Copy backup escolhido → canonical/init.lua
         │
         ▼
  CANONICAL RESTAURADO
```

**Invariantes Ma'at:**
- `I1`: `deploy staging` **nunca** toca `~/.config/lite-xl/init.lua`
- `I2`: Todo `promote` gera backup com hash único ANTES de escrever
- `I3`: Todo `rollback` gera backup do estado atual (reversível)
- `I4`: Session/workspace do canonical **nunca** é copiado, movido ou apagado
- `I5`: Hash dedup impede backups duplicados do mesmo estado

---

## 4. FASE 1 — Infrastructure Only (30 min, zero regressão)

### 🎯 Objetivo
Adicionar fundação: paths, backup system, rollback, status comparison.
**Nada muda no comportamento atual.** `deploy production` continua escrevendo
em canonical, mas com proteção invisível (backup automático).

### 📄 1.1 `lite_xl_paths.py` — 3 métodos novos

```python
@classmethod
def get_staging_dir(cls) -> Path:
    """Diretório de staging (production candidate, isolado do canonical)."""
    staging = cls.get_user_dir() / ".doxoade" / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    return staging

@classmethod
def get_canonical_backups_dir(cls) -> Path:
    """Diretório de backups rotativos do canonical."""
    bkp = cls.get_user_dir() / ".doxoade" / "backups" / "canonical"
    bkp.mkdir(parents=True, exist_ok=True)
    return bkp

@classmethod
def get_canonical_fingerprint_path(cls) -> Path:
    """Metadata do canonical atual (para detectar drift)."""
    return cls.get_user_dir() / ".doxoade" / "canonical_fingerprint.json"
```

### 📄 1.2 `typhon_deploy.py` — 5 métodos novos

```python
import hashlib  # se ausente

@classmethod
def create_canonical_backup(cls, reason: str = "manual") -> Tuple[bool, Optional[Path]]:
    """Backup canonical com dedup por hash. Rotação automática em 20."""
    from datetime import datetime
    canonical_init = LiteXLPaths.get_init_lua_path()
    if not canonical_init.exists():
        return True, None

    try:
        content_hash = hashlib.sha256(canonical_init.read_bytes()).hexdigest()[:8]
    except Exception:
        content_hash = "unknown"

    bkp_dir = LiteXLPaths.get_canonical_backups_dir()
    existing = sorted(bkp_dir.glob("init_*.lua.bak"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    if existing and content_hash != "unknown":
        parts = existing[0].name.split("_")
        if len(parts) >= 3 and parts[2] == content_hash:
            return True, existing[0]  # dedup

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bkp_path = bkp_dir / f"init_{timestamp}_{content_hash}_{reason}.lua.bak"

    try:
        shutil.copy2(canonical_init, bkp_path)
        cls._rotate_canonical_backups(max_backups=20)
        return True, bkp_path
    except Exception:
        return False, None

@classmethod
def _rotate_canonical_backups(cls, max_backups: int = 20):
    bkp_dir = LiteXLPaths.get_canonical_backups_dir()
    backups = sorted(bkp_dir.glob("init_*.lua.bak"),
                    key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[max_backups:]:
        try: old.unlink(missing_ok=True)
        except Exception: pass

@classmethod
def list_canonical_backups(cls) -> List[Path]:
    bkp_dir = LiteXLPaths.get_canonical_backups_dir()
    return sorted(bkp_dir.glob("init_*.lua.bak"),
                 key=lambda p: p.stat().st_mtime, reverse=True)

@classmethod
def rollback_canonical(cls, target_backup: Optional[Path] = None) -> Tuple[bool, str]:
    """Reversível: backup do atual antes de restaurar."""
    canonical_init = LiteXLPaths.get_init_lua_path()
    backups = cls.list_canonical_backups()
    if not backups:
        return False, "Nenhum backup canonical disponível."
    target = target_backup or backups[0]
    if not target.exists():
        return False, f"Backup não encontrado: {target}"
    cls.create_canonical_backup(reason="pre-rollback")
    try:
        shutil.copy2(target, canonical_init)
        return True, f"Rollback concluído: {target.name}"
    except Exception as e:
        return False, f"Falha no rollback: {e}"

@classmethod
def get_canonical_status(cls) -> Dict[str, Any]:
    """Compara canonical vs staging. Fonte única de verdade para HUD/CLI."""
    canonical_init = LiteXLPaths.get_init_lua_path()
    staging_init = cls._get_deploy_dir("staging") / "init.lua"

    result = {
        "canonical_exists": canonical_init.exists(),
        "staging_exists": staging_init.exists(),
        "identical": False,
        "canonical_size": 0, "staging_size": 0,
        "canonical_hash": None, "staging_hash": None,
        "canonical_is_aot": False, "staging_is_aot": False,
        "promotion_pending": False,
    }
    for src, key in ((canonical_init, "canonical"), (staging_init, "staging")):
        if src.exists():
            raw = src.read_bytes()
            result[f"{key}_size"] = len(raw)
            result[f"{key}_is_aot"] = raw[:4].startswith(b"\x1bLua")
            result[f"{key}_hash"] = hashlib.sha256(raw).hexdigest()[:16]
    if result["canonical_hash"] and result["staging_hash"]:
        result["identical"] = (result["canonical_hash"] == result["staging_hash"])
        result["promotion_pending"] = not result["identical"]
    return result
```

### 📄 1.3 `typhon_deploy.py` — aceitar `"staging"` como modo

```python
DeployMode = Literal["production", "staging", "sandbox", "test"]

# Em _get_deploy_dir:
if mode == "staging":
    return LiteXLPaths.get_staging_dir()
```

### 📄 1.4 `cmd_typhon_deploy.py` — atualizar choices

```python
@click.option("--mode", "-m",
              type=click.Choice(["production", "staging", "sandbox", "test"]))
```

### 📋 Tasklist Fase 1
- [ ] 1.1 Adicionar 3 métodos em `LiteXLPaths`
- [ ] 1.2 Adicionar 5 métodos em `TyphonDeployEngine`
- [ ] 1.3 Estender `DeployMode` e `_get_deploy_dir` com `"staging"`
- [ ] 1.4 Atualizar `click.Choice` em `cmd_typhon_deploy.py`
- [ ] 1.5 **Injetar backup automático** em `create_backup()` de `production`:
      chamar `create_canonical_backup(reason="pre-deploy")` ANTES de escrever

### ✅ DoD Fase 1
```bash
doxoade doxly check-templates           # 49/49 PASS
doxoade doxly deploy status             # mostra canonical vs staging
doxoade doxly deploy production -f      # gera backup canonical auto
doxoade doxly deploy rollback --list -m production
doxoade doxly deploy rollback -m production  # restaura último backup
```

Zero regressão: `deploy production` continua funcionando, mas protegido.

---

## 5. FASE 2 — Staging & Promote Commands (30 min)

### 🎯 Objetivo
Introduzir `deploy staging` e `promote`. `deploy production` mantém
compatibilidade mas ganha aviso quando staging diverge.

### 📄 2.1 `cmd_typhon_deploy.py` — `deploy staging`

```python
@deploy_group.command("staging", help="🎯 Deploy em STAGING (candidato, isolado).")
@click.option("--force", "-f", is_flag=True)
@click.option("--no-khonsu", is_flag=True)
@click.option("--launch-test", is_flag=True,
              help="Abre Lite XL em modo staging para validação visual.")
def cmd_deploy_staging(force, no_khonsu, launch_test):
    print(f"\n{Fore.YELLOW}{Style.BRIGHT}🎯 DEPLOY STAGING (CANDIDATO){Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}  ⚠ Canonical NÃO será tocado.{Fore.RESET}\n")

    result = TyphonDeployEngine.deploy("staging", force=force, no_khonsu=no_khonsu)
    if not result["success"]:
        print(f"{Fore.RED}✖ Deploy staging falhou: {result['error']}{Fore.RESET}")
        return

    print(f"{Fore.GREEN}✔ Staging pronto: {result['init']}{Fore.RESET}")
    print(f"{Fore.CYAN}  Modo: {result.get('opt_mode', '?')}{Fore.RESET}")

    status = TyphonDeployEngine.get_canonical_status()
    if status["promotion_pending"]:
        delta = status["staging_size"] - status["canonical_size"]
        print(f"{Fore.YELLOW}💡 Canonical difere do staging ({delta:+d} bytes).{Fore.RESET}")
        print(f"{Fore.WHITE}   Promova com: doxoade doxly deploy promote{Fore.RESET}\n")

    if launch_test:
        print(f"{Fore.CYAN}🧪 Lançando Lite XL em modo STAGING...{Fore.RESET}")
        TyphonDeployEngine.launch("staging", exorcise=False)
```

### 📄 2.2 `cmd_typhon_deploy.py` — `promote`

```python
@deploy_group.command("promote", help="⚡ Promove staging → canonical (com backup).")
@click.option("--force", "-f", is_flag=True, help="Sem confirmação.")
@click.option("--allow-aot", is_flag=True,
              help="Permite AOT no canonical (padrão: bloqueia).")
def cmd_promote(force, allow_aot):
    print(f"\n{Fore.CYAN}{Style.BRIGHT}⚡ PROMOTE — Staging → Canonical{Style.RESET_ALL}\n")

    status = TyphonDeployEngine.get_canonical_status()
    if not status["staging_exists"]:
        print(f"{Fore.RED}✖ Staging não existe. Rode 'deploy staging' antes.{Fore.RESET}")
        return

    if status["identical"] and not force:
        print(f"{Fore.GREEN}✔ Canonical e staging já são idênticos.{Fore.RESET}")
        print(f"{Fore.LIGHTBLACK_EX}  Nada a promover.{Fore.RESET}\n")
        return

    if status["staging_is_aot"] and not allow_aot and not force:
        print(f"{Fore.RED}{Style.BRIGHT}⚠ Staging é AOT bytecode{Fore.RESET}")
        print(f"{Fore.YELLOW}  Promote para canonical em AOT é PERMANENTE.{Fore.RESET}")
        print(f"{Fore.YELLOW}  Debug será impossível até próximo promote source.{Fore.RESET}")
        print(f"\n{Fore.CYAN}💡 Use '--no-khonsu' no deploy staging, ou passe --allow-aot.{Fore.RESET}\n")
        return

    print(f"  {Fore.WHITE}Canonical: {status['canonical_size']:,} bytes "
          f"({'AOT' if status['canonical_is_aot'] else 'source'}){Fore.RESET}")
    print(f"  {Fore.WHITE}Staging:   {status['staging_size']:,} bytes "
          f"({'AOT' if status['staging_is_aot'] else 'source'}){Fore.RESET}\n")

    if not force:
        if not click.confirm(f"{Fore.YELLOW}Promover staging para canonical?{Fore.RESET}",
                            default=False):
            print(f"{Fore.YELLOW}Promote cancelado.{Fore.RESET}")
            return

    # 1. Backup canonical (obrigatório)
    ok_bkp, bkp_path = TyphonDeployEngine.create_canonical_backup("pre-promote")
    if not ok_bkp:
        print(f"{Fore.RED}✖ Falha no backup. Promote abortado.{Fore.RESET}")
        return
    if bkp_path:
        print(f"  {Fore.CYAN}💾 Backup: {bkp_path.name}{Fore.RESET}")

    # 2. Copy staging → canonical
    canonical = LiteXLPaths.get_init_lua_path()
    staging = TyphonDeployEngine._get_deploy_dir("staging") / "init.lua"
    try:
        shutil.copy2(staging, canonical)
    except Exception as e:
        print(f"{Fore.RED}✖ Falha na escrita: {e}{Fore.RESET}")
        print(f"{Fore.YELLOW}  Backup preservado: {bkp_path}{Fore.RESET}")
        return

    print(f"\n{Fore.GREEN}{Style.BRIGHT}✔ PROMOTE CONCLUÍDO{Fore.RESET}")
    print(f"{Fore.LIGHTBLACK_EX}  Rollback disponível: doxoade doxly deploy rollback{Fore.RESET}\n")
```

### 📄 2.3 `cmd_typhon_deploy.py` — `rollback-canone` com list

```python
@deploy_group.command("rollback", help="🛡️ Rollback canonical de backup.")
@click.option("--list", "-l", "list_backups", is_flag=True,
              help="Lista backups disponíveis.")
@click.option("--to", "-t", default=None,
              help="Restaura backup específico (nome do arquivo).")
def cmd_rollback_canone(list_backups, to):
    from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
    backups = TyphonDeployEngine.list_canonical_backups()

    if list_backups:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}💾 BACKUPS CANONICAL ({len(backups)}){Fore.RESET}\n")
        if not backups:
            print(f"{Fore.YELLOW}  Nenhum backup disponível.{Fore.RESET}\n")
            return
        for i, bkp in enumerate(backups, 1):
            st = bkp.stat()
            ts = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            print(f"  {Fore.WHITE}{i:2d}. {bkp.name}{Fore.RESET}")
            print(f"      {Fore.LIGHTBLACK_EX}{st.st_size:,} bytes | {ts}{Fore.RESET}")
        print()
        return

    target = None
    if to:
        for bkp in backups:
            if bkp.name == to or bkp.stem == to:
                target = bkp
                break
        if not target:
            print(f"{Fore.RED}✖ Backup não encontrado: {to}{Fore.RESET}")
            return

    ok, msg = TyphonDeployEngine.rollback_canonical(target)
    if ok:
        print(f"\n{Fore.GREEN}✔ {msg}{Fore.RESET}")
        print(f"{Fore.LIGHTBLACK_EX}  Próximo .exe abrirá com o init restaurado.{Fore.RESET}\n")
    else:
        print(f"\n{Fore.RED}✖ {msg}{Fore.RESET}\n")
```

### 📄 2.4 Aviso em `deploy production`

Adicionar em `cmd_deploy_production`, antes de escrever:

```python
status = TyphonDeployEngine.get_canonical_status()
if status["promotion_pending"] and not force:
    print(f"{Fore.YELLOW}⚠ Staging tem conteúdo diferente de canonical.{Fore.RESET}")
    print(f"{Fore.CYAN}💡 Considere: doxoade doxly deploy promote{Fore.RESET}\n")
```

### 📋 Tasklist Fase 2
- [ ] 2.1 `deploy staging` command
- [ ] 2.2 `promote` command com detecção AOT
- [ ] 2.3 `rollback` com `--list` e `--to`
- [ ] 2.4 Aviso de divergência em `deploy production`
- [ ] 2.5 Testar fluxo completo end-to-end

### ✅ DoD Fase 2
```bash
# Fluxo completo:
doxoade doxly deploy staging -f --no-khonsu
doxoade doxly deploy staging --launch-test        # valida visualmente
doxoade doxly deploy status                       # promotion_pending: true
doxoade doxly deploy promote -f
doxoade doxly deploy status                       # promotion_pending: false

# Rollback:
doxoade doxly deploy rollback --list
doxoade doxly deploy rollback                     # volta para pre-promote
```

Zero regressão: `deploy production -f` funciona como antes + backup automático.

---

## 6. Decisões Arquiteturais Pendentes (a resolver antes da Fase 2)

Estas 4 questões definem o comportamento final e devem ser resolvidas antes da
implementação da Fase 2 (para evitar refatoração):

### D1: `deploy production` — vira alias de `promote` no futuro?

- **Opção A** (recomendada): `deploy production` = alias de `promote` na Fase 4.
  Semântica limpa: só existe uma forma de tocar canonical = `promote`.
  Desvantagem: escape rápido perdido.
- **Opção B** (atual na Fase 2): `deploy production` continua escrevendo
  direto + backup automático. `promote` é caminho recomendado mas não obrigatório.
- **Opção C**: `deploy production` **aborta** se staging divergir (força uso de promote).

**Recomendação**: B na Fase 2 (compatibilidade), migrar para A na Fase 4.

### D2: Staging tem session próprio ou compartilha com canonical?

- **Opção A** (recomendada): session isolada (`.doxoade/staging/session.lua` +
  workspace próprio). Testar staging = ambiente limpo. Promover troca só
  `init.lua` — session canonical intocado.
- **Opção B**: compartilha session canonical. Você testa staging com seus
  arquivos abertos, mas se staging crashar pode corromper session.

**Recomendação**: A. Custo: reabrir arquivos ao testar staging. Benefício: zero
risco ao canonical.

### D3: Backup rotation — 20 é bom?

- **Atual proposto**: 20 snapshots (~10 MB máximo com init de 500KB).
- **Alternativa**: aumentar para 50 (~25 MB, ~2 meses a 1 promote/dia).

**Recomendação**: 20 é suficiente. Se precisar histórico longo, adicionar
`--keep N` no `create_canonical_backup`.

### D4: AOT no canonical — bloquear ou permitir?

- **Atual proposto**: `promote` bloqueia AOT por padrão. `--allow-aot` bypassa.
- **Alternativa**: canonical sempre source (proibir AOT eternamente).

**Recomendação**: manter `--allow-aot` como escape. AOT no canonical é válido
para performance final, mas você raramente vai querer isso durante
desenvolvimento.

---

## 7. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Staging + Promote + Rollback Reversível)
Implementar Fases 1 e 2 exatamente como descritas. `deploy production` mantém
compatibilidade. Session isolado. Backups rotativos com dedup por hash.
HUD `[⚡ PROMOTE]` na Fase 3.

### 🔹 Plano B (Fallback — Lock + Prompt sem Staging)
Se staging adicionar complexidade demais:
- `deploy production` faz backup automático + prompt "canonical será
  sobrescrito, continuar?"
- `rollback` manual continua disponível.
- Sem staging, você valida testando antes ou usando `deploy test` como
  staging informal.
- **Trade-off**: ainda arrisca canonical, mas com rede de segurança (backups).

### 🔹 Plano C (Contingência — Rollback-Only)
Se nada disso estabilizar:
- Zero mudanças no deploy. Só adicionar `create_canonical_backup()` automático
  antes de qualquer escrita + `rollback` manual.
- Você recupera o editor em caso de desastre, mas perde a prevenção.
- **Custo**: ~30 linhas. **Benefício**: 80% da segurança, 0% da UX.

---

## 8. Roteiro de Implementação (RIT — Ritual ProDeNov)

```
┌────────────────────────────────────────────────────────────┐
│ [RITUAL DE ENGENHARIA NOVÍSSIMA]                           │
│                                                            │
│  1. Discussão & Alinhamento (ESTE DOCUMENTO)               │
│  2. Resolver D1–D4 (decisões pendentes)                    │
│  3. Implementar FASE 1 (infrastructure)                    │
│  4. Validar Fase 1: check-templates + deploy status        │
│  5. Implementar FASE 2 (commands)                          │
│  6. Testar fluxo end-to-end                                │
│  7. Auditoria: doxoade regret + check-templates            │
│  8. FASE 3 (HUD button + session isolation) — futuro       │
│  9. FASE 4 (alias de production → promote) — futuro        │
└────────────────────────────────────────────────────────────┘
```

### 📊 Cronograma proposto

| Ciclo | Foco | Entregável |
| :--- | :--- | :--- |
| **Ciclo A** | Fase 1 | Infra + backup + rollback + status (30 min) |
| **Ciclo B** | Fase 2 | `deploy staging` + `promote` + `rollback` (30 min) |
| **Ciclo C** | Fase 3 | HUD button + session isolation (30 min) |
| **Ciclo D** | Fase 4 | `production` → `promote` alias (opcional) |

---

## 9. Riscos & Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
| :--- | :---: | :---: | :--- |
| Corrupção de backup por I/O | Baixa | Alto | `shutil.copy2` atômico, `hashlib` valida |
| Promote acidental de staging bugado | Média | Alto | Prompt de confirmação + AOT block |
| Session canonical quebrada | Baixa | Crítico | Isolamento absoluto (Fase 3) |
| Backup rotation apaga backup válido | Baixa | Médio | Dedup por hash; 20 snapshots é folgado |
| HUD button clicado por engano | Média | Baixo | Confirm dialog no `promote` |

---

## 10. Próximos Passos

1. **Você valida este documento** (Fase 1 + Fase 2 acima).
2. **Você responde D1–D4** (4 decisões arquiteturais).
3. **Ciclo A**: implementação da Fase 1 (infra + backups + rollback + status).
4. **Ciclo B**: implementação da Fase 2 (commands).
5. **Ciclos C/D**: HUD + alias de `production` (opcional, futuro).

**Aguardando**:
- Aprovação da Fase 1.
- Aprovação da Fase 2.
- Respostas D1–D4.

---

