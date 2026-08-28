-- doxoade/commands/lite_xl_systems/template/11_tab_context_menu.lua
-- =============================================================================
-- 11. MENU FLUTUANTE NATIVO NO CLIQUE DIREITO DA ABA (IMMEDIATE-MODE POPUP)
-- =============================================================================
local core = require "core"
local style = require "core.style"
local command = require "core.command"
local Node = require "core.node"
local RootView = require "core.rootview"
local common = require "core.common"
local keymap = require "core.keymap"

-- 🛡️ Polyfill de Renderização
local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

-- =====================================================
-- 🧂 QUOTING E ABERTURA SEGURA EM FILE MANAGER
-- =====================================================
local function quote_windows_path(path)
  return '"' .. tostring(path):gsub('"', '""') .. '"'
end

local function quote_posix_path(path)
  return "'" .. tostring(path):gsub("'", "'\\''") .. "'"
end

local function open_in_file_manager(path)
  if system.show_in_file_manager then
    system.show_in_file_manager(path)
    return
  end

  if PLATFORM == "Windows" then
    system.exec("explorer.exe /select," .. quote_windows_path(path))
  else
    local dir_path = tostring(path):match("^(.*)[/\\]") or path
    system.exec("xdg-open " .. quote_posix_path(dir_path))
  end
end

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

-- =====================================================
-- 🧂 QUOTING E ABERTURA SEGURA EM FILE MANAGER
-- =====================================================
local function quote_windows_path(path)
  return '"' .. tostring(path):gsub('"', '""') .. '"'
end

local function quote_posix_path(path)
  return "'" .. tostring(path):gsub("'", "'\\''") .. "'"
end

local function open_in_file_manager(path)
  if system.show_in_file_manager then
    system.show_in_file_manager(path)
    return
  end

  if PLATFORM == "Windows" then
    system.exec("explorer.exe /select," .. quote_windows_path(path))
  else
    local dir_path = tostring(path):match("^(.*)[/\\]") or path
    system.exec("xdg-open " .. quote_posix_path(dir_path))
  end
end

local FloatingMenu = {
  visible = false,
  x = 0,
  y = 0,
  w = 260,
  h = 100,
  hovered_idx = nil,
  items = {},
}

local PADDING_X = 14
local PADDING_Y = 6

local function get_item_height()
  local font = style.font or style.code_font
  return font:get_height() + (PADDING_Y * 2)
end

