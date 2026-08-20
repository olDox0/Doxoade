-- doxoade/commands/lite_xl_systems/template/template/01_ipc_dispatcher.lua
-- =============================================================================
-- 01. SINGLE INSTANCE DISPATCHER (IPC)
-- =============================================================================
local ipc_queue_file = USERDIR .. PATHSEP .. ".ipc_queue"

core.add_thread(function()
  while true do
    local f = io.open(ipc_queue_file, "r")
    if f then
      local content = f:read("*a")
      f:close()
      os.remove(ipc_queue_file)

      if content and content:match("%S") then
        for line in content:gmatch("[^\r\n]+") do
          local target = line:match("^%s*(.-)%s*$")
          if target ~= "" then
            pcall(function()
              local abs_target = system.absolute_path(target) or target
              local info = system.get_file_info(abs_target) or system.get_file_info(target)
              if info then
                if info.type == "dir" then
                  core.add_project_directory(abs_target)
                  core.log("Projeto anexado à Árvore: " .. abs_target)
                else
                  local doc = core.open_doc(abs_target)
                  core.root_view:open_doc(doc)
                  core.log("Arquivo aberto com sucesso: " .. abs_target)
                end
              else
                core.error("Caminho inexistente no disco: " .. target)
              end
            end)
          end
        end
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