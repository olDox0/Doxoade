-- doxoade/commands/lite_xl_systems/template/00_header_and_logger.lua
-- =============================================================================
-- 00. HEADER, MÓDULOS E LOGGER EM DISCO PERSISTENTE COM ANTI-FREEZE
-- =============================================================================
local core = require "core"
local common = require "core.common"
local config = require "core.config"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local Node = require "core.node"
local DocView = require "core.docview"
-- =====================================================
-- 📜 LOGGER BASE EM DISCO
-- =====================================================
local session_log_file = USERDIR .. PATHSEP .. "session_log.txt"

local function safe_format(...)
  local argc = select("#", ...)

  if argc == 0 then
    return ""
  end

  local first = select(1, ...)

  if argc == 1 then
    return tostring(first)
  end

  -- Se parecer uma chamada de format, tenta string.format primeiro.
  -- Exemplo:
  --   core.log("Saved \"%s\"", filename)
  if type(first) == "string" and first:find("%%") then
    local ok, res = pcall(string.format, ...)
    if ok then
      return res
    end
  end

  -- Fallback: concatena todos os argumentos como string.
  local t = {}
  for i = 1, argc do
    t[i] = tostring(select(i, ...))
  end

  return table.concat(t, " ")
end

local inside_append_log = false

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

-- =====================================================
-- 🖨️ PRINT HOOK
-- =====================================================
local original_print = print

function print(...)
  append_session_log("PRINT", safe_format(...))

  if original_print then
    original_print(...)
  end
end

-- =====================================================
-- ℹ️ CORE.LOG HOOK
-- =====================================================
local original_core_log = core.log
local inside_core_log = false

function core.log(...)
  if inside_core_log then
    if original_core_log then
      return original_core_log(...)
    end
    return
  end

  inside_core_log = true

  append_session_log("INFO", safe_format(...))

  local ok, res
  if original_core_log then
    ok, res = pcall(original_core_log, ...)
  else
    ok = true
  end

  inside_core_log = false

  if ok then
    return res
  end
end

-- =====================================================
-- ❌ CORE.ERROR HOOK COM RATE LIMIT E EVIDÊNCIA
-- =====================================================
-- 🛡️ Anti-Freeze Forense (rate limit + contador + anti-reentrância)
local original_core_error = core.error
local inside_core_error = false

local error_rate = {
  last_msg = "",
  last_time = 0,
  count = 0,
}

function core.error(...)
  if inside_core_error then
    if original_core_error then
      return original_core_error(...)
    end
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

  if ok then
    return res
  end
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
  style.accent           = { 38, 148, 95 }
  style.line_number2     = { 38, 108, 95 }
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
