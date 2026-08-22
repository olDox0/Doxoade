-- doxoade/commands/lite_xl_systems/template/template/00_header_and_logger.lua
-- =============================================================================
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

-- -----------------------------------------------------------------------------
-- TEMA SOBERANO DOXOADE (PIANO BLACK & ESMERALDA)
-- -----------------------------------------------------------------------------
pcall(function()
  -- Fundo e painéis (Piano Black 3, 2, 1)
--  style.background       = { 15, 13, 15 }       -- #0f0d0f (Piano Black 3)
  style.background       = { 1, 1, 1 }       -- #000000 (FullBlack)
  style.background2      = { 25, 23, 26 }       -- #19171a (Piano Black 2 - Treeview/Tabs)
  style.background3      = { 47, 46, 48 }       -- #2f2e30 (Piano Black 1 - Hover)

  -- Tipografia e bordas
  style.text             = { 210, 220, 230 }    -- #d2dce6 (Nordic Breeze)
  style.dim              = { 94, 92, 94 }       -- #5e5c5e (Piano Black 0)
  style.divider          = { 76, 69, 82 }       -- #4c4552 (Mortar)

  -- Destaques e cursor
  style.caret            = { 38, 188, 95 }      -- #26bc5f (Esmeralda)
  style.accent           = { 38, 188, 95 }      -- #26bc5f (Esmeralda)
  style.line_number2     = { 38, 188, 95 }      -- Número da linha ativa
  style.line_highlight   = { 25, 23, 26 }       -- Fundo da linha ativa
  style.selection        = { 0, 108, 255, 110 } -- #006cff (Brandeis Blue)

  -- Cores de Sintaxe (Código)
  style.syntax["keyword"]   = { 255, 103, 0 }   -- #ff6700 (Laranja Blaze)
  style.syntax["keyword2"]  = { 200, 21, 118 }  -- #c81576 (Magenta Electric)
  style.syntax["function"]  = { 0, 108, 255 }   -- #006cff (Brandeis Blue)
  style.syntax["string"]    = { 38, 188, 95 }   -- #26bc5f (Esmeralda)
  style.syntax["comment"]   = { 94, 92, 94 }    -- #5e5c5e (Piano Black 0)
  style.syntax["number"]    = { 232, 170, 0 }   -- #e8aa00 (Urobilin Yellow)
  style.syntax["operator"]  = { 210, 220, 230 } -- #d2dce6 (Nordic Breeze)
  style.syntax["symbol"]    = { 206, 105, 158 } -- #ce699e (Pastel Pink)
end)
