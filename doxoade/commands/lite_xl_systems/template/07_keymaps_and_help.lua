-- doxoade/commands/lite_xl_systems/template/07_keymaps_and_help.lua
--[[
  Mapeamento Central de Teclas, Atalhos Estilo Notepad++, Hub de Ajuda e Busca Global.
  - Ctrl+Alt+Shift+F: Busca Global Vulcan de alta velocidade delegada ao Doxoade Engine.
  - Enter: Salto instantâneo para o arquivo e linha exata no buffer de busca.
  - Ctrl+H: Localizar e substituir interativo em 2 passos.
]]
local core = require "core"
local command = require "core.command"
local keymap = require "core.keymap"

-- =============================================================================
-- KEYMAPS SOBERANOS (NOTEPAD++ PARITY & NAVEGAÇÃO RÁPIDA)
-- =============================================================================
keymap.add {
  ["ctrl+alt+shift+f"] = "doxoade:global-project-search",
  ["ctrl+alt+shift+d"] = "root:move-following-tabs-to-opposite-panel",
  ["ctrl+alt+d"]       = "root:move-tab-to-opposite-panel",
  ["ctrl+alt+i"]       = "doxoade:toggle-indent-guides",
  ["ctrl+o"]           = "doxoade:open-file",
  ["ctrl+alt+shift+k"] = "doxoade:diagnose-live",
}

