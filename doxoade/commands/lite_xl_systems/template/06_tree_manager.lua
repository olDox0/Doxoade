-- doxoade/commands/lite_xl_systems/template/06_tree_manager.lua
--[[
  Módulo de Gerenciamento da Árvore de Arquivos (TreeView Soberana).
  - Controle cirúrgico de margem esquerda (elimina o vazio à esquerda).
  - Indentação compacta configurável por nível de subpasta (default 8px).
  - Criação recursiva de pastas, toggles de projeto e comandos rápidos.
]]
local core = require "core"
local common = require "core.common"
local command = require "core.command"
local DocView = require "core.docview"
local style = require "core.style"
local config = require "core.config"

-- =============================================================================
-- CONFIGURAÇÕES DE DENSIDADE E MARGEM DA TREEVIEW
-- =============================================================================
config.treeview_indent = config.treeview_indent or 8         -- Passo por subpasta (era 16px -> agora 8px)
config.treeview_left_padding = config.treeview_left_padding or 2 -- Recuo da borda esquerda (era 14px -> agora 2px)

local function normalize_path(path)
  if not path then return nil end
  local str = tostring(path):gsub('^["\']', ''):gsub('["\']$', '')
  if str:sub(1, 1) == "~" then
    local home = os.getenv("USERPROFILE") or os.getenv("HOME") or ""
    str = home .. str:sub(2)
  end
  return system.absolute_path(str) or str
end

local _created_dirs = {}
local function ensure_parent_directories(file_path)
    local dir = file_path:match("^(.*)[/\\]")
    if not dir or dir == "" or _created_dirs[dir] then return end
    local current = ""
    for part in dir:gmatch("[^/\\]+") do
        if current == "" and part:find("^[a-zA-Z]:") then
            current = part
        else
            current = (current == "" and "" or current .. PATHSEP) .. part
            if not _created_dirs[current] then
                pcall(system.mkdir, current)
                _created_dirs[current] = true
            end
        end
    end
    _created_dirs[dir] = true
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

-- =============================================================================
-- HOOKS NA TREEVIEW: MARGEM ESQUERDA ZERO + INDENTAÇÃO COMPACTA
-- =============================================================================
pcall(function()
  local TreeView = require "plugins.treeview" or require "core.treeview"
  if TreeView then
    -- 1. Altura compacta das linhas
    TreeView.get_item_height = function(self)
      local font = style.tree_font or style.font
      return math.floor(font:get_height() + 2)
    end

    -- 2. Recuo do texto/ícone encostado na margem esquerda
    if TreeView.get_item_text_offset then
      TreeView.get_item_text_offset = function(self)
        local font = style.tree_font or style.font
        return font:get_width("w") + (config.treeview_left_padding or 2)
      end
    end

    -- 3. Interceptação de indentação por profundidade
    if TreeView.get_item_indent then
      TreeView.get_item_indent = function(self, item)
        local depth = item and (item.depth or item.level or 1) or 1
        return (config.treeview_left_padding or 2) + (depth - 1) * (config.treeview_indent or 8)
      end
    end
  end
end)

-- =============================================================================
-- COMANDOS SOBERANOS DA ÁRVORE
-- =============================================================================
command.add(nil, {
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
    for idx, p in ipairs(core.project_directories) do
      local raw_path = type(p) == "table" and (p.path or p.name) or p
      local ppath = tostring(raw_path or ""):gsub("\\", "/"):lower()
      if ppath == clean_userdir then
        if core.remove_project_directory then
          core.remove_project_directory(type(p) == "table" and (p.path or p) or p)
        else
          table.remove(core.project_directories, idx)
        end
        core.log("Lite XL Config desanexado da Árvore.")
        core.redraw = true
        return
      end
    end
    if core.add_project_directory then
      core.add_project_directory(USERDIR)
      core.log("Lite XL Config anexado à Árvore.")
      core.redraw = true
    end
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
            local doc = core.open_doc(path)
            core.root_view:open_doc(doc)
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
      local label = string.format("%s (%s)", pname, ppath)
      table.insert(items, label)
      map[label] = ppath
    end
    core.command_view:enter("Selecione o Projeto para Desanexar", {
      submit = function(item)
        local target_path = map[item]
        if target_path then
          core.remove_project_directory(target_path)
          core.log("Projeto desanexado: " .. target_path)
          core.redraw = true
        end
      end,
      suggest = function(text)
        return common.fuzzy_match(items, text)
      end
    })
  end
})

-- =============================================================================
-- 3. INTEGRAÇÃO COM O MENU DE CONTEXTO DO TREEVIEW
-- =============================================================================
pcall(function()
  local contextmenu = require "plugins.contextmenu"
  local TreeView = require "plugins.treeview"
  if contextmenu and TreeView then
    contextmenu.register(function(view)
      return view:is(TreeView)
    end, {
      { text = "New File...", command = "doxoade:create-file-interactive" },
      { text = "Add Project Folder...", command = "treeview:add-project-folder" },
      { text = "Remove Project Folder...", command = "treeview:remove-project-folder" },
    })
  end
end)
