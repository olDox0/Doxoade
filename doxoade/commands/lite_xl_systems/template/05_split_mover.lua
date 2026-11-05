-- doxoade/commands/lite_xl_systems/template/05_split_mover.lua
--[[
  🔀 DOXOADE SPLIT MOVER (V3.0 — Correção de Sintaxe + Movimento Real)
  ----------------------------------------------------------------------------
  Comandos:
    • Ctrl+Alt+D          → mover aba ativa para o painel oposto
    • Ctrl+Alt+Shift+D    → mover abas à direita para o painel oposto
    • Ctrl+L              → alternar orientação do split (H ↔ V)
    • Ctrl+Shift+L        → inverter ordem dos painéis
    • F6 / Ctrl+Alt+←/→   → focar painel oposto
]]

--[[
## 📌 Débito Técnico #001 — Logo Customizada

**Status:** Congelado (Fase 1.5)

**Diagnóstico:**
- Lite XL 2.1.8 **não tem** `renderer.image.load` (API removida)
- Lite XL 2.1.8 **não tem** `core.draw_logo` (função removida)
- A WelcomeView ("Get Started") é suprimida pelo Doxoade no boot
- O TTF gerado pelo GIMP tem 1 glifo (0x41) com 15 contours — insuficiente para logo complexa

**Decisões arquiteturais possíveis para retomada:**
1. Pipeline de tiles (8x8 glifos, cada um 64x64) + FreeType nítido
2. Bridge Vulcan C para `renderer.image.load` (patchear o binário)
3. Texto estilizado "DOXOADE" (fallback simples, viável)

**Ponto de retomada:** Após Fase 2 (`plugin_watchdog`) estabilizar o ecossistema.
]]

local core = require "core"
local command = require "core.command"
local keymap = require "core.keymap"
local DocView = require "core.docview"

-- ============================================================================
-- Utilitários
-- ============================================================================

--- Lista TODOS os leaves editáveis (não locked, não TreeView).
local function get_editor_leaves()
  local root = core.root_view and core.root_view.root_node
  local leaves = {}
  local function traverse(n)
    if not n then return end
    if n.type == "leaf" then
      if not n.locked then
        local is_tree = false
        for _, v in ipairs(n.views or {}) do
          if v and type(v.get_name) == "function" then
            local ok, name = pcall(v.get_name, v)
            if ok and type(name) == "string" and name:lower():find("tree") then
              is_tree = true
              break
            end
          end
        end
        if not is_tree then
          table.insert(leaves, n)
        end
      end
    else
      traverse(n.a)
      traverse(n.b)
    end
  end
  traverse(root)
  return leaves
end

--- Verifica se o layout atual é retrato (mais alto que largo).
local function is_portrait()
  local rv = core.root_view
  if not rv or not rv.size then return false end
  return rv.size.y > rv.size.x
end

--- Encontra o nó ativo de forma segura.
local function get_active_node()
  if not core.root_view then return nil end
  local ok, node = pcall(core.root_view.get_active_node, core.root_view)
  return ok and node or nil
end

--- Reorganiza o layout após mudanças estruturais.
local function refresh_layout()
  local root = core.root_view and core.root_view.root_node
  if root and type(root.update_layout) == "function" then
    pcall(root.update_layout, root)
  end
  if core.root_view and type(core.root_view.update) == "function" then
    pcall(core.root_view.update, core.root_view)
  end
  core.redraw = true
end

-- ============================================================================
-- Comando: Ctrl+Alt+D — Mover aba ativa para painel oposto (V3.0)
-- ============================================================================

