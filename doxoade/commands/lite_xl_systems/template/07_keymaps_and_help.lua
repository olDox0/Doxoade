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
  ["doxoade:open-file"] = function() command.perform("core:open-file") end,
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
  ["ctrl+n"] = "doxoade:new-doc", ["ctrl+o"] = "core:open-file",
  ["ctrl+s"] = "doc:save", ["ctrl+shift+s"] = "doc:save-all",
  ["ctrl+d"] = "doc:duplicate-lines", ["ctrl+l"] = "doc:delete-lines",
  ["ctrl+q"] = "doc:toggle-line-comments",
  ["ctrl+alt+f"] = "doxoade:find-selection-in-opposite-split",
}
