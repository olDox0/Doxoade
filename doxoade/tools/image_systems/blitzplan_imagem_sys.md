Esse conceito de **Evidências Visuais e Anotações Multimodais (Image-Link & Evidence Studio)** dentro de uma IDE de engenharia é um dos maiores diferenciais do Doxly. Ter a imagem ligada diretamente ao código/log (com thumbnail inline leve + clique para alta definição no Canvas) muda totalmente a velocidade de depuração.

Para transformar esse sistema em algo **fácil de manter, imune a erros e desacoplado** (evitando que a complexidade de misturar Python, C, SDL2 e Lua vire um fardo), estruturei o planejamento arquitetural sob o **ProDeNov 1.2.1**.

---

# 📜 BLUEPRINT: ARQUITETURA DO SISTEMA DE IMAGENS & EVIDÊNCIAS (DOX-IMAGE)

---

## 1. 🧭 DIAGNÓSTICO DA COMPLEXIDADE ATUAL (W5)

Atualmente o sistema tem 3 pontas que precisam conversar em harmonia:

```
[Captura / Clipboard] ➔ [ThumbEngine Python] ➔ [Sidecar .thumb.rlebin] ➔ [Inline Card 19a (Lua)] ➔ [Canvas Studio 19c (SDL2)]
```

### Onde estavam os nós de atrito:
1. **Contrato de Tipagem Frágil:** O `typhon_deploy.py` esperava um `dict` (`res.get(...)`), mas o `ThumbnailEngine` retornava um `ThumbResult` (dataclass).
2. **Múltiplos formatos simultâneos:** Mistura de `.meta.json`, `.thumb.rlebin` e `preview_rle.dat`.
3. **Carga em Runtime vs Pré-bake:** Decodificar imagens em tempo de execução no Lua rouba ciclos de CPU dos 60 FPS se não houver um sidecar pré-gerado.

---

## 2. 🏛️ PILARES DE MANUTENIBILIDADE (DESIGN SIMPLIFICADO)

Para a manutenção ser trivial, dividimos o sistema em **3 camadas de responsabilidade única**:

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │ 1. FORJA (PYTHON) — I/O Pesado, Pillow, RLE, Clipboard Win32 / Linux   │
 │    • Única responsabilidade: Ler PNG ➔ Gerar Sidecar Binário Leve.     │
 ├────────────────────────────────────────────────────────────────────────┤
 │ 2. CONTRATO (ARQUIVO SIDECAR) — O Ponto de Encontro                    │
 │    • print_01.png          (Imagem original em alta resolução)         │
 │    • print_01.thumb.rlebin (Miniatura binária ~2KB com header DOXRLE1) │
 ├────────────────────────────────────────────────────────────────────────┤
 │ 3. EXIBIÇÃO (LUA / SDL2) — Zero I/O Pesado, 60 FPS                     │
 │    • Template 19a: Desenha o Card no DocView lendo o .rlebin em O(1).  │
 │    • Clique / Enter: Abre a imagem original no Canvas 19c ou Externo.  │
 └────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 📋 PLANOS DE EXECUÇÃO (PRODENOV 1.2.1)

### 🔹 Plano A (Pipeline Padronizado & DTO Estrito)
1. **Padronização do `ThumbResult` (Python):**
   * Interface unificada que suporta tanto acesso por atributos (`res.ok`, `res.rects`) quanto compatibilidade com `.get()` e `as_dict()` (evitando quebras em chamadores antigos).
2. **Tag Canônica Universal de Imagem:**
   O leitor reconhece 2 formatos no editor:
   * **Tag Doxly:** `DOX-IMG: nome_imagem.png | 1920x1080 | 2026-09-09]`
   * **Markdown Padrão:** `!Evidência](.doxoade/assets/images/nome_imagem.png)`
3. **Interatividade com 1 Clique:**
   * **Passar o mouse / Gutter:** Mostra badge de prévia.
   * **Clique duplo / `Enter` sobre a tag:** Dispara `doxoade:open-image-in-canvas` (abre no Canvas 19c com zoom/pan 60 FPS).
   * **`Ctrl+Shift+C` sobre a tag:** Copia o arquivo da imagem ou bitmap direto para a área de transferência do SO.

