-- doxoade/commands/lite_xl_systems/template/00_header_and_logger.lua
-- =============================================================================
-- 00. HEADER, MÓDULOS E LOGGER EM DISCO PERSISTENTE COM ANTI-FREEZE
-- =============================================================================
local core = require "core"
local RootView = require "core.rootview"
local common = require "core.common"
local config = require "core.config"
local style = require "core.style"
local syntax = require "core.syntax"
local command = require "core.command"
local keymap = require "core.keymap"
local Node = require "core.node"
local DocView = require "core.docview"

config.load_workspace = true
config.max_project_files = 50000

-- =============================================================================
-- 🚨 DOXOADE RUNTIME VISUAL ALERT (HUD OSD)
-- Mostra um banner vermelho no topo da tela sempre que houver falha de módulo.
-- =============================================================================

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local function draw_rect_safe(x, y, w, h, color)
  if rencache and rencache.draw_rect then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

local original_rootview_draw = RootView.draw
function RootView:draw(...)
  original_rootview_draw(self, ...)

  local report = rawget(_G, "_DOXOADE_BOOT_REPORT")
  if report and report.failed and report.failed > 0 then
    local font = require("core.style").font
    local w = self.size.x
    local banner_h = 26

    -- Banner Vermelho de Alerta no Topo
    draw_rect_safe(0, 0, w, banner_h, { 220, 38, 38, 240 })
    
    local msg = string.format("🚨 [DOXOADE ALERT] %d módulo(s) falharam no boot! Verifique o log ou 'Ctrl+Alt+Shift+L'", report.failed)
    if rencache and rencache.draw_text then
      rencache.draw_text(font, msg, 14, 6, { 255, 255, 255, 255 })
    end
  end
end

-- =============================================================================
-- 🛡️ GUARDA DE ESCOPO RAIZ (DECLARADAS FORA DE QUALQUER BLOCO OU PCALL)
-- =============================================================================
local inside_append_log = false
local inside_core_log = false
local inside_core_error = false

local session_log_file = USERDIR .. PATHSEP .. "session_log.txt"

-- =============================================================================
-- 📜 FUNÇÃO DE FORMATAÇÃO SEGURA
-- =============================================================================
local function safe_format(...)
  local argc = select("#", ...)
  if argc == 0 then return "" end
  local first = select(1, ...)
  if argc == 1 then return tostring(first) end

  if type(first) == "string" and first:find("%%") then
    local ok, res = pcall(string.format, ...)
    if ok then return res end
  end

  local t = {}
  for i = 1, argc do
    t[i] = tostring(select(i, ...))
  end
  return table.concat(t, " ")
end

-- =============================================================================
-- 💾 GRAVAÇÃO EM DISCO PERSISTENTE
-- =============================================================================
local function append_session_log(level, msg)
  if inside_append_log then return end
  inside_append_log = true

  pcall(function()
    local f = io.open(session_log_file, "a")
    if f then
      local ts = os.date("%H:%M:%S")
      f:write(string.format("[%s] [%s] %s\n", ts, level, tostring(msg)))
      f:flush()
      f:close()
    end
  end)

  inside_append_log = false
end

-- Reset do log no início da sessão
pcall(function()
  os.remove(session_log_file)
  local f = io.open(session_log_file, "w")
  if f then
    f:write(string.format("=== LITE XL SESSION INICIADA: %s ===\n", os.date()))
    f:flush()
    f:close()
  end
end)

-- =============================================================================
-- 🖨️ HOOK DE PRINT
-- =============================================================================
local original_print = print
function print(...)
  if not inside_core_log then
    append_session_log("PRINT", safe_format(...))
  end
  if original_print then original_print(...) end
end

-- =============================================================================
-- ℹ️ HOOK DE CORE.LOG
-- =============================================================================
local original_core_log = core.log
function core.log(...)
  if inside_core_log then
    if original_core_log then return original_core_log(...) end
    return
  end

  inside_core_log = true
  append_session_log("INFO", safe_format(...))

  local ok, res = true, nil
  if original_core_log then
    ok, res = pcall(original_core_log, ...)
  end
  inside_core_log = false

  if ok then return res end
end

-- =============================================================================
-- ❌ HOOK DE CORE.ERROR COM RATE LIMIT
-- =============================================================================
local original_core_error = core.error
local error_rate = {
  last_msg = "",
  last_time = 0,
  count = 0,
}

function core.error(...)
  if inside_core_error then
    if original_core_error then return original_core_error(...) end
    return
  end

  inside_core_error = true

  pcall(function(...)
    local msg = safe_format(...)
    local now = os.clock()
    local tb = debug.traceback("", 2)

    if msg ~= error_rate.last_msg then
      if error_rate.count > 1 then
        append_session_log(
          "WARN",
          string.format("Última mensagem de erro repetiu %d vezes antes de mudar.", error_rate.count)
        )
      end

      error_rate.last_msg = msg
      error_rate.last_time = now
      error_rate.count = 1

      append_session_log("ERROR", msg)
      append_session_log("TRACE", tb)
    else
      error_rate.count = error_rate.count + 1
      if (now - error_rate.last_time) >= 1.0 then
        append_session_log(
          "ERROR",
          string.format("%s [repetido %dx]", msg, error_rate.count)
        )
        append_session_log("TRACE", tb)
        error_rate.last_time = now
        error_rate.count = 0
      end
    end
  end, ...)

  local ok, res = true, nil
  if original_core_error then
    ok, res = pcall(original_core_error, ...)
  end
  inside_core_error = false

  if ok then return res end
end

-- =============================================================================
-- 🎨 TEMA SOBERANO DOXOADE (PIANO BLACK & ESMERALDA NATIVO)
-- =============================================================================
pcall(function()
  style.background       = { 1, 1, 1 }
  style.background2      = { 25, 23, 26 }
  style.background3      = { 47, 46, 48 }
  style.text             = { 210, 220, 230 }
  style.dim              = { 94, 92, 94 }
  style.divider          = { 76, 69, 82 }
  style.caret            = { 38, 188, 95 }
  style.accent           = { 38, 188, 95 }
  style.line_number      = { 94, 92, 94 }
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
