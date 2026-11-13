-- doxoade/commands/lite_xl_systems/template/05_split_mover.lua
--[[
  🔀 DOXOADE CANONICAL SPLIT ENGINE (V13.0 — Parent-Map Deterministic Flip)
  ----------------------------------------------------------------------------
  - Ctrl+L              ➔ Alterna orientação (Horizontal ↔ Vertical) in-place
  - Ctrl+Shift+L        ➔ Inverte os painéis (Swap A ↔ B)
  - Ctrl+Alt+D          ➔ Move a aba ativa entre os painéis (Ping-Pong)
  - Ctrl+Alt+Shift+D    ➔ Move todas as abas à direita para o outro painel
  - Ctrl+Alt+X          ➔ Fecha abas à direita no painel atual
  - F6                  ➔ Alterna foco entre os painéis
]]

local core = require "core"
local command = require "core.command"
local DocView = require "core.docview"

-- ==============
-- 1. Topologia da Árvore com Mapa de Pais (Parent-Map)
-- ============================================================================

local function _fm(cat, act, det)
  local F = rawget(_G, "DOXOADE_FLOW")
  if F and F.mark then F.mark(cat, act, det) end
end

local NON_EDITOR_NAMES = {
    "tree", "canvas", "sketch", "open editors",
    "terminal", "shelf", "bottom shelf", "pty"
}
local function is_editor_leaf(node)
  if not node or node.type ~= "leaf" or node.locked then return false end
  for _, v in ipairs(node.views or {}) do
    -- 🛡️ FIX: nome só classifica views SEM doc (TreeView/OpenEditors/docks).
    -- Arquivo com "tree"/"terminal"/"canvas" no nome NÃO desqualifica o painel.
    if v and not v.doc then
      local name = (v.get_name and v:get_name()) or ""
      name = type(name) == "string" and name:lower() or ""
      for _, ex in ipairs(NON_EDITOR_NAMES) do
        if name:find(ex, 1, true) then return false end
      end
    end
  end
  return true
end

local function get_editor_leaves()
  local root = core.root_view and core.root_view.root_node
  if not root then return {} end

  local leaves = {}
  local function traverse(n)
    if not n then return end
    if n.type == "leaf" then
      if is_editor_leaf(n) then
        table.insert(leaves, n)
      end
    else
      if n.a then traverse(n.a) end
      if n.b then traverse(n.b) end
    end
  end

  traverse(root)
  return leaves
end

--- Mapeia parent_of[filho] = pai
local function build_parent_map(root)
  root = root or (core.root_view and core.root_view.root_node)
  local parent_of = {}
  local function traverse(n)
    if not n or n.type == "leaf" then return end
    if n.a then
      parent_of[n.a] = n
      traverse(n.a)
    end
    if n.b then
      parent_of[n.b] = n
      traverse(n.b)
    end
  end
  traverse(root)
  return parent_of
end

--- Localiza o nó divisor comum mais próximo entre os editores livres
local function find_editor_split_parent()
  local leaves = get_editor_leaves()
  if #leaves < 2 then return nil end

  local parent_of = build_parent_map()
  local active = core.root_view and core.root_view:get_active_node()
  if not active or not is_editor_leaf(active) then
    active = leaves[1]
  end

  local other = (leaves[1] == active) and leaves[2] or leaves[1]

  -- Coleta ancestrais do nó ativo
  local ancestors = {}
  local p = parent_of[active]
  while p do
    ancestors[p] = true
    p = parent_of[p]
  end

  -- Sobe a partir do outro nó até encontrar o primeiro ancestral comum
  p = parent_of[other]
  while p do
    if ancestors[p] and p.type ~= "leaf" then
      -- Verifica se esse nó não é a divisão geral da TreeView
      -- Um divisor de editores divide folhas que não são a TreeView
      return p
    end
    p = parent_of[p]
  end

  -- Fallback: o próprio root se não for folha
  local root = core.root_view and core.root_view.root_node
  return (root and root.type ~= "leaf") and root or nil
end

local function safe_refresh_layout()
  _fm("LAYOUT", "refresh_start", "")
  local root = core.root_view and core.root_view.root_node
  local layout_ok, layout_err = true, nil

  if root and root.update_layout then
    layout_ok, layout_err = pcall(root.update_layout, root)
    if not layout_ok then
      _fm("LAYOUT", "update_layout_FAILED", tostring(layout_err):sub(1, 120))
    end
  end
  if core.root_view and core.root_view.update then
    local ok2, err2 = pcall(core.root_view.update, core.root_view)
    if not ok2 then
      _fm("LAYOUT", "rootview_update_FAILED", tostring(err2):sub(1, 120))
    end
  end
  core.redraw = true
  _fm("LAYOUT", "refresh_end", layout_ok and "ok" or "FAILED")
