-- doxoade/commands/lite_xl_systems/template/template/06_tree_manager.lua
-- =============================================================================
-- 06. GESTÃO DE PROJETOS NA TREEVIEW + CRIAÇÃO INTERATIVA (Ctrl + Alt + N)
-- =============================================================================
local core = require "core"
local common = require "core.common"
local command = require "core.command"
local DocView = require "core.docview"

local function normalize_path(path)
  if not path then return nil end
  local str = tostring(path):gsub('^["\']', ''):gsub('["\']$', '')
  if str:sub(1, 1) == "~" then
    local home = os.getenv("USERPROFILE") or os.getenv("HOME") or ""
    str = home .. str:sub(2)
  end
  return system.absolute_path(str) or str
end

local function ensure_parent_directories(file_path)
  local dir = file_path:match("^(.*)[/\\]")
  if dir and dir ~= "" then
    local current = ""
    for part in dir:gmatch("[^/\\]+") do
      if current == "" and part:find("^[a-zA-Z]:") then
        current = part
      else
        current = (current == "" and "" or current .. PATHSEP) .. part
        pcall(function() system.mkdir(current) end)
      end
    end
  end
end

local function get_tree_target_dir()
  local view = core.active_view
  if view and view.hovered_item and view.hovered_item.filename then
    local info = system.get_file_info(view.hovered_item.filename)
    if info and info.type == "dir" then
      return view.hovered_item.filename
    else
      return view.hovered_item.filename:match("^(.*)[/\\]") or view.hovered_item.filename
    end
  end
  if core.project_directories and #core.project_directories > 0 then
    local p = core.project_directories[1]
    return type(p) == "table" and (p.path or p.name) or p
  end
  return "."
end

command.add(nil, {
  -- Criação Interativa (Ctrl + Alt + N): digite o caminho relativo ou absoluto
  ["doxoade:create-file-interactive"] = function()
    local base_dir = get_tree_target_dir()
    core.command_view:enter("Criar Arquivo (ex: doxoade/commands/novo_modulo.py)", {
      submit = function(input_path)
        if input_path and input_path:match("%S") then
          local full_path
          if input_path:find("^[a-zA-Z]:") or input_path:sub(1, 1) == "/" or input_path:sub(1, 1) == "~" then
            full_path = normalize_path(input_path)
          else
            full_path = base_dir .. PATHSEP .. input_path
          end

          ensure_parent_directories(full_path)
          local f = io.open(full_path, "a")
          if f then f:close() end

          local doc = core.open_doc(full_path)
          core.root_view:open_doc(doc)
          core.log("Arquivo criado e aberto: " .. full_path)
          core.redraw = true
        end
      end
    })
  end,

  ["doxoade:new-file-in-tree"] = function()
    command.perform("doxoade:create-file-interactive")
  end,

  ["doxoade:toggle-litexl-in-tree"] = function()
    if not core.project_directories then return end
    local clean_userdir = tostring(system.absolute_path(USERDIR) or USERDIR):gsub("\\", "/"):lower()
    for i, p in ipairs(core.project_directories) do
      local raw_path = type(p) == "table" and (p.path or p.name) or p
      local ppath = tostring(raw_path or ""):gsub("\\", "/"):lower()
      if ppath == clean_userdir then
        core.remove_project_directory(type(p) == "table" and (p.path or p) or p)
        core.log("Lite XL Config desanexado da Árvore.")
        core.redraw = true
        return
      end
    end
    core.add_project_directory(USERDIR)
    core.log("Lite XL Config anexado à Árvore.")
    core.redraw = true
  end,

  ["treeview:add-project-folder"] = function()
    core.command_view:enter("Caminho do Projeto para Adicionar", {
      submit = function(path)
        path = normalize_path(path)
        if path and tostring(path):match("%S") then
          local info = system.get_file_info(path)
          if info and info.type == "dir" then
            core.add_project_directory(path)
            core.log("Projeto anexado à Árvore: " .. tostring(path))
            core.redraw = true
          elseif info and info.type == "file" then
            core.root_view:open_doc(core.open_doc(path))
          else
            core.error("Caminho inexistente no disco: " .. tostring(path))
          end
        end
      end
    })
  end,

  ["treeview:remove-project-folder"] = function()
    local projects = core.project_directories
    if not projects or #projects == 0 then return end
    local items = {}
    local map = {}
    for _, p in ipairs(projects) do
      local pname = type(p) == "table" and (p.name or p.path) or p
      local ppath = type(p) == "table" and (p.path or p.name) or p
      local label = tostring(pname or "Projeto") .. " -> [" .. tostring(ppath or "") .. "]"
      table.insert(items, label)
      map[label] = ppath
    end

    core.command_view:enter("Selecione o Projeto para Desanexar", {
      submit = function(item)
        local target_path = map[item]
        if target_path then
          core.remove_project_directory(target_path)
          core.log("Projeto desanexado: " .. tostring(target_path))
          core.redraw = true
        end
      end,
      suggest = function(text) return common.fuzzy_match(items, text) end
    })
  end
})

pcall(function()
  local contextmenu = require "plugins.contextmenu"
  local TreeView = require "plugins.treeview"

  if contextmenu then
    contextmenu:register(function()
      return core.active_view and TreeView and core.active_view:is(TreeView)
    end, {
      contextmenu.DIVIDER,
      { text = "New File...",            command = "doxoade:create-file-interactive" },
      contextmenu.DIVIDER,
      { text = "Add Project Folder...",    command = "treeview:add-project-folder" },
      { text = "Remove Project Folder...", command = "treeview:remove-project-folder" },
    })
  end
end)
