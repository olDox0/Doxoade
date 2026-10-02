-- doxoade/commands/lite_xl_systems/template/05_split_mover.lua
--[[
  ⚖️ DOXOADE IN-PLACE SPLIT CONTROLLER (V37.0 Parent-Map & High-Priority Keymap)
  - Ctrl+L: Alterna orientação in-place (Lado a Lado <-> Cima/Baixo).
  - Ctrl+Shift+L: Permuta os painéis (Swap A <-> B).
  - Ctrl+Alt+D: Move a aba ativa para o painel oposto.
  - Ctrl+Alt+Shift+D: Move todas as abas à direita da ativa para o painel oposto.
  - Ctrl+Alt+X: Fecha todas as abas à direita no painel atual.
  - F6 / Ctrl+Alt+Right: Alterna o foco entre os painéis.
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = require "core"
local command = require "core.command"
local keymap = require "core.keymap"
local DocView = require "core.docview"

local function is_portrait_mode()
  local rv = core.root_view
  if not rv or not rv.size then return false end
  return rv.size.y > rv.size.x
end

local function is_editor_leaf(node)
  if not node or node.type ~= "leaf" then return false end
  if node.locked then return false end
  for _, v in ipairs(node.views or {}) do
    local name = (v.get_name and v:get_name()) or ""
    if name:lower():find("tree") then return false end
  end
  return true
end

local function get_editor_leaves(root)
  root = root or (core.root_view and core.root_view.root_node)
  local leaves = {}
  local function traverse(n)
    if not n then return end
    if n.type == "leaf" then
      if is_editor_leaf(n) then
        table.insert(leaves, n)
      end
    else
      traverse(n.a)
      traverse(n.b)
    end
  end
  traverse(root)
  return leaves
end

-- Constrói o mapa de ascendência top-down (já que Node no Lite XL não tem .parent nativo)
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

local function find_editor_split_parent(leaf1, leaf2)
  if not leaf1 or not leaf2 then return nil end
  local parent_of = build_parent_map()
  local ancestors = {}
  local p = parent_of[leaf1]
  while p do
    ancestors[p] = true
    p = parent_of[p]
  end
  p = parent_of[leaf2]
  while p do
    if ancestors[p] and p.type ~= "leaf" then
      return p
    end
    p = parent_of[p]
  end
  return parent_of[leaf1]
end

local function cleanup_empty_splits()
  local root = core.root_view and core.root_view.root_node
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
end

local function safe_update_layout()
  local root = core.root_view and core.root_view.root_node
  if root and type(root.update_layout) == "function" then
    pcall(root.update_layout, root)
  end
  if core.root_view and type(core.root_view.update) == "function" then
    pcall(core.root_view.update, core.root_view)
  end
  core.redraw = true
end

local function toggle_split_orientation()
  cleanup_empty_splits()
  local leaves = get_editor_leaves()
  
  if #leaves >= 2 then
    local active_node = core.root_view:get_active_node()
    local other_leaf = (leaves[1] == active_node) and leaves[2] or leaves[1]
    local split_parent = find_editor_split_parent(active_node or leaves[1], other_leaf)
    
    if split_parent and split_parent.type ~= "leaf" then
      local current_type = tostring(split_parent.type):lower()
      local is_vert = (current_type:find("v") ~= nil)
      
      -- Alterna universalmente hsplit <-> vsplit e horizontal <-> vertical
      if is_vert then
        split_parent.type = (current_type == "vsplit") and "hsplit" or "horizontal"
      else
        split_parent.type = (current_type == "hsplit") and "vsplit" or "vertical"
      end
      
      split_parent.divider = 0.5
      safe_update_layout()
      
      if core.log then
        core.log(string.format("🔄 [SPLIT] Orientação: %s (50%% / 50%%).",
          is_vert and "Horizontal (Lado a Lado)" or "Vertical (Cima / Baixo)"))
      end
      return
    end
  end

  -- Se há apenas 1 painel, cria o segundo e clona o DocView ativo
  if #leaves == 1 then
    local split_dir = is_portrait_mode() and "down" or "right"
    local active_view = core.active_view
    local new_view = nil
    if active_view and active_view.doc then
      new_view = DocView(active_view.doc)
    end
    
    local new_node = leaves[1]:split(split_dir, new_view)
    if new_node and new_view then
      new_node.active_view = new_view
    end
    
    safe_update_layout()
    if core.log then
      core.log(string.format("📐 [SPLIT] Painel criado (%s). Pressione Ctrl+L para alternar orientação.", split_dir))
    end
  end
end

local function swap_split_panels()
  cleanup_empty_splits()
  local leaves = get_editor_leaves()
  if #leaves >= 2 then
    local active_node = core.root_view:get_active_node()
    local other_leaf = (leaves[1] == active_node) and leaves[2] or leaves[1]
    local split_parent = find_editor_split_parent(active_node or leaves[1], other_leaf)
    if split_parent and split_parent.a and split_parent.b then
      local tmp = split_parent.a
      split_parent.a = split_parent.b
      split_parent.b = tmp
      safe_update_layout()
      if core.log then
        core.log("🔀 [SPLIT] Painéis invertidos com sucesso (Swap A ↔ B).")
      end
    end
  else
    if core.log then core.log("⚠ [SPLIT] Necessário ao menos 2 painéis abertos para permutar.") end
  end
end

local function move_tab_to_opposite_panel()
  cleanup_empty_splits()
  local node = core.root_view and core.root_view:get_active_node()
  local view = core.active_view
  if not node or not view or not view.doc or node.locked then return end
  
  local leaves = get_editor_leaves()
  local target_node = nil
  
  if #leaves >= 2 then
    for _, leaf in ipairs(leaves) do
      if leaf ~= node then
        target_node = leaf
        break
      end
    end
    if target_node then
      local idx = node.get_view_idx and node:get_view_idx(view)
      if idx then
        table.remove(node.views, idx)
        if #node.views > 0 then
          node.active_view = node.views[math.min(idx, #node.views)]
        else
          local parent_of = build_parent_map()
          local parent = parent_of[node]
          if parent and parent.consume then
            local sibling = (parent.a == node) and parent.b or parent.a
            if sibling then parent:consume(sibling) end
          end
        end
      end
      target_node:add_view(view)
      target_node.active_view = view
      core.set_active_view(view)
    end
  else
    local split_dir = is_portrait_mode() and "down" or "right"
    local new_node = node:split(split_dir)
    if node.a and node.a.views then
      local idx = node.a.get_view_idx and node.a:get_view_idx(view)
      if idx then
        table.remove(node.a.views, idx)
        if #node.a.views > 0 then
          node.a.active_view = node.a.views[math.min(idx, #node.a.views)]
        end
      end
    end
    new_node:add_view(view)
    new_node.active_view = view
    core.set_active_view(view)
  end
  safe_update_layout()
end

-- Registro com duplo predicado ("core.docview" e global) para garantir captura quando digitando
local commands_map = {
  ["doxoade:toggle-split-orientation"] = toggle_split_orientation,
  ["doxoade:swap-split-panels"]        = swap_split_panels,
  ["root:move-tab-to-opposite-panel"]  = move_tab_to_opposite_panel,
  ["root:move-following-tabs-to-opposite-panel"] = function()
    cleanup_empty_splits()
    local node = core.root_view and core.root_view:get_active_node()
    local view = core.active_view
    if not node or not view or not view.doc or node.locked or not node.views then return end
    local cur_idx = (type(node.get_view_idx) == "function") and node:get_view_idx(view)
    if not cur_idx or cur_idx >= #node.views then return end
    
    local leaves = get_editor_leaves()
    local target_node = nil
    if #leaves >= 2 then
      for _, leaf in ipairs(leaves) do
        if leaf ~= node then target_node = leaf break end
      end
    else
      local split_dir = is_portrait_mode() and "down" or "right"
      target_node = node:split(split_dir)
    end
    
    if not target_node then return end
    local moved_count = 0
    for i = #node.views, cur_idx + 1, -1 do
      local v = table.remove(node.views, i)
      if v then
        target_node:add_view(v)
        moved_count = moved_count + 1
      end
    end
    safe_update_layout()
    if core.log and moved_count > 0 then
      core.log(string.format("📦 %d aba(s) movida(s) para o painel oposto.", moved_count))
    end
  end,
  ["doxoade:focus-opposite-panel"] = function()
    local leaves = get_editor_leaves()
    if #leaves < 2 then return end
    local active_node = core.root_view:get_active_node()
    for _, leaf in ipairs(leaves) do
      if leaf ~= active_node and leaf.active_view then
        core.set_active_view(leaf.active_view)
        if core.root_view and core.root_view.set_active_node then
          core.root_view:set_active_node(leaf)
        end
        core.redraw = true
        return
      end
    end
  end,
  ["root:close-following-tabs"] = function()
    local node = core.root_view and core.root_view:get_active_node()
    local view = core.active_view
    if not node or not view or not view.doc or node.locked or not node.views then return end
    local cur_idx = (type(node.get_view_idx) == "function") and node:get_view_idx(view)
    if not cur_idx or cur_idx >= #node.views then return end
    local closed_count = 0
    local root_node = core.root_view and core.root_view.root_node
    for i = #node.views, cur_idx + 1, -1 do
      local target_view = node.views[i]
      if target_view then
        if node.close_view then
          pcall(node.close_view, node, root_node, target_view)
        else
          table.remove(node.views, i)
        end
        closed_count = closed_count + 1
      end
    end
    core.redraw = true
    if core.log and closed_count > 0 then
      core.log(string.format("🧹 %d aba(s) à direita fechada(s).", closed_count))
    end
  end,
}

command.add("core.docview", commands_map)
command.add(nil, commands_map)

-- Desvincula atalhos nativos conflitantes (ex: doc:select-lines)
pcall(function()
  if keymap.unbind then
    keymap.unbind("ctrl+l")
    keymap.unbind("ctrl+shift+l")
  end
end)

-- Injeta diretamente no mapa de teclado do Lite XL
keymap.add({
  ["ctrl+l"]           = "doxoade:toggle-split-orientation",
  ["ctrl+shift+l"]     = "doxoade:swap-split-panels",
  ["ctrl+alt+d"]       = "root:move-tab-to-opposite-panel",
  ["ctrl+alt+shift+d"] = "root:move-following-tabs-to-opposite-panel",
  ["ctrl+alt+x"]       = "root:close-following-tabs",
  ["f6"]               = "doxoade:focus-opposite-panel",
  ["ctrl+alt+right"]   = "doxoade:focus-opposite-panel",
  ["ctrl+alt+left"]    = "doxoade:focus-opposite-panel",
}, true)

-- Blindagem direta na tabela keymap.map para impedir sobrescrita de plugins posteriores
if keymap.map then
  keymap.map["ctrl+l"] = { "doxoade:toggle-split-orientation" }
  keymap.map["ctrl+shift+l"] = { "doxoade:swap-split-panels" }
end
