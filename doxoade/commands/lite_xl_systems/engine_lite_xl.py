# doxoade/commands/lite_xl_systems/engine_lite_xl.py
"""
Motor Soberano Lite XL - Ártemis/Apolo Engine.
V17.0: Sovereign Immediate-Mode Architecture, Lexical AST Auditor, IPC Dispatcher & Full Bootstrap.
"""
import os
import re
import sys
import time
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Union

try:
    from doxoade.tools.lua_systems.lua_manager import LuaRuntimeManager
except ImportError:
    try:
        from doxoade.tools.lua_systems import LuaRuntimeManager
    except ImportError:
        LuaRuntimeManager = None

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ""


NOTEPADPP_CANONICAL_KEYS = {
    "ctrl+n": "doxoade:new-doc",
    "ctrl+o": "core:open-file",
    "ctrl+s": "doc:save",
    "ctrl+shift+s": "doc:save-all",
    "ctrl+w": "root:close",
    "ctrl+f": "find-replace:find",
    "ctrl+h": "find-replace:replace",
    "f3": "find-replace:repeat-find",
    "shift+f3": "find-replace:previous-find",
    "ctrl+g": "doc:go-to-line",
    "ctrl+d": "doc:duplicate-lines",
    "ctrl+l": "doc:delete-lines",
    "ctrl+q": "doc:toggle-line-comments",
    "ctrl+tab": "root:switch-to-next-tab",
    "ctrl+shift+tab": "root:switch-to-previous-tab",
    "ctrl+alt+d": "root:move-tab-to-opposite-panel",
    "ctrl+,": "doxoade:open-init-lua",
    "ctrl+alt+u": "doxoade:toggle-litexl-in-tree",
    "ctrl+alt+o": "treeview:add-project-folder",
    "ctrl+alt+r": "treeview:remove-project-folder",
    "ctrl+shift+l": "doxoade:open-log",
    "ctrl+alt+c": "doxoade:copy-path-menu",
    "f1": "doxoade:show-shortcuts-cheat-sheet",
}

KNOWN_LITEXL_MODULES = {
    "core": "Core Engine",
    "core.common": "Common Utilities & Fuzzy Match",
    "core.config": "Configuration System",
    "core.style": "Theme & Styling",
    "core.command": "Command Dispatcher",
    "core.keymap": "Keymap Manager",
    "core.node": "Node Tree Layout",
    "core.docview": "Document View",
    "core.doc": "Document Buffer",
    "core.view": "Base View",
    "core.rootview": "Root Layout View",
    "core.rencache": "Render Cache System",
    "core.logview": "Log Viewer Panel",
    "renderer": "C-Level Native Renderer (Global)",
    "system": "C-Level System API (Global)",
    "regex": "C-Level Regex Engine",
}

UNIVERSAL_RENCACHE_POLYFILL = (
    'local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)'
)
UNIVERSAL_RENDERER_POLYFILL = (
    'local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)'
)

