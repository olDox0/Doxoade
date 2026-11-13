-- doxoade/commands/lite_xl_systems/template/01_ipc_dispatcher.lua
--[[
  🪽 DOXOADE IPC DISPATCHER & SOVEREIGN SESSION MANAGER (V2.1)
  - Persistência blindada e Restauração da Sessão (Treeview + Abas).
  - Filtro de argumentos CLI ignora corretamente o --userdir.
]]

local core = require "core"
local DocView = require "core.docview"

local user_dir = USERDIR or "."
local sep = PATHSEP or "/"
local doxoade_dir = user_dir .. sep .. ".doxoade"
pcall(function() system.mkdir(doxoade_dir) end)

local ipc_queue_file = user_dir .. sep .. ".ipc_queue"
local ipc_processing_file = user_dir .. sep .. ".ipc_processing"
local session_file = doxoade_dir .. sep .. "sovereign_session.lua"
local last_proj_file = doxoade_dir .. sep .. "last_project.txt"

local _can_save_session = false

-- =============================================================================
-- 1. AUXILIARES DE NAVEGAÇÃO DE NÓS (LEAVES)
-- =============================================================================
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

-- =============================================================================
-- 2. GRAVAÇÃO DA SESSÃO SOBERANA
-- =============================================================================
local function save_sovereign_session()
  if not _can_save_session then return end
  if not core.root_view or not core.root_view.root_node then return end

  local project_paths = {}
  local user_norm = (system.absolute_path(USERDIR) or USERDIR):gsub("\\", "/"):lower():gsub("/+$", "")
  if core.project_directories then
    for _, p in ipairs(core.project_directories) do
      local ppath = type(p) == "table" and (p.path or p.name) or p
      if ppath and type(ppath) == "string" and ppath ~= "" then
        local is_busca = ppath:find("^%[Busca%]") ~= nil
        local abs = system.absolute_path(ppath) or ppath
        local clean = abs:gsub("[/\\]+$", ""):gsub("\\", "/")
        local p_norm = clean:lower()
        local is_userdir = (p_norm == user_norm) or (p_norm:sub(1, #user_norm + 1) == user_norm .. "/")
        if not is_busca and not is_userdir then
          table.insert(project_paths, clean)
        end
      end
    end
  end
  if #project_paths == 0 and core.project_dir then
    local abs = system.absolute_path(core.project_dir) or core.project_dir
    local clean = abs:gsub("[/\\]+$", ""):gsub("\\", "/")
    local rn = clean:lower()
    local is_userdir = (rn == user_norm) or (rn:sub(1, #user_norm + 1) == user_norm .. "/")
    if not is_userdir then table.insert(project_paths, clean) end
  end

  local leaves = get_doc_leaves(core.root_view.root_node)
  local active_node = core.root_view:get_active_node()
  local panels = {}
  local active_panel_idx = 1
  for idx, node in ipairs(leaves) do
    if node == active_node then active_panel_idx = idx end
    local panel_data = { files = {}, active_file = nil }
    for _, view in ipairs(node.views or {}) do
      if view and view.doc and view.doc.filename then
        local abs_fn = system.absolute_path(view.doc.filename) or view.doc.filename
        local fn_lower = tostring(abs_fn):lower()
        local is_busca = fn_lower:find("%[busca%]") ~= nil
        local is_canonical = fn_lower:match("/canonical$") ~= nil
        if not is_busca and not is_canonical then
          local line, col = 1, 1
          if view.doc.get_selection then line, col = view.doc:get_selection(true) end
          table.insert(panel_data.files, { filename = abs_fn:gsub("\\", "/"), line = line, col = col })
          if node.active_view == view then panel_data.active_file = abs_fn:gsub("\\", "/") end
        end
      end
    end
    if #panel_data.files > 0 then table.insert(panels, panel_data) end
  end

  pcall(function()
    local f = io.open(session_file, "w")
    if f then
      f:write("return {\n")
      f:write(string.format("  active_panel_idx = %d,\n", active_panel_idx))
      f:write("  projects = {\n")
      for _, p in ipairs(project_paths) do f:write(string.format("    %q,\n", p)) end
      f:write("  },\n  panels = {\n")
      for _, p in ipairs(panels) do
        f:write("    {\n")
        f:write(string.format("      active_file = %q,\n      files = {\n", tostring(p.active_file or "")))
        for _, fi in ipairs(p.files) do
          f:write(string.format("        { filename = %q, line = %d, col = %d },\n", fi.filename, fi.line, fi.col))
        end
        f:write("      }\n    },\n")
      end
      f:write("  }\n}\n")
      f:flush(); f:close()
    end
    if #project_paths > 0 then
      local lf = io.open(last_proj_file, "w")
      if lf then lf:write(project_paths[1] .. "\n"); lf:flush(); lf:close() end
    end
  end)
end

-- =============================================================================
-- 3. RESTAURAÇÃO DA SESSÃO
-- =============================================================================
local _session_restored = false

local function has_cli_project_argument()
  local args = rawget(_G, "ARGS") or {}
  local skip_next = false
  for i, arg in ipairs(args) do
    if i > 1 and type(arg) == "string" then   -- ARGS[1] é o executável
      if skip_next then
        skip_next = false
      elseif arg == "--userdir" or arg == "-u" then
        skip_next = true
      elseif arg:match("^%-%-") or arg:match("^%-") then
      elseif arg:lower() == "canonical" then
      else
        local ok, info = pcall(system.get_file_info, arg)
        if ok and info then return true end
      end
    end
  end
  return false
end

local function restore_sovereign_session()
  if _session_restored then return end
  _session_restored = true

  local info = system.get_file_info(session_file)
  if not info then return end

  local ok, session = pcall(dofile, session_file)
  if not ok or type(session) ~= "table" then return end

  if not has_cli_project_argument() and session.projects and #session.projects > 0 then
    local user_norm = (system.absolute_path(USERDIR) or USERDIR):gsub("\\", "/"):lower():gsub("/+$", "")
    for _, proj in ipairs(session.projects) do
      local pinfo = system.get_file_info(proj)
      if pinfo and pinfo.type == "dir" then
        local p_norm = (system.absolute_path(proj) or proj):gsub("\\", "/"):lower():gsub("/+$", "")
        local is_userdir = (p_norm == user_norm) or (p_norm:sub(1, #user_norm + 1) == user_norm .. "/")
        if not is_userdir then
          local already = false
          for _, existing in ipairs(core.project_directories or {}) do
            local ep = type(existing) == "table" and (existing.path or existing.name) or existing
            local en = (system.absolute_path(ep) or ep):gsub("\\", "/"):lower():gsub("/+$", "")
            if en == p_norm then already = true; break end
          end
          if not already and core.add_project_directory then
            pcall(core.add_project_directory, proj)
          end
        end
      end
    end
  end

  if not session.panels or #session.panels == 0 then return end

  local primary_node = (function()
    local leaves = get_doc_leaves(core.root_view.root_node)
    return leaves[1] or core.root_view.root_node:get_primary_node()
  end)()

  for p_idx, panel_data in ipairs(session.panels) do
    local valid_files = {}
    for _, f_info in ipairs(panel_data.files or {}) do
      if f_info.filename and f_info.filename ~= "" then
        local fn_lower = tostring(f_info.filename):lower():gsub("\\", "/")
        local is_init_bytecode = fn_lower:match("/init%.lua$") or fn_lower:match("/init%.luac$") or fn_lower:match("%.luac$")
        if not is_init_bytecode then
          local finfo = system.get_file_info(f_info.filename)
          if finfo and finfo.type == "file" then
            table.insert(valid_files, f_info)
          end
        end
      end
    end

    if #valid_files > 0 then
      local target_node = nil
      if p_idx == 1 then
        target_node = primary_node
      elseif p_idx == 2 then
        local leaves = get_doc_leaves(core.root_view.root_node)
        local is_portrait = (core.root_view and core.root_view.size and core.root_view.size.y > core.root_view.size.x)
        local default_split = is_portrait and "down" or "right"
        target_node = (#leaves >= 2) and leaves[2] or primary_node:split(default_split)
      end

      if target_node then
        local existing_map = {}
        for _, v in ipairs(target_node.views or {}) do
          if v and v.doc and v.doc.filename then
            local clean_k = (system.absolute_path(v.doc.filename) or v.doc.filename):gsub("\\", "/"):lower()
            existing_map[clean_k] = v
          end
        end

        local active_to_set = nil
        for _, f_info in ipairs(valid_files) do
          local clean_fn = tostring(f_info.filename):gsub("\\", "/"):lower()
          local view_to_use = existing_map[clean_fn]

          if not view_to_use then
            local doc = core.open_doc(f_info.filename)
            if doc then
              if f_info.line and f_info.col and doc.set_selection then
                doc:set_selection(f_info.line, f_info.col, f_info.line, f_info.col)
              end
              view_to_use = DocView(doc)
              if target_node.add_view then
                target_node:add_view(view_to_use)
              end
              existing_map[clean_fn] = view_to_use
            end
          end

          if panel_data.active_file and clean_fn == panel_data.active_file:lower() then
            active_to_set = view_to_use
          end
        end

        if active_to_set then
          target_node.active_view = active_to_set
          core.set_active_view(active_to_set)
        end
      end
    end
  end

  core.redraw = true
  if core.log then
    core.log("✔ Sessão Soberana restaurada sem duplicações.")
  end
end

-- =============================================================================
-- 4. DESPACHANTE IPC
-- =============================================================================
local function process_ipc_line(line)
  if not line or line == "" then return end
  line = line:gsub("^%s*", ""):gsub("%s*$", "")
  line = line:gsub('^["\']', ''):gsub('["\']$', '')

  if line == "__DOXOADE_GRACEFUL_QUIT__" then
    if core.quit then
      pcall(save_sovereign_session)
      core.quit()
    end
    return
  end

  local target_fn = line
  local target_line = nil
  local target_col = 1

  local fn_c, l_c, c_c = line:match("^(.-):(%d+):(%d+)$")
  if fn_c and l_c and c_c then
    target_fn = fn_c
    target_line = tonumber(l_c)
    target_col = tonumber(c_c)
  else
    local fn_l, l_l = line:match("^(.-):(%d+)$")
    if fn_l and l_l then
      target_fn = fn_l
      target_line = tonumber(l_l)
      target_col = 1
    end
  end

  local info = system.get_file_info(target_fn)
  if info and info.type == "dir" then
    if core.add_project_directory then
      core.add_project_directory(target_fn)
      if core.log then core.log("📂 [IPC] Diretório anexado: " .. target_fn) end
    end
    core.redraw = true
    return
  end

  local doc = core.open_doc(target_fn)
  if doc then
    core.root_view:open_doc(doc)
    if target_line and target_line > 0 then
      if doc.set_selection then
        doc:set_selection(target_line, target_col, target_line, target_col)
      end
    end
    core.redraw = true
    if core.log then
      local fname = target_fn:match("[^/\\]+$") or target_fn
      if target_line then
        core.log(string.format("📂 [IPC] Aberto: %s (linha %d)", fname, target_line))
      else
        core.log("📂 [IPC] Aberto: " .. fname)
      end
    end
  end
end

-- =============================================================================
-- 5. THREADS DE SESSÃO E MONITORAMENTO
-- =============================================================================
core.add_thread(function()
  coroutine.yield(0.05)
  restore_sovereign_session()

  local save_timer = 0
  while true do
    coroutine.yield(0.25)
    save_timer = save_timer + 0.25

    local info = system.get_file_info(ipc_queue_file)
    if info and (info.size or 0) > 0 then
      pcall(function()
        os.rename(ipc_queue_file, ipc_processing_file)
        local f = io.open(ipc_processing_file, "r")
        if f then
          for l in f:lines() do
            process_ipc_line(l)
          end
          f:close()
          os.remove(ipc_processing_file)
        end
      end)
    end

    if save_timer >= 2.0 then
      save_timer = 0
      save_sovereign_session() 
    end
  end
end)

local orig_add_project = core.add_project_directory
if orig_add_project then
  core.add_project_directory = function(...)
    local res = orig_add_project(...)
    pcall(save_sovereign_session)
    return res
  end
end

-- =============================================================================
-- 📂 SINGLE INSTANCE — Processamento de Argumentos CLI (ARGS) [V2.1]
-- =============================================================================
local _cli_args_processed = false
local _BINARY_EXTS = {
    ["exe"] = true, ["dll"] = true, ["so"] = true, ["dylib"] = true,
    ["pyd"] = true, ["pyc"] = true, ["pyo"] = true, ["bin"] = true,
    ["dat"] = true, ["db"] = true, ["sqlite"] = true, ["sqlite3"] = true,
}

rawset(_G, "is_binary_path", function(path)
    if not path then return true end
    local p = tostring(path):lower()
    if p:find("lite%-xl%.exe$") or p:find("lite%-xl$") then return true end
    local ext = p:match("%.([%w_]+)$")
    if ext and _BINARY_EXTS[ext] then return true end
    return false
end)

local function process_cli_arguments()
    if _cli_args_processed then return end
    _cli_args_processed = true

    local args = rawget(_G, "ARGS") or {}
    if #args == 0 then return end

    local files_to_open = {}
    local dirs_to_add = {}
    local user_dir_normalized = (USERDIR or "."):gsub("\\", "/"):lower():gsub("/+$", "")
    local skip_next = false

    for i, arg in ipairs(args) do
        -- ARGS[1] é o executável — nunca é um projeto
        if i > 1 and type(arg) == "string" then
            if skip_next then
                skip_next = false
            elseif arg == "--userdir" or arg == "-u" then
                skip_next = true
            elseif not arg:match("^%-%-")
               and not arg:match("^%-")
               and arg:lower() ~= "canonical"
               and not _G.is_binary_path(arg) then
                local ok_info, info = pcall(system.get_file_info, arg)
                if ok_info and info then
                    local arg_normalized = (system.absolute_path(arg) or arg):gsub("\\", "/"):lower():gsub("/+$", "")
                    if arg_normalized == user_dir_normalized 
                       or arg_normalized:sub(1, #user_dir_normalized + 1) == user_dir_normalized .. "/" then
                        -- Ignora o USERDIR como projeto
                    elseif info.type == "file" then
                        table.insert(files_to_open, arg)
                    elseif info.type == "dir" then
                        table.insert(dirs_to_add, arg)
                    end
                end
            end
        end
    end

    for _, dir_path in ipairs(dirs_to_add) do
        if core.add_project_directory then
            pcall(core.add_project_directory, dir_path)
        end
    end

    for _, file_path in ipairs(files_to_open) do
        local ok_open, doc = pcall(core.open_doc, file_path)
        if ok_open and doc then
            pcall(core.root_view.open_doc, core.root_view, doc)
        end
    end

    if #files_to_open > 0 or #dirs_to_add > 0 then
        core.redraw = true
    end
end

core.add_thread(function()
    coroutine.yield(1.5)
    pcall(process_cli_arguments)
end)

-- =============================================================================
-- 🔄 IPC QUEUE MONITOR
-- =============================================================================
core.add_thread(function()
    while true do
        coroutine.yield(0.5)
        pcall(function()
            local ipc_file = user_dir .. sep .. ".ipc_queue"
            local f = io.open(ipc_file, "r")
            if not f then return end

            local lines = {}
            for line in f:lines() do
                if line and line ~= "" then
                    table.insert(lines, line)
                end
            end
            f:close()

            if #lines == 0 then return end

            local fw = io.open(ipc_file, "w")
            if fw then fw:close() end

            for _, line in ipairs(lines) do
                process_ipc_line(line)
            end
            core.redraw = true
        end)
    end
end)

-- =============================================================================
-- 💾 HADES SESSION LOCK — Auto-Save com Anti-Loop (V2.1)
-- =============================================================================
local _hades_last_signature = ""
local _hades_save_in_progress = false
local _hades_last_save_time = 0

local function hades_autosave_if_changed()
    if _hades_save_in_progress then return end
    local now = os.clock()
    if (now - _hades_last_save_time) < 3.0 then return end

    pcall(function()
        local sig = {}
        sig[#sig+1] = tostring(core.project_directories and #core.project_directories or 0)
        local leaves = get_doc_leaves(core.root_view and core.root_view.root_node)
        local views = 0
        for _, n in ipairs(leaves) do views = views + #(n.views or {}) end
        sig[#sig+1] = tostring(views)
        sig[#sig+1] = tostring(core.active_view and core.active_view.doc
            and core.active_view.doc.filename or "")
        local signature = table.concat(sig, "|")
        if signature ~= _hades_last_signature then
            _hades_last_signature = signature
            _hades_save_in_progress = true
            _hades_last_save_time = now
            pcall(save_sovereign_session)
            _hades_save_in_progress = false
        end
    end)
end

local _boot_complete = false
core.add_thread(function()
  coroutine.yield(3.0)
  _boot_complete = true
  _can_save_session = true -- 🛡️ Libera o save aqui
  if core.log then
    core.log("💾 [SESSION] Boot completo. Estado será salvo.")
  end
end)

local original_core_quit = core.quit
core.quit = function(...)
  if _boot_complete then
    pcall(save_sovereign_session)
  end
  if original_core_quit then
    return original_core_quit(...)
  end
end

pcall(function()
    if type(core.on_quit) == "function" then
        local original_on_quit = core.on_quit
        core.on_quit = function(...)
            pcall(save_sovereign_session)
            return original_on_quit(...)
        end
    end
end)

core.add_thread(function()
    coroutine.yield(5.0)
    while true do
        coroutine.yield(30)
        hades_autosave_if_changed()
    end
end)

if core.log then
    core.log("💾 [HADES LOCK] Auto-save de sessão ativo.")
end

pcall(function()
    local original_open_doc = core.open_doc
    core.open_doc = function(...)
        local doc = original_open_doc(...)
        pcall(function()
            local Khonsu = rawget(_G, "Khonsu")
            if Khonsu and Khonsu.debounce then
                Khonsu.debounce("hades_session_save", 1.0, save_sovereign_session)
            end
        end)
        return doc
    end
end)
