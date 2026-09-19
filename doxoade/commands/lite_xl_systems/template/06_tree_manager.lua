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
  local clean = tostring(file_path):gsub("\\", "/")
  local dir = clean:match("^(.*)/")
  if not dir or dir == "" then return end

  local current = ""
  local drive = dir:match("^([a-zA-Z]:)")
  if drive then
    current = drive
    dir = dir:sub(#drive + 1)
  end

  for part in dir:gmatch("[^/]+") do
    current = current .. "/" .. part
    local info = system.get_file_info(current)
    if not info then
      pcall(system.mkdir, current)
    end
  end
end

local function get_real_workspace_root()
  -- 1. Procura a raiz de trabalho real (ignora test_deploy e sandbox)
  if core.project_directories then
    for _, p in ipairs(core.project_directories) do
      local p_str = tostring(type(p) == "table" and (p.path or p.name) or p)
      local clean = p_str:gsub("\\", "/"):lower()
      if not clean:find("test_deploy") and not clean:find("sandbox") then
        local abs = system.absolute_path(p_str) or p_str
        return abs:gsub("\\", "/"):gsub("/+$", "")
      end
    end
  end

  -- 2. Fallback para primeira raiz disponível ou CWD
  if core.project_directories and #core.project_directories > 0 then
    local p1 = core.project_directories[1]
    local p_str = tostring(type(p1) == "table" and (p1.path or p1.name) or p1)
    local abs = system.absolute_path(p_str) or p_str
    return abs:gsub("\\", "/"):gsub("/+$", "")
  end

  local cwd = system.absolute_path(".") or "."
  return cwd:gsub("\\", "/"):gsub("/+$", "")
end

local function resolve_smart_file_path(input_path)
  if not input_path or input_path:match("^%s*$") then return nil end

  -- 1. Normalização de barras e limpeza de aspas/espaços
  local clean_input = input_path:gsub("\\", "/"):gsub("^%s+", ""):gsub("%s+$", "")
  clean_input = clean_input:gsub('^["\']', ''):gsub('["\']$', '')

  -- 2. Se já for absoluto (C:/... ou /... ou ~)
  if clean_input:find("^[a-zA-Z]:") or clean_input:sub(1, 1) == "/" or clean_input:sub(1, 1) == "~" then
    return normalize_path(clean_input)
  end

  -- 3. Resolução fiel: anexa exatamente o que o desenvolvedor digitou à raiz do projeto
  local project_root = get_real_workspace_root()
  return project_root .. "/" .. clean_input
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
    core.command_view:enter("Criar Arquivo (Ctrl+Alt+N)", {
      submit = function(input_path)
        local full_path = resolve_smart_file_path(input_path)
        if not full_path then return end

        ensure_parent_directories(full_path)

        -- Cria o arquivo no disco se não existir
        local f = io.open(full_path, "a")
        if f then f:close() end

        -- Abre o arquivo criado em uma nova aba
        local doc = core.open_doc(full_path)
        if doc then
          core.root_view:open_doc(doc)
          core.log("✔ [Ctrl+Alt+N] Arquivo criado e aberto: " .. full_path)
          core.redraw = true
        else
          core.error("✖ Falha ao abrir o arquivo criado: " .. full_path)
        end
      end,
      suggest = function(text)
        -- Auto-reversão dinâmica de barras em tempo real ao colar/digitar '\'
        if text and text:find("\\") then
          local converted = text:gsub("\\", "/")
          pcall(function()
            if core.command_view and core.command_view.set_text then
              core.command_view:set_text(converted)
            end
          end)
        end
        return {}
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