### 🔹 Plano B (Fallback Gradual & Auto-Cura)
* Se uma tag `[DOX-IMG: ...]` apontar para um PNG cujo `.thumb.rlebin` ainda não existe:
  * O template 19a renderiza um **Card Placeholder Elegante** com o nome do arquivo.
  * Dispara uma corrotina assíncrona em background (`Khonsu`) chamando o Python para gerar o sidecar sem travar a interface.
  * No tick seguinte, o card se auto-atualiza para a miniatura colorida.

### 🔹 Plano C (Resgate e Abertura Externa)
* Se por qualquer razão o subsistema gráfico SDL2 estiver indisponível ou o arquivo for corrompido:
  * O menu contextual ou atalho dispara `system.show_in_file_manager()` ou `explorer.exe /select,"caminho"` abrindo instantaneamente no visualizador de fotos nativo do Windows/Linux.

---

## 4. 🩺 MATRIZ DE DIAGNÓSTICO (ANÚBIS / HORUS)

Para não ficarmos em *development hell*, criamos um comando de auditoria rápida de evidências:

```bash
doxoade doxly image-audit
```

Ele responde automaticamente às **5 Perguntas (W5)**:
* 📂 **O quê:** Varre todos os arquivos `.md` e `.lua` do projeto procurando tags `[DOX-IMG]`.
* 🔍 **Onde:** Verifica se os arquivos PNG existem em `.doxoade/assets/images/`.
* ⚡ **Quando / Estado:** Aponta quais imagens estão com thumbnails sincronizadas, quais estão pendentes e quais são órfãs (PNGs sem nenhuma referência em texto).
* 🛠️ **Auto-Fix:** Flag `--fix` gera todos os `.thumb.rlebin` faltantes em lote via CPU multi-thread.

---

## 5. 🔨 CORREÇÃO IMEDIATA DO AVISO (HOUSEKEEPING)

Para zerar imediatamente o aviso `AttributeError: 'ThumbResult' object has no attribute 'get'` no seu deploy, o ajuste no `ThumbnailEngine` e no chamador do `typhon_deploy.py` é cirúrgico:

### No Python (`doxoade/tools/image_systems/`):
Garantimos que o `ThumbResult` implemente `__getitem__` e `.get()` para total compatibilidade retroativa:

```python
@dataclass
class ThumbResult:
    ok: bool
    status: str
    rects: int = 0
    bytes: int = 0
    error: Optional[str] = None

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)
```

---

## 🎯 Próximo Passo Recomendado

Podemos aplicar essa padronização da classe `ThumbResult` e refinar o fluxo de **clicar na tag `[DOX-IMG]` para abrir instantaneamente no Canvas 19c**? 

Isso deixará o ciclo de investigação de prints 100% fluido e com manutenção modular simples.

---

# 📜 BLITZPLAN — ETAPA 1: BACKEND DE THUMBNAILS & SOBERANIA DE CONTRATO (DOXOADE CAS)

**Subsistemas Alvo:** `doxoade/tools/image_systems/`, `doxoade/commands/lite_xl_systems/typhon_deploy.py`, CLI `doxoade image`  
**Protocolo de Conformidade:** ProDeNov 1.2.1 (Planos A, B e C | W5 | Limite < 50KB | Zero-Regressão)  
**Data:** 09/09/2026 | **Panteões:** Ártemis (Autonomia), Hefesto (Construção/Binários) e Apolo (UX/CLI)

---

## 1. Contexto e Objetivos (W5 / 5 Perguntas)

* **O quê (What):**
  1. **Fix do Contrato `ThumbResult`:** Blindagem do objeto de retorno de geração de thumbnails para suportar tanto acesso por atributos (`res.ok`, `res.rects`) quanto compatibilidade transparente como dicionário (`res.get()`, `res["status"]`), eliminando o erro `AttributeError: 'ThumbResult' object has no attribute 'get'` no deploy Typhon.
  2. **Motor de Compressão RLE `DOXRLE1` (`thumbnail_engine.py`):** Motor de alta performance em Python (Pillow) que converte imagens PNG em grades compactas RLE binárias (`.thumb.rlebin`) com amostragem inteligente de cores e fusão de blocos horizontais.
  3. **Comando CLI Soberano `doxoade image`:** Interface de linha de comando para sincronização em lote (`doxoade image sync`), inspeção de integridade (`doxoade image status`) e geração pontual (`doxoade image thumb <arquivo>`), com suporte a `--dry-run` e `--force`.
