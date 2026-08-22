-- doxoade/commands/lite_xl_systems/template/09_panel_manager.lua
-- =============================================================================
-- 09. GERENCIADOR SOBERANO DE PAINÉIS E DOCKING (SLOT ENGINE)
-- =============================================================================
local core = require "core"
local DocView = require "core.docview"
local command = require "core.command"

local PanelSlots = {}

local function get_doc_leaves(n, list)
  list = list or {}
  if not n then return list end
  if n.type == "leaf" and not n.locked then
    table.insert(list, n)
  elseif n.type ~= "leaf" then
    get_doc_leaves(n.a, list)
    get_doc_leaves(n.b, list)
  end
  return list
end

-- Resolve ou cria um nó de divisão para um slot específico
function PanelSlots.get_slot_node(slot_type)
  local leaves = get_doc_leaves(core.root_view.root_node)

  if slot_type == "right" then
    if #leaves >= 2 then
      return leaves[#leaves]
    elseif #leaves == 1 then
      return leaves[1]:split("right")
    end
  elseif slot_type == "bottom" then
    local active_node = core.root_view:get_active_node()
    if active_node and not active_node.locked then
      return active_node:split("down")
    end
  elseif slot_type == "left" then
    if #leaves >= 1 then
      return leaves[1]
    end
  end

  return core.root_view.root_node:get_primary_node()
end

-- Abre qualquer documento ou View em um slot designado ("right", "bottom", "left")
function PanelSlots.open_in_slot(slot_type, file_or_doc, log_msg)
  local target_node = PanelSlots.get_slot_node(slot_type)
  local doc = type(file_or_doc) == "string" and core.open_doc(file_or_doc) or file_or_doc

  for _, v in ipairs(target_node.views) do
    if v.doc == doc then
      target_node.active_view = v
      core.set_active_view(v)
      core.redraw = true
      return v
    end
  end

  local view = DocView(doc)
  target_node:add_view(view)
  core.set_active_view(view)
  if log_msg then core.log(log_msg) end
  core.redraw = true
  return view
end

-- Comandos prontos para acoplar painéis
command.add(nil, {
  ["doxoade:split-bottom-panel"] = function()
    local active_node = core.root_view:get_active_node()
    if active_node and not active_node.locked then
      active_node:split("down")
      core.redraw = true
    end
  end
})
