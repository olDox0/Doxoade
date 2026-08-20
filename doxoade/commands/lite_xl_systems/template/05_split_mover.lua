-- doxoade/commands/lite_xl_systems/template/template/05_split_mover.lua
-- =============================================================================
-- 05. SPLIT MOVER BIDIRECIONAL (Ctrl + Alt + D) - ESQUERDA ⇄ DIREITA
-- =============================================================================
command.add("core.docview", {
  ["root:move-tab-to-opposite-panel"] = function()
    local node = core.root_view:get_active_node()
    local view = core.active_view
    if not view or not view.doc or node.locked then return end

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

    local leaves = get_doc_leaves(core.root_view.root_node)
    local target_node = nil

    if #leaves >= 2 then
      for _, leaf in ipairs(leaves) do
        if leaf ~= node then
          target_node = leaf
          break
        end
      end
    else
      target_node = node:split("right")
    end

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
  end
})