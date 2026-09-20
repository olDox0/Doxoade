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

-- =============================================================================
-- 🧭 RESOLUÇÃO INTELIGENTE MULTI-PROJETO (Ctrl+Alt+N)
-- Deduz a pasta certa entre VÁRIOS projetos anexados na TreeView, mesmo quando
-- o caminho digitado omite uma pasta filha com o mesmo nome da raiz
-- (ex: digitar "doxoade/commands/x/y.py" quando a pasta real é
-- "doxoade/doxoade/commands/x/y.py").
-- =============================================================================
local CREATE_FILE_IGNORED_DIRS = {
  ["^%.git$"] = true, ["^venv$"] = true, ["^%.venv$"] = true, ["^env$"] = true,
  ["^__pycache__$"] = true, ["^node_modules$"] = true, ["^dist$"] = true, ["^build$"] = true,
  ["^%.idea$"] = true, ["^%.vscode$"] = true, ["^%.doxoade_cache$"] = true, ["^w64devkit$"] = true,
}

local function _is_ignored_dirname(name)
  for pat in pairs(CREATE_FILE_IGNORED_DIRS) do
    if name:match(pat) then return true end
  end
  return false
end

local function _is_excluded_root(clean_lower)
  if clean_lower:find("test_deploy") or clean_lower:find("sandbox") then return true end
  local user_dir = USERDIR or ""
  if user_dir ~= "" then
    local abs_user = (system.absolute_path(user_dir) or user_dir):gsub("\\", "/"):lower():gsub("/+$", "")
    if abs_user ~= "" and (clean_lower == abs_user or clean_lower:sub(1, #abs_user + 1) == abs_user .. "/") then
      return true
    end
  end
  return false
end

-- Todas as raízes de projeto "reais" anexadas na TreeView (multi-projeto),
-- excluindo test_deploy, sandbox e a pasta de config do próprio Lite XL.
local function get_all_real_project_roots()
  local roots, seen = {}, {}
  if core.project_directories then
    for _, p in ipairs(core.project_directories) do
      local p_str = tostring(type(p) == "table" and (p.path or p.name) or p)
      local abs = system.absolute_path(p_str) or p_str
      local clean = abs:gsub("\\", "/"):gsub("/+$", "")
      local clean_lower = clean:lower()
      if not seen[clean_lower] and not _is_excluded_root(clean_lower) then
        seen[clean_lower] = true
        table.insert(roots, clean)
      end
    end
  end
  if #roots == 0 then
    local cwd = (system.absolute_path(".") or "."):gsub("\\", "/"):gsub("/+$", "")
    table.insert(roots, cwd)
  end
  return roots
end

-- Coleta recursivamente todas as subpastas (path absoluto + caminho relativo
-- à raiz + nome da raiz de origem) de todos os projetos reais anexados.
local function _collect_directories(dir, rel_prefix, out, depth, root_basename)
  if depth > 20 then return end
  table.insert(out, { path = dir, relative = rel_prefix, root_basename = root_basename })
  local ok, items = pcall(system.list_dir, dir)
  if not ok or not items then return end
  for _, item in ipairs(items) do
    if not _is_ignored_dirname(item) then
      local full = dir .. "/" .. item
      local finfo_ok, finfo = pcall(system.get_file_info, full)
      if finfo_ok and finfo and finfo.type == "dir" then
        local new_rel = (rel_prefix == "") and item or (rel_prefix .. "/" .. item)
        _collect_directories(full, new_rel, out, depth + 1, root_basename)
      end
    end
  end
end

local function get_all_directories()
  local roots = get_all_real_project_roots()
  local dirs = {}
  for _, root in ipairs(roots) do
    local basename = (root:match("([^/]+)$") or root):lower()
    _collect_directories(root, "", dirs, 0, basename)
  end
  return dirs, roots
end

local function _path_segments(path)
  local segments = {}
  for seg in tostring(path):gsub("\\", "/"):gmatch("[^/]+") do
    table.insert(segments, seg:lower())
  end
  return segments
end

-- Casa needle_segs (pastas digitadas) como subsequência ORDENADA, de trás para
-- frente, dentro de hay_segs (pasta/arquivo real existente). Pastas extras no
-- meio ou no início do caminho real só são toleradas de graça quando são
-- "explicáveis" — ou seja, repetem um nome que o usuário já digitou (ex: a
-- própria pasta duplicada "doxoade/doxoade") ou o nome da raiz do projeto de
-- origem. Uma pasta extra qualquer sem relação nenhuma (ex: "check-templates")
-- é fortemente penalizada, para não empatar com o match correto. Retorna um
-- score (menor = melhor) ou nil se não houver correspondência.
local function _match_score(needle_segs, hay_segs, root_basename)
  local nn, nh = #needle_segs, #hay_segs
  if nn == 0 or nh == 0 then return nil end
  if needle_segs[nn] ~= hay_segs[nh] then return nil end

  local explainable = {}
  for _, s in ipairs(needle_segs) do explainable[s] = true end
  if root_basename then explainable[root_basename] = true end

  local hi, ni, gaps, unexplained = nh, nn, 0, 0
  while ni >= 1 do
    if hi < 1 then return nil end
    if hay_segs[hi] == needle_segs[ni] then
      ni = ni - 1
      hi = hi - 1
    else
      gaps = gaps + 1
      if not explainable[hay_segs[hi]] then unexplained = unexplained + 1 end
      hi = hi - 1
    end
  end

  -- Prefixo restante (não consumido pelo match) também conta como "extra"
  local leftover = hi
  for i = 1, hi do
    if not explainable[hay_segs[i]] then unexplained = unexplained + 1 end
  end

  -- Pastas "não explicáveis" pesam muito mais: nunca deixam um match ruim
  -- empatar com um match limpo/explicável.
  return (unexplained * 1000) + gaps + leftover
end



-- Extensões ignoradas ao escanear ARQUIVOS existentes (binários, caches, etc.)
local CREATE_FILE_IGNORED_EXTS = {
  ["pyc"] = true, ["pyo"] = true, ["pyd"] = true, ["exe"] = true, ["dll"] = true,
  ["so"] = true, ["dylib"] = true, ["zip"] = true, ["tar"] = true, ["gz"] = true,
  ["png"] = true, ["jpg"] = true, ["jpeg"] = true, ["gif"] = true, ["ico"] = true,
  ["db"] = true, ["sqlite"] = true, ["sqlite3"] = true, ["bin"] = true,
}

local function _collect_files(dir, rel_prefix, out, depth, root_basename)
  if depth > 20 then return end
  local ok, items = pcall(system.list_dir, dir)
  if not ok or not items then return end
  for _, item in ipairs(items) do
    local full = dir .. "/" .. item
    local finfo_ok, finfo = pcall(system.get_file_info, full)
    if finfo_ok and finfo then
      if finfo.type == "dir" then
        if not _is_ignored_dirname(item) then
          local new_rel = (rel_prefix == "") and item or (rel_prefix .. "/" .. item)
          _collect_files(full, new_rel, out, depth + 1, root_basename)
        end
      elseif finfo.type == "file" then
        local ext = item:match("%.([%w_]+)$")
        if not ext or not CREATE_FILE_IGNORED_EXTS[ext:lower()] then
          local new_rel = (rel_prefix == "") and item or (rel_prefix .. "/" .. item)
          table.insert(out, { path = full, relative = new_rel, root_basename = root_basename })
        end
      end
    end
  end
end

-- Escaneia TODOS os arquivos existentes de TODOS os projetos reais anexados.
local function get_all_files()
  local roots = get_all_real_project_roots()
  local files = {}
  for _, root in ipairs(roots) do
    local basename = (root:match("([^/]+)$") or root):lower()
    _collect_files(root, "", files, 0, basename)
  end
  return files
end

-- Resolve um caminho digitado (arquivo OU pasta) contra TODOS os projetos
-- reais anexados na TreeView, usando o mesmo match por segmentos. Usado por
-- "Adicionar Projeto" quando o usuário cola um caminho de arquivo em vez de
-- uma pasta, ou quando o caminho digitado é relativo a um projeto que não é
-- o diretório de trabalho (CWD) do processo.
local function resolve_smart_existing_path(input_path)
  if not input_path or input_path:match("^%s*$") then return nil end
  local clean = input_path:gsub("\\", "/"):gsub("^%s+", ""):gsub("%s+$", "")
  clean = clean:gsub('^["\']', ''):gsub('["\']$', '')

  if clean:find("^[a-zA-Z]:") or clean:sub(1, 1) == "/" or clean:sub(1, 1) == "~" then
    return normalize_path(clean)
  end

  local needle_segs = _path_segments(clean)
  local best_path, best_score = nil, math.huge

  for _, d in ipairs(get_all_directories()) do
    if d.relative ~= "" then
      local score = _match_score(needle_segs, _path_segments(d.relative), d.root_basename)
      if score and score < best_score then
        best_path, best_score = d.path, score
      end
    end
  end

  for _, f in ipairs(get_all_files()) do
    local score = _match_score(needle_segs, _path_segments(f.relative), f.root_basename)
    if score and score < best_score then
      best_path, best_score = f.path, score
    end

  end

  if best_path then return best_path end

  -- Fallback antigo: resolve relativo ao diretório de trabalho do processo
  return normalize_path(clean)
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

  local filename = clean_input:match("([^/]+)$") or clean_input
  local dir_part = clean_input:sub(1, #clean_input - #filename):gsub("/+$", "")

  local roots = get_all_real_project_roots()
  local primary_root = roots[1] or get_real_workspace_root()

  -- 3. Sem subpasta no input (só o nome do arquivo): cria na raiz principal
  if dir_part == "" then
    return primary_root .. "/" .. filename
  end

  -- 4. Resolve a MELHOR pasta existente entre TODOS os projetos anexados,
  --    por segmentos de caminho (lida com pastas filhas de mesmo nome e com
  --    múltiplos projetos simultâneos na TreeView).
  local all_dirs = get_all_directories()
  local needle_segs = _path_segments(dir_part)
  local best_dir, best_score = nil, math.huge
  for _, d in ipairs(all_dirs) do
    if d.relative ~= "" then
      local score = _match_score(needle_segs, _path_segments(d.relative), d.root_basename)
      if score and score < best_score then
        best_dir, best_score = d.path, score
      end
    end
  end

  if best_dir then
    return best_dir .. "/" .. filename
  end

  -- 5. Fallback: nenhuma pasta existente corresponde (estrutura totalmente
  --    nova) — cria a partir da raiz principal, criando as pastas
  --    intermediárias que faltarem.
  return primary_root .. "/" .. clean_input
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
        path = resolve_smart_existing_path(path)
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
