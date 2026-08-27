-- doxoade/commands/lite_xl_systems/template/01_ipc_dispatcher.lua
-- =============================================================================
-- 01. SINGLE INSTANCE DISPATCHER & NATIVE SOVEREIGN SESSION ENGINE
-- =============================================================================
local core = require "core"
local DocView = require "core.docview"

local ipc_queue_file = USERDIR .. PATHSEP .. ".ipc_queue"
local ipc_processing_file = USERDIR .. PATHSEP .. ".ipc_processing"
local session_file = USERDIR .. PATHSEP .. ".doxoade" .. PATHSEP .. "sovereign_session.lua"

-- =============================================================================
-- 💾 MOTOR DE SERIALIZAÇÃO DE SESSÃO (ABAS, SPLITS E CURSORES)
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

local function save_sovereign_session()
  if not core.root_view or not core.root_view.root_node then return end

  local leaves = get_doc_leaves(core.root_view.root_node)
  local active_node = core.root_view:get_active_node()

  local session = {
    panels = {},
    active_panel_idx = 1
  }

  for idx, node in ipairs(leaves) do
    if node == active_node then
      session.active_panel_idx = idx
    end

    local panel_data = {
      files = {},
      active_file = nil
    }

    for _, view in ipairs(node.views or {}) do
      if view and view.doc and view.doc.filename then
        local abs_fn = system.absolute_path(view.doc.filename) or view.doc.filename
        local line, col = 1, 1
        if view.doc.get_selection then
          line, col = view.doc:get_selection(true)
        end

        table.insert(panel_data.files, {
          filename = abs_fn,
          line = line,
          col = col
        })

        if node.active_view == view then
          panel_data.active_file = abs_fn
        end
      end
    end

    if #panel_data.files > 0 then
      table.insert(session.panels, panel_data)
    end
  end

  pcall(function()
    system.mkdir(USERDIR .. PATHSEP .. ".doxoade")
    local f = io.open(session_file, "w")
    if f then
      f:write("return {\n")
      f:write(string.format("  active_panel_idx = %d,\n", session.active_panel_idx))
      f:write("  panels = {\n")
      for _, p in ipairs(session.panels) do
        f:write("    {\n")
        f:write(string.format("      active_file = %q,\n", tostring(p.active_file or "")))
        f:write("      files = {\n")
        for _, file_info in ipairs(p.files) do
          local esc_fn = tostring(file_info.filename):gsub("\\", "/")
          f:write(string.format("        { filename = %q, line = %d, col = %d },\n",
            esc_fn, file_info.line, file_info.col))
        end
        f:write("      }\n")
        f:write("    },\n")
      end
      f:write("  }\n")
      f:write("}\n")
      f:flush()
      f:close()
    end
  end)
end

local function restore_sovereign_session()
  local info = system.get_file_info(session_file)
  if not info then return end

  local ok, session = pcall(dofile, session_file)
  if not ok or type(session) ~= "table" or not session.panels or #session.panels == 0 then
    return
  end

  local leaves = get_doc_leaves(core.root_view.root_node)
  local total_reopened = 0
  local primary_node = leaves[1] or core.root_view.root_node:get_primary_node()

  for p_idx, panel_data in ipairs(session.panels) do
    local target_node = nil
    if p_idx == 1 then
      target_node = primary_node
    elseif p_idx == 2 then
      leaves = get_doc_leaves(core.root_view.root_node)
      if #leaves >= 2 then
        target_node = leaves[2]
      else
        target_node = primary_node:split("right")
      end
    end

    if target_node then
      local active_to_set = nil
      for _, file_info in ipairs(panel_data.files or {}) do
        if file_info.filename and file_info.filename ~= "" then
          local finfo = system.get_file_info(file_info.filename)
          if finfo then
            local doc = core.open_doc(file_info.filename)
            if doc then
              local view = DocView(doc)
              target_node:add_view(view)
              total_reopened = total_reopened + 1

              if file_info.line and file_info.line > 1 then
                pcall(function()
                  doc:set_selection(file_info.line, file_info.col or 1, file_info.line, file_info.col or 1)
                end)
              end

              if panel_data.active_file == file_info.filename then
                active_to_set = view
              end
            end
          end
        end
      end

      if active_to_set then
        target_node.active_view = active_to_set
      end

      -- Remove documento em branco não salvo inicial se arquivos reais foram abertos
      if #target_node.views > 1 then
        for v_idx = #target_node.views, 1, -1 do
          local v = target_node.views[v_idx]
          if v and v.doc and not v.doc.filename and not v.doc:is_dirty() then
            table.remove(target_node.views, v_idx)
            break
          end
        end
      end
    end
  end

  if total_reopened > 0 then
    core.redraw = true
    core.log(string.format("Sessão Soberana restaurada: %d aba(s) preservadas.", total_reopened))
  end
end

-- =============================================================================
-- 📬 DESPACHANTE IPC & CICLO DE VIDA
-- =============================================================================
local function process_line(target)
  if target == "__DOXOADE_GRACEFUL_QUIT__" then
    save_sovereign_session()
    core.quit()
    return "quit"
  elseif target ~= "" then
    pcall(function()
      local abs_target = system.absolute_path(target) or target
      local info = system.get_file_info(abs_target) or system.get_file_info(target)
      if info and info.type == "dir" then
        core.add_project_directory(abs_target)
        core.log("Projeto anexado à Árvore: " .. abs_target)
      else
        local doc = core.open_doc(abs_target)
        core.root_view:open_doc(doc)
        core.log("Arquivo aberto: " .. abs_target)
      end
    end)
  end
  return nil
end

-- Thread de Inicialização da Sessão
core.add_thread(function()
  coroutine.yield(0.05)
  pcall(restore_sovereign_session)

  -- Loop de auto-save periódico a cada 5 segundos
  local last_save = os.time()
  while true do
    if os.time() - last_save >= 5 then
      save_sovereign_session()
      last_save = os.time()
    end
    coroutine.yield(1.0)
  end
end)

-- Thread Principal do IPC Dispatcher
core.add_thread(function()
  while true do
    local info = system.get_file_info(ipc_queue_file)
    if info and info.size and info.size > 0 then
      local content = nil
      pcall(os.remove, ipc_processing_file)

      local renamed = os.rename(ipc_queue_file, ipc_processing_file)
      if renamed then
        local f = io.open(ipc_processing_file, "r")
        if f then
          content = f:read("*a")
          f:close()
        end
        pcall(os.remove, ipc_processing_file)
      else
        local f = io.open(ipc_queue_file, "r")
        if f then
          content = f:read("*a")
          f:close()
        end
        local f_clean = io.open(ipc_queue_file, "w")
        if f_clean then f_clean:close() end
        pcall(os.remove, ipc_queue_file)
      end

      if content and content:match("%S") then
        local quit = false
        for line in content:gmatch("[^\r\n]+") do
          local target = line:match("^%s*(.-)%s*$")
          if process_line(target) == "quit" then
            quit = true
            break
          end
        end
        if quit then return end

        core.redraw = true
        pcall(function()
          if system.show_window then system.show_window() end
          if system.raise_window then system.raise_window() end
        end)
      end
    end

    coroutine.yield(0.1)
  end
end)