# ═════════════════════════════════════════════════════════════════════════════
# ACERVO COMPLETO DE TEMPLATES PADRÃO (13 MÓDULOS NATIVOS)
# ═════════════════════════════════════════════════════════════════════════════
DEFAULT_TEMPLATE_CHUNKS = {
    "00_header_and_logger.lua": r'''-- =============================================================================
-- 00. HEADER, MÓDULOS E LOGGER EM DISCO PERSISTENTE
-- =============================================================================
local core = require "core"
local common = require "core.common"
local config = require "core.config"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local Node = require "core.node"
local DocView = require "core.docview"

-- 🛡️ Polyfill Universal de Renderização
local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

config.load_workspace = true
config.max_project_files = 50000

local session_log_file = USERDIR .. PATHSEP .. "session_log.txt"

local function safe_format(...)
  local args = { ... }
  if #args == 0 then return "" end
  if #args == 1 then return tostring(args[1]) end
  local ok, res = pcall(string.format, ...)
  if ok then return res end
  local t = {}
  for _, v in ipairs(args) do table.insert(t, tostring(v)) end
  return table.concat(t, " ")
end

local function append_session_log(level, msg)
  pcall(function()
    local f = io.open(session_log_file, "a")
    if f then
      local ts = os.date("%H:%M:%S")
      f:write(string.format("[%s] [%s] %s\n", ts, level, tostring(msg)))
      f:flush()
      f:close()
    end
  end)
end

pcall(function()
  os.remove(session_log_file)
  local f = io.open(session_log_file, "w")
  if f then
    f:write(string.format("=== LITE XL SESSION INICIADA: %s ===\n", os.date()))
    f:flush()
    f:close()
  end
end)

local original_print = print
function print(...)
  append_session_log("PRINT", safe_format(...))
  if original_print then original_print(...) end
end

local original_core_log = core.log
local is_logging = false

function core.log(...)
  local msg = safe_format(...)
  append_session_log("INFO", msg)
  is_logging = true
  local ok, res = pcall(original_core_log, ...)
  is_logging = false
  if ok then return res end
end

local original_core_error = core.error
function core.error(...)
  local msg = safe_format(...)
  append_session_log("ERROR", msg)
  return original_core_error(...)
end

local original_core_log_quiet = core.log_quiet
function core.log_quiet(...)
  if not is_logging then
    local msg = safe_format(...)
    append_session_log("QUIET", msg)
  end
  if original_core_log_quiet then return original_core_log_quiet(...) end
end

-- Tema Soberano Doxoade (Piano Black & Esmeralda)
pcall(function()
  style.background       = { 1, 1, 1 }
  style.background2      = { 25, 23, 26 }
  style.background3      = { 47, 46, 48 }
  style.text             = { 210, 220, 230 }
  style.dim              = { 94, 92, 94 }
  style.divider          = { 76, 69, 82 }
  style.caret            = { 38, 188, 95 }
  style.accent           = { 38, 188, 95 }
  style.line_number2     = { 38, 188, 95 }
  style.line_highlight   = { 25, 23, 26 }
  style.selection        = { 0, 108, 255, 110 }

  style.syntax["keyword"]   = { 255, 103, 0 }
  style.syntax["keyword2"]  = { 200, 21, 118 }
  style.syntax["function"]  = { 0, 108, 255 }
  style.syntax["string"]    = { 38, 188, 95 }
  style.syntax["comment"]   = { 94, 92, 94 }
  style.syntax["number"]    = { 232, 170, 0 }
  style.syntax["operator"]  = { 210, 220, 230 }
  style.syntax["symbol"]    = { 206, 105, 158 }
end)
''',

    "01_ipc_dispatcher.lua": r'''-- =============================================================================
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
          if target == "__DOXOADE_GRACEFUL_QUIT__" then
            pcall(function()
              local workspace = require "plugins.workspace"
              if workspace and workspace.save then workspace.save() end
            end)
            core.quit()
            return
          elseif target ~= "" then
            pcall(function()
              local abs_target = system.absolute_path(target) or target
              local info = system.get_file_info(abs_target) or system.get_file_info(target)
              if info and info.type == "dir" then
                core.add_project_directory(abs_target)
                core.log("Projeto anexado à Árvore: " .. abs_target)
              else
                local doc = core.open_doc(abs_target)
                core.root_view:open_doc(doc)
                core.log("Arquivo aberto: " .. abs_target)
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
''',

    "02_blacklist.lua": r'''-- =============================================================================
-- 02. BLACKLIST DE PASTAS (PYTHON VENV, CACHE, GIT)
-- =============================================================================
local ignored_patterns = {
  "^%.?venv[/\\]",          "^venv[/\\]",
  "^%.?env[/\\]",           "^env[/\\]",
  "[/\\]%.?venv[/\\]",      "[/\\]venv[/\\]",
  "[/\\]%.?env[/\\]",       "[/\\]env[/\\]",
  "[/\\]__pycache__[/\\]",  "^__pycache__[/\\]",
  "[/\\]%.pytest_cache[/\\]", "[/\\]%.mypy_cache[/\\]", "[/\\]%.ruff_cache[/\\]",
  "[/\\]%.git[/\\]",        "^%.git[/\\]",
  "[/\\]%.idea[/\\]",       "[/\\]%.vscode[/\\]",
  "[/\\]node_modules[/\\]", "^node_modules[/\\]",
  "[/\\]dist[/\\]",         "[/\\]build[/\\]",
  "[/\\]%.egg%-info[/\\]",
  "%.pyc$", "%.pyo$", "%.pyd$",
  "%.DS_Store$", "Thumbs%.db$"
}

for _, pattern in ipairs(ignored_patterns) do
  table.insert(config.ignore_files, pattern)
end
''',

    "03_tab_colors.lua": r'''-- =============================================================================
-- 03. MATRIZ DE CORES DE ABAS POR PROJETO RAIZ COM INDICADOR DE MODIFICADO
-- =============================================================================
local core = require "core"
local style = require "core.style"
local Node = require "core.node"

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local function draw_rect_safe(x, y, w, h, color)
  if rencache and rencache.draw_rect then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

local PROJECT_THEMES = {
  { accent = { 255, 0, 0 },     active_bg = { 175, 0, 0 },   hover_bg = { 170, 68, 0 },  inactive_bg = { 130, 0, 0 } },
  { accent = { 255, 103, 0 },   active_bg = { 224, 90, 0 },  hover_bg = { 170, 68, 0 },  inactive_bg = { 90, 36, 0 } },
  { accent = { 232, 170, 0 },   active_bg = { 170, 125, 0 }, hover_bg = { 130, 95, 0 },  inactive_bg = { 70, 50, 0 } },
  { accent = { 38, 188, 95 },   active_bg = { 25, 123, 63 }, hover_bg = { 18, 90, 46 },  inactive_bg = { 10, 51, 26 } },
  { accent = { 0, 108, 255 },   active_bg = { 0, 80, 190 },  hover_bg = { 0, 60, 140 },  inactive_bg = { 0, 35, 80 } },
  { accent = { 200, 21, 118 },  active_bg = { 150, 16, 88 }, hover_bg = { 110, 12, 65 }, inactive_bg = { 60, 6, 35 } },
  { accent = { 77, 145, 232 },  active_bg = { 30, 57, 92 },  hover_bg = { 22, 42, 68 },   inactive_bg = { 14, 28, 45 } },
  { accent = { 206, 105, 158 }, active_bg = { 82, 41, 63 },  hover_bg = { 60, 30, 46 },  inactive_bg = { 38, 19, 29 } },
  { accent = { 227, 141, 83 },  active_bg = { 90, 56, 33 },  hover_bg = { 68, 42, 25 },   inactive_bg = { 42, 26, 15 } },
}

local DEFAULT_THEME = { accent = { 94, 92, 94 }, active_bg = { 47, 46, 48 }, hover_bg = { 35, 34, 36 }, inactive_bg = { 25, 23, 26 } }
local MODIFIED_YELLOW = { 234, 179, 8, 255 }

local function get_project_tab_theme(filename)
  if not filename then return DEFAULT_THEME end
  local clean_fn = tostring(filename):gsub("\\", "/"):lower()
  local matched_project = nil

  if core.project_directories then
    for _, proj in ipairs(core.project_directories) do
      local ppath = type(proj) == "table" and (proj.path or proj.name) or proj
      if ppath and type(ppath) == "string" then
        local clean_ppath = tostring(ppath):gsub("\\", "/"):lower()
        if clean_fn:sub(1, #clean_ppath) == clean_ppath then
          matched_project = type(proj) == "table" and (proj.name or proj.path) or proj
          break
        end
      end
    end
  end

  if not matched_project then
    matched_project = clean_fn:match("^(.*)[/\\]") or clean_fn
  end

  matched_project = tostring(matched_project or "default")
  local hash = 0
  for i = 1, #matched_project do
    hash = (hash * 31 + matched_project:byte(i)) % #PROJECT_THEMES
  end
  return PROJECT_THEMES[hash + 1] or DEFAULT_THEME
end

local original_draw_tab_title = Node.draw_tab_title
function Node:draw_tab_title(view, font, is_active, is_hovered, x, y, w, h)
  local ok, theme = pcall(function()
    local doc = view and view.doc
    local filename = doc and doc.filename or (view and view:get_name() or nil)
    return get_project_tab_theme(filename)
  end)

  if ok and theme then
    local bg = is_active and theme.active_bg or (is_hovered and theme.hover_bg or theme.inactive_bg)
    draw_rect_safe(x, y, w, h, bg)

    local is_dirty = false
    pcall(function()
      if view and view.doc and view.doc.is_dirty then
        is_dirty = view.doc:is_dirty()
      end
    end)

    if is_dirty then
      draw_rect_safe(x, y, w, is_active and 3 or 2, MODIFIED_YELLOW)
    else
      draw_rect_safe(x, y, w, is_active and 3 or 1, theme.accent)
    end

    local old_text = style.text
    local old_dim = style.dim
    style.text = is_active and { 255, 255, 255, 255 } or (is_hovered and { 240, 240, 240, 255 } or { 190, 190, 190, 255 })
    style.dim = { 180, 180, 180, 255 }
    local res = original_draw_tab_title(self, view, font, is_active, is_hovered, x, y, w, h)
    style.text = old_text
    style.dim = old_dim
    return res
  end

  return original_draw_tab_title(self, view, font, is_active, is_hovered, x, y, w, h)
end
''',

    "04_color_and_search_highlight.lua": r'''-- =============================================================================
-- 04. HIGHLIGHT GLOBAL (SPLITS) + CORES INLINE (#HEX, {R, G, B}) + GUTTER AMARELO
-- =============================================================================
local core = require "core"
local Doc = require "core.doc"
local DocView = require "core.docview"

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local function draw_rect_safe(x, y, w, h, color)
  if rencache and rencache.draw_rect then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

local original_doc_insert = Doc.insert
function Doc:insert(line, col, text)
  self.modified_lines = self.modified_lines or {}
  self.modified_lines[line] = true
  return original_doc_insert(self, line, col, text)
end

local original_doc_remove = Doc.remove
function Doc:remove(line1, col1, line2, col2)
  self.modified_lines = self.modified_lines or {}
  self.modified_lines[line1] = true
  return original_doc_remove(self, line1, col1, line2, col2)
end

local original_doc_save = Doc.save
function Doc:save(...)
  self.modified_lines = {}
  return original_doc_save(self, ...)
end

local function get_active_highlight_query()
  local active_view = core.active_view
  if active_view and active_view.doc and active_view.doc:has_selection() then
    local l1, c1, l2, c2 = active_view.doc:get_selection(true)
    if l1 == l2 and c1 ~= c2 then
      local sel = active_view.doc:get_text(l1, c1, l2, c2)
      if sel and #sel >= 1 and #sel <= 100 and not sel:find("\n") and not sel:match("^%s+$") then
        return sel
      end
    end
  end
  if core.command_view and core.command_view.text and #core.command_view.text > 0 then
    local cv_text = core.command_view.text
    if #cv_text >= 1 and #cv_text <= 100 and not cv_text:find("\n") and not cv_text:match("^%s+$") then
      return cv_text
    end
  end
  return nil
end

local function get_col_x(view, line_text, col)
  if not line_text or col <= 1 then return 0 end
  return view:get_font():get_width(line_text:sub(1, col - 1))
end

local function parse_any_color(text)
  local hex = text:match("^#([%da-fA-F]+)$")
  if hex then
    local len = #hex
    if len == 3 or len == 4 then
      local r = tonumber(hex:sub(1, 1):rep(2), 16) or 0
      local g = tonumber(hex:sub(2, 2):rep(2), 16) or 0
      local b = tonumber(hex:sub(3, 3):rep(2), 16) or 0
      return { r, g, b, 220 }
    elseif len == 6 or len == 8 then
      local r = tonumber(hex:sub(1, 2), 16) or 0
      local g = tonumber(hex:sub(3, 4), 16) or 0
      local b = tonumber(hex:sub(5, 6), 16) or 0
      return { r, g, b, 220 }
    end
  end
  local r, g, b = text:match("^{%s*(%d+)%s*,%s*(%d+)%s*,%s*(%d+)")
  if r and g and b then
    local nr, ng, nb = tonumber(r) or 0, tonumber(g) or 0, tonumber(b) or 0
    if nr <= 255 and ng <= 255 and nb <= 255 then
      return { nr, ng, nb, 220 }
    end
  end
  return nil
end

local HIGHLIGHT_BLUE = { 0, 108, 255, 140 }
local MODIFIED_YELLOW = { 234, 179, 8, 200 }

local original_draw_line_body = DocView.draw_line_body
function DocView:draw_line_body(line, x, y)
  pcall(function()
    local doc = self.doc
    if not doc or not doc.lines then return end
    local line_text = doc.lines[line]
    if not line_text then return end
    local line_h = self.get_line_height and self:get_line_height() or 16

    local search_text = get_active_highlight_query()
    if search_text then
      local start_idx = 1
      while true do
        local s_idx, e_idx = line_text:find(search_text, start_idx, true)
        if not s_idx then break end
        local x1 = x + get_col_x(self, line_text, s_idx)
        local x2 = x + get_col_x(self, line_text, e_idx + 1)
        local w = x2 - x1
        if w > 0 then
          draw_rect_safe(x1, y, w, line_h, HIGHLIGHT_BLUE)
        end
        start_idx = e_idx + 1
      end
    end
  end)
  return original_draw_line_body(self, line, x, y)
end
''',

    "05_split_mover.lua": r'''-- =============================================================================
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
''',

    "06_tree_manager.lua": r'''-- =============================================================================
-- 06. GESTÃO DINÂMICA DE PROJETOS NA TREEVIEW
-- =============================================================================
local core = require "core"
local common = require "core.common"
local command = require "core.command"

local function normalize_path(path)
  if not path then return nil end
  local str = tostring(path):gsub('^["\']', ''):gsub('["\']$', '')
  if str:sub(1, 1) == "~" then
    local home = os.getenv("USERPROFILE") or os.getenv("HOME") or ""
    str = home .. str:sub(2)
  end
  return system.absolute_path(str) or str
end

local function ensure_parent_directories(file_path)
  local dir = file_path:match("^(.*)[/\\]")
  if dir and dir ~= "" then
    local current = ""
    for part in dir:gmatch("[^/\\]+") do
      if current == "" and part:find("^[a-zA-Z]:") then
        current = part
      else
        current = (current == "" and "" or current .. PATHSEP) .. part
        pcall(function() system.mkdir(current) end)
      end
    end
  end
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
    local clean_userdir = tostring(system.absolute_path(USERDIR) or USERDIR):gsub("\\", "/"):lower()
    for _, p in ipairs(core.project_directories) do
      local raw_path = type(p) == "table" and (p.path or p.name) or p
      local ppath = tostring(raw_path or ""):gsub("\\", "/"):lower()
      if ppath == clean_userdir then
        core.remove_project_directory(type(p) == "table" and (p.path or p) or p)
        core.log("Lite XL Config desanexado da Árvore.")
        core.redraw = true
        return
      end
    end
    core.add_project_directory(USERDIR)
    core.log("Lite XL Config anexado à Árvore.")
    core.redraw = true
  end,

  ["treeview:add-project-folder"] = function()
    core.command_view:enter("Caminho do Projeto para Adicionar", {
      submit = function(path)
        path = normalize_path(path)
        if path and tostring(path):match("%S") then
          local info = system.get_file_info(path)
          if info and info.type == "dir" then
            core.add_project_directory(path)
            core.log("Projeto anexado à Árvore: " .. tostring(path))
            core.redraw = true
          elseif info and info.type == "file" then
            core.root_view:open_doc(core.open_doc(path))
          else
            core.error("Caminho inexistente no disco: " .. tostring(path))
          end
        end
      end
    })
  end,
})
''',

    "07_keymaps_and_help.lua": r'''-- =============================================================================
-- 07. GUIA DE ATALHOS & KEYMAP CONSOLIDADO (NOTEPAD++ COMPATIBILITY)
-- =============================================================================
keymap.add {
  ["ctrl+n"]           = "doxoade:new-doc",
  ["ctrl+o"]           = "core:open-file",
  ["ctrl+s"]           = "doc:save",
  ["ctrl+shift+s"]     = "doc:save-all",
  ["ctrl+,"]           = "doxoade:open-init-lua",
  ["ctrl+alt+u"]       = "doxoade:toggle-litexl-in-tree",
  ["ctrl+shift+l"]     = "doxoade:open-log",
  ["ctrl+f2"]          = "doxoade:open-log",
  ["ctrl+alt+c"]       = "doxoade:copy-path-menu",
  ["ctrl+shift+c"]     = "doxoade:tab-copy-relative-path",
  ["f1"]               = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+shift+?"]     = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+shift+/"]     = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+/"]           = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+alt+/"]       = "doxoade:show-shortcuts-cheat-sheet",

  ["ctrl+f"]           = "find-replace:find",
  ["f3"]               = "find-replace:repeat-find",
  ["shift+f3"]         = "find-replace:previous-find",
  ["ctrl+h"]           = "find-replace:replace",
  ["ctrl+g"]           = "doc:go-to-line",

  ["ctrl+alt+d"]       = "root:move-tab-to-opposite-panel",
  ["alt+d"]            = "root:split-right",
  ["alt+shift+d"]      = "root:split-down",
  ["ctrl+alt+left"]    = "root:switch-to-left",
  ["ctrl+alt+right"]   = "root:switch-to-right",
  ["alt+w"]            = "root:close",
  ["ctrl+w"]           = "root:close",
  ["ctrl+tab"]         = "root:switch-to-next-tab",
  ["ctrl+shift+tab"]   = "root:switch-to-previous-tab",

  ["ctrl+d"]           = "doc:duplicate-lines",
  ["ctrl+l"]           = "doc:delete-lines",
  ["ctrl+q"]           = "doc:toggle-line-comments",

  ["ctrl+alt+o"]       = "treeview:add-project-folder",
  ["ctrl+alt+r"]       = "treeview:remove-project-folder",
}
''',

    "08_pot_panel.lua": r'''-- =============================================================================
-- 08. HUB DE FERRAMENTAS LATERAIS (DUMPPOT & WORKSPACE HUB)
-- =============================================================================
local core = require "core"
local DocView = require "core.docview"
local command = require "core.command"

local doxoade_cfg_dir = USERDIR .. PATHSEP .. ".doxoade"
pcall(function() system.mkdir(doxoade_cfg_dir) end)
local dumppot_file = doxoade_cfg_dir .. PATHSEP .. "dumppot.txt"

pcall(function()
  local f = io.open(dumppot_file, "a")
  if f then f:close() end
end)

local function get_or_create_right_panel()
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
  if #leaves >= 2 then
    return leaves[#leaves]
  elseif #leaves == 1 then
    return leaves[1]:split("right")
  end
  return core.root_view.root_node:get_primary_node()
end

local function open_in_right_panel(file_path, log_msg)
  local right_node = get_or_create_right_panel()
  local doc = core.open_doc(file_path)
  for _, v in ipairs(right_node.views) do
    if v.doc == doc then
      right_node.active_view = v
      core.set_active_view(v)
      core.redraw = true
      return v
    end
  end
  local view = DocView(doc)
  right_node:add_view(view)
  core.set_active_view(view)
  if log_msg then core.log(log_msg) end
  core.redraw = true
  return view
end

command.add(nil, {
  ["doxoade:open-pot-in-right-panel"] = function()
    open_in_right_panel(dumppot_file, "Dumppot fixado na direita.")
  end,
  ["doxoade:open-workspace-hub"] = function()
    open_in_right_panel(dumppot_file, "Workspace Hub ativado na direita.")
  end,
})
''',

    "09_panel_manager.lua": r'''-- =============================================================================
-- 09. GERENCIADOR DE PAINÉIS E SLOTS (DIREITA, BAIXO, ESQUERDA)
-- =============================================================================
local core = require "core"
local DocView = require "core.docview"
local command = require "core.command"

local PanelSlots = {}

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

function PanelSlots.get_slot_node(slot_type)
  local leaves = get_doc_leaves(core.root_view.root_node)
  if slot_type == "right" then
    if #leaves >= 2 then
      return leaves[#leaves]
    elseif #leaves == 1 then
      return leaves[1]:split("right")
    end
  elseif slot_type == "bottom" then
    local active_node = core.root_view:get_active_node()
    if active_node and not active_node.locked then
      return active_node:split("down")
    end
  elseif slot_type == "left" then
    if #leaves >= 1 then
      return leaves[1]
    end
  end
  return core.root_view.root_node:get_primary_node()
end

command.add(nil, {
  ["doxoade:split-bottom-panel"] = function()
    local active_node = core.root_view:get_active_node()
    if active_node and not active_node.locked then
      active_node:split("down")
      core.redraw = true
    end
  end
})
''',

    "10_forensic_engine.lua": r'''-- =============================================================================
-- 10. DOXOADE FORENSIC TELEMETRY ENGINE
-- =============================================================================
local core = require "core"
local diag_dir = USERDIR .. PATHSEP .. ".doxoade" .. PATHSEP .. "diagnostics"
pcall(function() system.mkdir(diag_dir) end)
local report_path = diag_dir .. PATHSEP .. "forensic_report.txt"

local forensic_data = {
    errors = {},
    performance = {},
    env_plugins = {},
    start_time = os.time()
}

local original_core_error = core.error
function core.error(...)
    local msg = table.concat({...}, " ")
    local traceback = debug.traceback("", 2)
    local culprit = "core"
    local culprit_file = "unknown"
    local culprit_line = 0

    for line in traceback:gmatch("[^\r\n]+") do
        if not line:match("core[/\\]init%.lua") and 
           not line:match("forensic_engine%.lua") and
           not line:match("%[C%]:") and
           not line:match("%[string") then
            local file, ln = line:match("(.-):(%d+):")
            if file and not file:match("core[/\\]") then
                culprit_file = file
                culprit_line = tonumber(ln) or 0
                culprit = file:match("plugins[/\\](.-)[/\\]") or 
                          file:match("plugins[/\\](.-)%.lua") or "user_config"
                break
            end
        end
    end

    table.insert(forensic_data.errors, {
        msg = msg,
        culprit = culprit,
        file = culprit_file,
        line = culprit_line,
        trace = traceback,
        time = os.date("%H:%M:%S")
    })

    return original_core_error(...)
end
''',

    "11_tab_context_menu.lua": r'''-- =============================================================================
-- 11. MENU FLUTUANTE NATIVO IMEDIATO (IMMEDIATE-MODE TAB POPUP)
-- =============================================================================
local core = require "core"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local Node = require "core.node"
local RootView = require "core.rootview"

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
  if not view or not view.doc or not view.doc.filename then
    return nil
  end

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
        if system.show_in_file_manager then
          system.show_in_file_manager(abs_path)
        elseif PLATFORM == "Windows" then
          system.exec(string.format('explorer.exe /select,"%s"', clean_abs))
        else
          system.exec(string.format('xdg-open "%s"', dir_path))
        end
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
      local text_x = x + PADDING_X
      local text_y = curr_y + PADDING_Y

      draw_text_safe(font, it.text, text_x, text_y, text_color)
      curr_y = curr_y + item_h
    end
  end
end

local original_rootview_mouse_moved = RootView.on_mouse_moved
function RootView:on_mouse_moved(x, y, ...)
  if FloatingMenu.visible then
    local mx = FloatingMenu.x
    local my = FloatingMenu.y
    local mw = FloatingMenu.w
    local mh = FloatingMenu.h
    local item_h = get_item_height()

    if x >= mx and x <= mx + mw and y >= my and y <= my + mh then
      local rel_y = y - my - 4
      local idx = math.floor(rel_y / item_h) + 1
      if idx >= 1 and idx <= #FloatingMenu.items then
        if FloatingMenu.hovered_idx ~= idx then
          FloatingMenu.hovered_idx = idx
          core.redraw = true
        end
        return true
      end
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

        if item and item.action then
          item.action()
        end
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

command.add("core.docview", {
  ["doxoade:copy-path-menu"] = function()
    local view = core.active_view
    if view then
      open_floating_menu(view, 80, 50)
    end
  end
})
''',

    "12_ui_forge.lua": r'''-- =============================================================================
-- 12. DOXOADE UI FORGE - Sistema Declarativo de Interface
-- =============================================================================
local core = require "core"
local command = require "core.command"
local keymap = require "core.keymap"

local UIForge = {
  commands = {},
  keymaps = {},
  panels = {},
}

function UIForge.register_command(name, handler)
  UIForge.commands[name] = handler
end

function UIForge.register_keymap(keys, command_name)
  UIForge.keymaps[keys] = command_name
end

function UIForge.register_panel(spec)
  table.insert(UIForge.panels, spec)
end

function UIForge.build_all()
  local cmd_table = {}
  for name, handler in pairs(UIForge.commands) do
    cmd_table[name] = handler
  end
  if next(cmd_table) then
    command.add(nil, cmd_table)
  end

  if next(UIForge.keymaps) then
    keymap.add(UIForge.keymaps)
  end

  core.log("UIForge: " ..
    #UIForge.panels .. " painéis, " ..
    tostring(next(UIForge.commands) and "comandos" or "0 comandos") .. ", " ..
    tostring(next(UIForge.keymaps) and "atalhos" or "0 atalhos") ..
    " registrados.")
end

UIForge.register_command("doxoade:tab-open-in-explorer", function()
  local view = core.active_view
  if not view or not view.doc or not view.doc.filename then
    core.error("Nenhum arquivo ativo.")
    return
  end
  local abs_path = system.absolute_path(view.doc.filename) or view.doc.filename
  local dir_path = abs_path:match("^(.*)[/\\]") or abs_path
  if system.show_in_file_manager then
    system.show_in_file_manager(abs_path)
  elseif PLATFORM == "Windows" then
    system.exec(string.format('explorer.exe /select,"%s"', abs_path:gsub('/', '\\')))
  else
    system.exec(string.format('xdg-open "%s"', dir_path))
  end
  core.log("Explorer aberto em: " .. dir_path)
end)

UIForge.register_keymap("ctrl+alt+e", "doxoade:tab-open-in-explorer")

UIForge.build_all()
''',
}


