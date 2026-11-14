
-- doxoade/commands/lite_xl_systems/template/29_reveal_in_tree.lua
--[[
🌳 REVEAL IN TREE (V1.0)
Alt+Shift+R: localiza o arquivo ativo na TreeView — expande as pastas do
caminho, seleciona o item e rola até ele. Classificação por classe/estrutura,
nunca por nome de arquivo (doutrina H4).
]]
local core = require "core"
local command = require "core.command"
local keymap = require "core.keymap"

local function norm(p)
  if type(p) ~= "string" or p == "" then return nil end
  return (system.absolute_path(p) or p):gsub("\\", "/"):lower():gsub("/+$", "")
end

local function item_path(it)
  return norm(it and (it.abs_filename or it.filename or it.path))
end

local function find_treeview()
  local ok_tv, TreeView = pcall(require, "plugins.treeview")
  if not ok_tv or not TreeView then
    ok_tv, TreeView = pcall(require, "plugins.treeview.treeview")
  end
  local found
  local function scan(n)
    if not n or found then return end
    if n.type == "leaf" then
      for _, v in ipairs(n.views or {}) do
        if v and not v.doc then
          if ok_tv and TreeView and type(v.is) == "function" then
            local ok, res = pcall(v.is, v, TreeView)
            if ok and res then found = v return end
          end
          if v.items ~= nil and type(v.scroll_to_item) == "function" then
            found = v return
          end
        end
      end
    else
      scan(n.a); scan(n.b)
    end
  end
  scan(core.root_view and core.root_view.root_node)
  return found
end

local function reveal(tv, target)
  local function walk(items)
    for _, it in ipairs(items or {}) do
      local p = item_path(it)
      if p then
        if p == target then return it end
        if it.type == "dir" and target:sub(1, #p + 1) == p .. "/" then
          it.expanded = true
          if not it.items and type(tv.get_items) == "function" then
            local ok, kids = pcall(tv.get_items, tv, p)
            if ok and type(kids) == "table" then it.items = kids end
          end
          local hit = walk(it.items)
          if hit then return hit end
        end
      end
    end
    return nil
  end
  return walk(tv.items)
end

command.add(nil, {
  ["doxoade:reveal-in-tree"] = function()
    local doc = core.active_view and core.active_view.doc
    local target = doc and doc.filename and norm(doc.filename)
    if not target then
      core.log("⚠ [REVEAL] Nenhum arquivo ativo para localizar na tree.")
      return
    end
    local tv = find_treeview()
    if not tv then
      core.log("⚠ [REVEAL] TreeView não encontrada.")
      return
    end
    local item = reveal(tv, target)
    if not item then
      core.log("⚠ [REVEAL] Arquivo fora dos projetos da tree: " .. tostring(doc.filename))
      return
    end
    pcall(function() if tv.update_cached_items then tv:update_cached_items() end end)
    tv.selected_item = item
    pcall(function() if tv.scroll_to_item then tv:scroll_to_item(item) end end)
    core.set_active_view(tv)
    core.redraw = true
    core.log("🌳 [REVEAL] Localizado na tree: " .. (doc.filename:match("[^/\\]+$") or doc.filename))
  end,
})

keymap.add({ ["alt+shift+r"] = "doxoade:reveal-in-tree" }, true)

if core.log then
  core.log("🌳 [REVEAL] Reveal-in-tree registrado (Alt+Shift+R).")
end