-- Pastas e extensões ignoradas para máxima velocidade na busca
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
-- 🔍 EXECUÇÃO DE BUSCA VIA DOXOADE SEARCH BRIDGE (PYTHON / VULCAN)
-- =============================================================================
local function execute_global_search_bridge(query)
  if not query or query:match("^%s*$") then return end
  core.log("🔍 Buscando por: '" .. query .. "' (via Doxoade Search Engine)...")

  core.add_thread(function()
    local user_dir = USERDIR or "."
    local sep = PATHSEP or "/"
    local doxoade_dir = user_dir .. sep .. ".doxoade"
    pcall(system.mkdir, doxoade_dir)

    local pot_path = doxoade_dir .. sep .. "search_results.pot"
    local doc_title = string.format("[Busca] %s.pot", query:gsub('[\\/:*?"<>|]', "_"))

    -- Remove resultado antigo para garantir leitura limpa
    pcall(os.remove, pot_path)

    -- Dispara a busca em segundo plano via Python Engine
    local cmd = string.format('doxoade lite-xl search-bridge %q -o %q', query, pot_path)
    system.exec(cmd)

    -- Aguarda o término da busca (até 3 segundos)
    local attempts = 0
    while attempts < 30 do
      coroutine.yield(0.1)
      local info = system.get_file_info(pot_path)
      if info and (info.size or 0) > 0 then
        break
      end
      attempts = attempts + 1
    end

    local f = io.open(pot_path, "r")
    if f then
      local content = f:read("*a")
      f:close()

      local doc = core.open_doc()
      doc.filename = doc_title
      doc:insert(1, 1, content)
      doc:clean()

      core.root_view:open_doc(doc)
      core.log("✔ Busca Doxoade concluída com sucesso!")
      core.redraw = true
    else
      core.error("Falha ao obter resultados do Doxoade Search Engine.")
    end
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

                -- Yield suave a cada 20 arquivos
                if file_batch_counter >= 20 then
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

    -- Formatação do Buffer de Resultados
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
-- 🔍 MOTOR DE BUSCA GLOBAL ASSÍNCRONA NO PROJETO
-- =============================================================================
local function scan_project_files_async(root_dirs, on_file_fn)
  local function scan_dir(dir_path)
    local items = system.list_dir(dir_path) or {}
    for _, item in ipairs(items) do
      local is_ignored_dir = false
      for pat in pairs(IGNORED_SEARCH_DIRS) do
        if item:match(pat) then is_ignored_dir = true; break end
      end

      if not is_ignored_dir then
        local full_path = dir_path .. PATHSEP .. item
        local finfo = system.get_file_info(full_path)
        if finfo then
          if finfo.type == "dir" then
            scan_dir(full_path)
          elseif finfo.type == "file" and finfo.size < 2000000 then
            local ext = item:match("%.([%w_]+)$")
            if not ext or not IGNORED_SEARCH_EXTS[ext:lower()] then
              on_file_fn(full_path)
            end
          end
        end
      end
    end
  end

  for _, r in ipairs(root_dirs) do
    local path = type(r) == "table" and (r.path or r.name) or r
    if path and path ~= "" then
      scan_dir(path)
    end
  end
end

local function execute_global_search(query)
  if not query or query:match("^%s*$") then return end
  local start_time = os.clock()
  local search_results = {}
  local total_hits = 0
  local total_files_searched = 0
  local root_dirs = core.project_directories or { "." }
  local is_case_sensitive = (query:lower() ~= query)
  local query_pat = is_case_sensitive and query or query:lower()

  core.log("🔍 Buscando por: '" .. query .. "' no projeto...")

  core.add_thread(function()
    local files_batch = 0
    scan_project_files_async(root_dirs, function(fpath)
      total_files_searched = total_files_searched + 1
      files_batch = files_batch + 1

      -- Yield periódico a cada 15 arquivos para não travar a taxa de quadros
      if files_batch >= 15 then
        files_batch = 0
        coroutine.yield()
      end

      local f = io.open(fpath, "r")
      if f then
        local line_no = 1
        local file_matches = {}
        for line in f:lines() do
          local target_line = is_case_sensitive and line or line:lower()
          if target_line:find(query_pat, 1, true) then
            table.insert(file_matches, {
              line_no = line_no,
              text = line:gsub("^%s*", ""):gsub("%s*$", "")
            })
            total_hits = total_hits + 1
          end
          line_no = line_no + 1
        end
        f:close()

        if #file_matches > 0 then
          local clean_fn = system.absolute_path(fpath) or fpath
          clean_fn = clean_fn:gsub("\\", "/")
          table.insert(search_results, {
            path = clean_fn,
            matches = file_matches
          })
        end
      end
    end)

    -- Montagem do buffer de resultados formatado
    local elapsed = (os.clock() - start_time)
    local out = {
      "================================================================================",
      string.format("  🔍 RESULTADOS DA BUSCA GLOBAL: %q", query),
      string.format("  Encontrados: %d ocorrência(s) em %d arquivo(s) | Varredura: %d arquivos (%.2fs)", 
                    total_hits, #search_results, total_files_searched, elapsed),
      "  💡 Pressione [ENTER] em qualquer linha com 'arquivo:linha' para ir direto ao código!",
      "================================================================================\n"
    }

    if #search_results == 0 then
      table.insert(out, string.format("  (Nenhum resultado encontrado para %q)", query))
    else
      for _, res in ipairs(search_results) do
        table.insert(out, string.format("📄 %s", res.path))
        for _, m in ipairs(res.matches) do
          table.insert(out, string.format("   %s:%d: %s", res.path, m.line_no, m.text))
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
-- REGISTRO DE COMANDOS
-- =============================================================================
command.add(nil, {
  ["doxoade:global-project-search"] = function()
    local default_find = ""
    local view = core.active_view
    local doc = view and view.doc
    if doc and doc.has_selection and doc:has_selection() then
      local l1, c1, l2, c2 = doc:get_selection(true)
      if l1 == l2 then
        default_find = doc:get_text(l1, c1, l2, c2)
      end
    end

    core.command_view:enter("🔍 Buscar no Projeto (ex: def _paint_cell, get_doc_leaves, etc.)", {
      text = default_find,
      submit = function(query)
        execute_global_search_bridge(query)
      end
    })
  end,

  ["doxoade:open-file"] = function()
    -- Delega para o diálogo nativo do Lite XL
    command.perform("core:open-file")
  end,

  ["doxoade:find-file"] = function()
    -- Alternativa: abrir arquivo por nome no projeto (fuzzy match)
    command.perform("core:find-file")
  end,

  ["doxoade:jump-to-search-match"] = function()
    local view = core.active_view
    local doc = view and view.doc
    if not doc or not doc.filename or not tostring(doc.filename):find("^%[Busca%]") then
      command.perform("doc:newline")
      return
    end
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
Versão      : %s
Init.lua    : %s
Log Sessão  : %s
Status      : 100%% Íntegro e Operacional
================================================================================
]], os.date("%Y-%m-%d %H:%M:%S"), tostring(PLATFORM or "Unknown"), tostring(VERSION or "2.1.8"), init_file, session_log_file))
    core.root_view:open_doc(doc)
  end,

  ["doxoade:global-project-search"] = function()
    local default_find = ""
    local active_view = core.active_view
    if active_view and active_view.doc and active_view.doc.has_selection and active_view.doc:has_selection() then
      local l1, c1, l2, c2 = active_view.doc:get_selection(true)
      if l1 == l2 then
        default_find = active_view.doc:get_text(l1, c1, l2, c2)
      end
    end

    core.command_view:enter("🔍 Buscar no Projeto (ex: def _paint_cell, get_doc_leaves, etc.)", {
      text = default_find,
      submit = function(query)
        execute_global_search_bridge(query)
      end
    })
  end,

  ["doxoade:jump-to-search-match"] = function()
    local view = core.active_view
    local doc = view and view.doc
    if not doc or not doc.filename or not tostring(doc.filename):find("^%[Busca%]") then
      command.perform("doc:newline")
      return
    end

    local line_idx = doc:get_selection(true)
    local line_text = doc.lines[line_idx] or ""
    
    -- Captura caminhos no formato 'C:/caminho/arquivo.ext:linha:' ou 'caminho/arquivo.ext:linha:'
    local fpath, line_no = line_text:match("^%s*([a-zA-Z]:[\\/][^:]+):(%d+):")
    if not fpath then
      fpath, line_no = line_text:match("^%s*([^:]+%.[%w_]+):(%d+):")
    end

    if fpath and line_no then
      local clean_fpath = fpath:gsub("/", PATHSEP or "\\")
      local info = system.get_file_info(clean_fpath)
      if info then
        local target_doc = core.open_doc(clean_fpath)
        if target_doc then
          core.root_view:open_doc(target_doc)
          local ln = tonumber(line_no) or 1
          target_doc:set_selection(ln, 1, ln, 1)
          core.log("Salto para: " .. clean_fpath .. ":" .. ln)
          core.redraw = true
        end
      else
        core.error("Arquivo não encontrado no disco: " .. clean_fpath)
      end
    else
      command.perform("doc:newline")
    end
  end,

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
})

