-- doxoade/commands/lite_xl_systems/template/05_split_mover.lua
--[[
  ⚖️ DOXOADE IN-PLACE SPLIT CONTROLLER (V35.0 Zero-Split Rotation)
  - Zero criação de nós no Ctrl+L (altera apenas o divisor existente).
  - Faxina automática de qualquer área preta vazia residual (EmptyView).
  - Ctrl+L: Alterna Cima/Baixo (100% width) <-> Lado a Lado (100% height) in-place.
  - Ctrl+Shift+L: Permuta os painéis (Swap A <-> B).
  - Ctrl+Alt+D: Move a aba ativa para o outro painel (mantido intacto).
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = require "core"
local command = require "core.command"
local keymap = require "core.keymap"
local DocView = require "core.docview"

-- 1. Sonda de orientação do monitor
local function is_portrait_mode()
  local rv = core.root_view
  if not rv or not rv.size then return false end
  return rv.size.y > rv.size.x
end

-- 2. Faxina: dissolve qualquer painel vazio preto residual na árvore
local function cleanup_empty_splits()
  local root = core.root_view.root_node
  local function traverse(n)
    if not n or n.type == "leaf" then return false end
    -- Se o filho A é folha vazia (sem docs), consome B
    if n.a and n.a.type == "leaf" and not n.a.locked then
      local has_doc = false
      for _, v in ipairs(n.a.views or {}) do
        if v.doc or (v.is and v:is(DocView)) then has_doc = true break end
      end
      if not has_doc and n.b then
        n:consume(n.b)
        return true
      end
    end
    -- Se o filho B é folha vazia (sem docs), consome A
    if n.b and n.b.type == "leaf" and not n.b.locked then
      local has_doc = false
      for _, v in ipairs(n.b.views or {}) do
        if v.doc or (v.is and v:is(DocView)) then has_doc = true break end
      end
      if not has_doc and n.a then
        n:consume(n.a)
        return true
      end
    end
    if traverse(n.a) then return true end
    if traverse(n.b) then return true end
    return false
  end

  for _ = 1, 5 do
    if not traverse(root) then break end
  end
end

-- 3. Coleta os painéis reais que contêm código aberto
local function get_real_editor_leaves()
  local leaves = {}
  local function traverse(n)
    if not n then return end
    if n.type == "leaf" and not n.locked then
      local has_doc = false
      local is_tv = false
      for _, v in ipairs(n.views or {}) do
        local name = (v.get_name and v:get_name()) or ""
        if name:lower():find("tree") then is_tv = true break end
        if v.doc or (v.is and v:is(DocView)) then has_doc = true end
      end
      if has_doc and not is_tv then
        table.insert(leaves, n)
      end
    elseif n.type ~= "leaf" then
      traverse(n.a)
      traverse(n.b)
    end
  end
  traverse(core.root_view.root_node)
  return leaves
end

local function safe_update_layout()
  if core.root_view and core.root_view.root_node and type(core.root_view.root_node.update_layout) == "function" then
    pcall(core.root_view.root_node.update_layout, core.root_view.root_node)
  end
end

-- 4. Localiza o nó ancestral comum divisor entre os dois painéis
local function find_common_split_parent(leaf1, leaf2)
  local p1 = leaf1.parent
  while p1 do
    local p2 = leaf2.parent
    while p2 do
      if p1 == p2 and p1.type ~= "leaf" then
        return p1
      end
      p2 = p2.parent
    end
    p1 = p1.parent
  end
  return leaf1.parent
end

-- 5. Comandos
command.add(nil, {
  -- Ctrl+L: Alterna a orientação IN-PLACE (ZERO novos splits)
  ["doxoade:toggle-split-orientation"] = function()
    -- Passo 1: Elimina qualquer painel preto vazio residual
    cleanup_empty_splits()

    local leaves = get_real_editor_leaves()

    -- CASO 1: Já temos 2 painéis abertos -> GIRA O DIVISOR EXISTENTE (Zero splits novos)
    if #leaves >= 2 then
      local split_parent = find_common_split_parent(leaves[1], leaves[2])
      if split_parent and split_parent.type ~= "leaf" then
        -- Inverte o tipo do divisor existente sem criar nenhum nó:
        -- "vertical" = Cima e Baixo (100% largura)
        -- "horizontal" = Lado a Lado (100% altura)
        if split_parent.type == "vertical" then
          split_parent.type = "horizontal"
        else
          split_parent.type = "vertical"
        end
        split_parent.divider = 0.5

        -- Recalcula geometrias na tela inteira
        --core.root_view.root_node:update_layout()
        safe_update_layout()
        core.redraw = true

        if core.log then
          core.log(string.format("🔄 [SPLIT] Orientação in-place: %s.",
            split_parent.type == "vertical" and "Horizontal (Cima/Baixo)" or "Vertical (Lado a Lado)"))
        end
        return
      end
    end

    -- CASO 2: Só existe 1 painel -> Cria a segunda partição na direção ideal
    if #leaves == 1 then
      local split_dir = is_portrait_mode() and "down" or "right"
      leaves[1]:split(split_dir)
      --core.root_view.root_node:update_layout()
      safe_update_layout()
      core.redraw = true
      if core.log then
        core.log(string.format("📐 [SPLIT] Painel criado na direção '%s'.", split_dir))
      end
    end
  end,

  -- Ctrl+Shift+L: Permuta os painéis (inverte topo/base ou esquerda/direita)
  ["doxoade:swap-split-panels"] = function()
    cleanup_empty_splits()
    local leaves = get_real_editor_leaves()
    if #leaves >= 2 then
      local split_parent = find_common_split_parent(leaves[1], leaves[2])
      if split_parent and split_parent.a and split_parent.b then
        local tmp = split_parent.a
        split_parent.a = split_parent.b
        split_parent.b = tmp
        --core.root_view.root_node:update_layout()
        safe_update_layout()
        core.redraw = true
        if core.log then
          core.log("🔀 [SPLIT] Painéis invertidos com sucesso.")
        end
      end
    end
  end,

  -- Ctrl+Alt+D: Move a aba ativa para o outro painel (mantido exatamente como está)
  ["root:move-tab-to-opposite-panel"] = function()
    cleanup_empty_splits()
    local node = core.root_view and core.root_view:get_active_node()
    local view = core.active_view
    if not node or not view or not view.doc or node.locked then return end

    local leaves = get_real_editor_leaves()
    local target_node = nil

    if #leaves >= 2 then
      for _, leaf in ipairs(leaves) do
        if leaf ~= node then
          target_node = leaf
          break
        end
      end

      if target_node then
        local idx = node.get_view_idx and node:get_view_idx(view)
        if idx then
          table.remove(node.views, idx)
          if #node.views > 0 then
            node.active_view = node.views[math.min(idx, #node.views)]
          else
            local parent = node.parent
            if parent and parent.consume then
              local sibling = (parent.a == node) and parent.b or parent.a
              if sibling then parent:consume(sibling) end
            end
          end
        end

        target_node:add_view(view)
        target_node.active_view = view
        core.set_active_view(view)
      end
    else
      local split_dir = is_portrait_mode() and "down" or "right"
      local new_node = node:split(split_dir)

      if node.a and node.a.views then
        local idx = node.a.get_view_idx and node.a:get_view_idx(view)
        if idx then
          table.remove(node.a.views, idx)
          if #node.a.views > 0 then
            node.a.active_view = node.a.views[math.min(idx, #node.a.views)]
          end
        end
      end

      new_node:add_view(view)
      new_node.active_view = view
      core.set_active_view(view)
    end

    --core.root_view.root_node:update_layout()
    safe_update_layout()
    core.redraw = true
  end,

  ["root:close-following-tabs"] = function()
    local node = core.root_view and core.root_view:get_active_node()
    local view = core.active_view
    if not node or not view or not view.doc or node.locked or not node.views then return end
    local cur_idx = (type(node.get_view_idx) == "function") and node:get_view_idx(view)
    if not cur_idx or cur_idx >= #node.views then return end
    local closed_count = 0
    local root_node = core.root_view and core.root_view.root_node
    for i = #node.views, cur_idx + 1, -1 do
      local target_view = node.views[i]
      if target_view then
        if node.close_view then
          pcall(node.close_view, node, root_node, target_view)
        else
          table.remove(node.views, i)
        end
        closed_count = closed_count + 1
      end
    end
    core.redraw = true
    if core.log and closed_count > 0 then
      core.log(string.format("🧹 %d aba(s) à direita fechada(s).", closed_count))
    end
  end,
})

keymap.add {
  ["ctrl+l"]       = "doxoade:toggle-split-orientation",
  ["ctrl+shift+l"] = "doxoade:swap-split-panels",
  ["ctrl+alt+d"]   = "root:move-tab-to-opposite-panel",
}
