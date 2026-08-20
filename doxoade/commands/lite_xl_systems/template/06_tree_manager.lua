-- doxoade/commands/lite_xl_systems/template/template/06_tree_manager.lua
-- =============================================================================
-- 06. GESTÃO DINÂMICA DE PROJETOS NA TREEVIEW (Ctrl+Alt+O / Ctrl+Alt+R)
-- =============================================================================
local function normalize_path(path)
  if not path then return nil end
  path = path:gsub('^["\']', ''):gsub('["\']$', '')
  if path:sub(1, 1) == "~" then
    local home = os.getenv("USERPROFILE") or os.getenv("HOME") or ""
    path = home .. path:sub(2)
  end
  return system.absolute_path(path) or path
end

command.add(nil, {
  ["doxoade:new-doc"] = function()
    local doc = core.open_doc()
    core.root_view:open_doc(doc)
    core.log("Novo documento em branco criado.")
  end,

  ["doxoade:open-log"] = function()
    local performed = command.perform("core:open-log")
    if not performed then
      for _, doc in ipairs(core.docs) do
        if doc:get_name() == "Log" or (doc.filename and doc.filename:find("Log")) then
          core.root_view:open_doc(doc)
          return
        end
      end
    end
  end,

  ["doxoade:open-init-lua"] = function()
    local config_file = USERDIR .. PATHSEP .. "init.lua"
    core.root_view:open_doc(core.open_doc(config_file))
  end,

  ["doxoade:toggle-litexl-in-tree"] = function()
    if not core.project_directories then return end
    local clean_userdir = (system.absolute_path(USERDIR) or USERDIR):gsub("\\", "/")
    for _, p in ipairs(core.project_directories) do
      local ppath = (type(p) == "table" and p.path or p):gsub("\\", "/")
      if ppath == clean_userdir then
        core.remove_project_directory(p.path or p)
        core.log("Lite XL Config removido da Árvore.")
        return
      end
    end
    core.add_project_directory(USERDIR)
    core.log("Lite XL Config anexado à Árvore.")
  end,

  ["treeview:add-project-folder"] = function()
    core.command_view:enter(
      "Caminho do Projeto para Adicionar (suporta ~ e caminhos absolutos)",
      function(path)
        path = normalize_path(path)
        if path and path:match("%S") then
          local info = system.get_file_info(path)
          if info and info.type == "dir" then
            core.add_project_directory(path)
            core.log("Projeto adicionado com sucesso: " .. path)
          elseif info and info.type == "file" then
            core.root_view:open_doc(core.open_doc(path))
            core.log("Arquivo aberto: " .. path)
          else
            core.error("Caminho inexistente no disco: " .. path)
          end
        end
      end
    )
  end,

  ["treeview:remove-project-folder"] = function()
    local projects = core.project_directories
    if not projects or #projects == 0 then
      core.log("Nenhum projeto adicional para remover.")
      return
    end

    local items = {}
    local map = {}
    for _, p in ipairs(projects) do
      local pname = type(p) == "table" and p.name or p
      local ppath = type(p) == "table" and p.path or p
      local label = pname .. " -> [" .. ppath .. "]"
      table.insert(items, label)
      map[label] = ppath
    end

    core.command_view:enter(
      "Selecione o Projeto para Desanexar da Árvore",
      function(item)
        local target_path = map[item]
        if target_path then
          core.remove_project_directory(target_path)
          core.log("Projeto removido da Árvore: " .. target_path)
          core.redraw = true
        end
      end,
      function(text)
        return common.fuzzy_match(items, text)
      end
    )
  end
})
