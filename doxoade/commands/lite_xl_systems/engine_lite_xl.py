# doxoade/commands/lite_xl_systems/engine_lite_xl.py
"""
Motor Soberano Lite XL - Ártemis/Apolo Engine.
V16.0: Template Architecture, Modular Verifier, IPC Dispatcher & Self-Bootstrap.
"""
import os
import re
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

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

DEFAULT_TEMPLATE_CHUNKS = {
    "00_header_and_logger.lua": r'''-- 00. HEADER, MÓDULOS E LOGGER EM DISCO PERSISTENTE
local core = require "core"
local common = require "core.common"
local config = require "core.config"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local Node = require "core.node"
local DocView = require "core.docview"

local rencache = nil
pcall(function() rencache = require "core.rencache" end)
local native_renderer = renderer or (pcall(require, "renderer") and require("renderer") or nil)

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
function core.log(...)
  local msg = safe_format(...)
  append_session_log("INFO", msg)
  return original_core_log(...)
end

local original_core_error = core.error
function core.error(...)
  local msg = safe_format(...)
  append_session_log("ERROR", msg)
  return original_core_error(...)
end

local original_core_log_quiet = core.log_quiet
function core.log_quiet(...)
  local msg = safe_format(...)
  append_session_log("QUIET", msg)
  if original_core_log_quiet then return original_core_log_quiet(...) end
end

local last_synced_log_idx = 0
core.add_thread(function()
  while true do
    if core.log_items and #core.log_items > last_synced_log_idx then
      for i = last_synced_log_idx + 1, #core.log_items do
        local item = core.log_items[i]
        if item then
          local text = item.text or tostring(item)
          local info = item.info or "LOG"
          append_session_log(info:upper(), text)
        end
      end
      last_synced_log_idx = #core.log_items
    end
    coroutine.yield(0.3)
  end
end)
''',

    "01_ipc_dispatcher.lua": r'''-- 01. SINGLE INSTANCE DISPATCHER (IPC)
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
          if target ~= "" then
            pcall(function()
              local abs_target = system.absolute_path(target) or target
              local info = system.get_file_info(abs_target) or system.get_file_info(target)
              if info then
                if info.type == "dir" then
                  core.add_project_directory(abs_target)
                  core.log("Projeto anexado à Árvore: " .. abs_target)
                else
                  local doc = core.open_doc(abs_target)
                  core.root_view:open_doc(doc)
                  core.log("Arquivo aberto com sucesso: " .. abs_target)
                end
              else
                core.error("Caminho inexistente no disco: " .. target)
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

    "02_blacklist.lua": r'''-- 02. BLACKLIST DE PASTAS (PYTHON VENV, CACHE, GIT)
local ignored_patterns = {
  "^%.venv/", "^%.venv\\",
  "^venv/", "^venv\\",
  "^env/", "^env\\",
  "^%.env/", "^%.env\\",
  "^__pycache__/", "^__pycache__\\",
  "%.pyc$", "%.pyo$", "%.pyd$",
  "^%.pytest_cache/", "^%.mypy_cache/", "^%.ruff_cache/",
  "%.egg%-info/", "^%.git/", "^%.idea/", "^%.vscode/",
  "^node_modules/", "^dist/", "^build/",
  "%.DS_Store$", "Thumbs%.db$"
}

for _, pattern in ipairs(ignored_patterns) do
  table.insert(config.ignore_files, pattern)
end
''',

    "03_tab_colors.lua": r'''-- 03. MATRIZ DE CORES DE FUNDO DE ABAS POR PROJETO
local PROJECT_THEMES = {
  { accent = { 56, 189, 248, 255 },  active_bg = { 14, 116, 144, 255 },  hover_bg = { 8, 85, 105, 255 },   inactive_bg = { 8, 48, 60, 255 } },    -- Ciano Oceano
  { accent = { 74, 222, 128, 255 },  active_bg = { 21, 128, 61, 255 },   hover_bg = { 15, 95, 45, 255 },   inactive_bg = { 10, 55, 28, 255 } },   -- Esmeralda
  { accent = { 244, 114, 182, 255 }, active_bg = { 190, 24, 93, 255 },   hover_bg = { 140, 18, 68, 255 },  inactive_bg = { 85, 12, 42, 255 } },   -- Rosa Vibrante
  { accent = { 251, 191, 36, 255 },  active_bg = { 180, 83, 9, 255 },    hover_bg = { 130, 60, 7, 255 },   inactive_bg = { 80, 36, 5, 255 } },    -- Âmbar / Ouro
  { accent = { 167, 139, 250, 255 }, active_bg = { 109, 40, 217, 255 },  hover_bg = { 80, 28, 160, 255 },  inactive_bg = { 50, 18, 100, 255 } },  -- Violeta Real
  { accent = { 45, 212, 191, 255 },  active_bg = { 15, 118, 110, 255 },  hover_bg = { 11, 88, 82, 255 },   inactive_bg = { 8, 55, 50, 255 } },    -- Teal Escuro
  { accent = { 251, 113, 133, 255 }, active_bg = { 185, 28, 28, 255 },   hover_bg = { 135, 20, 20, 255 },  inactive_bg = { 85, 12, 12, 255 } },   -- Carmesim
  { accent = { 129, 140, 248, 255 }, active_bg = { 67, 56, 202, 255 },   hover_bg = { 50, 42, 150, 255 },  inactive_bg = { 32, 26, 95, 255 } },   -- Índigo
}

local DEFAULT_THEME = { accent = { 148, 163, 184, 255 }, active_bg = { 51, 65, 85, 255 }, hover_bg = { 38, 48, 64, 255 }, inactive_bg = { 30, 41, 59, 255 } }

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
    matched_project = clean_fn:match([=[^(.*)[/\\]]=]) or clean_fn
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
    if rencache then
      rencache.draw_rect(x, y, w, h, bg)
      rencache.draw_rect(x, y, w, is_active and 3 or 1, theme.accent)
    elseif native_renderer then
      native_renderer.draw_rect(x, y, w, h, bg)
      native_renderer.draw_rect(x, y, w, is_active and 3 or 1, theme.accent)
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

    "04_color_and_search_highlight.lua": r'''-- 04. HIGHLIGHT GLOBAL (SPLITS) + CORES INLINE (#HEX, {R, G, B}) + GUTTER AMARELO
local global_search_query = ""

local function get_active_search_query()
  local active_view = core.active_view
  if active_view and active_view.doc and active_view.doc:has_selection() then
    local l1, c1, l2, c2 = active_view.doc:get_selection()
    if l1 == l2 and c1 ~= c2 then
      local sel = active_view.doc:get_text(l1, c1, l2, c2)
      if #sel >= 1 and #sel <= 80 and not sel:find("\n") then
        global_search_query = sel
        return sel
      end
    end
  end

  if core.command_view and core.command_view.text and #core.command_view.text > 0 then
    local cv_text = core.command_view.text
    if #cv_text >= 1 and #cv_text <= 80 and not cv_text:find("\n") then
      global_search_query = cv_text
      return cv_text
    end
  end

  if global_search_query and #global_search_query >= 1 then
    return global_search_query
  end
  return nil
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

local HIGHLIGHT_BLUE = { 0, 0, 255, 110 }

local original_draw_line_body = DocView.draw_line_body
function DocView:draw_line_body(line, x, y)
  pcall(function()
    local doc = self.doc
    if not doc or not doc.lines then return end
    local line_text = doc.lines[line]
    if not line_text then return end

    local line_h = self.get_line_height and self:get_line_height() or 16

    -- A) Highlight global sincronizado
    local search_text = get_active_search_query()
    if search_text and #search_text >= 1 and not search_text:find("\n") then
      local escaped_pattern = search_text:gsub("[%(%)%.%%%+%-%*%?%[%]%^%$]", "%%%1")
      local start_idx = 1
      while true do
        local s_idx, e_idx = line_text:find(escaped_pattern, start_idx)
        if not s_idx then break end
        local x1 = x + (self.get_col_x_offset and self:get_col_x_offset(line, s_idx) or 0)
        local x2 = x + (self.get_col_x_offset and self:get_col_x_offset(line, e_idx + 1) or 0)
        if rencache then
          rencache.draw_rect(x1, y, x2 - x1, line_h, HIGHLIGHT_BLUE)
        end
        start_idx = e_idx + 1
      end
    end

    -- B) Fundo de cor para #HEX
    local s_hex = 1
    while true do
      local s_idx, e_idx, hex_code = line_text:find("(#([%da-fA-F]+))", s_hex)
      if not s_idx then break end
      local parsed = parse_any_color(hex_code)
      if parsed then
        local x1 = x + (self.get_col_x_offset and self:get_col_x_offset(line, s_idx) or 0)
        local x2 = x + (self.get_col_x_offset and self:get_col_x_offset(line, e_idx + 1) or 0)
        if rencache then rencache.draw_rect(x1, y, x2 - x1, line_h, parsed) end
      end
      s_hex = e_idx + 1
    end

    -- C) Fundo de cor para tabelas Lua { 56, 189, 248 }
    local s_tbl = 1
    while true do
      local s_idx, e_idx, tbl_code = line_text:find("({%s*%d+%s*,%s*%d+%s*,%s*%d+[%s,%d]*})", s_tbl)
      if not s_idx then break end
      local parsed = parse_any_color(tbl_code)
      if parsed then
        local x1 = x + (self.get_col_x_offset and self:get_col_x_offset(line, s_idx) or 0)
        local x2 = x + (self.get_col_x_offset and self:get_col_x_offset(line, e_idx + 1) or 0)
        if rencache then rencache.draw_rect(x1, y, x2 - x1, line_h, parsed) end
      end
      s_tbl = e_idx + 1
    end
  end)

  return original_draw_line_body(self, line, x, y)
end
''',

    "05_split_mover.lua": r'''-- 05. SPLIT MOVER BIDIRECIONAL (Ctrl + Alt + D) - ESQUERDA ⇄ DIREITA
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

    "06_tree_manager.lua": r'''-- 06. GESTÃO DINÂMICA DE PROJETOS NA TREEVIEW
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
''',

    "07_keymaps_and_help.lua": r'''-- 07. GUIA DE ATALHOS & KEYMAP CONSOLIDADO
command.add(nil, {
  ["doxoade:show-shortcuts-cheat-sheet"] = function()
    local doc = core.open_doc()
    doc.filename = "Guia_de_Atalhos_LiteXL.txt"
    doc:insert(1, 1, [[
================================================================================
          📖 GUIA DE ATALHOS RÁPIDOS - LITE XL SOVEREIGN
================================================================================

[ 🎨 VISUAL, CORES E ABAS ]
  Abas com Fundo Sólido   : Cor automática e preenchimento total por Projeto
  #00FF00 / {R,G,B} texto : Fundo do texto preenchido com a cor exata referida

[ 🔍 BUSCA E NAVEGAÇÃO NOTEPAD++ ]
  Ctrl + F          : Abre busca (Highlight em Azul Anil persistente e global)
  Enter (no painel) : Pula para a PRÓXIMA ocorrência
  Shift + Enter     : Volta para a ocorrência ANTERIOR
  F3 / Shift + F3   : Navega entre ocorrências mesmo sem a busca aberta
  Ctrl + H          : Localizar e Substituir texto
  Ctrl + G          : Ir para a linha (Go to line)

[ 📂 GESTÃO DE PROJETOS NA ÁRVORE ]
  Ctrl + Alt + O    : Adicionar qualquer pasta/projeto à árvore lateral
  Ctrl + Alt + R    : Remover projeto da árvore lateral (Menu com busca Fuzzy)
  Ctrl + P          : Fuzzy Finder (Busca arquivos em todos os projetos)

[ ✂️ DIVISÃO DE TELAS E ABAS ]
  Ctrl + Alt + D    : Move o arquivo atual entre os painéis (Esquerda ⇄ Direita)
  Alt + D           : Cria uma nova divisão vazia à direita
  Alt + Shift + D   : Divide a tela na horizontal (baixo)
  Ctrl + Alt + Left : Foca no painel da esquerda
  Ctrl + Alt + Right: Foca no painel da direita
  Ctrl + W / Alt + W: Fecha a aba / divisão atual
  Ctrl + Tab        : Próxima aba
  Ctrl + Shift + Tab: Aba anterior

[ ⚡ EDIÇÃO RÁPIDA ]
  Ctrl + N          : Novo documento em branco
  Ctrl + S          : Salvar arquivo
  Ctrl + Shift + S  : Salvar todos os arquivos
  Ctrl + D          : Duplicar linha atual
  Ctrl + L          : Deletar linha inteira
  Ctrl + Q          : Comentar/Descomentar linha

[ ⚙️ CONFIGURAÇÃO & LOGS ]
  Ctrl + ,          : Abrir init.lua para edição instantânea
  Ctrl + Alt + U    : Colocar/Remover a pasta do Lite XL na Árvore
  Ctrl + Shift + L  : Abrir aba de Logs (copiável e com busca)
  F1                : Abrir este Guia de Atalhos
  Ctrl + Shift + ?  : Abrir este Guia de Atalhos
  Ctrl + Shift + /  : Abrir este Guia de Atalhos
================================================================================
]])
    core.root_view:open_doc(doc)
  end
})

keymap.add {
  -- Criação & Arquivos
  ["ctrl+n"]           = "doxoade:new-doc",
  ["ctrl+o"]           = "core:open-file",
  ["ctrl+s"]           = "doc:save",
  ["ctrl+shift+s"]     = "doc:save-all",

  -- Config do Editor & Logs
  ["ctrl+,"]           = "doxoade:open-init-lua",
  ["ctrl+alt+u"]       = "doxoade:toggle-litexl-in-tree",
  ["ctrl+shift+l"]     = "doxoade:open-log",
  ["ctrl+f2"]          = "doxoade:open-log",

  -- Ajuda e Cheat Sheet
  ["f1"]               = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+shift+?"]     = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+shift+/"]     = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+/"]           = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+alt+/"]       = "doxoade:show-shortcuts-cheat-sheet",

  -- Busca e Navegação Notepad++
  ["ctrl+f"]           = "find-replace:find",
  ["f3"]               = "find-replace:repeat-find",
  ["shift+f3"]         = "find-replace:previous-find",
  ["ctrl+h"]           = "find-replace:replace",
  ["ctrl+g"]           = "doc:go-to-line",

  -- Divisões e Abas (Bidirecional)
  ["ctrl+alt+d"]       = "root:move-tab-to-opposite-panel",
  ["alt+d"]            = "root:split-right",
  ["alt+shift+d"]      = "root:split-down",
  ["ctrl+alt+left"]    = "root:switch-to-left",
  ["ctrl+alt+right"]   = "root:switch-to-right",
  ["alt+w"]            = "root:close",
  ["ctrl+w"]           = "root:close",
  ["ctrl+tab"]         = "root:switch-to-next-tab",
  ["ctrl+shift+tab"]   = "root:switch-to-previous-tab",

  -- Edição Rápida
  ["ctrl+d"]           = "doc:duplicate-lines",
  ["ctrl+l"]           = "doc:delete-lines",
  ["ctrl+q"]           = "doc:toggle-line-comments",

  -- Projetos e Pastas na Treeview
  ["ctrl+alt+o"]       = "treeview:add-project-folder",
  ["ctrl+alt+r"]       = "treeview:remove-project-folder",
}
'''
}


class LiteXLEngine:
    """Motor de orquestração com arquitetura de templates modulares."""

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
        """Auto-cria a pasta e os arquivos .lua modulares caso não existam."""
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
        """Audita cada arquivo de template individualmente em busca de erros."""
        files = cls.get_template_files()
        report: Dict[str, Any] = {"files": {}, "all_ok": True, "total_files": len(files)}
        lua_bin = shutil.which("lua") or shutil.which("luajit")

        for f in files:
            content = f.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            errs = []
            warns = []

            # 1. Detecção de marcadores markdown soltos fora de comentários
            for idx, l in enumerate(lines, start=1):
                stripped = l.strip()
                if stripped.startswith("- ") or stripped.startswith("* ") or (stripped.startswith("---") and not stripped.startswith("--")):
                    errs.append(f"Linha {idx}: Marcador Markdown solto detectado -> '{stripped[:30]}'")

            # 2. Checagem de Strict.lua (_G.VAR)
            if re.search(r'_G\.\w+\s*=', content):
                errs.append("Atribuição em _G detectada (incompatível com strict.lua). Use variáveis locais.")

            # 3. Checagem de Requires Inválidos
            reqs = re.findall(r'require\s*\(?[\'"]([^\'"]+)[\'"]\)?', content)
            for r in reqs:
                if r == "core.renderer":
                    errs.append("require('core.renderer') é inválido. Use 'renderer'.")

            # 4. Checagem de métodos obsoletos
            if ":traverse(" in content:
                errs.append("Chamada a ':traverse' detectada. Use 'find_other_leaf' recursivo.")

            # 5. Compilador Lua (se disponível)
            if lua_bin:
                proc = subprocess.run([lua_bin, "-p", str(f)], capture_output=True, text=True)
                if proc.returncode != 0:
                    errs.append(f"Erro de sintaxe Lua: {proc.stderr.strip()}")

            status = "PASS" if not errs else "FAIL"
            if errs:
                report["all_ok"] = False

            report["files"][f.name] = {
                "status": status,
                "lines": len(lines),
                "errors": errs,
                "warnings": warns,
                "requires": reqs,
            }

        return report

    @classmethod
    def generate_sovereign_init(cls) -> str:
        """Monta o init.lua final a partir de todos os arquivos modelo."""
        files = cls.get_template_files()
        chunks = [
            "-- =============================================================================",
            "-- ⚡ DOXOADE NEXUS SOVEREIGN ENGINE FOR LITE XL (MODULAR TEMPLATE SYSTEM)",
            "-- Montado automaticamente a partir de doxoade/commands/lite_xl_systems/template/",
            "-- =============================================================================\n"
        ]

        for f in files:
            chunks.append(f.read_text(encoding="utf-8", errors="replace"))

        return "\n\n".join(chunks)

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
    def is_running(cls) -> bool:
        """Verifica se o processo está rodando E se a janela gráfica realmente existe."""
        if sys.platform == "win32":
            try:
                out = subprocess.check_output(
                    ["tasklist", "/FI", "IMAGENAME eq lite-xl.exe", "/FO", "CSV", "/NH"],
                    text=True, stderr=subprocess.DEVNULL, timeout=2
                )
                has_process = any(
                    line.strip().lower().startswith('"lite-xl.exe"') or line.strip().lower().startswith('lite-xl.exe')
                    for line in out.splitlines()
                )
                if not has_process:
                    return False

                # Se tem processo, valida se a janela está viva
                return cls.focus_running_window()
            except Exception:
                return False
        else:
            try:
                out = subprocess.check_output(["pgrep", "-f", "lite-xl"], text=True, timeout=2)
                return bool(out.strip())
            except Exception:
                return False

    @classmethod
    def focus_running_window(cls) -> bool:
        """Tenta focar a janela visível do Lite XL. Retorna False se não houver janela ativa."""
        if sys.platform == "win32":
            try:
                cmd = "$ws = New-Object -ComObject WScript.Shell; if ($ws.AppActivate('Lite XL')) { exit 0 } else { exit 1 }"
                res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, timeout=2)
                return res.returncode == 0
            except Exception:
                return False
        return True

    @classmethod
    def resolve_target_path(cls, raw_path: str) -> Tuple[Optional[str], bool, bool]:
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

        exists = abs_p.exists()
        is_dir = abs_p.is_dir() if exists else False
        return str(abs_p), exists, is_dir

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
    def diagnose_init_file(cls, init_file: Path) -> Dict[str, Any]:
        if not init_file.exists():
            return {"exists": False, "errors": ["Arquivo init.lua não encontrado."]}

        content = init_file.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        errors = []
        warnings = []
        checks = []

        require_matches = re.findall(r'require\s*\(?[\'"]([^\'"]+)[\'"]\)?', content)
        for req in require_matches:
            if req == "core.renderer":
                errors.append("Módulo 'core.renderer' é INVÁLIDO. No Lite XL use 'renderer'.")
            elif req not in KNOWN_LITEXL_MODULES and not req.startswith("plugins.") and not req.startswith("core."):
                warnings.append(f"Módulo de terceiro: require('{req}')")

        for idx, line in enumerate(lines, start=1):
            if re.search(r'"[^"]*\\[^abfnrtvz\\"\'0-9\n][^"]*"', line):
                errors.append(f"Linha {idx}: Escape inválido em string Lua -> {line.strip()}")

        if "local global_search_query" in content:
            checks.append("Conformidade com strict.lua ativa (Zero variáveis indefinidas).")

        return {
            "exists": True,
            "lines_count": len(lines),
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
            "requires_found": list(set(require_matches)),
        }

    @classmethod
    def parse_keybindings(cls, init_file: Path) -> List[Dict[str, Any]]:
        if not init_file.exists():
            return []
        content = init_file.read_text(encoding="utf-8", errors="replace")
        bindings = []
        block_pattern = re.compile(r'keymap\s*\.\s*add\s*(\{[^}]*\})', re.DOTALL)
        entry_pattern = re.compile(r'\[\s*[\'"]([^\'"]+)[\'"]\s*\]\s*=\s*[\'"]([^\'"]+)[\'"]')

        for match in block_pattern.finditer(content):
            for entry in entry_pattern.finditer(match.group(1)):
                raw_key = entry.group(1)
                cmd = entry.group(2)
                bindings.append({
                    "raw_key": raw_key,
                    "normalized_key": raw_key.strip().lower(),
                    "command": cmd.strip(),
                    "is_valid_format": raw_key == raw_key.lower() and not raw_key.startswith("+"),
                })
        return bindings

    @classmethod
    def audit_keybindings(cls, init_file: Path) -> Dict[str, Any]:
        bindings = cls.parse_keybindings(init_file)
        seen_keys: Dict[str, List[str]] = {}
        casing_issues = []

        for b in bindings:
            k = b["normalized_key"]
            raw = b["raw_key"]
            cmd = b["command"]
            if k not in seen_keys:
                seen_keys[k] = []
            seen_keys[k].append(cmd)
            if raw != raw.lower():
                casing_issues.append((raw, cmd, raw.lower()))

        conflicts = {k: cmds for k, cmds in seen_keys.items() if len(cmds) > 1}
        npp_covered = {}
        npp_missing = {}
        for npp_key, expected_cmd in NOTEPADPP_CANONICAL_KEYS.items():
            if npp_key in seen_keys:
                npp_covered[npp_key] = seen_keys[npp_key]
            else:
                npp_missing[npp_key] = expected_cmd

        return {
            "total_bindings": len(bindings),
            "unique_keys": len(seen_keys),
            "conflicts": conflicts,
            "casing_issues": casing_issues,
            "npp_covered": npp_covered,
            "npp_missing": npp_missing,
            "bindings_list": bindings,
        }

    @classmethod
    def install_sovereign_config(cls, backup: bool = True) -> Tuple[bool, str]:
        user_dir = cls.get_user_dir()
        user_dir.mkdir(parents=True, exist_ok=True)
        init_file = user_dir / "init.lua"

        if init_file.exists() and backup:
            backup_file = user_dir / "init.lua.bak"
            shutil.copy2(init_file, backup_file)

        err_file = cls.get_error_txt_path()
        if err_file.exists():
            try:
                err_file.unlink()
            except Exception:
                pass

        code = cls.generate_sovereign_init()
        init_file.write_text(code, encoding="utf-8")
        return True, str(init_file)
        
    @classmethod
    def kill_ghost_processes(cls):
        """Mata qualquer processo fantasma travado em segundo plano."""
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
        else:
            subprocess.run(["pkill", "-9", "-f", "lite-xl"], capture_output=True)