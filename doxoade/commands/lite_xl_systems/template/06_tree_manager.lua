-- doxoade/commands/lite_xl_systems/template/template/06_tree_manager.lua
-- =============================================================================
-- 06. GESTÃO DINÂMICA DE PROJETOS NA TREEVIEW + MENU CONTEXTUAL
-- =============================================================================
local core = require "core"
local common = require "core.common"
local command = require "core.command"

local function normalize_path(path)
  if not path then return nil end
  local str = tostring(path):gsub('^["\']', ''):gsub('["\']$', '')
  if str:sub(1, 1) == "~" then
    local home = os.getenv("USERPROFILE") or os.getenv("HOME") or ""
    str = home .. str:sub(2)
  end
  return system.absolute_path(str) or str
end

command.add(nil, {
  -- Toggle pasta do Lite XL na árvore (100% blindado com tostring)
  ["doxoade:toggle-litexl-in-tree"] = function()
    if not core.project_directories then return end
    local clean_userdir = tostring(system.absolute_path(USERDIR) or USERDIR):gsub("\\", "/"):lower()
    for _, p in ipairs(core.project_directories) do
      local raw_path = type(p) == "table" and (p.path or p.name) or p
      local ppath = tostring(raw_path or ""):gsub("\\", "/"):lower()
      if ppath == clean_userdir then
        core.remove_project_directory(type(p) == "table" and (p.path or p) or p)
        core.log("Lite XL Config removido da Árvore.")
        core.redraw = true
        return
      end
    end
    core.add_project_directory(USERDIR)
    core.log("Lite XL Config anexado à Árvore.")
    core.redraw = true
  end,

  ["treeview:add-project-folder"] = function()
    core.command_view:enter(
      "Caminho do Projeto para Adicionar (suporta ~ e caminhos absolutos)",
      function(path)
        path = normalize_path(path)
        if path and tostring(path):match("%S") then
          local info = system.get_file_info(path)
          if info and info.type == "dir" then
            core.add_project_directory(path)
            core.log("Projeto adicionado com sucesso: " .. tostring(path))
            core.redraw = true
          elseif info and info.type == "file" then
            core.root_view:open_doc(core.open_doc(path))
            core.log("Arquivo aberto: " .. tostring(path))
          else
            core.error("Caminho inexistente no disco: " .. tostring(path))
          end
        end
      end
    )
  end,

  ["treeview:remove-project-folder"] = function()
    local projects = core.project_directories
    if not projects or #projects == 0 then
      core.log("Nenhum projeto adicional para remover.")
      return
    end

    local items = {}
    local map = {}
    for _, p in ipairs(projects) do
      local pname = type(p) == "table" and (p.name or p.path) or p
      local ppath = type(p) == "table" and (p.path or p.name) or p
      local label = tostring(pname or "Projeto") .. " -> [" .. tostring(ppath or "") .. "]"
      table.insert(items, label)
      map[label] = ppath
    end

    core.command_view:enter(
      "Selecione o Projeto para Desanexar da Árvore",
      function(item)
        local target_path = map[item]
        if target_path then
          core.remove_project_directory(target_path)
          core.log("Projeto removido da Árvore: " .. tostring(target_path))
          core.redraw = true
        end
      end,
      function(text)
        return common.fuzzy_match(items, text)
      end
    )
  end
})

-- Registro no botão direito da árvore lateral (Context Menu)
pcall(function()
  local contextmenu = require "plugins.contextmenu"
  if contextmenu then
    contextmenu:register("core.treeview", {
      contextmenu.DIVIDER,
      { text = "Add Project Folder...", command = "treeview:add-project-folder" },
      { text = "Remove Project Folder...", command = "treeview:remove-project-folder" },
    })
  end
end)