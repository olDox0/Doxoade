-- doxoade/commands/lite_xl_systems/template/05_split_mover.lua
-- =============================================================================
-- 05. SPLIT MOVER BIDIRECIONAL & MOVER ABAS EM LOTE
-- =============================================================================
local core = require "core"
local command = require "core.command"

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

local function get_target_split_node(node)
  local leaves = get_doc_leaves(core.root_view.root_node)
  if #leaves >= 2 then
    for _, leaf in ipairs(leaves) do
      if leaf ~= node then
        return leaf
      end
    end
  end
  return node:split("right")
end

command.add("core.docview", {
  -- Move apenas a aba ativa atual (Ctrl + Alt + D)
  ["root:move-tab-to-opposite-panel"] = function()
    local node = core.root_view:get_active_node()
    local view = core.active_view
    if not view or not view.doc or node.locked then return end

    local target_node = get_target_split_node(node)
    if target_node and target_node ~= node and not target_node.locked then
      target_node:add_view(view)
      local idx = node:get_view_idx(view)
      if idx then
        table.remove(node.views, idx)
        if #node.views > 0 then
          node.active_view = node.views[math.min(idx, #node.views)]
        else
          node:close()
        end
      end
      core.set_active_view(view)
      core.redraw = true
    end
  end,

  -- Move todas as abas à direita da atual para o painel oposto (Ctrl + Alt + Shift + D)
  ["root:move-following-tabs-to-opposite-panel"] = function()
    local node = core.root_view:get_active_node()
    local view = core.active_view
    if not view or not view.doc or node.locked then return end

    local cur_idx = node:get_view_idx(view)
    if not cur_idx or #node.views <= 1 then return end

    local target_node = get_target_split_node(node)
    if not target_node or target_node == node or target_node.locked then return end

    local views_to_move = {}
    for i = #node.views, cur_idx, -1 do
      local v = node.views[i]
      table.insert(views_to_move, 1, v)
      table.remove(node.views, i)
    end

    for _, v in ipairs(views_to_move) do
      target_node:add_view(v)
    end

    if #node.views > 0 then
      node.active_view = node.views[math.min(cur_idx, #node.views)]
    else
      node:close()
    end

    target_node.active_view = views_to_move[1] or target_node.active_view
    core.set_active_view(target_node.active_view)
    core.redraw = true
    core.log(string.format("✔ %d aba(s) transferida(s) para o painel oposto.", #views_to_move))
  end
})