command.add(nil, {
  ["doxoade:new-doc"] = function()
    local doc = core.open_doc()
    core.root_view:open_doc(doc)
    core.redraw = true
  end,
  ["doxoade:toggle-indent-guides"] = function()
    local config = require "core.config"
    config.draw_indent_guides = not (config.draw_indent_guides ~= false)
    core.redraw = true
  end,
})

-- =============================================================================
-- GUIA DE ATALHOS COMPLETO
-- =============================================================================
command.add(nil, {
  ["doxoade:show-shortcuts-cheat-sheet"] = function()
    local doc = core.open_doc()
    doc.filename = "Guia_de_Atalhos_LiteXL.txt"
    doc:insert(1, 1, [[
================================================================================
      📖 GUIA DE ATALHOS RÁPIDOS - LITE XL SOVEREIGN
================================================================================
[ 🎨 VISUAL, CORES E ABAS ]
  Abas com Fundo Sólido   : Cores automáticas por Projeto Raiz
  Linha Amarela (Aba)     : Indicador de arquivo modificado e não salvo
  Linhas de Indentação    : Grade 4x4 (Python) e 2x2 (Lua) contínua
  Ctrl + Alt + I          : Ligar / Desligar Guias de Indentação
[ 🔍 BUSCA E NAVEGAÇÃO NOTEPAD++ ]
  Ctrl + F                : Localizar texto no arquivo ativo
  Ctrl + Alt + Shift + F  : 🔍 BUSCA GLOBAL NO PROJETO (Vulcan Doxoade Engine)
  Enter (no buffer Busca) : Salto instantâneo para o arquivo e linha
  Ctrl + H                : Localizar e Substituir interativo
  F3 / Shift + F3         : Próxima / Anterior ocorrência da busca
  Ctrl + G                : Ir para a linha (Go to line)
  F2 / Shift + F2         : Próximo / Anterior achado de auditoria Ma'at
[ 📋 COPIAR NOMES & CAMINHOS ]
  Botão Direito na Aba   : Menu flutuante (Copy Name, Proj. Address, Total Address)
  Ctrl + Alt + C         : Hub interativo de cópia de caminhos
  Ctrl + Shift + C       : Copiar endereço relativo no projeto
  Ctrl + Alt + E         : Revelar arquivo no Windows Explorer / Gerenciador
[ ✂️ DIVISÃO DE TELAS E ABAS ]
  Ctrl + Alt + D          : Mover aba ativa entre painéis (Esquerda ⇄ Direita)
  Ctrl + Alt + Shift + D  : Mover TODAS as abas posteriores para o painel oposto
  Ctrl + Alt + P          : Fixar Dumppot na direita
  Alt + D                 : Dividir tela à direita (Split Right)
  Alt + Shift + D         : Dividir tela abaixo (Split Down)
  Ctrl + W / Alt + W      : Fechar aba / divisão atual
  Ctrl + Tab              : Próxima aba
  Ctrl + Shift + Tab      : Aba anterior
[ ⚡ EDIÇÃO RÁPIDA ]
  Ctrl + N                : Novo documento em branco
  Ctrl + S                : Salvar arquivo
  Ctrl + Shift + S        : Salvar todos os arquivos
  Ctrl + D                : Duplicar linha atual
  Ctrl + L                : Deletar linha inteira
  Ctrl + Q                : Comentar/Descomentar linha
[ 📝 NOTAS, TAREFAS & AUDITORIA ]
  Ctrl + Alt + N          : Criar arquivo interativo
  Ctrl + Alt + Shift + N  : Hub do Doxoade Note & Agenda
  Ctrl + Alt + A          : Abrir Agenda de Tarefas
  Ctrl + Alt + K          : Disparar auditoria Ma'at Check no arquivo ativo
  F1 / Ctrl+Shift+/       : Abrir este Guia de Atalhos
================================================================================
]])
    core.root_view:open_doc(doc)
  end
})

