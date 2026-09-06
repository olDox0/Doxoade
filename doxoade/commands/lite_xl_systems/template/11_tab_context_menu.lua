-- doxoade/commands/lite_xl_systems/template/11_tab_context_menu.lua
--[[
  📋 DOXOADE TAB CONTEXT MENU (Menu Flutuante Soberano de Abas)
  - Copia caminhos com 1 clique: Nome, Caminho Relativo e Caminho Absoluto.
  - Abertura de arquivo no gerenciador de arquivos nativo do SO.
  - Invalidação automática de caminhos cacheados e suporte a temas do Lite XL.
]]
local core = require "core"
local style = require "core.style"
local command = require "core.command"
local Node = require "core.node"
local RootView = require "core.rootview"
local keymap = require "core.keymap"

if rawget(_G, "DOXOADE_TAB_CONTEXT_LOADED") then
  return
end
rawset(_G, "DOXOADE_TAB_CONTEXT_LOADED", true)

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local function draw_rect_safe(x, y, w, h, color)
  if rencache and rencache.draw_rect then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

local function draw_text_safe(font, text, x, y, color)
  if rencache and rencache.draw_text then
    rencache.draw_text(font, text, x, y, color)
  elseif native_renderer and native_renderer.draw_text then
    native_renderer.draw_text(font, text, x, y, color)
  end
end

local _path_cache = {}
local _last_project_count = 0

