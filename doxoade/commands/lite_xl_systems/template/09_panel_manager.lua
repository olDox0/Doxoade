-- doxoade/commands/lite_xl_systems/template/09_panel_manager.lua
--[[
  🎛️ DOXOADE PANEL MANAGER & SLOT ORCHESTRATOR (V2.1 Canônica)
  - API Centralizada PanelSlots exposta para todo o ecossistema Doxoade.
  - Resolução robusta de slots: "right", "bottom", "left", "opposite", "primary".
  - Equalização (50%/50%) e comandos de balanceamento sem dependência de .parent nativo.
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = require "core"
local DocView = require "core.docview"
local command = require "core.command"
local keymap = require "core.keymap"

local PanelSlots = {}

local function is_editor_leaf(n)
  if not n or n.type ~= "leaf" then return false end
  if n.locked then return false end
  for _, v in ipairs(n.views or {}) do
    local name = (v.get_name and v:get_name()) or ""
    if name:lower():find("tree") then return false end
  end
  return true
end

function PanelSlots.get_editor_leaves(root)
  root = root or (core.root_view and core.root_view.root_node)
  local list = {}
  local function traverse(n)
    if not n then return end
    if n.type == "leaf" then
      if is_editor_leaf(n) then
        table.insert(list, n)
      end
    else
      traverse(n.a)
      traverse(n.b)
    end
  end
  traverse(root)
  return list
end

function PanelSlots.build_parent_map(root)
  root = root or (core.root_view and core.root_view.root_node)
  local parent_of = {}
  local function traverse(n)
    if not n or n.type == "leaf" then return end
    if n.a then parent_of[n.a] = n; traverse(n.a) end
    if n.b then parent_of[n.b] = n; traverse(n.b) end
  end
  traverse(root)
  return parent_of
end

function PanelSlots.get_slot_node(slot_type)
  local leaves = PanelSlots.get_editor_leaves()
  local is_portrait = (core.root_view and core.root_view.size and core.root_view.size.y > core.root_view.size.x)
  
  if slot_type == "right" then
    if #leaves >= 2 then
      return leaves[#leaves]
    elseif #leaves == 1 then
      return leaves[1]:split(is_portrait and "down" or "right")
    end
  elseif slot_type == "bottom" or slot_type == "down" then
    local active_node = core.root_view:get_active_node()
    if active_node and not active_node.locked then
      return active_node:split("down")
    elseif #leaves >= 1 then
      return leaves[#leaves]:split("down")
    end
  elseif slot_type == "left" or slot_type == "primary" then
    if #leaves >= 1 then
      return leaves[1]
    end
  elseif slot_type == "opposite" then
    local active_node = core.root_view:get_active_node()
    for _, leaf in ipairs(leaves) do
      if leaf ~= active_node then return leaf end
    end
    if #leaves == 1 then
      return leaves[1]:split(is_portrait and "down" or "right")
    end
  end
  
  return core.root_view.root_node:get_primary_node()
end

function PanelSlots.open_in_slot(slot_type, file_or_doc, log_msg)
  local target_node = PanelSlots.get_slot_node(slot_type)
  if not target_node then return nil end
  
  local doc = type(file_or_doc) == "string" and core.open_doc(file_or_doc) or file_or_doc
  if not doc then return nil end
  
  for _, v in ipairs(target_node.views or {}) do
    if v.doc == doc then
      target_node.active_view = v
      core.set_active_view(v)
      core.redraw = true
      return v
    end
  end
  
  local view = DocView(doc)
  if target_node.add_view then
    target_node:add_view(view)
  end
  target_node.active_view = view
  core.set_active_view(view)
  
  if log_msg and core.log then core.log(log_msg) end
  core.redraw = true
  return view
end

function PanelSlots.equalize_splits()
  local root = core.root_view and core.root_view.root_node
  local function traverse(n)
    if not n or n.type == "leaf" then return end
    if not (n.a and n.a.locked) and not (n.b and n.b.locked) then
      n.divider = 0.5
    end
    traverse(n.a)
    traverse(n.b)
  end
  traverse(root)
  if root and root.update_layout then root:update_layout() end
  core.redraw = true
end

-- Exportação Global Canônica
rawset(_G, "PanelSlots", PanelSlots)
rawset(_G, "_DOXOADE_PANEL_SLOTS", PanelSlots)

command.add(nil, {
  ["doxoade:split-bottom-panel"] = function()
    local node = PanelSlots.get_slot_node("bottom")
    if node then
      local active_view = core.active_view
      if active_view and active_view.doc then
        node:add_view(DocView(active_view.doc))
      end
      core.redraw = true
      if core.log then core.log("📐 [PANEL] Split inferior criado.") end
    end
  end,

  ["doxoade:split-right-panel"] = function()
    local node = PanelSlots.get_slot_node("right")
    if node then
      local active_view = core.active_view
      if active_view and active_view.doc then
        node:add_view(DocView(active_view.doc))
      end
      core.redraw = true
      if core.log then core.log("📐 [PANEL] Split lateral direito criado.") end
    end
  end,

  ["doxoade:equalize-splits"] = function()
    PanelSlots.equalize_splits()
    if core.log then core.log("⚖️ [PANEL] Splits equalizados (50% / 50%).") end
  end,
})

keymap.add({
  ["ctrl+alt+="] = "doxoade:equalize-splits",
  ["ctrl+alt+0"] = "doxoade:equalize-splits",
}, true)

return PanelSlots
