-- doxoade/commands/lite_xl_systems/template/28_tree_search_override.lua
--[[
🌳 TREE SEARCH OVERRIDE (V1.1)
"Find in Directory" + Alt+F sobre a tree → executor recursivo (07),
painel flutuante (18), aba preservada. Instala pós-plugins (1.5s).
]]
local core = require "core"
local command = require "core.command"

local function resolve_tree_dir()
  local tv = nil
  local function scan(n)
    if not n or tv then return end
    if n.type == "leaf" then
      for _, v in ipairs(n.views or {}) do
        if v and (v.hovered_item or v.selected_item) then tv = v return end
      end
    else
      scan(n.a); scan(n.b)
    end
  end
  if core.root_view and core.root_view.root_node then scan(core.root_view.root_node) end
  local item = tv and (tv.hovered_item or tv.selected_item)
  local path = item and (item.abs_filename or item.filename or item.path)
  if type(path) == "string" and path ~= "" then
    local info = system.get_file_info(path)
    if info and info.type == "dir" then return path end
    if info and info.type == "file" then
      return (path:gsub("\\", "/"):match("^(.*)/[^/]+$"))
    end
  end
  local p0 = core.project_directories and core.project_directories[1]
  if p0 then return (type(p0) == "table" and (p0.path or p0.name) or p0) end
  return core.project_dir
end

core.add_thread(function()
  coroutine.yield(1.5)
  local function open_scoped_search()
    local dir = resolve_tree_dir()
    if not dir then return end
    local short = dir:gsub("\\", "/"):match("[^/]+$") or dir
    core.command_view:enter("🔍 Buscar em '" .. short .. "' (recursivo)", {
      submit = function(q)
        if not q or q:match("^%s*$") then return end
        local executor = rawget(_G, "DOXOADE_EXECUTE_GLOBAL_SEARCH")
        if type(executor) == "function" then
          pcall(executor, q, dir, true)
        end
      end,
    })
  end
  command.add(nil, {
    ["treeview:search-in-directory"] = open_scoped_search,
    ["doxoade:search-in-treeview-path"] = open_scoped_search,
  })
  if core.log then core.log("🌳 [TREE-SEARCH] Override V1.1 instalado (tree + Alt+F na tree).") end
end)