-- =============================================================================
-- LOCALIZAR E SUBSTITUIR SEGURO EM 2 PASSOS
-- =============================================================================

-- =============================================================================
-- ⏎ SALTO PARA RESULTADO DE BUSCA (PREDICADO CONTEXTUAL)
-- Só intercepta 'return' quando um buffer [Busca] está ativo.
-- Fora dele, o evento segue para o handler nativo da view (submit/newline).
-- =============================================================================
local function is_search_buffer_active()
  local view = core.active_view
  local doc = view and view.doc
  return doc ~= nil
     and doc.filename ~= nil
     and tostring(doc.filename):find("^%[Busca%]") ~= nil
end

command.add(is_search_buffer_active, {
  ["doxoade:jump-to-search-match"] = function()
    local view = core.active_view
    local doc = view and view.doc
    -- 🛡️ Guarda defensiva: o Shadow Simulator invoca ações SEM checar predicado.
    if not doc or not doc.filename or not tostring(doc.filename):find("^%[Busca%]") then
      command.perform("doc:newline")
      return
    end
    local line_idx = doc:get_selection(true)
    local line_text = doc.lines[line_idx] or ""

    local fpath, line_no = line_text:match("^%s*([a-zA-Z]:[\\/][^:]+):(%d+):")
    if not fpath then
      fpath, line_no = line_text:match("^%s*([^:]+%.[%w_]+):(%d+):")
    end

    if fpath and line_no then
      local clean_fpath = fpath:gsub("/", PATHSEP or "\\")
      local info = system.get_file_info(clean_fpath)
      if info then
        local target_doc = core.open_doc(clean_fpath)
        if target_doc then
          core.root_view:open_doc(target_doc)
          local ln = tonumber(line_no) or 1
          target_doc:set_selection(ln, 1, ln, 1)
          core.log("Salto para: " .. clean_fpath .. ":" .. ln)
          core.redraw = true
        end
      else
        core.error("Arquivo não encontrado no disco: " .. clean_fpath)
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
      if l1 == l2 then
        default_find = doc:get_text(l1, c1, l2, c2)
      end
    end
    core.command_view:enter("1/2 Localizar texto para substituir", {
      text = default_find,
      submit = function(find_query)
        if not find_query or find_query == "" then return end
        if find_query:find("\n") then
          core.error("Busca com quebra de linha não suportada neste modo.")
          return
        end
        local prompt_label = string.format("2/2 Substituir '%s' por:", find_query)
        core.command_view:enter(prompt_label, {
          submit = function(replace_query)
            replace_query = replace_query or ""
            local count = 0
            local escaped_pat = find_query:gsub("[%(%)%.%%%+%-%*%?%[%]%^%$]", "%%%1")
            for line_idx = 1, #doc.lines do
              local line_text = doc.lines[line_idx]
              local s, e = line_text:find(escaped_pat)
              if s then
                local new_text = line_text:gsub(escaped_pat, replace_query)
                doc.lines[line_idx] = new_text
                count = count + 1
              end
            end
            if count > 0 then
              doc.session_modified = doc.session_modified or {}
              core.log(string.format("✔ Substituídas %d ocorrência(s).", count))
              core.redraw = true
            else
              core.log("Nenhuma ocorrência encontrada.")
            end
          end
        })
      end
    })
  end
})

