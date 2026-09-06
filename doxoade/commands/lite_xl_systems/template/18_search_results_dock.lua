-- doxoade/commands/lite_xl_systems/template/18_search_results_dock.lua
--[[
🔍 SEARCH RESULTS DOCK — Painel Dedicado de Resultados (Model-View)
- Não é um editor de texto, é uma View customizada do Lite XL.
- Renderiza arquivos agrupados com contagem de hits.
- Clique ou Enter abre o arquivo no painel principal e salta para a linha.
]]
local core = require "core"
local View = require "core.view"
local command = require "core.command"
local style = require "core.style"
local keymap = require "core.keymap"

local SearchResultsView = View:extend()

function SearchResultsView:new()
  if SearchResultsView.super and SearchResultsView.super.new then
    pcall(SearchResultsView.super.new, self)
  end
  self.scrollable = true
  self.font = style.font or style.code_font
  self.line_h = 20
  self.header_h = 32
  self.hovered_idx = nil
  self.selected_idx = 0
end

function SearchResultsView:get_name()
  local state = rawget(_G, "_DOXOADE_SEARCH_STATE")
  if state and state.query and state.query ~= "" and not state.is_searching then
    return string.format("🔍 %s (%d)", state.query, state.total_hits)
  end
  return "🔍 Search Results"
end

function SearchResultsView:draw()
  self:draw_background(style.background2)
  local x, y, w, h = self.position.x, self.position.y, self.size.x, self.size.y
  local state = rawget(_G, "_DOXOADE_SEARCH_STATE")

  -- Header
  renderer.draw_rect(x, y, w, self.header_h, style.background3 or {30,30,30,255})
  renderer.draw_rect(x, y, w, 2, style.accent or {38,188,95,255})
  
  local title = "🔍 Search Results"
  if state then
    if state.is_searching then
      title = "⏳ Searching: " .. state.query .. "..."
    elseif state.query ~= "" then
      title = string.format("🔍 %q — %d hits in %d files (%.2fs)", state.query, state.total_hits, state.total_files, state.elapsed)
    end
  end
  renderer.draw_text(self.font, title, x + 12, y + 9, style.text)

  if not state or #state.results == 0 then
    local msg = "Press Ctrl+Alt+Shift+F to search the project."
    if state and state.is_searching then msg = "Indexing and scanning project..." end
    if state and state.query ~= "" and not state.is_searching then msg = "No results found." end
    renderer.draw_text(self.font, msg, x + 12, y + self.header_h + 16, style.dim)
    return
  end

  -- Results List
  local scroll_y = self.scroll and self.scroll.y or 0
  local cy = y + self.header_h - scroll_y
  local last_file = nil

  for i, res in ipairs(state.results) do
    local is_new_file = (res.path ~= last_file)
    local item_h = is_new_file and (self.line_h * 2) or self.line_h

    if cy + item_h > y + self.header_h and cy < y + h then
      local is_hovered = (self.hovered_idx == i)
      local is_selected = (self.selected_idx == i)

      if is_new_file then
        local fname = res.path:match("[/\\]([^/\\]+)$") or res.path
        local fdir = res.path:match("^(.*)[/\\]") or ""
        renderer.draw_text(self.font, "📄 " .. fname, x + 10, cy + 4, style.accent)
        renderer.draw_text(self.font, "  " .. fdir, x + 10 + self.font:get_width("📄 " .. fname), cy + 4, style.dim)
        cy = cy + self.line_h
        last_file = res.path
      end

      local bg = style.background2
      if is_selected then bg = style.background3 or {45,45,45,255}
      elseif is_hovered then bg = {35,35,35,255} end
      renderer.draw_rect(x, cy, w, self.line_h, bg)
      
      if is_selected then renderer.draw_rect(x, cy, 3, self.line_h, style.accent) end

      local line_text = string.format("%4d: %s", res.line, res.text)
      if #line_text > 120 then line_text = line_text:sub(1, 120) .. "..." end
      renderer.draw_text(self.font, line_text, x + 24, cy + 4, style.text)
    end
    cy = cy + item_h
  end
end

function SearchResultsView:on_mouse_moved(px, py, dx, dy)
  SearchResultsView.super.on_mouse_moved(self, px, py, dx, dy)
  local state = rawget(_G, "_DOXOADE_SEARCH_STATE")
  if not state or #state.results == 0 then self.hovered_idx = nil return end
  
  local scroll_y = self.scroll and self.scroll.y or 0
  local rel_y = py - self.position.y - self.header_h + scroll_y
  if rel_y >= 0 then
    local idx = math.floor(rel_y / self.line_h) + 1
    if idx >= 1 and idx <= #state.results then
      self.hovered_idx = idx
      core.redraw = true
    end
  end
end

function SearchResultsView:on_mouse_pressed(button, px, py, clicks)
  if button == "left" and self.hovered_idx then
    self:open_result(self.hovered_idx)
    return true
  end
  return SearchResultsView.super.on_mouse_pressed(self, button, px, py, clicks)
end

function SearchResultsView:open_result(idx)
  local state = rawget(_G, "_DOXOADE_SEARCH_STATE")
  if not state or not state.results[idx] then return end
  local res = state.results[idx]
  self.selected_idx = idx
  core.redraw = true

  local ok, doc = pcall(core.open_doc, res.path)
  if ok and doc then
    -- Abre no painel principal, não no dock
    local main_node = nil
    local function find_main(node)
      if not node then return end
      if node.type == "leaf" then
        for _, v in ipairs(node.views or {}) do
          if v:is(SearchResultsView) then return end
        end
        main_node = node
      else
        find_main(node.a); find_main(node.b)
      end
    end
    find_main(core.root_view.root_node)
    
    if main_node then
      local DocView = require "core.docview"
      main_node:add_view(DocView(doc))
      main_node:set_active_view(main_node.views[#main_node.views])
      core.set_active_view(main_node.active_view)
    else
      core.root_view:open_doc(doc)
    end
    doc:set_selection(res.line, 1, res.line, 1)
    core.log(string.format("📄 %s:%d", res.path:match("[^/\\]+$"), res.line))
  end
end

-- Comando para abrir/fechar o Dock
command.add(nil, {
  ["doxoade:toggle-search-dock"] = function()
    local function find_dock()
      local function traverse(node)
        if not node then return nil, nil end
        if node.type == "leaf" then
          for i, v in ipairs(node.views or {}) do
            if v.class and v.class == SearchResultsView then return node, v end
          end
        else
          local n, v = traverse(node.a)
          if n then return n, v end
          return traverse(node.b)
        end
      end
      return traverse(core.root_view.root_node)
    end

    local node, view = find_dock()
    if view and node then
      if node.close_view then
        node:close_view(core.root_view.root_node, view)
      end
    else
      local active = core.root_view:get_active_node()
      if active and not active.locked then
        local new_node = active:split("right")
        local sv = SearchResultsView()
        new_node:add_view(sv)
        core.set_active_view(sv)
      end
    end
    core.redraw = true
  end
})

keymap.add { ["ctrl+alt+shift+s"] = "doxoade:toggle-search-dock" }
