# DOSSIER SOFTCLUB — GUI Nativa Windows sem WebView2

**Versão**: v23 (estável)  
**Data**: 2026-08-12  
**Autor**: equipa Altonomo / Projeto OADE  
**Plataforma**: Windows (x64) — Python 3.12 + ctypes + DLL C (`dxgui.dll`)

---

## 1. Resumo Executivo

SoftClub Notes é um **bloco de notas com GUI nativa Windows**, sem WebView2, sem Electron, sem navegador embutido. O motor gráfico (**Benzaiten**) é uma DLL C compilada com GCC que expõe primitivas GDI via `ctypes`. A camada Python orquestra render, teclado, drop de ficheiros, animação e temas.

**Porquê importa**: abre uma via de escalabilidade para todo o sistema Doxoade — GUIs leves, sem runtime de browser, sem overhead de Chromium, sem dependência de rede. O mesmo padrão (DLL + ctypes + WndProc subclass) pode ser reutilizado em qualquer ferramenta interna.

---

## 2. Arquitetura em Camadas

```
┌─────────────────────────────────────────────────────────┐
│  CLI (click) → gui_cmd.gui_softclub()                   │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│  notes_app.py  — orquestrador (paint, key, drop, state) │
└──┬──────────┬──────────┬──────────┬─────────────────────┘
   ▼          ▼          ▼          ▼
┌──────┐ ┌────────┐ ┌──────── ┌──────────┐
│ kit  │ │bg_image│ │palette │ │editor_   │
│.py   │ │.py     │ │.py     │ │input.py  │
└──┬───┘ └───┬────┘ └───┬────┘ ────┬─────┘
   │         │          │           │
   ▼         ▼          ▼           ▼
┌─────────────────────────────────────────────────────────┐
│  renderer.py  — ponte ctypes para dxgui.dll (GDI)       │
│  • WndProc subclass (PostMessage thread-safe)           │
│  • present(bgra), draw_text, fill_rect                  │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│  dxgui.dll (C)  — CreateWindow, DIB, GDI, message loop  │
└─────────────────────────────────────────────────────────┘
```

### Responsabilidades por módulo

| Módulo | Responsabilidade |
|---|---|
| `renderer.py` | Cria janela, expõe `present()`, `draw_text()`, subclassa WndProc para repaint thread-safe |
| `kit.py` | Primitivas de desenho (ring, double_bevel, draw_text, glass_rect) |
| `bg_image.py` | Decodifica foto/GIF/WebP, staircase low→full, recolor, animator ping-pong, FrameStore |
| `palette.py` | Temas day/night + `photo_theme_for` (tema derivado da foto) |
| `bg_gen.py` | Fundo procedural (gradiente + haze + spill + Bayer dither) |
| `notes_app.py` | Loop principal, paint, key handler, drop handler, estado |
| `editor_input.py` | Teclado do editor/pote (isolado do render) |
| `events.py` | Barramento de eventos (bus) |

---

## 3. Decisões Técnicas Críticas (e porquê)

### 3.1. Repaint thread-safe via WndProc subclass (v20/v21)

**Problema**: `dxgui_request_repaint()` da DLL chama `UpdateWindow` — se invocado de thread secundária (animator/staircase), dois threads dentro do GDI simultaneamente → access violation ou deadlock.

**Solução**: subclass do WndProc via `SetWindowLongPtrW`. O animator/staircase faz `PostMessage(WM_APP+92)` (thread-safe por definição do Win32). O loop principal despacha a mensagem no nosso proc → chama `flush_paint()` → `paint()` → `present()` — **todo GDI na thread principal**.

```python
# renderer.py
def request_repaint_safe(self):
    if getattr(self, '_repaint_pending', False):
        return
    self._repaint_pending = True
    u.PostMessageW(self._hwnd, _WM_APP_REPAINT, 0, 0)
```

### 3.2. Coalescing de repaint (v23)

**Problema**: `PostMessage` não coalesce — 20fps × 7 degraus = 140 mensagens enfileiradas → backlog → freeze.

**Solução**: flag `_repaint_pending` — só 1 mensagem in-flight. O próximo tick descarta se já há uma pendente; o paint sempre apresenta o `_frame_idx` mais recente.

### 3.3. TTL 2s em `api_get_note` / `api_agenda` (v23)

**Problema**: `draw_ui` lia disco a cada frame (20×/s) → scan de tarefas × 20 = CPU e I/O desnecessários.

**Solução**: cache com TTL de 2 segundos. Disco vira 0,5×/s.

```python
def _note_detail(root_s, name):
    now = time.time()
    hit = _DETAIL_CACHE.get((root_s, name))
    if hit and now - hit[0] < 2.0:
        return hit[1]
    val = api_get_note(root_s, name)
    _DETAIL_CACHE[(root_s, name)] = (now, val)
    return val
```

### 3.4. Staircase progressivo (v15+)

**Problema**: processar foto em resolução cheia bloqueia o paint → UX travada.

**Solução**: degraus low→full (1/24, 6/24, 12/24, 24/24). Cada degrau pronto posta repaint → blur → nítido progressivo. Cache por `(sig, variant, i)`.

