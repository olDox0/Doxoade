-- doxoade/commands/lite_xl_systems/template/00_header_and_logger.lua
--[[
  🛡️ DOXOADE SOVEREIGN HEADER & ACTIVE SHIELD (V2.0 Canônica)
  - Logger Unificado com I/O em Memória e Flush Periódico.
  - Vacinas Contratuais de Layout e Views Órfãs (Ma'at).
  - Telemetria de Comandos e HUD OSD de Boot.
]]
local core = rawget(_G, "core") or (pcall(require, "core") and require("core") or nil)
--local config = rawget(_G, "config") or (pcall(require, "core.config") and require("core.config") or {})
local system = rawget(_G, "system") or (pcall(require, "system") and require("system") or nil)
local RootView = require "core.rootview"
local common = require "core.common"
local config = require "core.config"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local Node = require "core.node"
local DocView = require "core.docview"

local PHANTO_CONFIG = {
  enabled = true,
  max_entries = 100,
  flush_interval_sec = 2.0,
  diag_dir = (USERDIR or ".") .. (PATHSEP or "/") .. ".doxoade" .. (PATHSEP or "/") .. "diagnostics",
  ndjson_file = "phanto_crisis.ndjson",
}

local _phanto_ring = {}
local _phanto_head = 1
local _phanto_count = 0
local _phanto_last_flush = os.clock()
local _inside_capture = false

rawset(_G, "_PHANTO_CRISIS_STATE", {
  ring = _phanto_ring,
  config = PHANTO_CONFIG,
  total_captured = 0,
  last_error = nil,
})

local function safe_json_escape(str)
  if not str then return "" end
  str = tostring(str)
  return str:gsub("\\", "\\\\")
            :gsub('"', '\\"')
            :gsub("\n", "\\n")
            :gsub("\r", "\\r")
            :gsub("\t", "\\t")
end

local function ensure_diag_dir(dir_path)
  if not system or not system.mkdir then return end
  local parts = {}
  for p in tostring(dir_path):gmatch("[^/\\]+") do
    table.insert(parts, p)
  end
  local cur = ""
  for i, p in ipairs(parts) do
    if i == 1 and p:find("^[a-zA-Z]:") then
      cur = p
    else
      cur = (cur == "" and "" or cur .. (PATHSEP or "/")) .. p
      pcall(system.mkdir, cur)
    end
  end
end

local function phanto_shadow_flush()
  if _phanto_count == 0 then return end
  ensure_diag_dir(PHANTO_CONFIG.diag_dir)

  local sep = PATHSEP or "/"
  local file_path = PHANTO_CONFIG.diag_dir .. sep .. PHANTO_CONFIG.ndjson_file

  local f = io.open(file_path, "a")
  if f then
    local start_idx = _phanto_head - _phanto_count
    if start_idx <= 0 then start_idx = start_idx + PHANTO_CONFIG.max_entries end

    for i = 1, _phanto_count do
      local idx = ((start_idx + i - 2) % PHANTO_CONFIG.max_entries) + 1
      local entry = _phanto_ring[idx]
      if entry then
        local json_line = string.format(
          '{"ts":%d,"ts_iso":%q,"module":%q,"error":%q,"traceback":%q,"context":%q}\n',
          entry.ts, entry.ts_iso,
          safe_json_escape(entry.module),
          safe_json_escape(entry.error),
          safe_json_escape(entry.traceback),
          safe_json_escape(entry.context and entry.context.active_file or "nil")
        )
        f:write(json_line)
      end
    end
    f:flush()
    f:close()

    _phanto_ring = {}
    _phanto_head = 1
    _phanto_count = 0
    _G._PHANTO_CRISIS_STATE.ring = _phanto_ring
  end
end

local function phanto_capture(module_name, fn, ...)
  if config.phanto_crisis_enabled == false or PHANTO_CONFIG.enabled == false then
    return pcall(fn, ...)
  end
  if _inside_capture then return pcall(fn, ...) end

  local args = { ... }
  local ok, result = xpcall(function()
    return fn(table.unpack(args))
  end, function(err)
    _inside_capture = true
    local trace = debug.traceback("", 2) or ""

    local entry = {
      ts = os.time(),
      ts_iso = os.date("%Y-%m-%d %H:%M:%S"),
      module = tostring(module_name or "unknown"),
      error = tostring(err),
      traceback = trace,
      context = {
        active_file = (core and core.active_view and core.active_view.doc and core.active_view.doc.filename) or "nil",
      }
    }

    _phanto_ring[_phanto_head] = entry
    _phanto_head = (_phanto_head % PHANTO_CONFIG.max_entries) + 1
    if _phanto_count < PHANTO_CONFIG.max_entries then
      _phanto_count = _phanto_count + 1
    end

    _G._PHANTO_CRISIS_STATE.total_captured = _G._PHANTO_CRISIS_STATE.total_captured + 1
    _G._PHANTO_CRISIS_STATE.last_error = tostring(err)

    -- 🔍 EXPOSIÇÃO FORENSE TOTAL: Imprime a causa exata no session_log
    if core and core.log then
      core.log(string.format("👻 [PHANTO:%s] 💥 Causa: %s", tostring(module_name), tostring(err)))
    end

    _inside_capture = false
    return err
  end)

  return ok, result
end

rawset(_G, "phanto_capture", phanto_capture)
rawset(_G, "phanto_shadow_flush", phanto_shadow_flush)

-- Corrotina sentinela: descarrega o buffer em lote sem interrupção de frames
if core and core.add_thread then
  core.add_thread(function()
    while true do
      coroutine.yield(PHANTO_CONFIG.flush_interval_sec)
      if _phanto_count > 0 then
        phanto_shadow_flush()
      end
    end
  end)
end

if core and core.log then
  core.log("👻 [PHANTO_CRISIS] Core V2.0 armado. Isolamento atômico ativo.")
end

-- =============================================================================
-- 🚨 INTERCEPTOR GLOBAL DE PROCESSOS (Proteção contra Handles Inválidos no Windows)
-- =============================================================================
local original_process_start = nil
pcall(function()
    local proc = require("process")
    if proc and type(proc.start) == "function" and not rawget(_G, "_DOXOADE_PROC_VACCINE") then
        rawset(_G, "_DOXOADE_PROC_VACCINE", true)
        original_process_start = proc.start

        proc.start = function(...)
            local argc = select("#", ...)
            local cmd_args = select(1, ...)
            local options = select(2, ...)

            -- Se options for passado com strings inválidas ("pipe" em vez de constante numérica):
            if argc > 1 and type(options) == "table" then
                local sanitized_options = {}
                for k, v in pairs(options) do
                    -- Converte string "pipe" para a constante numérica nativa se existir
                    local INVALID_REDIRECT = { pipe = true, stdout = true, stderr = true, stdin = true }
                    if type(v) == "string" and INVALID_REDIRECT[v] and proc.REDIRECT_PIPE then
                        sanitized_options[k] = proc.REDIRECT_PIPE
                    elseif type(v) == "number" then
                        sanitized_options[k] = v          -- constantes nativas REDIRECT_*
                    else
                        sanitized_options[k] = nil        -- extirpa paths/handles/booleans
                    end
                end
                return original_process_start(cmd_args, sanitized_options)
            end

            return original_process_start(...)
        end
    end
end)

-- =============================================================================
-- 1. CONFIGURAÇÕES E ESTADO GLOBAL
-- =============================================================================
rawset(_G, "active_view", nil)
rawset(_G, "command_view", nil)
rawset(_G, "status_view", nil)
rawset(_G, "root_view", nil)

config.load_workspace = true
config.max_project_files = 50000
config.always_show_tabs = false

rawset(_G, "_DOXOADE_RUNTIME_INCIDENTS", {
  errors = 0,
  warnings = 0,
  last_error = nil
})

-- =============================================================================
-- 2. POLYFILLS DE RENDERIZAÇÃO
-- =============================================================================
local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

-- 🛡️ POLYFILL GLOBAL: Intercepta draw_rect para validar cor (anti-boolean crash)
-- Resolve: "bad argument #5 to 'draw_rect' (table expected, got boolean)"
local _validate_draw_color = function(c)
    if type(c) ~= "table" then return { 128, 128, 128, 255 } end
    return c
end

if rencache and type(rencache.draw_rect) == "function" then
    local _orig = rencache.draw_rect
    rencache.draw_rect = function(x, y, w, h, color)
        return _orig(x, y, w, h, _validate_draw_color(color))
    end
end

if native_renderer and type(native_renderer.draw_rect) == "function" then
    local _orig = native_renderer.draw_rect
    native_renderer.draw_rect = function(x, y, w, h, color)
        return _orig(x, y, w, h, _validate_draw_color(color))
    end
end

local function draw_rect_safe(x, y, w, h, color)
    if rencache and rencache.draw_rect then
        rencache.draw_rect(x, y, w, h, color)
    elseif native_renderer and native_renderer.draw_rect then
        native_renderer.draw_rect(x, y, w, h, color)
    end
end

local user_dir = USERDIR or "."
local path_sep = PATHSEP or "/"
local session_log_file = user_dir .. path_sep .. "session_log.txt"
local inside_logging = false
local _log_memory_buffer = {}
local _last_log_flush = os.clock()

local function flush_session_log()
    if #_log_memory_buffer == 0 then return end
    pcall(function()
        -- Rotação de segurança: se passar de 5MB, renomeia para .bak e zera
        local finfo = system and system.get_file_info and system.get_file_info(session_log_file)
        if finfo and finfo.size and finfo.size > (5 * 1024 * 1024) then
            pcall(os.remove, session_log_file .. ".bak")
            pcall(os.rename, session_log_file, session_log_file .. ".bak")
        end
        
        local f = io.open(session_log_file, "a")
        if f then
            f:write(table.concat(_log_memory_buffer, "\n") .. "\n")
            f:flush()
            f:close()
        end
        _log_memory_buffer = {}
        _last_log_flush = os.clock()
    end)
end
rawset(_G, "flush_session_log", flush_session_log)

local function append_session_log(level, msg)
    local ts = os.date("%H:%M:%S")
    local line = string.format("[%s] [%s] %s", ts, tostring(level), tostring(msg))
    table.insert(_log_memory_buffer, line)
    
    -- ⚡ SENSORIUM DISPATCH: Eventos de Caos, Sensores, Erros ou Alertas Críticos são gravados imediatamente!
    local is_urgent = (level == "CRITICAL") 
                   or (level == "ERROR") 
                   or tostring(msg):find("%[CHAOS%]") 
                   or tostring(msg):find("%[SENSOR") 
                   or tostring(msg):find("%[HOOK")
                   
    if is_urgent or #_log_memory_buffer >= 10 or (os.clock() - _last_log_flush) >= 1.0 then
        flush_session_log()
    end
end

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
    for i = 1, argc do t[i] = tostring(select(i, ...)) end
    return table.concat(t, " ")
end

-- local function append_session_log(level, msg)
--     local ts = os.date("%H:%M:%S")
--     local line = string.format("[%s] [%s] %s", ts, tostring(level), tostring(msg))
--     table.insert(_log_memory_buffer, line)
--     if level == "CRITICAL" or level == "ERROR" or #_log_memory_buffer >= 10 or (os.clock() - _last_log_flush) >= 2.0 then
--         flush_session_log()
--     end
-- end

if core and core.add_thread then
    core.add_thread(function()
        coroutine.yield(0.1)
        flush_session_log()
    end)
end

local original_print = print
function print(...)
    if not inside_logging then
        inside_logging = true
        append_session_log("PRINT", safe_format(...))
        if original_print then original_print(...) end
        inside_logging = false
    elseif original_print then
        original_print(...)
    end
end

local original_core_log = core.log
core.log = function(...)
    if not inside_logging then
        inside_logging = true
        local msg = safe_format(...)
        append_session_log("INFO", msg)
        if original_core_log then pcall(original_core_log, "%s", msg) end
        inside_logging = false
    elseif original_core_log then
        pcall(original_core_log, ...)
    end
end

local original_core_error = core.error
local error_rate = { last_msg = "", last_time = 0, count = 0 }

core.error = function(...)
    local msg = safe_format(...)
    local now = os.clock()
    local incidents = rawget(_G, "_DOXOADE_RUNTIME_INCIDENTS")
    if incidents then
        incidents.errors = incidents.errors + 1
        incidents.last_error = msg
    end

    -- 👻 PONTE PHANTO-CRISIS: Registra no Ring Buffer NDJSON
    local capture = rawget(_G, "phanto_capture")
    if type(capture) == "function" then
        capture("core.error", function()
            error(msg, 2)
        end)
    end

    if msg ~= error_rate.last_msg then
        error_rate.last_msg = msg
        error_rate.last_time = now
        error_rate.count = 1
        append_session_log("ERROR", msg)
    else
        error_rate.count = error_rate.count + 1
        if (now - error_rate.last_time) >= 1.0 then
            append_session_log("ERROR", string.format("%s [repetido %dx]", msg, error_rate.count))
            error_rate.last_time = now
            error_rate.count = 0
        end
    end
    if original_core_error then return original_core_error(...) end
end

if command and command.perform then
    local original_command_perform = command.perform
    command.perform = function(cmd_name, ...)
        pcall(function() append_session_log("CMD", string.format("⚡ Disparado: '%s'", tostring(cmd_name))) end)
        return original_command_perform(cmd_name, ...)
    end
end

local original_should_show_tabs = Node.should_show_tabs
function Node:should_show_tabs()
    if not self.views or #self.views == 0 or self.views[1] == nil then return false end
    return original_should_show_tabs(self)
end

local original_node_update_layout = Node.update_layout
function Node:update_layout(...)
    if self.type == "leaf" then
        if type(self.views) ~= "table" then self.views = {} end
        for i = #self.views, 1, -1 do
            local v = self.views[i]
            if not v or type(v) ~= "table" then table.remove(self.views, i) end
        end
        if #self.views == 0 then
            local ok_ev, EmptyView = pcall(require, "core.emptyview")
            if ok_ev and EmptyView then
                local ok_new, ev = pcall(EmptyView)
                if ok_new and ev and self.add_view then pcall(self.add_view, self, ev) end
            end
        end
    end
    return original_node_update_layout(self, ...)
end

local _static_orphan_get_name = function() return "Orphan View" end
local _static_orphan_get_title = function(self) return self:get_name() end
local _static_orphan_is = function(self, class) return false end
local _static_active_orphan_name = function() return "Active Orphan" end

local function _sanitize_node_tree(node)
    if not node then return end
    if node.type == "leaf" then
        for _, view in ipairs(node.views or {}) do
            if type(view) == "table" then
                if not view.get_name then view.get_name = _static_orphan_get_name end
                if not view.get_title then view.get_title = _static_orphan_get_title end
                if not view.is then view.is = _static_orphan_is end
            end
        end
    else
        _sanitize_node_tree(node.a)
        _sanitize_node_tree(node.b)
    end
end

pcall(collectgarbage, "generational", 20, 50)
local _last_sanitize_time = 0
local original_core_step = core.step

function core.step()
    local now = os.clock()
    if (now - _last_sanitize_time) >= 0.25 then
        _last_sanitize_time = now
        if core.root_view and core.root_view.root_node then
            _sanitize_node_tree(core.root_view.root_node)
        end
        if core.active_view and type(core.active_view) == "table" then
            if not core.active_view.get_name then core.active_view.get_name = _static_active_orphan_name end
            if not core.active_view.is then core.active_view.is = _static_orphan_is end
        end
    end
    return original_core_step()
end

-- Vacina 4: Blindagem no set_active_view
local original_set_active_view = core.set_active_view
core.set_active_view = function(view)
  if view and type(view) == "table" then
    if not view.is then view.is = function(self, class) return false end end
    if not view.get_name then view.get_name = function(self) return "Orphan View" end end
    if not view.get_title then view.get_title = function(self) return self:get_name() end end
  end
  if original_set_active_view then
    return original_set_active_view(view)
  end
end

-- Vacina 5: Blindagem no Node:add_view
local original_node_add_view = Node.add_view
function Node:add_view(view)
  if view and type(view) == "table" then
    if not view.get_name then view.get_name = function(self) return "Orphan View" end end
    if not view.is then view.is = function(self, class) return false end end
  end
  return original_node_add_view(self, view)
end

-- =============================================================================
-- 📥 DRAG-AND-DROP HANDLER (Abre arquivos arrastados do Explorer/Desktop)
-- =============================================================================
local original_rootview_on_file_dropped = RootView.on_file_dropped
function RootView:on_file_dropped(file_path, x, y)
    if file_path and type(file_path) == "string" and file_path ~= "" then
        local info = system.get_file_info(file_path)
        if info and info.type == "file" then
            local doc = core.open_doc(file_path)
            if doc then
                core.root_view:open_doc(doc)
                if core.log then
                    core.log("📥 [DRAG-DROP] Arquivo aberto: " .. file_path)
                end
                core.redraw = true
                return
            end
        elseif info and info.type == "dir" then
            if core.add_project_directory then
                core.add_project_directory(file_path)
                if core.log then
                    core.log("📂 [DRAG-DROP] Projeto anexado: " .. file_path)
                end
                core.redraw = true
                return
            end
        end
    end
    if original_rootview_on_file_dropped then
        return original_rootview_on_file_dropped(self, file_path, x, y)
    end
end

-- =============================================================================
-- 🚨 OSD BOOT REPORT BANNER (Alerta Visual Imediato de Falhas no Boot)
-- =============================================================================
local original_rootview_draw = RootView.draw
function RootView:draw(...)
  original_rootview_draw(self, ...)
  local report = rawget(_G, "_DOXOADE_BOOT_REPORT")
  if report and report.failed and report.failed > 0 then
    local font = style.font
    local screen_w = self.size and self.size.x or 800
    local banner_h = 24
    draw_rect_safe(0, 0, screen_w, banner_h, { 220, 38, 38, 50 })
    draw_rect_safe(0, banner_h - 1, screen_w, 1, { 255, 255, 255, 80 })
    local alert_msg = string.format("⚠ [DOXOADE BOOT] %d módulo(s) falharam na inicialização! Verifique o session_log.txt", report.failed)
    if font and rencache and rencache.draw_text then
      rencache.draw_text(font, alert_msg, 14, 4, { 255, 255, 255, 255 })
    elseif font and native_renderer and native_renderer.draw_text then
      native_renderer.draw_text(font, alert_msg, 14, 4, { 255, 255, 255, 255 })
    end
  end
end

-- local function _doxoade_shadow_boot(name, weight, fn)
--     if core and core.add_thread then
--         core.add_thread(function()
--             -- O yield escalonado garante que o loop principal desenhe frames entre as cargas
--             coroutine.yield(weight) 
--             _doxoade_safe_boot(name, fn)
--         end)
--     else
--         _doxoade_safe_boot(name, fn)
--     end
-- end

-- =============================================================================
-- 🐺 ARCT (ANÚBIS ROOT CAUSE TRACER) - FASE 1: INTERCEPTOR & CIRCUIT BREAKER
-- =============================================================================
-- ✅ CORREÇÃO: Removido __mode = "k" para evitar que o GC colete as chaves string dinâmicas
local _DOXOADE_ERROR_FREQUENCY = {} 

local function arct_intercept(module_name, err_msg)
    local now = os.clock()
    local key = (module_name or "unknown") .. ":" .. tostring(err_msg):sub(1, 60)

    local record = _DOXOADE_ERROR_FREQUENCY[key]
    if not record then
        record = { count = 1, first_seen = now, silenced = false }
        _DOXOADE_ERROR_FREQUENCY[key] = record
    else
        record.count = record.count + 1

        -- ⚡ CIRCUIT BREAKER: > 3 ocorrências em < 2 segundos
        if (now - record.first_seen) < 2.0 and record.count >= 3 and not record.silenced then
            record.silenced = true
            
            local user_dir = USERDIR or "."
            local sep = PATHSEP or "/"
            local diag_dir = user_dir .. sep .. ".doxoade" .. sep .. "diagnostics"
            pcall(function() system.mkdir(diag_dir) end)

            local trigger_file = diag_dir .. sep .. "arct_trigger.json"
            local f = io.open(trigger_file, "w")
            if f then
                local json_payload = string.format(
                    '{"module": %q, "error": %q, "count": %d, "time": %q}', 
                    module_name, tostring(err_msg), record.count, os.date("%Y-%m-%d %H:%M:%S")
                )
                f:write("{\n  \"trigger\": " .. json_payload .. "\n}\n")
                f:flush()
                f:close()
            end

            if core and core.log then
                core.log(string.format("🚨 [ARCT] Circuito interrompido em '%s' após %d falhas. Log silenciado.", module_name, record.count))
            end
            return true
        end
    end
    return false
end

local function arct_xpcall(fn, module_name, ...)
    local ok, err = pcall(fn, ...)
    if not ok then
        local silenced = arct_intercept(module_name, err)
        if not silenced and core and core.log then
            core.log("👻 [HOOK] pcall capturou erro: " .. tostring(err))
        end
    end
    return ok, err
end

-- ✅ CORREÇÃO: Exportar como globais para que outros módulos possam usar

-- =============================================================================
-- 8. TEMA SOBERANO (PIANO BLACK & ESMERALDA)
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

append_session_log("BOOT", "=== SOVEREIGN BOOT OK ===")

rawset(_G, "INDENT_GUIDE_ACTIVE", (config.draw_indent_guides ~= false))
rawset(_G, 'arct_xpcall', arct_xpcall)
rawset(_G, 'arct_intercept', arct_intercept)