local function build_menu_items(view)
  if not view or not view.doc or not view.doc.filename then return nil end

  local raw_path = view.doc.filename
  local abs_path = system.absolute_path(raw_path) or raw_path
  local clean_abs = abs_path:gsub("[/\\]", PATHSEP or "\\")
  local fname = raw_path:match("[/\\]([^/\\]+)$") or raw_path

  local rel_path = abs_path:gsub("\\", "/")
  if core.project_directories then
    for _, proj in ipairs(core.project_directories) do
      local ppath = tostring(type(proj) == "table" and (proj.path or proj.name) or proj or ""):gsub("\\", "/")
      if ppath ~= "" and abs_path:sub(1, #ppath) == ppath then
        rel_path = abs_path:sub(#ppath + 1):gsub("^/", "")
        break
      end
    end
  end
  rel_path = rel_path:gsub("/", PATHSEP or "\\")
  local dir_path = abs_path:match("^(.*)[/\\]") or abs_path

  return {
    {
      text = "📋 Copy Name     : " .. fname,
      action = function()
        system.set_clipboard(fname)
        core.log("Copiado (Nome): " .. fname)
      end
    },
    {
      text = "📂 Proj. Address : " .. rel_path,
      action = function()
        system.set_clipboard(rel_path)
        core.log("Copiado (Proj. Address): " .. rel_path)
      end
    },
    {
      text = "📍 Total Address : " .. clean_abs,
      action = function()
        system.set_clipboard(clean_abs)
        core.log("Copiado (Total Address): " .. clean_abs)
      end
    },
    {
      text = "🧭 Open Explorer : " .. dir_path,
      action = function()
        open_in_file_manager(abs_path)
        core.log("Explorer aberto em: " .. dir_path)
      end
    }
  }
end

local function open_floating_menu(view, mx, my)
  local items = build_menu_items(view)
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

  local fx = mx
  local fy = my
  if fx + menu_w > screen_w then fx = screen_w - menu_w - 6 end
  if fy + menu_h > screen_h then fy = screen_h - menu_h - 6 end
  if fx < 4 then fx = 4 end
  if fy < 4 then fy = 4 end

  FloatingMenu.x = fx
  FloatingMenu.y = fy
  FloatingMenu.w = menu_w
  FloatingMenu.h = menu_h
  FloatingMenu.items = items
  FloatingMenu.hovered_idx = nil
  FloatingMenu.visible = true
  core.redraw = true
end

-- 🎨 Renderização do Menu Flutuante
local original_rootview_draw = RootView.draw
function RootView:draw()
  original_rootview_draw(self)

  if FloatingMenu.visible and #FloatingMenu.items > 0 then
    local x = FloatingMenu.x
    local y = FloatingMenu.y
    local w = FloatingMenu.w
    local h = FloatingMenu.h
    local item_h = get_item_height()
    local font = style.font or style.code_font

    draw_rect_safe(x - 2, y - 2, w + 4, h + 4, { 10, 10, 10, 200 })
    draw_rect_safe(x, y, w, h, { 25, 23, 26, 255 })
    draw_rect_safe(x, y, 3, h, { 38, 188, 95, 255 })
    draw_rect_safe(x, y, w, 1, { 76, 69, 82, 255 })

    local curr_y = y + 4

    for i, it in ipairs(FloatingMenu.items) do
      local is_hovered = (FloatingMenu.hovered_idx == i)

      if is_hovered then
        draw_rect_safe(x + 3, curr_y, w - 4, item_h, { 47, 46, 48, 255 })
      end

      local text_color = is_hovered and { 255, 255, 255, 255 } or { 210, 220, 230, 255 }

      draw_text_safe(
        font,
        it.text,
        x + PADDING_X,
        curr_y + PADDING_Y,
        text_color
      )

      curr_y = curr_y + item_h
    end
  end
end

-- 🖱️ Interações do Mouse com o Menu Flutuante
local original_rootview_mouse_moved = RootView.on_mouse_moved
function RootView:on_mouse_moved(x, y, ...)
  if FloatingMenu.visible then
    local mx = FloatingMenu.x
    local my = FloatingMenu.y
    local mw = FloatingMenu.w
    local mh = FloatingMenu.h

    if x >= mx and x <= mx + mw and y >= my and y <= my + mh then
      local item_h = get_item_height()
      local idx = math.floor((y - my - 4) / item_h) + 1

      if idx >= 1 and idx <= #FloatingMenu.items then
        FloatingMenu.hovered_idx = idx
      else
        FloatingMenu.hovered_idx = nil
      end

      core.redraw = true
    else
      if FloatingMenu.hovered_idx ~= nil then
        FloatingMenu.hovered_idx = nil
        core.redraw = true
      end
    end
  end

  return original_rootview_mouse_moved(self, x, y, ...)
end

local original_rootview_mouse_pressed = RootView.on_mouse_pressed
function RootView:on_mouse_pressed(button, x, y, clicks)
  if FloatingMenu.visible then
    local mx = FloatingMenu.x
    local my = FloatingMenu.y
    local mw = FloatingMenu.w
    local mh = FloatingMenu.h
    local item_h = get_item_height()

    if button == "left" or button == 1 then
      if x >= mx and x <= mx + mw and y >= my and y <= my + mh then
        local rel_y = y - my - 4
        local idx = math.floor(rel_y / item_h) + 1
        local item = FloatingMenu.items[idx]
        FloatingMenu.visible = false
        core.redraw = true

        if item and item.action then item.action() end
        return true
      end
    end

    FloatingMenu.visible = false
    core.redraw = true
    return true
  end
  return original_rootview_mouse_pressed(self, button, x, y, clicks)
end

local original_node_mouse_pressed = Node.on_mouse_pressed
function Node:on_mouse_pressed(button, x, y, clicks)
  if button == "right" or button == 3 or button == "secondary" then
    local idx = self:get_tab_idx(x, y)
    if idx and self.views and self.views[idx] then
      local view = self.views[idx]
      self:set_active_view(view)
      core.set_active_view(view)
      open_floating_menu(view, x, y)
      return true
    end
  end
  return original_node_mouse_pressed(self, button, x, y, clicks)
end

-- 🌟 Hub Interativo de Caminhos (Ctrl + Alt + C)
command.add("core.docview", {
  ["doxoade:copy-path-menu"] = function()
    local view = core.active_view
    if view then open_floating_menu(view, 80, 50) end
  end,
  ["doxoade:tab-copy-relative-path"] = function()
    local view = core.active_view
    if not view or not view.doc or not view.doc.filename then return end
    local abs_path = (system.absolute_path(view.doc.filename) or view.doc.filename):gsub("\\", "/")
    local rel = abs_path
    if core.project_directories then
      for _, proj in ipairs(core.project_directories) do
        local ppath = tostring(type(proj) == "table" and (proj.path or proj.name) or proj or ""):gsub("\\", "/")
        if ppath ~= "" and abs_path:sub(1, #ppath) == ppath then
          rel = abs_path:sub(#ppath + 1):gsub("^/", "")
          break
        end
      end
    end
    rel = rel:gsub("/", PATHSEP or "\\")
    if system.set_clipboard then
      system.set_clipboard(rel)
      core.log("Copiado (Proj. Address): " .. rel)
    end
  end,
})

-- Carrega o módulo contextmenu (core ou plugin)
local contextmenu = nil
pcall(function() contextmenu = require "core.contextmenu" end)
if not contextmenu then
  pcall(function() contextmenu = require "plugins.contextmenu" end)
end

-- 🎯 Predicado: Retorna true se o mouse estiver sobre uma aba ou se houver docview ativo
local function tab_predicate(x, y)
  if x and y and core.root_view and core.root_view.root_node then
    local node = core.root_view.root_node:get_child_overlapping_point(x, y)
    if node and node.type == "leaf" and node.get_tab_idx then
      local idx = node:get_tab_idx(x, y)
      if idx and node.views and node.views[idx] then
        return true
      end
    end
  end
  if core.active_view and core.active_view.doc then
    return true
  end
  return false
end

-- 🖱️ Hook no Node: Ativa a aba clicada e força a exibição do menu de contexto
local original_node_mouse_pressed = Node.on_mouse_pressed
function Node:on_mouse_pressed(button, x, y, clicks)
  if button == "right" or button == 3 or button == "secondary" then
    local idx = self:get_tab_idx(x, y)
    if idx and self.views and self.views[idx] then
      local view = self.views[idx]
      self:set_active_view(view)
      core.set_active_view(view)

      if contextmenu and contextmenu.show then
        contextmenu:show(x, y)
        return true
      elseif command and command.perform then
        command.perform("context-menu:show", x, y)
        return true
      end
    end
  end
  return original_node_mouse_pressed(self, button, x, y, clicks)
end

-- 📋 Registra os itens do menu de contexto com suporte universal a predicados
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

  pcall(function() contextmenu:register(tab_predicate, items) end)
  pcall(function() contextmenu:register("core.docview", items) end)
  pcall(function() contextmenu:register("core.node", items) end)
end

-- -----------------------------------------------------------------------------
-- Utilitários de Clipboard e Explorer
-- -----------------------------------------------------------------------------
local function copy_to_clipboard(text)
  if system.set_clipboard then
    system.set_clipboard(text)
    core.log("Copiado: " .. text)
  else
    core.error("Clipboard não disponível nesta plataforma.")
  end
end

local function open_in_explorer(dir_path)
  if not dir_path or dir_path == "" then
    core.error("Diretório inválido.")
    return
  end
  -- 🔧 CORREÇÃO: system.execute NÃO existe na API do Lite XL.
  -- Usamos os.execute (Lua padrão) com start/open/xdg-open.
  local cmd
  if PLATFORM == "Windows" then
    cmd = 'start "" "' .. dir_path .. '"'
  elseif PLATFORM == "Mac OS X" then
    cmd = 'open "' .. dir_path .. '"'
  else
    cmd = 'xdg-open "' .. dir_path .. '"'
  end
  os.execute(cmd)
  core.log("Explorer aberto em: " .. dir_path)
end

local function get_active_doc_info()
  local view = core.active_view
  if not view or not view.doc or not view.doc.filename then
    return nil
  end

  local raw_path = view.doc.filename
  local abs_path = system.absolute_path(raw_path) or raw_path
  local clean_abs = abs_path:gsub("[/\\]", PATHSEP or "\\")
  local fname = raw_path:match("[/\\]([^/\\]+)$") or raw_path

  -- Resolução de Caminho Relativo ao Projeto Raiz
  local rel_path = abs_path:gsub("\\", "/")
  if core.project_directories then
    for _, proj in ipairs(core.project_directories) do
      local ppath = tostring(type(proj) == "table" and (proj.path or proj.name) or proj or ""):gsub("\\", "/")
      if ppath ~= "" and rel_path:sub(1, #ppath) == ppath then
        rel_path = rel_path:sub(#ppath + 1):gsub("^/", "")
        break
      end
    end
  end
  rel_path = rel_path:gsub("/", PATHSEP or "\\")

  return {
    filename = fname,
    proj_address = rel_path,
    total_address = clean_abs,
    dir_path = abs_path:match("^(.*)[/\\]") or abs_path
  }
end

-- -----------------------------------------------------------------------------
-- Registro de Comandos
-- -----------------------------------------------------------------------------
command.add(nil, {
  ["doxoade:tab-open-in-explorer"] = function()
    local info = get_active_doc_info()
    if info then
      open_in_explorer(info.dir_path)
    else
      core.error("Nenhum arquivo ativo para abrir no Explorer.")
    end
  end,

  ["doxoade:tab-copy-filename"] = function()
    local info = get_active_doc_info()
    if info then
      copy_to_clipboard(info.file_name)
    else
      core.error("Nenhum arquivo ativo.")
    end
  end,

  ["doxoade:tab-copy-directory"] = function()
    local info = get_active_doc_info()
    if info then
      copy_to_clipboard(info.dir_path)
    else
      core.error("Nenhum arquivo ativo.")
    end
  end,

  ["doxoade:tab-copy-full-path"] = function()
    local info = get_active_doc_info()
    if info then
      copy_to_clipboard(info.abs_path)
    else
      core.error("Nenhum arquivo ativo.")
    end
  end,

  ["doxoade:tab-copy-relative-path"] = function()
    local info = get_active_doc_info()
    if not info then
      core.error("Nenhum arquivo ativo.")
      return
    end
    -- Tenta calcular caminho relativo ao primeiro projeto
    local rel = info.abs_path
    if core.project_directories and #core.project_directories > 0 then
      for _, proj in ipairs(core.project_directories) do
        local ppath = type(proj) == "table" and (proj.path or proj.name) or proj
        if ppath and type(ppath) == "string" then
          local clean_proj = tostring(ppath):gsub("\\", "/")
          local clean_abs = info.abs_path:gsub("\\", "/")
          if clean_abs:sub(1, #clean_proj) == clean_proj then
            rel = clean_abs:sub(#clean_proj + 2)
            break
          end
        end
      end
    end
    copy_to_clipboard(rel)
  end,
})

-- -----------------------------------------------------------------------------
-- Context Menu nas Abas (via plugin contextmenu)
-- -----------------------------------------------------------------------------
-- 📋 Registra os itens do menu de contexto
pcall(function()
  local contextmenu = require "plugins.contextmenu"
  if not contextmenu then return end

  contextmenu:register("core.docview", {
    contextmenu.DIVIDER,
    { text = "Copy Name",        command = "doxoade:tab-copy-filename" },
    { text = "Proj. Address",    command = "doxoade:tab-copy-relative-path" },
    { text = "Total Address",    command = "doxoade:tab-copy-full-path" },
    contextmenu.DIVIDER,
    { text = "Open in Explorer", command = "doxoade:tab-open-in-explorer" },
  })
end)

command.add("core.docview", {
  ["doxoade:copy-path-menu"] = function()
    local info = get_active_doc_info()
    if not info then
      core.error("Nenhum arquivo ativo para copiar endereço.")
      return
    end

    local items = {
      {
        label = "📋 [1] Copy Name        : " .. info.filename,
        value = info.filename,
        action = "copy",
        msg = "Copiado (Copy Name): " .. info.filename
      },
      {
        label = "📂 [2] Proj. Address    : " .. info.proj_address,
        value = info.proj_address,
        action = "copy",
        msg = "Copiado (Proj. Address): " .. info.proj_address
      },
      {
        label = "📍 [3] Total Address    : " .. info.total_address,
        value = info.total_address,
        action = "copy",
        msg = "Copiado (Total Address): " .. info.total_address
      },
      {
        label = "🧭 [4] Open in Explorer : Revelar pasta no Explorer",
        value = info.total_address,
        action = "explorer",
        msg = "Explorer aberto em: " .. info.dir_path
      },
    }

    local labels = {}
    local map = {}
    for _, item in ipairs(items) do
      table.insert(labels, item.label)
      map[item.label] = item
    end

    core.command_view:enter("Copiar Endereço / Nome do Arquivo", {
      submit = function(text, item)
        local selected = map[text] or (item and map[item.text or item])

        -- Suporte a seleção rápida digitando apenas o número (1, 2, 3, 4)
        if not selected then
          local num = tonumber(tostring(text):match("^%d+"))
          if num and items[num] then
            selected = items[num]
          end
        end

        if selected then
          if selected.action == "copy" then
            if system.set_clipboard then
              system.set_clipboard(selected.value)
              core.log(selected.msg)
            end
          elseif selected.action == "explorer" then
            command.perform("doxoade:tab-open-in-explorer")
          end
        end
      end,
      suggest = function(text)
        return common.fuzzy_match(labels, text)
      end
    })
  end,

  -- Comandos Diretos One-Shot
  ["doxoade:tab-copy-filename"] = function()
    local info = get_active_doc_info()
    if info and system.set_clipboard then
      system.set_clipboard(info.filename)
      core.log("Copiado (Nome): " .. info.filename)
    end
  end,

  ["doxoade:tab-copy-relative-path"] = function()
    local info = get_active_doc_info()
    if info and system.set_clipboard then
      system.set_clipboard(info.proj_address)
      core.log("Copiado (Proj. Address): " .. info.proj_address)
    end
  end,

  ["doxoade:tab-copy-full-path"] = function()
    local info = get_active_doc_info()
    if info and system.set_clipboard then
      system.set_clipboard(info.total_address)
      core.log("Copiado (Total Address): " .. info.total_address)
    end
  end,
})

-- -----------------------------------------------------------------------------
-- Keymaps (opcional, para acesso rápido)
-- -----------------------------------------------------------------------------
keymap.add {
  ["ctrl+alt+e"]   = "doxoade:tab-open-in-explorer",
  ["ctrl+alt+c"]   = "doxoade:copy-path-menu",
  ["ctrl+shift+c"] = "doxoade:tab-copy-relative-path",
}
