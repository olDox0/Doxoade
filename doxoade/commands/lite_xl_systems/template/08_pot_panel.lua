-- doxoade/commands/lite_xl_systems/template/08_pot_panel.lua
-- =============================================================================
-- 08. PAINEL DIREITO PARA CONFIGS, LOGS E DUMPPOT (.doxoade/dumppot.txt)
-- =============================================================================
local core = require "core"
local DocView = require "core.docview"

-- Função auxiliar que localiza ou cria a divisão da direita
local function get_or_create_right_panel()
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

  local leaves = get_doc_leaves(core.root_view.root_node)
  if #leaves >= 2 then
    return leaves[#leaves]
  elseif #leaves == 1 then
    return leaves[1]:split("right")
  end
  return core.root_view.root_node:get_primary_node()
end

local function open_in_right_panel(file_path, log_msg)
  local right_node = get_or_create_right_panel()
  local doc = core.open_doc(file_path)

  for _, v in ipairs(right_node.views) do
    if v.doc == doc then
      right_node.active_view = v
      core.set_active_view(v)
      core.redraw = true
      return
    end
  end

  right_node:add_view(DocView(doc))
  core.set_active_view(right_node.active_view)
  if log_msg then core.log(log_msg) end
  core.redraw = true
end

-- Cria o diretório .doxoade se não existir
local doxoade_cfg_dir = USERDIR .. PATHSEP .. ".doxoade"
pcall(function() system.mkdir(doxoade_cfg_dir) end)
local dumppot_file = doxoade_cfg_dir .. PATHSEP .. "dumppot.txt"

command.add(nil, {
  -- Pote abre sempre na direita no caminho fixo
  ["doxoade:open-pot-in-right-panel"] = function()
    open_in_right_panel(dumppot_file, "dumppot.txt aberto no painel da direita.")
  end,

  -- Init.lua abre sempre na direita
  ["doxoade:open-init-lua"] = function()
    local config_file = USERDIR .. PATHSEP .. "init.lua"
    open_in_right_panel(config_file, "init.lua aberto no painel da direita.")
  end,

  -- Log abre sempre na direita
  ["doxoade:open-log"] = function()
    local right_node = get_or_create_right_panel()
    for _, doc in ipairs(core.docs) do
      if doc:get_name() == "Log" or (doc.filename and doc.filename:find("Log")) then
        for _, v in ipairs(right_node.views) do
          if v.doc == doc then
            right_node.active_view = v
            core.set_active_view(v)
            core.redraw = true
            return
          end
        end
        right_node:add_view(DocView(doc))
        core.set_active_view(right_node.active_view)
        core.redraw = true
        return
      end
    end
    command.perform("core:open-log")
  end
})