-- =====================================================
-- ⌨️ 3. MAPEAMENTO GLOBAL CANÔNICO NOTEPAD++ / DOXOADE
-- =====================================================
keymap.add {
  -- Painéis, abas e navegação
  ["alt+d"] = "root:split-right",
  ["alt+shift+d"] = "root:split-down",
  ["ctrl+alt+d"] = "root:move-tab-to-opposite-panel",
  ["ctrl+w"] = "root:close",
  ["alt+w"] = "root:close",
  ["ctrl+tab"] = "root:switch-to-next-tab",
  ["ctrl+shift+tab"] = "root:switch-to-previous-tab",

  -- Opcional: somente se esses comandos existirem na sua versão do Lite XL.
  ["ctrl+alt+left"] = "root:switch-to-left",
  ["ctrl+alt+right"] = "root:switch-to-right",

  -- Sistema Doxoade
  ["ctrl+,"] = "doxoade:open-init-lua",
  ["ctrl+alt+\\"] = "doxoade:open-pantheon",
  ["ctrl+alt+u"] = "doxoade:toggle-litexl-in-tree",
  ["ctrl+alt+p"] = "doxoade:open-pot-in-right-panel",
  ["ctrl+shift+l"] = "doxoade:open-log",
  ["ctrl+f2"] = "doxoade:open-log",

  -- Cheat sheet
  ["f1"] = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+shift+/"] = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+alt+/"] = "doxoade:show-shortcuts-cheat-sheet",

  -- Notas, agenda e auditoria
  ["ctrl+alt+n"] = "doxoade:create-file-interactive",
  ["ctrl+alt+shift+n"] = "doxoade:note-hub-menu",
  ["ctrl+alt+a"] = "doxoade:open-agenda-view",
  ["ctrl+alt+i"] = "doxoade:toggle-indent-guides",
  ["ctrl+alt+k"] = "doxoade:trigger-active-check",
  ["ctrl+alt+shift+k"] = "doxoade:diagnose-live",
  ["f2"] = "doxoade:next-audit-incident",
  ["shift+f2"] = "doxoade:prev-audit-incident",

  -- Opcional: atalho alternativo para Note Hub.
  -- ["ctrl+alt+m"] = "doxoade:note-hub-menu",

  -- Caminhos / Explorer
  ["ctrl+alt+c"] = "doxoade:copy-path-menu",
  ["ctrl+shift+c"] = "doxoade:tab-copy-relative-path",
  --["ctrl+alt+shift+c"] = "doxoade:tab-copy-full-path",
  ["ctrl+alt+e"] = "doxoade:tab-open-in-explorer",

  -- Projetos / Treeview
  ["ctrl+alt+o"] = "treeview:add-project-folder",
  ["ctrl+alt+r"] = "treeview:remove-project-folder",

  -- Busca e navegação Notepad++
  ["ctrl+f"] = "find-replace:find",
  ["ctrl+h"] = "doxoade:interactive-find-replace",
  ["f3"] = "find-replace:repeat-find",
  ["shift+f3"] = "find-replace:previous-find",
  ["ctrl+g"] = "doc:go-to-line",

  -- Opcional: se o auditor canônico exigir Ctrl+H nativo, use:
  ["ctrl+h"] = "find-replace:replace",
  ["ctrl+alt+h"] = "doxoade:interactive-find-replace",

  -- Edição rápida
  ["ctrl+n"] = "doxoade:new-doc",
  ["ctrl+o"] = "core:open-file",
  ["ctrl+s"] = "doc:save",
  ["ctrl+shift+s"] = "doc:save-all",
  ["ctrl+d"] = "doc:duplicate-lines",
  ["ctrl+l"] = "doc:delete-lines",
  ["ctrl+q"] = "doc:toggle-line-comments",

  -- Opcional: somente se o comando existir.
  ["ctrl+alt+f"] = "doxoade:find-selection-in-opposite-split",
}