local function resolve_active_paths(view)
  view = view or core.active_view
  if not view or not view.doc or not view.doc.filename then return nil end
  local raw = view.doc.filename

  -- Invalida o cache caso os diretórios do projeto tenham mudado
  local current_proj_count = core.project_directories and #core.project_directories or 0
  if current_proj_count ~= _last_project_count then
    _path_cache = {}
    _last_project_count = current_proj_count
  end

  if _path_cache[raw] then return _path_cache[raw] end

  local abs = system.absolute_path(raw) or raw
  local clean_abs = abs:gsub("[/\\]", PATHSEP or "\\")
  local fname = raw:match("[/\\]([^/\\]+)$") or raw
  local rel = abs:gsub("\\", "/")

  if core.project_directories then
    for _, proj in ipairs(core.project_directories) do
      local ppath = tostring(type(proj) == "table" and (proj.path or proj.name) or proj or ""):gsub("\\", "/")
      if ppath ~= "" and abs:sub(1, #ppath) == ppath then
        rel = abs:sub(#ppath + 1):gsub("^/", "")
        break
      end
    end
  end
  rel = rel:gsub("/", PATHSEP or "\\")
  local dir = clean_abs:match("^(.*)[/\\]") or clean_abs
  local result = { filename = fname, relative = rel, absolute = clean_abs, dir = dir, raw = abs }
  _path_cache[raw] = result
  return result
end

-- =============================================================================
-- UTILITÁRIOS DE RENDERIZAÇÃO E SISTEMA
-- =============================================================================
local function draw_rect_safe(x, y, w, h, color)
  if rencache and rencache.draw_rect then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

local function draw_text_safe(font, text, x, y, color)
  if rencache and rencache.draw_text then
    rencache.draw_text(font, text, x, y, color)
  elseif native_renderer and native_renderer.draw_text then
    native_renderer.draw_text(font, text, x, y, color)
  end
end

local _path_cache = {}
local function resolve_active_paths(view)
  view = view or core.active_view
  if not view or not view.doc or not view.doc.filename then return nil end
  local raw = view.doc.filename
  if _path_cache[raw] then return _path_cache[raw] end

  local abs = system.absolute_path(raw) or raw
  local clean_abs = abs:gsub("[/\\]", PATHSEP or "\\")
  local fname = raw:match("[/\\]([^/\\]+)$") or raw
  local rel = abs:gsub("\\", "/")

  if core.project_directories then
    for _, proj in ipairs(core.project_directories) do
      local ppath = tostring(type(proj) == "table" and (proj.path or proj.name) or proj or ""):gsub("\\", "/")
      if ppath ~= "" and abs:sub(1, #ppath) == ppath then
        rel = abs:sub(#ppath + 1):gsub("^/", "")
        break
      end
    end
  end
  rel = rel:gsub("/", PATHSEP or "\\")
  local dir = clean_abs:match("^(.*)[/\\]") or clean_abs
  local result = { filename = fname, relative = rel, absolute = clean_abs, dir = dir, raw = abs }
  _path_cache[raw] = result
  return result
end

local function open_in_file_manager(path)
  if system.show_in_file_manager then
    system.show_in_file_manager(path)
    return
  end
  if PLATFORM == "Windows" then
    system.exec('explorer.exe /select,"' .. tostring(path):gsub('"', '""') .. '"')
  else
    local dir = tostring(path):match("^(.*)[/\\]") or path
    system.exec("xdg-open '" .. tostring(dir):gsub("'", "'\\''") .. "'")
  end
end

local FloatingMenu = {
  visible = false,
  x = 0, y = 0, w = 260, h = 100,
  hovered_idx = nil,
  items = {},
}

local PADDING_X = 14
local PADDING_Y = 6

local function get_item_height()
  local font = style.font or style.code_font
  return font:get_height() + (PADDING_Y * 2)
end

local function build_menu_items(paths)
  if not paths then return nil end
  return {
    {
      text = "📋 Copy Name     : " .. paths.filename,
      action = function()
        system.set_clipboard(paths.filename)
        core.log("Copiado (Nome): " .. paths.filename)
      end
    },
    {
      text = "📂 Proj. Address : " .. paths.relative,
      action = function()
        system.set_clipboard(paths.relative)
        core.log("Copiado (Proj. Address): " .. paths.relative)
      end
    },
    {
      text = "📍 Total Address : " .. paths.absolute,
      action = function()
        system.set_clipboard(paths.absolute)
        core.log("Copiado (Total Address): " .. paths.absolute)
      end
    },
    {
      text = "🖥️ Open Explorer : " .. paths.dir,
      action = function()
        open_in_file_manager(paths.raw)
        core.log("Explorer aberto em: " .. paths.dir)
      end
    },
    {
      text = "🧹 Close Tabs to Right",
      action = function()
        command.perform("root:close-following-tabs")
      end
    },
  }
end

local function open_floating_menu(view, mx, my)
  local paths = resolve_active_paths(view)
  local items = build_menu_items(paths)
  if not items then return end

  local font = style.font or style.code_font
  local item_h = get_item_height()
  local max_w = 200

  for _, it in ipairs(items) do
    local tw = font:get_width(it.text)
    if tw > max_w then max_w = tw end
  end

  local menu_w = max_w + (PADDING_X * 2) + 12
  local menu_h = (#items * item_h) + 8

  local screen_w = core.root_view and core.root_view.size and core.root_view.size.x or 1200
  local screen_h = core.root_view and core.root_view.size and core.root_view.size.y or 800

  local fx = (mx + menu_w > screen_w) and (screen_w - menu_w - 6) or mx
  local fy = (my + menu_h > screen_h) and (screen_h - menu_h - 6) or my
  fx = math.max(4, fx)
  fy = math.max(4, fy)

  FloatingMenu.x = fx
  FloatingMenu.y = fy
  FloatingMenu.w = menu_w
  FloatingMenu.h = menu_h
  FloatingMenu.items = items
  FloatingMenu.hovered_idx = nil
  FloatingMenu.visible = true
  core.redraw = true
end

-- =============================================================================
-- HOOKS DE RENDERIZAÇÃO E INTERAÇÃO
-- =============================================================================
local original_rootview_draw = RootView.draw
function RootView:draw(...)
  original_rootview_draw(self, ...)
  if not FloatingMenu.visible or #FloatingMenu.items == 0 then return end

  local x, y, w, h = FloatingMenu.x, FloatingMenu.y, FloatingMenu.w, FloatingMenu.h
  local item_h = get_item_height()
  local font = style.font or style.code_font

  draw_rect_safe(x - 2, y - 2, w + 4, h + 4, { 10, 10, 10, 200 })
  draw_rect_safe(x, y, w, h, style.background2 or { 25, 23, 26, 255 })
  draw_rect_safe(x, y, 3, h, style.accent or { 38, 188, 95, 255 })
  draw_rect_safe(x, y, w, 1, style.divider or { 76, 69, 82, 255 })

  local curr_y = y + 4
  for i, it in ipairs(FloatingMenu.items) do
    local is_hovered = (FloatingMenu.hovered_idx == i)
    if is_hovered then
      draw_rect_safe(x + 3, curr_y, w - 4, item_h, style.background3 or { 47, 46, 48, 255 })
    end
    local text_color = is_hovered and { 255, 255, 255, 255 } or (style.text or { 210, 220, 230, 255 })
    draw_text_safe(font, it.text, x + PADDING_X, curr_y + PADDING_Y, text_color)
    curr_y = curr_y + item_h
  end
end

local original_rootview_mouse_moved = RootView.on_mouse_moved
function RootView:on_mouse_moved(x, y, ...)
  if not FloatingMenu.visible then
    return original_rootview_mouse_moved(self, x, y, ...)
  end
  original_rootview_mouse_moved(self, x, y, ...)

  local mx, my, mw, mh = FloatingMenu.x, FloatingMenu.y, FloatingMenu.w, FloatingMenu.h
  if x >= mx and x <= mx + mw and y >= my and y <= my + mh then
    local item_h = get_item_height()
    local idx = math.floor((y - my - 4) / item_h) + 1
    FloatingMenu.hovered_idx = (idx >= 1 and idx <= #FloatingMenu.items) and idx or nil
    core.redraw = true
  else
    if FloatingMenu.hovered_idx ~= nil then
      FloatingMenu.hovered_idx = nil
      core.redraw = true
    end
  end
end

local original_rootview_mouse_pressed = RootView.on_mouse_pressed
function RootView:on_mouse_pressed(button, x, y, clicks)
  if not FloatingMenu.visible then
    return original_rootview_mouse_pressed(self, button, x, y, clicks)
  end

  local mx, my, mw, mh = FloatingMenu.x, FloatingMenu.y, FloatingMenu.w, FloatingMenu.h
  if (button == "left" or button == 1) and x >= mx and x <= mx + mw and y >= my and y <= my + mh then
    local item_h = get_item_height()
    local idx = math.floor((y - my - 4) / item_h) + 1
    local item = FloatingMenu.items[idx]
    FloatingMenu.visible = false
    core.redraw = true
    if item and item.action then item.action() end
    return true
  end

  FloatingMenu.visible = false
  core.redraw = true
  return true
end

local contextmenu = nil
pcall(function() contextmenu = require "plugins.contextmenu" end)

local original_node_mouse_pressed = Node.on_mouse_pressed
function Node:on_mouse_pressed(button, x, y, clicks)
  if button == "right" or button == 2 then
    local idx = self:get_tab_overlapping_point(x, y)
    if idx and self.views and self.views[idx] then
      local view = self.views[idx]
      self:set_active_view(view)
      core.set_active_view(view)

      -- Fallback para menu de contexto nativo se disponível
      if contextmenu and contextmenu.show then
        local ok = pcall(contextmenu.show, contextmenu, x, y)
        if ok then return true end
      elseif command and command.perform then
        local ok = pcall(command.perform, "context-menu:show", x, y)
        if ok then return true end
      end

      -- Menu Flutuante Soberano do Doxoade
      open_floating_menu(view, x, y)
      return true
    end
  end
  return original_node_mouse_pressed(self, button, x, y, clicks)
end

-- =============================================================================
-- REGISTRO DE COMANDOS (Único bloco)
-- =============================================================================
command.add("core.docview", {
  ["doxoade:tab-copy-filename"] = function()
    local p = resolve_active_paths()
    if p then system.set_clipboard(p.filename); core.log("Copiado (Nome): " .. p.filename) end
  end,

  ["doxoade:tab-copy-relative-path"] = function()
    local p = resolve_active_paths()
    if p then system.set_clipboard(p.relative); core.log("Copiado (Proj. Address): " .. p.relative) end
  end,

  ["doxoade:tab-copy-full-path"] = function()
    local p = resolve_active_paths()
    if p then system.set_clipboard(p.absolute); core.log("Copiado (Total Address): " .. p.absolute) end
  end,

  ["doxoade:tab-open-in-explorer"] = function()
    local p = resolve_active_paths()
    if p then open_in_file_manager(p.raw); core.log("Explorer aberto em: " .. p.dir) end
  end,

  ["doxoade:copy-path-menu"] = function()
    local p = resolve_active_paths()
    if not p then core.error("Nenhum documento ativo."); return end

    core.command_view:enter("Copiar Endereço (1: Nome, 2: Relativo, 3: Completo, 4: Explorer)", {
      submit = function(text)
        local opt = tostring(text):match("%d") or text:lower()
        if opt == "1" or opt:find("nome") or opt:find("name") then
          system.set_clipboard(p.filename); core.log("Copiado (Nome): " .. p.filename)
        elseif opt == "2" or opt:find("rel") or opt:find("proj") then
          system.set_clipboard(p.relative); core.log("Copiado (Proj. Address): " .. p.relative)
        elseif opt == "3" or opt:find("comp") or opt:find("total") then
          system.set_clipboard(p.absolute); core.log("Copiado (Total Address): " .. p.absolute)
        elseif opt == "4" or opt:find("exp") then
          open_in_file_manager(p.raw); core.log("Explorer aberto em: " .. p.dir)
        end
      end
    })
  end
})

-- =============================================================================
-- REGISTRO NO CONTEXTMENU NATIVO
-- =============================================================================
pcall(function()
  if contextmenu and contextmenu.register then
    local divider = contextmenu.DIVIDER or { divider = true }
    local items = {
      divider,
      { text = "Copy Name",        command = "doxoade:tab-copy-filename" },
      { text = "Proj. Address",    command = "doxoade:tab-copy-relative-path" },
      { text = "Total Address",    command = "doxoade:tab-copy-full-path" },
      divider,
      { text = "Open in Explorer", command = "doxoade:tab-open-in-explorer" },
    }

    local function predicate()
      local v = core.active_view
      return v and v.doc and v.doc.filename ~= nil
    end

    contextmenu:register(predicate, items)
  end
end)

-- =============================================================================
-- KEYMAPS
-- =============================================================================
keymap.add {
  ["ctrl+alt+e"]   = "doxoade:tab-copy-filename",
  ["ctrl+alt+c"]   = "doxoade:copy-path-menu",
  ["ctrl+shift+c"] = "doxoade:tab-copy-relative-path",
}
