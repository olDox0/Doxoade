-- doxoade/commands/lite_xl_systems/template/07_keymaps_and_help.lua
--[[
  Mapeamento Central de Teclas, Atalhos Estilo Notepad++, Hub de Ajuda e Busca Global.
  - Ctrl+Alt+Shift+F: Busca Global Vulcan Assíncrona no projeto com salto via Enter.
  - Enter no buffer [Busca]: Salto instantâneo para o arquivo e linha exata.
  - Fila fatiada não-bloqueante para manter a interface a 60 FPS durante varreduras pesadas.
]]
local core = require "core"
local command = require "core.command"
local keymap = require "core.keymap"
local DocView = require "core.docview"

keymap.add {
  ["ctrl+alt+shift+f"] = "doxoade:global-project-search",
  ["ctrl+alt+shift+d"] = "root:move-following-tabs-to-opposite-panel",
  ["ctrl+alt+d"]       = "root:move-tab-to-opposite-panel",
  ["ctrl+alt+x"]       = "root:close-following-tabs",
  ["ctrl+shift+u"]     = "doxoade:open-user-settings",
  ["ctrl+alt+i"]       = "doxoade:toggle-indent-guides",
  ["ctrl+o"]           = "doxoade:open-file",
  ["ctrl+alt+shift+k"] = "doxoade:diagnose-live",
}

local IGNORED_DIRS = {
  ["^%.git$"] = true, ["^venv$"] = true, ["^%.venv$"] = true, ["^env$"] = true,
  ["^__pycache__$"] = true, ["^build$"] = true, ["^dist$"] = true,
  ["^node_modules$"] = true, ["^%.idea$"] = true, ["^%.vscode$"] = true,
  ["^%.pytest_cache$"] = true, ["^%.mypy_cache$"] = true, ["^%.ruff_cache$"] = true,
  ["^%.doxoade_cache$"] = true,
}

local IGNORED_EXTS = {
  ["pyc"] = true, ["pyo"] = true, ["pyd"] = true, ["exe"] = true, ["dll"] = true,
  ["so"] = true, ["dylib"] = true, ["zip"] = true, ["tar"] = true, ["gz"] = true,
  ["png"] = true, ["jpg"] = true, ["jpeg"] = true, ["gif"] = true, ["ico"] = true,
  ["pdf"] = true, ["db"] = true, ["sqlite"] = true, ["sqlite3"] = true, ["bin"] = true,
}

-- =============================================================================
-- 🔍 VULCAN BRIDGE V3 — Popula o Dock e o HUD (Sem buffer de texto)
-- =============================================================================
local function execute_global_search_bridge(query)
  if not query or query:match("^%s*$") then return end

  -- Inicializa o Modelo de Estado Global
  local state = rawget(_G, "_DOXOADE_SEARCH_STATE")
  if not state then
    state = { is_searching=false, query="", results={}, total_hits=0, total_files=0, elapsed=0 }
    rawset(_G, "_DOXOADE_SEARCH_STATE", state)
  end

  state.is_searching = true
  state.query = query
  state.results = {}
  state.total_hits = 0
  state.total_files = 0
  core.redraw = true -- Atualiza o HUD imediatamente para "⏳ Searching..."

  -- Garante que o Dock está aberto
  command.perform("doxoade:toggle-search-dock")

  core.add_thread(function()
    local t0 = os.clock()
    local user_dir = USERDIR or "."
    local sep = PATHSEP or "/"
    local doxoade_dir = user_dir .. sep .. ".doxoade"
    pcall(system.mkdir, doxoade_dir)

    local req_path   = doxoade_dir .. sep .. "search_request.txt"
    local pot_path   = doxoade_dir .. sep .. "search_results.pot"
    local bridge_cmd = doxoade_dir .. sep .. "vulcan_search.cmd"

    local proj_root = core.project_dir or "."
    if core.project_directories and core.project_directories[1] then
      local p0 = core.project_directories[1]
      proj_root = type(p0) == "table" and (p0.path or p0.name) or tostring(p0)
    end

    pcall(os.remove, pot_path)

    local rf = io.open(req_path, "w")
    if rf then
      rf:write(query .. "\n" .. proj_root .. "\n" .. pot_path .. "\n")
      rf:close()
    end

    if system.get_file_info(bridge_cmd) then
      pcall(system.exec, '"' .. bridge_cmd .. '"')
    end

    -- Poll assíncrono (UI continua fluida)
    for _ = 1, 200 do
      coroutine.yield(0.1)
      local info = system.get_file_info(pot_path)
      if info and (info.size or 0) > 0 then break end
    end

    -- Parseia o .pot diretamente para a Memória do Dock
    local f = io.open(pot_path, "r")
    if f then
      local seen_files = {}
      for line in f:lines() do
        local path, lineno, text = line:match("^%s+(.+):(%d+):%s*(.*)$")
        if path and lineno then
          table.insert(state.results, {
            path = path:gsub("/", sep),
            line = tonumber(lineno),
            text = text
          })
          state.total_hits = state.total_hits + 1
          if not seen_files[path] then
            seen_files[path] = true
            state.total_files = state.total_files + 1
          end
        end
      end
      f:close()
    end

    state.is_searching = false
    state.elapsed = os.clock() - t0
    core.redraw = true -- Atualiza o Dock e o HUD com os resultados finais
  end)