end

-- ============================================================================
-- 2. Flip de Orientação Seguro e com Diagnóstico no Log (Ctrl+L)
-- ============================================================================

local _last_flip_time = 0
local function toggle_split_orientation()
  _fm("SPLIT", "toggle_start", "")
  local now = os.clock()
  if (now - _last_flip_time) < 0.25 then
    _fm("SPLIT", "toggle_debounced", "")
    return
  end
  _last_flip_time = now

  local leaves = get_editor_leaves()
  _fm("SPLIT", "leaves_found", "count=" .. #leaves)
  if #leaves < 2 then
    _fm("SPLIT", "need_two_leaves", "")
    return
  end

  local split_node = find_editor_split_parent()
  if not split_node then
    _fm("SPLIT", "no_parent_found", "")
    return
  end

  -- Tipo canônico do Lite XL 2.1.8
  local cur_type = tostring(split_node.type):lower()
  local is_horiz = (cur_type == "hsplit" or cur_type == "horizontal")
  local new_type = is_horiz and "vsplit" or "hsplit"
  _fm("SPLIT", "flip_plan", cur_type .. " -> " .. new_type)

  if not split_node.a or not split_node.b then
    _fm("SPLIT", "invalid_split_no_children", "")
    return
  end

  -- Estado anterior para rollback
  local old_type = split_node.type
  local old_divider = split_node.divider

  -- Troca APENAS type + divider (não invalida posições!)
  split_node.type = new_type
  split_node.divider = 0.5
  safe_refresh_layout()

  -- Verifica pós: filhos têm posição/size VÁLIDOS (não nil)
  local a = split_node.a
  local b = split_node.b
  local a_ok = a and a.position and a.position.x and a.size and a.size.x
  local b_ok = b and b.position and b.position.x and b.size and b.size.x

  if not (a_ok and b_ok) then
    _fm("SPLIT", "POST_INVALID", "a_ok=" .. tostring(a_ok ~= nil) .. " b_ok=" .. tostring(b_ok ~= nil) .. " -- ROLLBACK")
    split_node.type = old_type
    split_node.divider = old_divider
    safe_refresh_layout()
    if core.log then
      core.log("⚠️ [SPLIT] Flip cancelado: pós-layout inválido.")
    end
    return
  end

  -- Verifica geometria COERENTE (dx/dy realinhados)
  local dx = math.abs((a.position.x or 0) - (b.position.x or 0))
  local dy = math.abs((a.position.y or 0) - (b.position.y or 0))
  local geometry_ok
  if new_type == "hsplit" then
    geometry_ok = dx > dy  -- lado a lado: x difere mais
  else
    geometry_ok = dy > dx  -- empilhados: y difere mais
  end

  if not geometry_ok then
    _fm("SPLIT", "POST_INVALID",
      "geometry_mismatch dx=" .. dx .. " dy=" .. dy .. " -- ROLLBACK")
    split_node.type = old_type
    split_node.divider = old_divider
    safe_refresh_layout()
    if core.log then
      core.log("⚠️ [SPLIT] Flip cancelado: geometria pós-flip não bate.")
    end
    return
  end

  _fm("SPLIT", "post_ok",
    "a.pos=" .. a.position.x .. "," .. a.position.y ..
    " b.pos=" .. b.position.x .. "," .. b.position.y)
  _fm("SPLIT", "toggle_end", "")
end

local function swap_split_panels()
  _fm("SWAP", "start", "")
  local split_node = find_editor_split_parent()
  if split_node and split_node.a and split_node.b then
    _fm("SWAP", "a_type", tostring(split_node.a and split_node.a.type))
    _fm("SWAP", "b_type", tostring(split_node.b and split_node.b.type))
    local tmp = split_node.a
    split_node.a = split_node.b
    split_node.b = tmp
    _fm("SWAP", "swapped", "")
    safe_refresh_layout()
    if core.log then core.log("✔ [SPLIT] Painéis invertidos com sucesso (Swap A ↔ B).") end
    _fm("SWAP", "end", "")
  else
    _fm("SWAP", "no_split", "")
  end
end

-- ============================================================================
-- 3. Movimentação Ping-Pong de Abas (Ctrl+Alt+D) — Comprovadamente Funcional
-- ============================================================================

local _last_move_time = 0
local function move_active_tab_to_opposite()
  -- ═══ Declarações locais no TOPO (evita escopo fantasma) ═══
  local now = os.clock()
  local view, leaves, source_leaf, target_leaf, view_idx, leaf_count

  if (now - _last_move_time) < 0.25 then
    _fm("MOVE", "debounced", "delta=" .. tostring(now - _last_move_time))
    return
  end
  _last_move_time = now

  view = core.active_view
  if not view or not view.doc then
    if core.log then core.log("⚠️ [SPLIT] Nenhuma aba ativa para transferir.") end
    _fm("MOVE", "no_active_view", "")
    return
  end

  leaves = get_editor_leaves()
  _fm("MOVE", "start", "leaves=" .. tostring(#leaves))
  if not leaves or #leaves == 0 then
    _fm("MOVE", "no_leaves", "")
    return
  end

  -- ─── Localiza source_leaf ───────────────────────────────────
  source_leaf = nil
  local i, l, v
  for i = 1, #leaves do
    l = leaves[i]
    local lviews = (l and l.views) or {}
    for j = 1, #lviews do
      v = lviews[j]
      if v == view or (v and v.doc and view.doc and v.doc == view.doc) then
        source_leaf = l
        break
      end
    end
    if source_leaf then break end
  end

  if not source_leaf then
    source_leaf = leaves[1]
    _fm("MOVE", "fallback_source", "idx=1")
  else
    _fm("MOVE", "source_found", "views=" .. tostring(#((source_leaf.views) or {})))
  end

  -- ─── Localiza target_leaf ───────────────────────────────────
  target_leaf = nil
  for i = 1, #leaves do
    if leaves[i] ~= source_leaf then
      target_leaf = leaves[i]
      break
    end
  end

  if not target_leaf then
    local rv = core.root_view
    local is_portrait = (rv and rv.size and rv.size.y > rv.size.x)
    local dir = is_portrait and "down" or "right"
    local ok_split, new_node = pcall(function()
      return source_leaf:split(dir)
    end)
    if not ok_split or not new_node then
      _fm("MOVE", "split_failed", tostring(new_node))
      return
    end
    target_leaf = new_node
    _fm("MOVE", "split_created", dir)
  end

  if not target_leaf or target_leaf.locked then
    _fm("MOVE", "target_locked", "")
    return
  end

  -- ─── Já está no destino? ────────────────────────────────────
  local tviews = target_leaf.views or {}
  for i = 1, #tviews do
    if tviews[i] == view then
      target_leaf.active_view = view
      core.set_active_view(view)
      safe_refresh_layout()
      _fm("MOVE", "already_in_target", "")
      return
    end
  end

  -- ─── Localiza view_idx ──────────────────────────────────────
  view_idx = nil
  local sviews = source_leaf.views or {}
  for i = 1, #sviews do
    if sviews[i] == view then
      view_idx = i
      break
    end
  end

  if not view_idx then
    _fm("MOVE", "view_not_found_in_source", "")
    return
  end

  -- ─── Remove da origem ───────────────────────────────────────
  table.remove(source_leaf.views, view_idx)
  leaf_count = #source_leaf.views
  _fm("MOVE", "removed_from_source", "remaining=" .. tostring(leaf_count))

  if leaf_count > 0 then
    local new_idx = math.min(view_idx, leaf_count)
    source_leaf.active_view = source_leaf.views[new_idx]
  else
    source_leaf.active_view = nil
    _fm("MOVE", "source_empty", "")
    -- EmptyView fallback
    local ok_ev, EmptyView = pcall(require, "core.emptyview")
    if ok_ev and EmptyView then
      local ok_new, ev = pcall(EmptyView)
      if ok_new and ev then
        source_leaf:add_view(ev)
        source_leaf.active_view = ev
        _fm("MOVE", "emptyview_added", "ok")
      else
        _fm("MOVE", "emptyview_failed", "")
      end
    end
  end

  -- ─── Adiciona ao destino ────────────────────────────────────
  local ok_add, err_add = pcall(function()
    target_leaf:add_view(view)
    target_leaf.active_view = view
  end)
  if not ok_add then
    _fm("MOVE", "add_view_failed", tostring(err_add))
    return
  end

  if core.root_view and core.root_view.set_active_node then
    pcall(core.root_view.set_active_node, core.root_view, target_leaf)
  end
  core.set_active_view(view)

  safe_refresh_layout()
  _fm("MOVE", "end", "target_views=" .. tostring(#target_leaf.views))
end


-- ─── Helper: garantir que um leaf nunca fica vazio ─────────────
local function ensure_leaf_not_empty(leaf)
  if not leaf or #(leaf.views or {}) > 0 then return end
  _fm("SPLIT", "ensure_empty", "leaf")
  local ok_ev, EmptyView = pcall(require, "core.emptyview")
  if ok_ev and EmptyView then
    local ok_new, ev = pcall(EmptyView)
    if ok_new and ev then
      leaf:add_view(ev)
      leaf.active_view = ev
      _fm("SPLIT", "ensure_empty", "emptyview_added")
      return
    end
  end
  if core.open_doc then
    local ok_doc, doc = pcall(core.open_doc)
    if ok_doc and doc then
      local DocView = require "core.docview"
      local v = DocView(doc)
      leaf:add_view(v)
      leaf.active_view = v
      _fm("SPLIT", "ensure_empty", "blank_doc")
    end
  end
end

local function move_following_tabs_to_opposite()
  _fm("MOVE_FOLLOW", "start", "")
  local view = core.active_view
  if not view then return end

  local leaves = get_editor_leaves()
  local source_leaf = nil
  for _, l in ipairs(leaves) do
    for _, v in ipairs(l.views or {}) do
      if v == view then source_leaf = l; break end
    end
    if source_leaf then break end
  end

  if not source_leaf or not source_leaf.views then return end

  local cur_idx = nil
  for i, v in ipairs(source_leaf.views) do
    if v == view then cur_idx = i; break end
  end

  if not cur_idx or cur_idx >= #source_leaf.views then return end

  local target_leaf = nil
  for _, l in ipairs(leaves) do
    if l ~= source_leaf then target_leaf = l; break end
  end

  if not target_leaf then
    local rv = core.root_view
    local is_portrait = (rv and rv.size and rv.size.y > rv.size.x)
    target_leaf = source_leaf:split(is_portrait and "down" or "right")
    if not target_leaf or target_leaf.locked then return end
  end

  local count = 0
  for i = #source_leaf.views, cur_idx + 1, -1 do
    local v = table.remove(source_leaf.views, i)
    if v then
      target_leaf:add_view(v)
      count = count + 1
    end
  end

  target_leaf.active_view = target_leaf.views[#target_leaf.views]
  ensure_leaf_not_empty(source_leaf)
  _fm("MOVE_FOLLOW", "moved", "count=" .. tostring(count))
  safe_refresh_layout()
  if core.log and count > 0 then
    core.log(string.format("✔ [SPLIT] %d aba(s) transferida(s) para o outro slot.", count))
  end
end

local function close_following_tabs()
  local view = core.active_view
  if not view then return end

  local leaves = get_editor_leaves()
  local node = nil
  for _, l in ipairs(leaves) do
    for _, v in ipairs(l.views or {}) do
      if v == view then node = l; break end
    end
    if node then break end
  end

  if not node or not node.views then return end

  local cur_idx = nil
  for i, v in ipairs(node.views) do
    if v == view then cur_idx = i; break end
  end

  if not cur_idx or cur_idx >= #node.views then return end

  local closed = 0
  for i = #node.views, cur_idx + 1, -1 do
    table.remove(node.views, i)
    closed = closed + 1
  end
  ensure_leaf_not_empty(node)
  _fm("CLOSE_FOLLOW", "closed", "count=" .. tostring(closed))

  safe_refresh_layout()
  if core.log and closed > 0 then
    core.log(string.format("🧹 %d aba(s) à direita fechada(s).", closed))
  end
end

local function focus_opposite_panel()
  _fm("FOCUS_OPP", "start", "")
  local leaves = get_editor_leaves()
  if #leaves < 2 then return end
  _fm("FOCUS_OPP", "leaves", "count=" .. tostring(#leaves))

  local view = core.active_view
  local current_node = nil
  for _, l in ipairs(leaves) do
    for _, v in ipairs(l.views or {}) do
      if v == view then current_node = l; break end
    end
    if current_node then break end
  end

  for _, l in ipairs(leaves) do
    if l ~= current_node and l.active_view then
      core.set_active_view(l.active_view)
      _fm("FOCUS_OPP", "target", "type=" .. tostring(l.type))
      if core.root_view and core.root_view.set_active_node then
        core.root_view:set_active_node(l)
      end
      core.redraw = true
      return
    end
  end
end

-- ============================================================================
-- 4. Registro dos Comandos (Duplo Predicado)
-- ============================================================================

local commands_map = {
  ["doxoade:toggle-split-orientation"]            = toggle_split_orientation,
  ["doxoade:swap-split-panels"]                   = swap_split_panels,
  ["doxoade:move-tab-to-opposite-panel"]          = move_active_tab_to_opposite,
  ["root:move-tab-to-opposite-panel"]             = move_active_tab_to_opposite,
  ["doxoade:move-following-tabs-to-opposite"]     = move_following_tabs_to_opposite,
  ["root:move-following-tabs-to-opposite-panel"] = move_following_tabs_to_opposite,
  ["doxoade:close-following-tabs"]                = close_following_tabs,
  ["root:close-following-tabs"]                   = close_following_tabs,
  ["doxoade:focus-opposite-panel"]                = focus_opposite_panel,
}

command.add("core.docview", commands_map)
command.add(nil, commands_map)

if core.log then
  core.log("🔀 [SPLIT] Parent-Map Deterministic Engine V13.0 ativo.")
end