def _clean_lua_source(source: str) -> str:
    """Lexer atômico de passagem única (elimina colisões entre regexes e strings)."""
    # Ordem estrita de precedência léxica do Lua:
    # 1. Comentário de bloco: --[[ ... ]]
    # 2. Comentário de linha: -- ...
    # 3. String multilinha: [[ ... ]] ou [=[ ... ]=]
    # 4. String aspas duplas: " ... "
    # 5. String aspas simples: ' ... '
    lua_pattern = re.compile(
        r"--\[(=*)\[.*?\]\1\]|"  # 1. Comentário de bloco
        r"--[^\r\n]*|"  # 2. Comentário de linha
        r"\[(=*)\[.*?\]\2\]|"  # 3. String multilinha
        r'"(?:\\.|[^"\\])*"|'  # 4. String aspas duplas
        r"'(?:\\.|[^'\\])*'",  # 5. String aspas simples
        re.DOTALL,
    )
    # Substitui qualquer comentário ou string por espaço atômico
    return lua_pattern.sub(" ", source)

class LiteXLEngine:
    """Motor Soberano Lite XL V17.0."""

    # =========================================================================
    # 🗂️ PRESERVAÇÃO DE WORKSPACE, SESSÃO & GOLDEN SNAPSHOT
    # =========================================================================

    @classmethod
    def get_workspace_dir(cls) -> Path:
        """Diretório de sessões e abas do Lite XL."""
        return cls.get_user_dir() / "workspace"

    @classmethod
    def get_workspace_backup_dir(cls) -> Path:
        """Diretório de segurança para snapshots de sessão do Doxoade."""
        return cls.get_user_dir() / ".doxoade" / "workspace_backup"

    # =========================================================================
    # 🗂️ PRESERVAÇÃO INTEGRAL DE SESSÃO (WORKSPACE, SESSION.LUA, SETTINGS)
    # =========================================================================

    @classmethod
    def get_session_artifacts(cls) -> List[Path]:
        """Retorna todos os artefatos de sessão persistente no USERDIR."""
        user_dir = cls.get_user_dir()
        artifacts = []

        # 1. Diretório de workspace (splits, abas, projetos)
        ws_dir = user_dir / "workspace"
        if ws_dir.exists() and ws_dir.is_dir():
            artifacts.append(ws_dir)

        # 2. Arquivos de sessão e configurações dinâmicas
        for fname in ["session.lua", "user_settings.lua", "session.json"]:
            p = user_dir / fname
            if p.exists() and p.is_file():
                artifacts.append(p)

        return artifacts

    @classmethod
    def backup_workspace_state(cls) -> bool:
        """Cria snapshot abrangente de todos os artefatos de sessão do usuário."""
        try:
            bkp_dir = cls.get_workspace_backup_dir()
            bkp_dir.mkdir(parents=True, exist_ok=True)
            artifacts = cls.get_session_artifacts()

            for art in artifacts:
                dest = bkp_dir / art.name
                if art.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest, ignore_errors=True)
                    shutil.copytree(art, dest, dirs_exist_ok=True)
                elif art.is_file():
                    shutil.copy2(art, dest)

            return True
        except Exception:
            return False

    @classmethod
    def restore_workspace_state(cls) -> bool:
        """Restaura o estado exato de abas, splits, session.lua e user_settings."""
        try:
            bkp_dir = cls.get_workspace_backup_dir()
            user_dir = cls.get_user_dir()
            if not bkp_dir.exists():
                return False

            for item in bkp_dir.iterdir():
                dest = user_dir / item.name
                if item.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                elif item.is_file():
                    shutil.copy2(item, dest)

            return True
        except Exception:
            return False

    @classmethod
    def get_stable_init_path(cls) -> Path:
        """Retorna o caminho do snapshot estável (Golden State)."""
        return cls.get_init_lua_path().with_suffix(".lua.stable")

    @classmethod
    def get_broken_init_path(cls) -> Path:
        """Retorna o caminho de quarentena do init que falhou."""
        return cls.get_init_lua_path().with_suffix(".lua.broken")

    @classmethod
    def promote_to_stable_snapshot(cls) -> bool:
        """Promove o init.lua atual a Golden Snapshot estável."""
        init_path = cls.get_init_lua_path()
        if not init_path.exists():
            return False
        try:
            stable_path = cls.get_stable_init_path()
            shutil.copy2(init_path, stable_path)
            return True
        except Exception:
            return False

    @classmethod
    def restore_stable_snapshot(cls) -> Tuple[bool, str]:
        """Restaura o último init.lua estável conhecido."""
        init_path = cls.get_init_lua_path()
        stable_path = cls.get_stable_init_path()

        if init_path.exists():
            try:
                broken_path = cls.get_broken_init_path()
                shutil.copy2(init_path, broken_path)
            except Exception:
                pass

        if stable_path.exists():
            try:
                shutil.copy2(stable_path, init_path)
                return True, "Golden Snapshot (.stable) restaurado com sucesso."
            except Exception as e:
                return False, f"Falha ao copiar snapshot estável: {e}"

        try:
            cls.install_sovereign_config()
            return True, "Snapshot estável inexistente. Configuração padrão instalada."
        except Exception as e:
            return False, f"Falha no fallback de emergência: {e}"

    @staticmethod
    def get_code_snippet(
        lines: List[str], line_no: int, radius: int = 2
    ) -> List[Tuple[int, bool, str]]:
        """Retorna tuplas (numero_linha, is_target, texto) para renderização visual."""
        start = max(1, line_no - radius)
        end = min(len(lines), line_no + radius)
        return [
            (ln, ln == line_no, lines[ln - 1]) for ln in range(start, end + 1)
        ]

    @classmethod
    def fix_templates(cls, dry_run: bool = True) -> Dict[str, Any]:
        """Inspeciona e corrige templates com suporte a Dry-Run e diff visual."""
        t_dir = cls.get_template_dir()
        report = {"dry_run": dry_run, "fixed_files": [], "total_fixes": 0}

        if not t_dir.exists():
            return report

        for tf in sorted(list(t_dir.glob("*.lua"))):
            raw_content = tf.read_text(encoding="utf-8", errors="replace")
            lines = raw_content.splitlines()
            modified_lines = []
            file_diffs = []

            for idx, line in enumerate(lines, 1):
                original_line = line
                repaired_line = line

                # 1. Polyfill universal do rencache
                if re.search(r"local\s+rencache\s*=\s*rencache\b", repaired_line) and not re.search(
                    r"rawget\(_G,\s*[\"']rencache[\"']\)", repaired_line
                ):
                    repaired_line = re.sub(
                        r"local\s+rencache\s*=\s*rencache\b",
                        UNIVERSAL_RENCACHE_POLYFILL,
                        repaired_line,
                    )
                    file_diffs.append({
                        "line": idx,
                        "type": "Polyfill Universal rencache",
                        "old": original_line.strip(),
                        "new": repaired_line.strip(),
                    })

                # 2. Correção de API C obsoleta
                if "system.execute(" in repaired_line:
                    repaired_line = repaired_line.replace("system.execute(", "system.exec(")
                    file_diffs.append({
                        "line": idx,
                        "type": "Correção de API C (system.exec)",
                        "old": original_line.strip(),
                        "new": repaired_line.strip(),
                    })

                # 3. Deduplicação de declaração de funções
                if repaired_line.count("local function ") > 1:
                    first_decl = re.findall(r"local function \w+\([^)]*\)", repaired_line)
                    if first_decl:
                        repaired_line = first_decl[0]
                        file_diffs.append({
                            "line": idx,
                            "type": "Deduplicação de declaração de função",
                            "old": original_line.strip(),
                            "new": repaired_line.strip(),
                        })

                modified_lines.append(repaired_line)

            if file_diffs:
                new_content = "\n".join(modified_lines)
                if not dry_run:
                    tf.write_text(new_content, encoding="utf-8")

                report["fixed_files"].append({
                    "file": tf.name,
                    "path": str(tf),
                    "fixes": len(file_diffs),
                    "diffs": file_diffs,
                })
                report["total_fixes"] += len(file_diffs)

        return report

    @staticmethod
    def get_user_dir() -> Path:
        home = Path.home()
        xdg_config = os.getenv("XDG_CONFIG_HOME")
        if xdg_config and (Path(xdg_config) / "lite-xl").exists():
            return Path(xdg_config) / "lite-xl"

        dot_config = home / ".config" / "lite-xl"
        if dot_config.exists():
            return dot_config

        if sys.platform == "win32":
            appdata = os.getenv("APPDATA")
            if appdata and (Path(appdata) / "lite-xl").exists():
                return Path(appdata) / "lite-xl"

        return dot_config

    @classmethod
    def get_template_dir(cls) -> Path:
        return Path(__file__).parent / "template"

    @classmethod
    def get_init_lua_path(cls) -> Path:
        return cls.get_user_dir() / "init.lua"

    @classmethod
    def get_session_log_path(cls) -> Path:
        return cls.get_user_dir() / "session_log.txt"

    @classmethod
    def get_error_txt_path(cls) -> Path:
        return cls.get_user_dir() / "error.txt"

    @classmethod
    def get_ipc_queue_path(cls) -> Path:
        return cls.get_user_dir() / ".ipc_queue"

    @classmethod
    def bootstrap_templates_if_missing(cls):
        """Auto-cria a pasta e os 13 arquivos .lua modulares caso não existam."""
        t_dir = cls.get_template_dir()
        t_dir.mkdir(parents=True, exist_ok=True)
        for fname, content in DEFAULT_TEMPLATE_CHUNKS.items():
            fpath = t_dir / fname
            if not fpath.exists():
                fpath.write_text(content, encoding="utf-8")

    @classmethod
    def get_template_files(cls) -> List[Path]:
        cls.bootstrap_templates_if_missing()
        return sorted(cls.get_template_dir().glob("*.lua"))

    @classmethod
    def verify_templates(cls) -> Dict[str, Any]:
        """Audita todos os arquivos de template e retorna o laudo consolidado."""
        t_dir = cls.get_template_dir()
        files = cls.get_template_files()
        report: Dict[str, Any] = {
            "all_ok": True,
            "total_files": len(files),
            "files": {},
            "errors": [],
        }

        for f in files:
            raw = f.read_text(encoding="utf-8", errors="replace")
            lines = raw.splitlines()
            file_errors: List[str] = []
            findings: List[Dict[str, Any]] = []

            # 1. Scanner léxico (strict.lua + vararg)
            scan_errs = cls.compile_scan_lua(raw)
            for se in scan_errs:
                file_errors.append(se)
                m_ln = re.search(r"linha (\d+):", se)
                ln = min(int(m_ln.group(1)), len(lines)) if m_ln else len(lines)
                findings.append({
                    "line": ln,
                    "msg": se,
                    "type": "error",
                    "snippet": cls.get_code_snippet(lines, ln),
                })

            # 2. Compilação real individual
            real_err = cls.true_compile_check(f)
            if real_err and real_err != "NO_RUNTIME":
                file_errors.append(f"Erro de compilação: {real_err}")

            # 3. Balanceamento de blocos
            clean_code = _clean_lua_source(raw)
            opens = len(re.findall(r"\b(?:function|if|do)\b", clean_code))
            closes = len(re.findall(r"\b(?:end)\b", clean_code))
            if opens != closes:
                diff = opens - closes
                file_errors.append(
                    f"Escopo desbalanceado: {abs(diff)} bloco(s) '{'sem end' if diff > 0 else 'end excedente'}' "
                    f"(abertos: {opens}, fechados: {closes})"
                )
                findings.append({
                    "line": len(lines),
                    "msg": f"Desbalanceamento de blocos ({opens} vs {closes})",
                    "type": "error",
                    "snippet": cls.get_code_snippet(lines, len(lines)),
                })

            # Definição estrita de status
            status = "FAIL" if len(file_errors) > 0 else "PASS"
            if status == "FAIL":
                report["all_ok"] = False
                report["errors"].extend(file_errors)

            report["files"][f.name] = {
                "status": status,
                "lines": len(lines),
                "errors": file_errors,
                "findings": findings,
            }

        return report

    @classmethod
    def generate_sovereign_init(cls) -> str:
        """Gera o init.lua consolidado com rodapé canônico de handshake."""
        files = cls.get_template_files()
        chunks = []

        header = (
            "-- =============================================================================\n"
            "-- ⚡ DOXOADE SOVEREIGN LITE XL INIT (AUTO-GERADO)\n"
            f"-- Total de templates incorporados: {len(files)}\n"
            "-- =============================================================================\n\n"
        )
        chunks.append(header)

        for f in files:
            content = f.read_text(encoding="utf-8", errors="replace")
            chunks.append(f"-- 🧩 MÓDULO: {f.name}\n{content}\n\n")

        # 🛡️ Rodapé garantido de Handshake de Boot (independente de templates opcionais)
        footer = (
            "-- =============================================================================\n"
            "-- 🏁 FINALIZAÇÃO DO SOVEREIGN BOOT\n"
            "-- =============================================================================\n"
            'core.log("=== SOVEREIGN BOOT OK ===")\n'
        )
        chunks.append(footer)

        return "".join(chunks)

    @classmethod
    def find_executable(cls) -> Optional[Path]:
        if sys.platform == "win32":
            known_locations = [
                Path("C:/Program Files/Lite XL/lite-xl.exe"),
                Path("C:/Program Files (x86)/Lite XL/lite-xl.exe"),
                Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Lite XL\lite-xl.exe")),
                Path(os.path.expandvars(r"%APPDATA%\Lite XL\lite-xl.exe")),
                Path(os.path.expandvars(r"%USERPROFILE%\scoop\apps\lite-xl\current\lite-xl.exe")),
            ]
            for loc in known_locations:
                if loc.exists() and loc.is_file():
                    return loc

        scripts_dir = str(Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")).lower()
        path_entries = os.environ.get("PATH", "").split(os.pathsep)

        for entry in path_entries:
            if not entry or entry.lower().rstrip("\\/") == scripts_dir.rstrip("\\/"):
                continue
            p = Path(entry)
            if sys.platform == "win32":
                candidate = p / "lite-xl.exe"
                if candidate.exists() and candidate.is_file():
                    return candidate
            else:
                candidate = p / "lite-xl"
                if candidate.exists() and os.access(candidate, os.X_OK):
                    return candidate

        return None

    @classmethod
    def is_process_alive(cls) -> bool:
        """Verifica apenas se o processo do Lite XL está vivo no sistema operacional."""
        if sys.platform == "win32":
            try:
                out = subprocess.check_output(
                    [
                        "tasklist",
                        "/FI",
                        "IMAGENAME eq lite-xl.exe",
                        "/FO",
                        "CSV",
                        "/NH",
                    ],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
                return any(
                    line.strip().lower().startswith('"lite-xl.exe"')
                    or line.strip().lower().startswith("lite-xl.exe")
                    for line in out.splitlines()
                )
            except Exception:
                return False
        else:
            try:
                out = subprocess.check_output(
                    ["pgrep", "-f", "lite-xl"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
                return bool(out.strip())
            except Exception:
                return False

    @classmethod
    def is_running(cls, focus_window: bool = True) -> bool:
        """
        Compatibilidade com o comportamento antigo.

        Por padrão:
        - verifica se o processo está vivo;
        - tenta focar a janela;
        - retorna o resultado do foco.

        Para apenas checar processo sem focar:
            LiteXLEngine.is_running(focus_window=False)
        """
        if not cls.is_process_alive():
            return False

        if focus_window:
            return cls.focus_running_window()

        return True

    @classmethod
    def focus_running_window(cls) -> bool:
        """Tenta trazer a janela do Lite XL para o primeiro plano (Best Effort)."""
        if sys.platform == "win32":
            try:
                cmd = (
                    "$ws = New-Object -ComObject WScript.Shell; if"
                    " ($ws.AppActivate('Lite XL')) { exit 0 } else { exit 1 }"
                )
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", cmd],
                    capture_output=True,
                    timeout=2,
                )
                return res.returncode == 0
            except Exception:
                return False
        return True

    @classmethod
    def resolve_target_path(cls, raw_path: str) -> Tuple[Optional[str], bool, bool]:
        """Resolve caminhos e cria arquivos/pastas automaticamente se não existirem."""
        if not raw_path or raw_path.strip() == ".":
            cwd = Path.cwd().resolve()
            return str(cwd), True, True

        clean = raw_path.strip().strip("'\"")
        if clean.startswith("~"):
            clean = os.path.expanduser(clean)

        p = Path(clean)
        try:
            abs_p = p.resolve()
        except Exception:
            abs_p = p.absolute()

        if not abs_p.exists():
            if clean.endswith(("\\", "/")) or not abs_p.suffix:
                abs_p.mkdir(parents=True, exist_ok=True)
                return str(abs_p), True, True
            else:
                abs_p.parent.mkdir(parents=True, exist_ok=True)
                abs_p.touch(exist_ok=True)
                return str(abs_p), True, False

        return str(abs_p), True, abs_p.is_dir()

    _LUA_NOISE = re.compile(
      r"--\[[=]*\[[\s\S]*?\][=]*\]"          # comentário longo
      r"|--[^\n]*"                            # comentário de linha
      r"|\[[=]*\[[\s\S]*?\][=]*\]"            # string longa
      r"|\"(?:\\.|[^\"\\\n])*\""              # string dupla
      r"|'(?:\\.|[^'\\\n])*'"                 # string simples
    )

    @staticmethod
    def _blank_keep_lines(m) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    @classmethod
    def compile_scan_lua(cls, source: str) -> List[str]:
        """Tripwire léxico: detecta vararg fora de escopo e chamadas sem require."""
        errors: List[str] = []

        # 1. Checagem estática de strict.lua: uso de 'core.' sem require "core"
        clean = cls._LUA_NOISE.sub(cls._blank_keep_lines, source)
        if re.search(r"\bcore\.[a-zA-Z_]", clean):
            has_core_decl = (
                re.search(r"local\s+core\s*=", source)
                or re.search(r"require\s*\(?[\"']core[\"']\)?", source)
            )
            if not has_core_decl:
                errors.append(
                    "strict.lua: Chamadas para 'core.*' detectadas sem 'local core = require \"core\"'"
                )

        # 2. Tripwire de vararg (...)
        stack = [["f", True]]
        last_ctrl = None
        n = len(clean)
        tok = re.compile(
            r"\bfunction\b|\bif\b|\bfor\b|\bwhile\b|\brepeat\b|\bdo\b|\bend\b|\buntil\b|\.\.\."
        )

        for m in tok.finditer(clean):
            t = m.group(0)
            if t in ("if", "for", "while", "repeat"):
                stack.append(["b", False])
                last_ctrl = t
            elif t == "do":
                if last_ctrl not in ("for", "while"):
                    stack.append(["b", False])
                last_ctrl = None
            elif t == "function":
                depth = 0
                vararg = False
                j = m.end()
                while j < n:
                    c = clean[j]
                    if c == "(":
                        depth += 1
                    elif c == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    elif c == "." and clean.startswith("...", j):
                        vararg = True
                        j += 2
                    j += 1
                stack.append(["f", vararg])
                last_ctrl = None
            elif t in ("end", "until"):
                if len(stack) > 1:
                    stack.pop()
                last_ctrl = None
            elif t == "...":
                for frame in reversed(stack):
                    if frame[0] == "f":
                        if not frame[1]:
                            line = clean.count("\n", 0, m.start()) + 1
                            errors.append(
                                f"linha {line}: cannot use '...' outside a vararg function"
                            )
                        break

        return errors

    @classmethod
    def lua_runtime_info(cls) -> Optional[Tuple[str, str]]:
        """Retorna (caminho_do_lua, banner_de_versao) ou None se ausente."""
        lua = cls._find_lua_runtime()
        if not lua:
            return None
        try:
            res = subprocess.run(
                [lua, "-v"], capture_output=True, text=True, timeout=5
            )
            banner = (res.stdout + res.stderr).strip()
            version = banner.splitlines()[0] if banner else "versão desconhecida"
            return lua, version
        except Exception:
            return lua, "versão desconhecida"

#    @staticmethod
    @classmethod
    def _find_lua_runtime(cls) -> Optional[str]:
        """Encontra runtime Lua usando o sistema de gestão."""
        if LuaRuntimeManager is None:
            return None
        runtime = LuaRuntimeManager.find_lua_runtime()
        return str(runtime[0]) if runtime else None

    @classmethod
    def ensure_lua_runtime(cls) -> Optional[str]:
        """Garante que um runtime Lua esteja disponível, instalando se necessário."""
        runtime = LuaRuntimeManager.ensure_lua_runtime()
        return str(runtime[0]) if runtime else None

    @classmethod
    def true_compile_check(cls, path: Union[str, Path]) -> Optional[str]:
        """Compilação real via runtime Lua externo. None = OK."""
        runtime = LuaRuntimeManager.find_lua_runtime()
        if not runtime:
            return "NO_RUNTIME"

        exe_path, version = runtime
        # Normaliza o caminho com barras '/' evitando problemas de escape no Windows
        clean_path = str(path).replace("\\", "/").replace('"', '\\"')

        # Script com caminho literal embutido: sem dependência de arg[] e com exit(0)
        probe = (
            f'local f, err = loadfile("{clean_path}") '
            f'if not f then '
            f'  io.stderr:write(tostring(err)) '
            f'  os.exit(1) '
            f'else '
            f'  os.exit(0) '
            f'end'
        )

        try:
            res = subprocess.run(
                [str(exe_path), "-e", probe],
                capture_output=True,
                text=True,
                timeout=5,
                stdin=subprocess.DEVNULL,  # 🛡️ Impede qualquer bloqueio em STDIN
            )
            if res.returncode != 0:
                err_msg = (res.stderr or res.stdout).strip()
                return err_msg or "Erro de compilação desconhecido"
            return None
        except Exception as e:
            return f"Falha na execução do probe de runtime: {e}"

    @classmethod
    def probe_boot(cls, timeout: float = 8.0, start_time: Optional[float] = None) -> bool:
        """Prova de boot: valida se o 00_header criou/atualizou o session_log.txt nesta sessão."""
        log_path = cls.get_session_log_path()
        mark_time = start_time or time.time()
        deadline = time.time() + timeout

        while time.time() < deadline:
            if log_path.exists():
                try:
                    mtime = log_path.stat().st_mtime
                    if mtime >= (mark_time - 1.0):
                        return True
                except OSError:
                    pass
            time.sleep(0.3)
        return False

    @classmethod
    def send_to_running_instance(cls, target_path: str) -> Tuple[bool, str]:
        resolved, exists, is_dir = cls.resolve_target_path(target_path)
        if not resolved:
            return False, "Caminho inválido."

        if not exists:
            return False, f"O caminho não existe no disco: {resolved}"

        try:
            ipc_queue = cls.get_ipc_queue_path()
            with open(ipc_queue, "a", encoding="utf-8") as f:
                f.write(resolved + "\n")
            cls.focus_running_window()
            return True, resolved
        except Exception as e:
            return False, str(e)

    @classmethod
    def cleanup_old_shims(cls):
        scripts_dir = Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")
        if not scripts_dir.exists():
            return
        for name in ["lite-xl.cmd", "litexl.cmd", "lite-lx.cmd", "lxl.cmd", "lite-xl", "litexl", "lite-lx", "lxl"]:
            target = scripts_dir / name
            if target.exists():
                try:
                    target.unlink()
                except Exception:
                    pass

    @classmethod
    def install_terminal_shims(cls) -> List[str]:
        cls.cleanup_old_shims()
        scripts_dir = Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")
        if not scripts_dir.exists():
            return []

        py_exe = str(Path(sys.executable).resolve())
        installed = []
        aliases = ["lite-xl", "litexl", "lite-lx", "lxl"]

        for alias in aliases:
            if sys.platform == "win32":
                shim_path = scripts_dir / f"{alias}.cmd"
                content = f'@echo off\n"{py_exe}" -m doxoade lite-xl open %*\n'
                shim_path.write_text(content, encoding="utf-8")
                installed.append(str(shim_path))
            else:
                shim_path = scripts_dir / alias
                content = f'#!/bin/sh\nexec "{py_exe}" -m doxoade lite-xl open "$@"\n'
                shim_path.write_text(content, encoding="utf-8")
                shim_path.chmod(0o755)
                installed.append(str(shim_path))

        return installed

    @classmethod
    def diagnose_init_file(cls, init_path: Path) -> Dict[str, Any]:
        """Diagnóstico forense do init.lua consolidado."""
        report = {"exists": False, "errors": [], "checks": []}

        if not init_path.exists():
            return report

        report["exists"] = True
        raw_content = init_path.read_text(encoding="utf-8", errors="replace")
        lines = raw_content.splitlines()

        # 1. Tripwire de compilação (scanner interno)
        scan = cls.compile_scan_lua(raw_content)
        if scan:
            report["errors"].append(
                "Erro de compilação (scanner): " + "; ".join(scan[:5])
            )

        # 2. Compilação real, se houver runtime Lua
        info = cls.lua_runtime_info()
        if info:
            lua_path, lua_version = info
            real_err = cls.true_compile_check(init_path)
            if real_err and real_err != "NO_RUNTIME":
                report["errors"].append(
                    f"Erro de compilação REAL ({lua_version}): {real_err}"
                )
            else:
                report["checks"].append(
                    f"Sintaxe validada por COMPILAÇÃO REAL "
                    f"({lua_version} em {lua_path})."
                )
        else:
            report["checks"].append(
                "⚠ Sem runtime Lua externo. Validação por scanner interno + "
                "balanceamento de blocos. Cobertura PARCIAL."
            )

        # 3. Armadilha strict.lua
        if re.search(r"local\s+rencache\s*=\s*rencache\b", raw_content) and not re.search(
            r"rawget\(_G,\s*[\"']rencache[\"']\)", raw_content
        ):
            report["errors"].append(
                "Armadilha strict.lua: 'local rencache = rencache' detectado sem rawget."
            )

        # 4. Balanceamento de blocos
        clean_code = _clean_lua_source(raw_content)
        opens = len(re.findall(r"\b(?:function|if|do)\b", clean_code))
        closes = len(re.findall(r"\b(?:end)\b", clean_code))
        if opens == closes:
            report["checks"].append(
                f"Balanceamento de blocos Lua íntegro ({len(lines)} linhas | {opens} blocos)."
            )
        else:
            diff = opens - closes
            report["errors"].append(
                f"Erro de Sintaxe Crítico: {abs(diff)} bloco(s) "
                f"{'sem end' if diff > 0 else 'end excedente'}'."
            )

        report["checks"].append("Módulos Core e C-Level APIs validados.")
        return report

    @classmethod
    def parse_keybindings(cls, init_file: Path) -> List[Dict[str, Any]]:
        """Extrai atalhos reais preservando os literais entre aspas."""
        if not init_file.exists():
            return []
        raw_content = init_file.read_text(encoding="utf-8", errors="replace")

        # Remove apenas comentários, mantendo o conteúdo das strings dos atalhos
        code_only = re.sub(
            r"--\[(=*)\[.*?\]\1\]|--[^\r\n]*", "", raw_content, flags=re.DOTALL
        )

        bindings = []
        entry_pattern = re.compile(
            r'\[\s*[\'"]([^\'"]+)[\'"]\s*\]\s*=\s*[\'"]([^\'"]+)[\'"]'
        )

        for match in entry_pattern.finditer(code_only):
            raw_key = match.group(1).strip()
            cmd = match.group(2).strip()
            bindings.append({
                "raw_key": raw_key,
                "normalized_key": raw_key.lower(),
                "command": cmd,
                "is_valid_format": (
                    raw_key == raw_key.lower() and not raw_key.startswith("+")
                ),
            })
        return bindings

    @classmethod
    def graceful_shutdown(cls, timeout: float = 1.5) -> bool:
        """Envia sinal de fechamento gracioso via IPC para salvar sessão e workspace."""
        if not cls.is_process_alive():
            return True

        # Dispara o comando que executa workspace.save() e core.quit()
        cls.send_to_running_instance("__DOXOADE_GRACEFUL_QUIT__")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not cls.is_process_alive():
                time.sleep(0.2)  # Janela de flush do I/O no Windows
                return True
            time.sleep(0.1)

        # Fallback se a janela estiver travada/bloqueada
        cls.kill_ghost_processes()
        time.sleep(0.2)
        return True

    # =========================================================================
    # 🚀 SUPERVISOR DE BOOT COM RESTAURAÇÃO DE SESSÃO ATIVA
    # =========================================================================
    @classmethod
    def launch_with_safety_guard(
        cls, target_path: Optional[str] = None, restore_session: bool = True, *args, **kwargs
    ) -> Tuple[bool, str]:
        """Inicia o Lite XL com restauração de sessão ativa e supervisão segura."""
        if restore_session:
            cls.restore_workspace_state()
        else:
            cls.backup_workspace_state()

        init_path = cls.get_init_lua_path()
        exe = cls.find_executable()
        if not exe:
            return False, "Binário do Lite XL não encontrado."

        cmd_args = [str(exe)]
        if target_path:
            cmd_args.append(str(target_path))

        # Pre-flight check estático do init.lua
        if init_path.exists():
            raw_init = init_path.read_text(encoding="utf-8", errors="replace")
            scan_errs = cls.compile_scan_lua(raw_init)
            compile_err = cls.true_compile_check(init_path)

            if scan_errs or (compile_err and compile_err != "NO_RUNTIME"):
                err_detail = "; ".join(scan_errs) if scan_errs else str(compile_err)
                cls.restore_stable_snapshot()
                cls.restore_workspace_state()
                subprocess.Popen(cmd_args)
                return False, (
                    f"PRE-FLIGHT GATE: ERRO DETECTADO NO INIT.LUA.\n"
                    f"  MODO SEGURO ATIVADO (Snapshot Estável Restaurado).\n"
                    f"  Laudo: {err_detail}"
                )

        # Limpa session_log anterior para evitar falsos positivos
        log_path = cls.get_session_log_path()
        try:
            if log_path.exists():
                log_path.unlink()
        except Exception:
            pass

        start_time = time.time()
        proc = subprocess.Popen(cmd_args)

        # Handshake Watchdog Inteligente (até 2.5s)
        boot_confirmed = False
        has_errors = False
        error_excerpt = ""
        deadline = time.time() + 2.5

        while time.time() < deadline:
            if proc.poll() is not None:
                # Processo fechou antes do tempo
                break

            if log_path.exists():
                try:
                    log_content = log_path.read_text(encoding="utf-8", errors="replace")
                    if "[ERROR]" in log_content:
                        has_errors = True
                        err_lines = [l for l in log_content.splitlines() if "[ERROR]" in l or "[TRACE]" in l]
                        error_excerpt = "\n".join(err_lines[-5:])
                        break
                    
                    # Confirmado se tem o handshake OU se o log registrou inicialização sem erros
                    if "=== SOVEREIGN BOOT OK ===" in log_content or "UIForge:" in log_content:
                        boot_confirmed = True
                        break
                except Exception:
                    pass
            time.sleep(0.15)

        # Se o processo está vivo, logou e não teve erros: SUCESSO TOTAL
        if (boot_confirmed or (log_path.exists() and not has_errors)) and not has_errors and proc.poll() is None:
            cls.promote_to_stable_snapshot()
            cls.backup_workspace_state()
            return True, "Lite XL inicializado com sucesso em Modo Soberano (Sessão Preservada)."

        # Fallback de emergência
        try:
            proc.kill()
        except Exception:
            pass

        cls.restore_stable_snapshot()
        cls.restore_workspace_state()
        subprocess.Popen(cmd_args)

        return False, (
            f"FALHA CAPTURADA NO BOOT.\n"
            f"  MODO SEGURO ATIVADO (Sessão e Snapshot Estável Restaurados).\n"
            f"  Evidência capturada:\n{error_excerpt or 'Timeout aguardando handshake.'}"
        )

    @classmethod
    def install_sovereign_config(cls, force: bool = False, backup: bool = True) -> Tuple[bool, str]:
        """Instalação com Pre-Flight Gatekeeper completo (Sintaxe + strict.lua)."""
        init_path = cls.get_init_lua_path()
        init_path.parent.mkdir(parents=True, exist_ok=True)

        content = cls.generate_sovereign_init()

        # 1. Pre-Flight Estático em Memória
        scan_errs = cls.compile_scan_lua(content)
        if scan_errs and not force:
            return False, f"Pre-Flight rejeitou o init gerado: {'; '.join(scan_errs)}"

        temp_init = init_path.with_suffix(f".tmp_{os.getpid()}")
        try:
            temp_init.write_text(content, encoding="utf-8")

            # 2. Pre-Flight de Compilação Real
            compile_err = cls.true_compile_check(temp_init)
            if compile_err and compile_err != "NO_RUNTIME" and not force:
                temp_init.unlink(missing_ok=True)
                return False, f"Pre-Flight de compilação rejeitou o init: {compile_err}"

            # 3. Gravação atômica segura
            if backup and init_path.exists():
                cls.backup_workspace_state()

            temp_init.replace(init_path)

            # Promove apenas se passou em tudo
            if not scan_errs and (not compile_err or compile_err == "NO_RUNTIME"):
                cls.promote_to_stable_snapshot()

            return True, f"Configuração soberana instalada e validada em {init_path}"
        except Exception as e:
            temp_init.unlink(missing_ok=True)
            return False, f"Falha durante a instalação: {e}"

    @classmethod
    def _clear_ipc_queue(cls) -> None:
        """Remove a fila IPC residual com segurança."""
        try:
            ipc_file = cls.get_ipc_queue_path()
            if ipc_file.exists():
                ipc_file.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass

    @classmethod
    def kill_ghost_processes(cls):
        """Mata processos fantasmas travados em segundo plano e limpa a fila IPC residual."""
        # 1. Primeiro mata os processos
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True, timeout=5)
        else:
            subprocess.run(["pkill", "-9", "-f", "lite-xl"], capture_output=True, timeout=5)
            
        # # 2. Só depois limpa a fila IPC para não descartar comandos de uma instância viva
        # ipc_file = cls.get_ipc_queue_path()
        # if ipc_file.exists():
        #     try:
        #         ipc_file.unlink()
        #     except Exception:
        #         pass

        cls._clear_ipc_queue()