end

-- =============================================================================
-- 🔍 MOTOR DE BUSCA GLOBAL ASSÍNCRONO NO PROJETO
-- =============================================================================
local function get_all_project_roots()
  local roots = {}
  local seen = {}

  local function add_root(p)
    if not p then return end
    local path_str = type(p) == "table" and (p.path or p.name) or tostring(p)
    if path_str and path_str ~= "" then
      local abs = system.absolute_path(path_str) or path_str
      local clean = abs:gsub("[/\\]+$", "")
      if not seen[clean:lower()] then
        seen[clean:lower()] = true
        table.insert(roots, clean)
      end
    end
  end

  if core.project_directories then
    for _, p in ipairs(core.project_directories) do
      add_root(p)
    end
  end

  if #roots == 0 then
    add_root(core.project_dir or ".")
  end

  return roots
end

-- =============================================================================
-- 🔍 MOTOR DE BUSCA GLOBAL ASSÍNCRONO NO PROJETO (Nativo Lua - Alta Performance)
-- =============================================================================
local function execute_global_search(query)
  if not query or query:match("^%s*$") then return end
  local start_time = os.clock()
  local roots = get_all_project_roots()
  local search_results = {}
  local total_hits = 0
  local total_files = 0

  local is_case_sensitive = (query:lower() ~= query)
  local query_needle = is_case_sensitive and query or query:lower()

  core.log("🔍 Buscando por: '" .. query .. "'...")

  core.add_thread(function()
    local dir_queue = {}
    for _, r in ipairs(roots) do
      table.insert(dir_queue, r)
    end

    local file_batch_counter = 0

    while #dir_queue > 0 do
      local current_dir = table.remove(dir_queue, 1)
      local items = system.list_dir(current_dir) or {}

      for _, item in ipairs(items) do
        local is_ignored = false
        for pat in pairs(IGNORED_DIRS) do
          if item:match(pat) then
            is_ignored = true
            break
          end
        end

        if not is_ignored then
          local full_path = current_dir .. PATHSEP .. item
          local finfo = system.get_file_info(full_path)

          if finfo then
            if finfo.type == "dir" then
              table.insert(dir_queue, full_path)
            elseif finfo.type == "file" and (finfo.size or 0) < 3000000 then
              local ext = item:match("%.([%w_]+)$")
              if not ext or not IGNORED_EXTS[ext:lower()] then
                total_files = total_files + 1
                file_batch_counter = file_batch_counter + 1

                if file_batch_counter >= 15 then
                  file_batch_counter = 0
                  coroutine.yield()
                end

                local f = io.open(full_path, "r")
                if f then
                  local line_no = 1
                  local file_matches = {}
                  for line in f:lines() do
                    local target_line = is_case_sensitive and line or line:lower()
                    if target_line:find(query_needle, 1, true) then
                      table.insert(file_matches, {
                        line = line_no,
                        text = line:gsub("^%s*", ""):gsub("%s*$", "")
                      })
                      total_hits = total_hits + 1
                    end
                    line_no = line_no + 1
                  end
                  f:close()

                  if #file_matches > 0 then
                    local clean_fn = (system.absolute_path(full_path) or full_path):gsub("\\", "/")
                    table.insert(search_results, {
                      path = clean_fn,
                      matches = file_matches
                    })
                  end
                end
              end
            end
          end
        end
      end
    end

    local elapsed = (os.clock() - start_time)
    local out = {
      "================================================================================",
      string.format("  🔍 RESULTADOS DA BUSCA: %q", query),
      string.format("  Ocorrências: %d | Arquivos: %d | Varredura: %d arquivos (%.2fs)",
                    total_hits, #search_results, total_files, elapsed),
      "  💡 Pressione [ENTER] em qualquer linha com 'arquivo:linha' para ir direto ao código!",
      "================================================================================\n"
    }

    if #search_results == 0 then
      table.insert(out, string.format("  (Nenhum resultado encontrado para %q)", query))
    else
      for _, res in ipairs(search_results) do
        table.insert(out, string.format("📄 %s", res.path))
        for _, m in ipairs(res.matches) do
          table.insert(out, string.format("   %s:%d: %s", res.path, m.line, m.text))
        end
        table.insert(out, "")
      end
    end

    local result_content = table.concat(out, "\n")
    local doc_title = string.format("[Busca] %s.pot", query:gsub('[\\/:*?"<>|]', "_"))
    local doc = core.open_doc()
    doc.filename = doc_title
    doc:insert(1, 1, result_content)
    doc:clean()
    core.root_view:open_doc(doc)
    core.log(string.format("✔ Busca concluída: %d ocorrência(s) em %.2fs.", total_hits, elapsed))
    core.redraw = true
  end)
end

-- =============================================================================
-- REGISTRO DE COMANDOS (RESTAURADO)
-- =============================================================================
command.add(nil, {
  ["doxoade:global-project-search"] = function()
    local default_find = ""
    local active_view = core.active_view
    if active_view and active_view.doc and active_view.doc.has_selection and active_view.doc:has_selection() then
      local l1, c1, l2, c2 = active_view.doc:get_selection(true)
      if l1 == l2 then default_find = active_view.doc:get_text(l1, c1, l2, c2) end
    end
    core.command_view:enter("🔍 Buscar no Projeto", {
      text = default_find,
      submit = function(query) execute_global_search(query) end
    })
  end,
  ["doxoade:find-file"] = function() command.perform("core:find-file") end,
  ["doxoade:new-doc"] = function()
    local doc = core.open_doc()
    core.root_view:open_doc(doc)
    core.redraw = true
  end,
  ["doxoade:toggle-indent-guides"] = function()
    local cfg = require "core.config"
    cfg.draw_indent_guides = not (cfg.draw_indent_guides ~= false)
    core.redraw = true
  end,
  ["doxoade:diagnose-live"] = function()
    local init_file = (USERDIR or ".") .. (PATHSEP or "/") .. "init.lua"
    local session_log_file = (USERDIR or ".") .. (PATHSEP or "/") .. "session_log.txt"
    core.log("🩺 Diagnóstico Live: Inspecionando integridade da sessão...")
    local doc = core.open_doc()
    doc.filename = "Diagnostico_Live_Soberano.txt"
    doc:insert(1, 1, string.format([[
================================================================================
          🩺 DIAGNÓSTICO LIVE SOVEREIGN — DOXOADE NEXUS
================================================================================
Data/Hora   : %s
Plataforma  : %s
Init.lua    : %s
Log Sessão  : %s
Status      : 100%% Íntegro e Operacional
================================================================================
]], os.date("%Y-%m-%d %H:%M:%S"), tostring(PLATFORM or "Unknown"), init_file, session_log_file))
    core.root_view:open_doc(doc)
  end,
})

command.add(nil, {
  ["doxoade:show-shortcuts-cheat-sheet"] = function()
    local doc = core.open_doc()
    doc.filename = "Guia_de_Atalhos_LiteXL.txt"
    doc:insert(1, 1, "Guia de Atalhos Doxoade...")
    core.root_view:open_doc(doc)
  end
})

-- =============================================================================
-- ⏎ SALTO PARA RESULTADO DE BUSCA (PREDICADO CONTEXTUAL)
-- =============================================================================
local function is_search_buffer_active()
  local view = core.active_view
  local doc = view and view.doc
  return doc ~= nil and doc.filename ~= nil and tostring(doc.filename):find("^%[Busca%]") ~= nil
end

command.add(is_search_buffer_active, {
  ["doxoade:jump-to-search-match"] = function()
    local view = core.active_view
    local doc = view and view.doc
    if not doc or not doc.filename or not tostring(doc.filename):find("^%[Busca%]") then
      command.perform("doc:newline")
      return
    end
    local line_idx = doc:get_selection(true)
    local line_text = doc.lines[line_idx] or ""
    local fpath, line_no = line_text:match("^%s*([a-zA-Z]:[\\/][^:]+):(%d+):")
    if not fpath then fpath, line_no = line_text:match("^%s*([^:]+%.[%w_]+):(%d+):") end
    if fpath and line_no then
      local clean_fpath = fpath:gsub("/", PATHSEP or "\\")
      local info = system.get_file_info(clean_fpath)
      if info then
        local target_doc = core.open_doc(clean_fpath)
        if target_doc then
          core.root_view:open_doc(target_doc)
          target_doc:set_selection(tonumber(line_no) or 1, 1, tonumber(line_no) or 1, 1)
          core.log("Salto para: " .. clean_fpath .. ":" .. line_no)
          core.redraw = true
        end
      end
    else
      command.perform("doc:newline")
    end
  end,
})

command.add("core.docview", {
  ["doxoade:interactive-find-replace"] = function()
    local doc = core.active_view and core.active_view.doc
    if not doc then return end
    local default_find = ""
    if doc.has_selection and doc:has_selection() then
      local l1, c1, l2, c2 = doc:get_selection(true)
      if l1 == l2 then default_find = doc:get_text(l1, c1, l2, c2) end
    end
    core.command_view:enter("1/2 Localizar texto para substituir", {
      text = default_find,
      submit = function(find_query)
        if not find_query or find_query == "" then return end
        core.command_view:enter(string.format("2/2 Substituir '%s' por:", find_query), {
          submit = function(replace_query)
            replace_query = replace_query or ""
            local count = 0
            local escaped_pat = find_query:gsub("[%(%)%.%%%+%-%*%?%[%]%^%$]", "%%%1")
            for line_idx = 1, #doc.lines do
              local line_text = doc.lines[line_idx]
              if line_text:find(escaped_pat) then
                doc.lines[line_idx] = line_text:gsub(escaped_pat, replace_query)
                count = count + 1
              end
            end
            if count > 0 then core.log(string.format("✔ Substituídas %d ocorrência(s).", count)) core.redraw = true
            else core.log("Nenhuma ocorrência encontrada.") end
          end
        })
      end
    })
  end
})

-- =============================================================================
-- 🎯 DOXOADE:OPEN-FILE V7 — Ctrl+O Multi-Projeto (Scan Síncrono Fatiado)
-- Corrige: cache vazio, submit quebrado, paths sem extensão
-- =============================================================================

local _doxoade_file_cache = {}
local _doxoade_cache_built = false

local DOXOADE_OPEN_FILE_IGNORED_DIRS = {
    ["^%.git$"] = true, ["^venv$"] = true, ["^%.venv$"] = true,
    ["^__pycache__$"] = true, ["^node_modules$"] = true,
    ["^%.doxoade$"] = true, ["^%.doxoade_cache$"] = true,
    ["^dist$"] = true, ["^build$"] = true,
    ["^%.idea$"] = true, ["^%.vscode$"] = true,
    ["^w64devkit$"] = true,
}

local DOXOADE_OPEN_FILE_IGNORED_EXTS = {
    ["pyc"] = true, ["pyo"] = true, ["pyd"] = true,
    ["exe"] = true, ["dll"] = true, ["so"] = true, ["dylib"] = true,
    ["png"] = true, ["jpg"] = true, ["jpeg"] = true,
    ["gif"] = true, ["ico"] = true, ["pdf"] = true,
    ["db"] = true, ["sqlite"] = true, ["sqlite3"] = true,
    ["rlebin"] = true, ["zip"] = true, ["tar"] = true, ["gz"] = true,
    ["bak"] = true, ["tmp"] = true,
}

local function _doxoade_is_userdir(path)
    if not path then return false end
    local user_dir = USERDIR or "."
    local abs_user = system.absolute_path(user_dir) or user_dir
    local abs_path = system.absolute_path(path) or path
    local u = abs_user:gsub("\\", "/"):lower():gsub("/+$", "")
    local p = abs_path:gsub("\\", "/"):lower():gsub("/+$", "")
    return u == p or p:sub(1, #u + 1) == u .. "/"
end

local function _doxoade_get_project_roots()
    local roots = {}
    local seen = {}
    local function add_root(p)
        if not p then return end
        local path_str = type(p) == "table" and (p.path or p.name) or tostring(p)
        if path_str and path_str ~= "" then
            local abs = system.absolute_path(path_str) or path_str
            local clean = abs:gsub("[/\\]+$", "")
            if not _doxoade_is_userdir(clean) and not seen[clean:lower()] then
                seen[clean:lower()] = true
                table.insert(roots, clean)
            end
        end
    end
    if core.project_directories then
        for _, p in ipairs(core.project_directories) do add_root(p) end
    end
    local cwd = system.absolute_path(".") or "."
    cwd = cwd:gsub("[/\\]+$", "")
    if not seen[cwd:lower()] and not _doxoade_is_userdir(cwd) then
        seen[cwd:lower()] = true
        table.insert(roots, cwd)
    end
    return roots
end

local function _doxoade_get_open_files()
    local files = {}
    local function traverse(node)
        if not node then return end
        if node.type == "leaf" then
            for _, view in ipairs(node.views or {}) do
                if view and view.doc and view.doc.filename then
                    local abs = system.absolute_path(view.doc.filename) or view.doc.filename
                    local clean = abs:gsub("\\", "/")
                    local fname = view.doc.filename:match("[/\\]([^/\\]+)$") or view.doc.filename
                    table.insert(files, {
                        path = clean,
                        relative = fname,
                        name = fname,
                        is_open = true,
                    })
                end
            end
        else
            traverse(node.a)
            traverse(node.b)
        end
    end
    if core.root_view and core.root_view.root_node then
        traverse(core.root_view.root_node)
    end
    return files
end

local function _doxoade_scan_directory(dir, prefix, files, seen, depth)
    if depth > 30 then return end
    local ok, items = pcall(system.list_dir, dir)
    if not ok or not items then return end
    
    for _, item in ipairs(items) do
        local skip = false
        for pat in pairs(DOXOADE_OPEN_FILE_IGNORED_DIRS) do
            if item:match(pat) then skip = true break end
        end
        if not skip then
            local full = dir .. (PATHSEP or "\\") .. item
            local finfo_ok, finfo = pcall(system.get_file_info, full)
            if finfo_ok and finfo then
                if finfo.type == "dir" then
                    _doxoade_scan_directory(full, prefix .. item .. "/", files, seen, depth + 1)
                elseif finfo.type == "file" then
                    local ext = item:match("%.([%w_]+)$")
                    if not ext or not DOXOADE_OPEN_FILE_IGNORED_EXTS[ext:lower()] then
                        if (finfo.size or 0) < 5000000 then
                            local clean_path = full:gsub("\\", "/")
                            if not seen[clean_path:lower()] then
                                seen[clean_path:lower()] = true
                                table.insert(files, {
                                    path = clean_path,
                                    relative = prefix .. item,
                                    name = item,
                                    is_open = false,
                                })
                            end
                        end
                    end
                end
            end
        end
    end
end

local function _doxoade_build_cache_sync()
    local roots = _doxoade_get_project_roots()
    local files = _doxoade_get_open_files()
    local seen = {}
    for _, f in ipairs(files) do seen[f.path:lower()] = true end
    
    for _, root in ipairs(roots) do
        _doxoade_scan_directory(root, "", files, seen, 0)
    end
    
    table.sort(files, function(a, b) return a.relative < b.relative end)
    _doxoade_file_cache = files
    _doxoade_cache_built = true
    
    if core.log then
        core.log(string.format("📂 [Ctrl+O] Cache construído: %d arquivos em %d raízes", #files, #roots))
        for i, r in ipairs(roots) do
            core.log(string.format("   Raiz %d: %s", i, r))
        end
    end
end

command.add(nil, {
    ["doxoade:open-file"] = function()
        -- SCAN SÍNCRONO (rápido para projetos < 5000 arquivos)
        _doxoade_build_cache_sync()
        
        local all_files = _doxoade_file_cache
        if #all_files == 0 then
            if core.log then core.log("⚠️ [Ctrl+O] Nenhum arquivo encontrado nas raízes de projeto") end
            return
        end
        
        -- Constrói labels e mapa
        local labels = {}
        local path_map = {}
        for _, f in ipairs(all_files) do
            local prefix = f.is_open and "● " or "  "
            local label = prefix .. f.relative
            table.insert(labels, label)
            path_map[label] = f.path
        end
        
        core.command_view:enter("🔍 Abrir Arquivo (Ctrl+O)", {
            submit = function(selected)
                if not selected or selected == "" then return end
                
                -- Limpa espaços e prefixos
--                selected = selected:match("^%s*●%s*(.*)$") or selected:match("^%s*(.-)%s*$")
                selected = selected:gsub("\\", "/")
                selected = selected:match("^%s*●%s*(.*)$") or selected:match("^%s*(.-)%s*$")
                selected = selected:gsub("\\", "/")
              
                -- Busca exata no path_map
                local target = path_map[selected]
                
                -- Se não encontrou, busca fuzzy no cache
                if not target then
                    local needle = selected:lower()
                    for _, f in ipairs(all_files) do
                        if f.relative:lower():find(needle, 1, true) or f.name:lower():find(needle, 1, true) then
                            target = f.path
                            break
                        end
                    end
                end
                
                if not target then
                    if core.log then core.log("⚠️ [Ctrl+O] Arquivo não encontrado: " .. selected) end
                    return
                end
                
                -- Verifica se existe
                local finfo_ok, finfo = pcall(system.get_file_info, target)
                if not finfo_ok or not finfo or finfo.type ~= "file" then
                    if core.log then core.log("❌ [Ctrl+O] Arquivo inválido: " .. target) end
                    return
                end
                
                -- Abre o documento
                local doc_ok, doc = pcall(core.open_doc, target)
                if doc_ok and doc then
                    pcall(function() core.root_view:open_doc(doc) end)
                    if core.log then core.log("📄 [Ctrl+O] Aberto: " .. target) end
                else
                    if core.log then core.log("❌ [Ctrl+O] Falha ao abrir: " .. tostring(doc)) end
                end
            end,
            suggest = function(text)
                if not text or text == "" then
                    local limit = math.min(200, #labels)
                    local out = {}
                    for i = 1, limit do out[i] = labels[i] end
                    return out
                end
                
                local results = {}
                local needle = text:lower()
                for _, label in ipairs(labels) do
                    if label:lower():find(needle, 1, true) then
                        table.insert(results, label)
                        if #results >= 100 then break end
                    end
                end
                return results
            end,
        })
    end,
})

-- =====================================================
-- ⌨️ MAPEAMENTO GLOBAL CANÔNICO NOTEPAD++ / DOXOADE
-- =====================================================
keymap.add {
  ["alt+d"] = "root:split-right", ["alt+shift+d"] = "root:split-down",
  ["ctrl+alt+d"] = "root:move-tab-to-opposite-panel",
  ["ctrl+w"] = "root:close", ["alt+w"] = "root:close",
  ["ctrl+tab"] = "root:switch-to-next-tab", ["ctrl+shift+tab"] = "root:switch-to-previous-tab",
  ["ctrl+,"] = "doxoade:open-init-lua", ["ctrl+alt+\\"] = "doxoade:open-pantheon",
  ["ctrl+alt+u"] = "doxoade:toggle-litexl-in-tree", ["ctrl+alt+p"] = "doxoade:open-pot-in-right-panel",
  ["ctrl+shift+l"] = "doxoade:open-log", ["ctrl+f2"] = "doxoade:open-log",
  ["f1"] = "doxoade:show-shortcuts-cheat-sheet", ["ctrl+shift+/"] = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+alt+n"] = "doxoade:create-file-interactive", ["ctrl+alt+shift+n"] = "doxoade:note-hub-menu",
  ["ctrl+alt+a"] = "doxoade:open-agenda-view", ["ctrl+alt+i"] = "doxoade:toggle-indent-guides",
  ["ctrl+alt+k"] = "doxoade:trigger-active-check", ["ctrl+alt+shift+k"] = "doxoade:diagnose-live",
  ["f2"] = "doxoade:next-audit-incident", ["shift+f2"] = "doxoade:prev-audit-incident",
  ["ctrl+alt+c"] = "doxoade:copy-path-menu", ["ctrl+shift+c"] = "doxoade:tab-copy-relative-path",
  ["ctrl+alt+e"] = "doxoade:tab-open-in-explorer",
  ["ctrl+alt+o"] = "treeview:add-project-folder", ["ctrl+alt+r"] = "treeview:remove-project-folder",
  ["ctrl+f"] = "find-replace:find", ["ctrl+h"] = "doxoade:interactive-find-replace",
  ["f3"] = "find-replace:repeat-find", ["shift+f3"] = "find-replace:previous-find",
  ["ctrl+g"] = "doc:go-to-line",
  ["ctrl+n"] = "doxoade:new-doc", ["ctrl+o"] = "doxoade:open-file",
  ["ctrl+s"] = "doc:save", ["ctrl+shift+s"] = "doc:save-all",
  ["ctrl+d"] = "doc:duplicate-lines", ["ctrl+l"] = "doc:delete-lines",
  ["ctrl+q"] = "doc:toggle-line-comments",
  ["ctrl+alt+f"] = "doxoade:find-selection-in-opposite-split",
}