* **Quem (Who):** Desenvolvedores e o pipeline automático de deploy supervisionado do Typhon / Doxly.
* **Onde (Where):**
  * `doxoade/tools/image_systems/thumbnail_engine.py` (Engine e Dataclass).
  * `doxoade/tools/image_systems/image_manager.py` (Sincronizador e Auditor).
  * `doxoade/commands/image_systems/cmd_image.py` (Grupo CLI Click Zeus).
  * `doxoade/commands/lite_xl_systems/typhon_deploy.py` (Correção da chamada no hook Ártemis).
* **Quando (When):** No pré-deploy (`doxoade doxly deploy [production|sandbox|test]`) ou sob demanda no terminal.
* **Por quê (Why):** Garantir que todos os sidecars binários estejam prontos antes do Lite XL abrir, permitindo renderização instantânea a 60 FPS sem gargalos no carregamento gráfico.
* **Origem & Consequências (Origin & Consequences):** Divergência entre a interface de dataclass e a chamada de dicionário no hook de deploy. Se não padronizado, os thumbnails deixam de ser pré-gerados e o Lite XL precisa recorrer a scripts pontuais de resgate.

---

## 2. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Dataclass Polimórfico + CLI Sync + DOXRLE1 Nativo)
1. **Contrato Universal `ThumbResult`:** Dataclass com suporte a `.ok`, `.rects`, `.bytes`, `.status`, `.error` e implementação de `__getitem__` e `.get(key, default)` para imunidade total contra quebras de tipagem.
2. **Motor `ThumbnailEngine`:** Gera sidecars binários com cabeçalho `DOXRLE1\x01` contendo largura/altura original e blocos $(x, y, w, r, g, b)$ em struct empacotada (`<HHHBBB`).
3. **Auditor e CLI:** `doxoade image sync` varre `.doxoade/assets/images/` e qualquer pasta de assets do projeto, gerando `.thumb.rlebin` apenas para arquivos novos ou modificados (`mtime(PNG) > mtime(RLE)`).
4. **Hook Ártemis no `typhon_deploy.py`:** Integração limpa e silenciosa reportando quantidade de thumbnails atualizadas.

### 🔹 Plano B (Fallback — Best Effort com Log Informativo)
* Se a biblioteca `Pillow` (PIL) não estiver instalada no ambiente Python, o motor emite aviso educativo via Apolo (`pip install pillow`) e ignora a geração sem interromper o deploy.
* Se um arquivo de imagem estiver corrompido, o erro é catalogado individualmente e o processo continua para os demais arquivos do projeto.

### 🔹 Plano C (Contingência & Resgate)
* Caso nenhum sidecar exista, o template Lua (`19a_dox_image_inline.lua`) utiliza o seu fallback de placeholder monocromático com dimensões aproximadas, garantindo que o editor nunca crashe.

---

## 3. Roteiro de Testagem (Matriz de Casos de Teste)

| ID | Cenário / Entrada | Ação | Comportamento Esperado |
| :--- | :--- | :--- | :--- |
| **TC-IMG-01** | Chamada `res.get("ok")` e `res.ok` no `ThumbResult` | Acesso de propriedades | Ambos retornam `True` sem lançar `AttributeError` |
| **TC-IMG-02** | PNG existente sem sidecar | `doxoade image sync` | Cria `.thumb.rlebin` com cabeçalho `DOXRLE1` válido |
| **TC-IMG-03** | PNG existente com sidecar atualizado (`mtime` idêntico) | `doxoade image sync` | Pula geração (Cache Hit) sem gastar CPU |
| **TC-IMG-04** | PNG modificado (`mtime(PNG) > mtime(rle)`) | `doxoade image sync` | Regenera o sidecar atualizado |
| **TC-IMG-05** | Deploy supervisionado | `doxoade doxly deploy test` | Executa sem warnings: `✔ [ÁRTEMIS] N thumbnails sincronizadas` |

---