### 3.5. Recolor v18 com numpy + cap f=1.75 (v19)

**Problema**: saturação ingênua cria platôs vermelhos (clipping em pixel escuro: `f = Lt/L` explode quando L→0).

**Solução**:
- Fast-path numpy (`_np.frombuffer`, `reshape`, `mean`, `clip`) → ~5× mais rápido que loop Python.
- `f = min(1.75, Lt / L)` — cap na razão de luminância.
- `_SAT_BOOST = {'day': 0.22, 'night': 0.08}` — ganhos conservadores.
- `_CHROMA_MIX = {'day': 0.30, 'night': 0.15}` — hue original re-escalado pela luminância alvo.

### 3.6. EDGE_TINT = dominante da foto (v18)

**Problema**: bordas dos painéis genéricas (cinza) não dialogam com a foto.

**Solução**: `kit.EDGE_TINT` recebe a cor dominante da paleta. `double_bevel` usa:
- Dominante escura (lum < 96) → degradê branco (sheen).
- Dominante clara → claro topo / escuro base.

### 3.7. FrameStore por assinatura (v14)

**Problema**: reprocessar a mesma fonte em cada variante = desperdício.

**Solução**: chave = `sig = sha256(fonte)[:12]`. Aquece os N frames **uma vez** → marca DONE → nunca re-kicka. Cada frame vira entrada `(sig, variant, i)` + hash de conteúdo.

### 3.8. Animator ping-pong ~15fps (v19/v23)

- Sequência: `0, 1, …, N-1, N-2, …, 1` (sem "pulo" no loop).
- Throttle: `(now - last) >= 0.066` (~15fps).
- Delay real por frame: `max(0.04, min(0.5, duration_ms / 1000))`.

### 3.9. Logger assíncrono (v14)

`_log()` só enfileira; thread daemon drena em lote. Não bloqueia render.

---

## 4. Como Rodar

```bash
# 1. Compilar a DLL (1x)
doxoade gui build

# 2. Rodar a GUI
doxoade gui softclub --run

# 3. Debug (logs no stderr)
set SOFTCLUB_DEBUG=1
doxoade gui softclub --run

# 4. Auditoria
doxoade check -fp doxoade/tools/benzaiten_gui/softclub/
```

### Drop de ficheiros
Arraste JPG/PNG/GIF/WebP para a janela → override do fundo. GIF/WebP multi-frame animam automaticamente.

### Atalhos
- `↑/↓` — navegar notas
- `ENTER` — editar
- `t` — trocar tema (day/night)
- `r seed` — mudar seed do fundo procedural
- `h/?` — ajuda
- `q` — sair

---

## 5. Ficheiros-Chave

```
doxoade/tools/benzaiten_gui/softclub/
├── renderer.py        # Ponte ctypes + WndProc subclass
── kit.py             # Primitivas de desenho
├── bg_image.py        # Decodificação, staircase, recolor, animator
├── palette.py         # Temas + photo_theme_for
├── bg_gen.py          # Fundo procedural
├── notes_app.py       # Orquestrador (paint, key, drop)
├── editor_input.py    # Teclado do editor
├── events.py          # Barramento de eventos
└── prefs.py           # Preferências (tema persistido)

.doxoade/benzaiten/
├── dxgui.dll          # Motor gráfico (C)
└── softclub/          # Cache de fundos (.raw)
```

---

## 6. Roadmap (opcional)

| Item | Descrição | Prioridade |
|---|---|---|
| Crossfade entre frames | Transição suave no animator | Baixa |
| Vinheta | Escurecer bordas da foto | Baixa |
| Grain | Ruído subtil sobre a foto | Baixa |
| Linux | `libdxgui.so` via X11/Wayland | Média |
| Tema "auto" | Day/night por hora do sistema | Baixa |
| Persistência de foto | Guardar última foto dropada | Média |

---

## 7. Lições Aprendidas

1. **GDI é single-thread**. Qualquer chamada de thread secundária = race. `PostMessage` + subclass é o padrão seguro.
2. **`PostMessage` não coalesce**. Sem flag `_repaint_pending`, a fila cresce sem limite.
3. **Disco no hot-path mata UX**. TTL de 2s em leituras de notas/agenda foi a diferença entre "fluido" e "trava".
4. **Saturação ingênua cria artefactos**. Cap na razão de luminância (`f ≤ 1.75`) é obrigatório.
5. **Staircase é UX, não otimização**. O utilizador vê progresso → sente o sistema vivo.
6. **FrameStore por assinatura** evita reprocessamento — a mesma foto em day+night só decodifica 1×.

---

## 8. Referências

- [Win32 Subclassing](https://learn.microsoft.com/en-us/windows/win32/controls/subclassing-overview)
- [PostMessage vs SendMessage](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-postmessagew)
- [GDI Thread Safety](https://learn.microsoft.com/en-us/windows/win32/gdi/thread-safety)
- [ctypes WinFunType](https://docs.python.org/3/library/ctypes.html#ctypes.WINFUNCTYPE)

---