rawset(_G, "move_active_tab_to_opposite", function()
  -- 🛡️ [FASE 1.5] Guard 1: debounce temporal
  local now = os.clock()
  local _last_call = rawget(_G, "_DOXOADE_LAST_MOVE_TAB_CALL") or 0
  if (now - _last_call) < 1.0 then
    return
  end
  rawset(_G, "_DOXOADE_LAST_MOVE_TAB_CALL", now)

  -- 🛡️ [FASE 1.5] Guard 2: modifier consistency
  -- Verifica se Ctrl e Alt estão fisicamente pressionados AGORA (não só na Lua)
  if keymap and keymap.modkeys then
    local ctrl_pressed = keymap.modkeys["ctrl"] or keymap.modkeys["control"]
    local alt_pressed = keymap.modkeys["alt"]
    if not ctrl_pressed or not alt_pressed then
      if core.log then
        core.log(string.format(
          "🛡️ [SPLIT] Ignorando: modifiers inconsistentes (ctrl=%s alt=%s) — auto-trigger?",
          tostring(ctrl_pressed), tostring(alt_pressed)
        ))
      end
      return
    end
  end

  -- Corpo original
  local view = core.active_view
--  if not view or not view.doc then return end
  if not view or not view.doc then
    if core.log then core.log("⚠ [SPLIT] Nenhuma aba ativa.") end
    return
  end
  
  local leaves = get_editor_leaves()
  local source_node = nil
  for _, leaf in ipairs(leaves) do
    for _, v in ipairs(leaf.views or {}) do
      if v == view then source_node = leaf; break end
    end
    if source_node then break end
  end

  if not source_node or source_node.locked then
    if core.log then core.log("⚠ [SPLIT] Painel ativo travado ou ausente.") end
    return
  end

  local leaves = get_editor_leaves()
  local target_node = nil
  for _, leaf in ipairs(leaves) do
    if leaf ~= source_node then
      target_node = leaf
      break
    end
  end

  if not target_node then
    if not source_node.split then
      if core.log then core.log("⚠ [SPLIT] Split não disponível.") end
      return
    end
    local dir = is_portrait() and "down" or "right"
    target_node = source_node:split(dir)
    if not target_node then
      if core.log then core.log("⚠ [SPLIT] Falha ao criar split.") end
      return
    end
  end

  local removed_idx = nil
  for i, v in ipairs(source_node.views or {}) do
    if v == view then removed_idx = i; break end
  end

  if not removed_idx then
    if core.log then core.log("⚠ [SPLIT] View não encontrada no painel ativo.") end
    return
  end

  table.remove(source_node.views, removed_idx)
  if #source_node.views > 0 then
    source_node.active_view = source_node.views[math.min(removed_idx, #source_node.views)]
  else
    source_node.active_view = nil
  end

  if target_node.add_view then
    target_node:add_view(view)
  end
  target_node.active_view = view
  cleanup_empty_splits()
  refresh_layout()
  if core.set_active_view then
    pcall(core.set_active_view, view)
  end
  rawset(_G, "_DOXOADE_SPLIT_LOCK", nil)
  core.redraw = true
end)

local function find_node_with_view(target_view)
  local leaves = get_editor_leaves()
  for _, leaf in ipairs(leaves) do
    for _, v in ipairs(leaf.views or {}) do
      if v == target_view then return leaf end
    end
  end
  return nil
end


-- ============================================================================
-- Comando: Ctrl+Alt+Shift+D — Mover abas à direita
-- ============================================================================

local function cleanup_empty_splits()
  local root = core.root_view and core.root_view.root_node
  if not root then return false end

  local function traverse(n)
    if not n or n.type == "leaf" then return false end

    if n.a and n.a.type == "leaf" and not n.a.locked and #(n.a.views or {}) == 0 and n.b then
      n:consume(n.b)
      return true
    end

    if n.b and n.b.type == "leaf" and not n.b.locked and #(n.b.views or {}) == 0 and n.a then
      n:consume(n.a)
      return true
    end

    if traverse(n.a) then return true end
    if traverse(n.b) then return true end

    return false
  end

  for _ = 1, 3 do
    if not traverse(root) then break end
  end

  return true
end

rawset(_G, "move_following_tabs_to_opposite", function()
  -- 🛡️ [FASE 1.5] Guard: modifier consistency
  if keymap and keymap.modkeys then
    local ctrl_pressed = keymap.modkeys["ctrl"] or keymap.modkeys["control"]
    local shift_pressed = keymap.modkeys["shift"]
    local alt_pressed = keymap.modkeys["alt"]
    if not ctrl_pressed or not shift_pressed or not alt_pressed then
      if core.log then
        core.log(string.format(
          "🛡️ [SPLIT] Ignorando move_following_tabs: modifiers inconsistentes (ctrl=%s shift=%s alt=%s)",
          tostring(ctrl_pressed), tostring(shift_pressed), tostring(alt_pressed)
        ))
      end
      return
    end
  end

  -- Corpo direto (sem função local aninhada)
  local source_node = get_active_node()
  local view = core.active_view
  if not source_node or not view or not source_node.views then return end

  local cur_idx = source_node.get_view_idx and source_node:get_view_idx(view)
  if not cur_idx or cur_idx >= #source_node.views then
    if core.log then core.log("⚠ [SPLIT] Nenhuma aba à direita.") end
    return
  end

  local leaves = get_editor_leaves()
  local target_node = nil
  for _, leaf in ipairs(leaves) do
    if leaf ~= source_node then target_node = leaf; break end
  end

  if not target_node then
    local dir = is_portrait() and "down" or "right"
    target_node = source_node:split(dir)
    if not target_node then return end
  end

  local moved = 0
  for i = #source_node.views, cur_idx + 1, -1 do
    local v = table.remove(source_node.views, i)
    if v then
      if target_node.add_view then target_node:add_view(v) end
      moved = moved + 1
    end
  end

  if #source_node.views > 0 then
    source_node.active_view = source_node.views[#source_node.views]
    if core.set_active_view then pcall(core.set_active_view, source_node.active_view) end
  end

  refresh_layout()
  if core.log and moved > 0 then
    core.log(string.format("✔ [SPLIT] %d aba(s) movida(s).", moved))
  end
end)

-- ============================================================================
-- Comando: Ctrl+L — Alternar orientação
-- ============================================================================

rawset(_G, "toggle_split_orientation", function()
  -- 🛡️ [FASE 1.5] Debounce
  local now = os.clock()
  local _last = rawget(_G, "_DOXOADE_LAST_TOGGLE_ORIENT") or 0
  if (now - _last) < 0.3 then return end
  rawset(_G, "_DOXOADE_LAST_TOGGLE_ORIENT", now)

  local leaves = get_editor_leaves()
  local root = core.root_view and core.root_view.root_node

  if #leaves <= 1 then
    local active = get_active_node() or leaves[1] or root
    if not active or not active.split then
      if core.log then core.log("⚠ [SPLIT] Split indisponível no nó ativo.") end
      return
    end
    local dir = is_portrait() and "down" or "right"
    local new_node = active:split(dir)
    if not new_node then
      if core.log then core.log("⚠ [SPLIT] Falha ao criar split " .. dir) end
      return
    end

    -- 🛡️ [FASE 1.5] Suporta doc real OU vazio (Get Started)
    local current_view = core.active_view
    if current_view and current_view.doc then
      local dup = DocView(current_view.doc)
      if new_node.add_view then new_node:add_view(dup) end
      new_node.active_view = dup
      if core.set_active_view then pcall(core.set_active_view, dup) end
    else
      -- Cria um doc vazio como fallback
      if core.open_doc then
        local empty_doc = core.open_doc()
        local new_view = DocView(empty_doc)
        if new_node.add_view then new_node:add_view(new_view) end
        new_node.active_view = new_view
        if core.set_active_view then pcall(core.set_active_view, new_view) end
      end
    end
    refresh_layout()
    if core.log then
      core.log(string.format("✔ [SPLIT] Painel duplicado (%s).", dir))
    end
    return
  end

  -- 2+ painéis: alterna orientação
  local function find_parent(n, target)
    if not n or n.type == "leaf" then return nil end
    if n.a == target or n.b == target then return n end
    return find_parent(n.a, target) or find_parent(n.b, target)
  end
  local parent = find_parent(root, leaves[1])
  if not parent then parent = find_parent(root, leaves[2]) end
  if not parent then
    if core.log then core.log("⚠ [SPLIT] Pai comum não encontrado.") end
    return
  end

  local current_type = tostring(parent.type):lower()
  if current_type:find("v") then
    parent.type = (current_type == "vsplit") and "hsplit" or "horizontal"
  else
    parent.type = (current_type == "hsplit") and "vsplit" or "vertical"
  end
  parent.divider = 0.5
  refresh_layout()
  if core.log then
    core.log(string.format("✔ [SPLIT] Orientação alterada para %s.",
      current_type:find("v") and "Horizontal" or "Vertical"))
  end
end)

-- ============================================================================
-- Comando: Ctrl+Shift+L — Inverter painéis
-- ============================================================================

rawset(_G, "swap_split_panels", function()
  -- 🛡️ [FASE 1.5] Guard 1: debounce temporal
  local now = os.clock()
  local _last_call = rawget(_G, "_DOXOADE_LAST_SWAP_PANELS") or 0
  if (now - _last_call) < 0.5 then
    return
  end
  rawset(_G, "_DOXOADE_LAST_SWAP_PANELS", now)

  -- 🛡️ [FASE 1.5] Guard 2: modifier consistency
  if keymap and keymap.modkeys then
    local ctrl_pressed = keymap.modkeys["ctrl"] or keymap.modkeys["control"]
    local shift_pressed = keymap.modkeys["shift"]
    if not ctrl_pressed or not shift_pressed then
      if core.log then
        core.log(string.format(
          "🛡️ [SPLIT] Ignorando swap_split_panels: modifiers inconsistentes (ctrl=%s shift=%s)",
          tostring(ctrl_pressed), tostring(shift_pressed)
        ))
      end
      return
    end
  end

  -- Corpo original
  local leaves = get_editor_leaves()
  if #leaves < 2 then
    if core.log then core.log("⚠ [SPLIT] Necessário 2+ painéis para swap_split_panels.") end
    return
  end

  local root = core.root_view and core.root_view.root_node
  local function find_parent(n, target)
    if not n or n.type == "leaf" then return nil end
    if n.a == target or n.b == target then return n end
    return find_parent(n.a, target) or find_parent(n.b, target)
  end

  local parent = find_parent(root, leaves[1])
  if parent and parent.a and parent.b then
    parent.a, parent.b = parent.b, parent.a
    refresh_layout()
    if core.log then core.log("✔ [SPLIT] Painéis invertidos.") end
  end
end)

-- ============================================================================
-- Comando: F6 — Focar painel oposto
-- ============================================================================

rawset(_G, "focus_opposite_panel", function()
  local tmp_dir = os.getenv("TEMP") or os.getenv("TMP") or "."
  local sl_file = tmp_dir .. (PATHSEP or "/") .. "doxoade_scroll_lock.txt"
  local f = io.open(sl_file, "r")
  if f then
    local content = f:read("*l") or ""
    f:close()
    if content == "1" then
      -- Scroll Lock ativo → ignorar (SDL2 está alucinando teclas)
      if core.log then
        core.log("🛡️ [SPLIT] Ignorando comando: Scroll Lock fisicamente ativo.")
      end
      return
    end
  end

  local function focus_opposite_panel()
    local leaves = get_editor_leaves()
    if #leaves < 2 then return end
    local active = get_active_node()
    for _, leaf in ipairs(leaves) do
      if leaf ~= active and leaf.active_view then
        if core.set_active_view then pcall(core.set_active_view, leaf.active_view) end
        if core.root_view.set_active_node then
          pcall(core.root_view.set_active_node, core.root_view, leaf)
        end
        core.redraw = true
        return
      end
    end
  end
end)

-- ============================================================================
-- Registro de comandos e keymaps
-- ============================================================================

-- 🛡️ [FASE 1.5] Desregistrar comandos antigos antes de re-registrar
pcall(function()
  if command.map then
    command.map["doxoade:move-tab-to-opposite-panel"] = nil
    command.map["doxoade:toggle-split-orientation"] = nil
    command.map["doxoade:swap-split-panels"] = nil
    command.map["doxoade:focus-opposite-panel"] = nil
    command.map["doxoade:move-following-tabs-to-opposite"] = nil
    command.map["root:move-tab-to-opposite-panel"] = nil
    command.map["root:move-following-tabs-to-opposite-panel"] = nil
  end
end)

-- 🛡️ [FASE 1.5] Registrar via rawget (evita strict.lua + valida existência)
local _cmd_move_tab     = rawget(_G, "move_active_tab_to_opposite")
local _cmd_move_follow  = rawget(_G, "move_following_tabs_to_opposite")
local _cmd_toggle_orient = rawget(_G, "toggle_split_orientation")
local _cmd_swap         = rawget(_G, "swap_split_panels")
local _cmd_focus_opp    = rawget(_G, "focus_opposite_panel")

if _cmd_move_tab then
  command.add(nil, {
    ["doxoade:move-tab-to-opposite-panel"] = _cmd_move_tab,
    ["root:move-tab-to-opposite-panel"]    = _cmd_move_tab,
  })
end

if _cmd_move_follow then
  command.add(nil, {
    ["doxoade:move-following-tabs-to-opposite"]  = _cmd_move_follow,
    ["root:move-following-tabs-to-opposite-panel"]= _cmd_move_follow,
  })
end

if _cmd_toggle_orient then
  command.add(nil, {
    ["doxoade:toggle-split-orientation"] = _cmd_toggle_orient,
  })
end

if _cmd_swap then
  command.add(nil, {
    ["doxoade:swap-split-panels"] = _cmd_swap,
  })
end

if _cmd_focus_opp then
  command.add(nil, {
    ["doxoade:focus-opposite-panel"] = _cmd_focus_opp,
  })
end

-- 🛡️ [FASE 1.5] Rebind keymap com unbind explícito (evita colisão)
pcall(function()
  if keymap.unbind then
    keymap.unbind("ctrl+l")
    keymap.unbind("ctrl+shift+l")
    keymap.unbind("ctrl+alt+d")
    keymap.unbind("ctrl+alt+shift+d")
    keymap.unbind("f6")
    keymap.unbind("ctrl+alt+right")
    keymap.unbind("ctrl+alt+left")
  end
end)

keymap.add({
  ["ctrl+l"]              = "doxoade:toggle-split-orientation",
  ["ctrl+shift+l"]        = "doxoade:swap-split-panels",
  ["ctrl+alt+d"]          = "doxoade:move-tab-to-opposite-panel",
  ["ctrl+alt+shift+d"]    = "doxoade:move-following-tabs-to-opposite",
  ["f6"]                  = "doxoade:focus-opposite-panel",
  ["ctrl+alt+right"]      = "doxoade:focus-opposite-panel",
  ["ctrl+alt+left"]       = "doxoade:focus-opposite-panel",
}, true)

if core.log then
  core.log("🔀 [SPLIT] Split Mover V3.1 carregado (com validação rawget).")
end
