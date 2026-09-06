-- doxoade/commands/lite_xl_systems/template/00_header_and_logger.lua
--[[
  🛡️ DOXOADE SOVEREIGN HEADER & ACTIVE SHIELD (V2.0 Canônica)
  - Logger Unificado com I/O Síncrono e Anti-Recursão.
  - Vacinas Contratuais de Layout e Views Órfãs (Ma'at).
  - Telemetria de Comandos e HUD OSD de Boot.
]]
local core = require "core"
local RootView = require "core.rootview"
local common = require "core.common"
local config = require "core.config"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local Node = require "core.node"
local DocView = require "core.docview"

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
    if type(c) ~= "table" then
        return { 128, 128, 128, 255 } -- cinza fallback seguro
    end
    return c
end

if rencache and type(rencache.draw_rect) == "function" then
    local _orig_rencache_dr = rencache.draw_rect
    rencache.draw_rect = function(x, y, w, h, color)
        return _orig_rencache_dr(x, y, w, h, _validate_draw_color(color))
    end
end

if native_renderer and type(native_renderer.draw_rect) == "function" then
    local _orig_renderer_dr = native_renderer.draw_rect
    native_renderer.draw_rect = function(x, y, w, h, color)
        return _orig_renderer_dr(x, y, w, h, _validate_draw_color(color))
    end
end

local function draw_rect_safe(x, y, w, h, color)
  if rencache and rencache.draw_rect then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

-- =============================================================================
-- 3. MOTOR DE LOG UNIFICADO (I/O Síncrono + Safe Format)
-- =============================================================================
local user_dir = USERDIR or "."
local path_sep = PATHSEP or "/"
local session_log_file = user_dir .. path_sep .. "session_log.txt"
local inside_logging = false

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

local function append_session_log(level, msg)
  if inside_logging then return end
  inside_logging = true

  pcall(function()
    local f = io.open(session_log_file, "a")
    if f then
      local ts = os.date("%H:%M:%S")
      f:write(string.format("[%s] [%s] %s\n", ts, tostring(level), tostring(msg)))
      if level == "ERROR" or level == "WARN" or level == "CRITICAL" or level == "CMD" then
        f:flush()
      end
      f:close()
    end
  end)

  inside_logging = false
end

-- =============================================================================
-- 4. HOOKS DE LOG, PRINT E ERRO COM RATE LIMIT
-- =============================================================================
local original_print = print
function print(...)
  append_session_log("PRINT", safe_format(...))
  if original_print then original_print(...) end
end

local original_core_log = core.log
core.log = function(...)
  local msg = safe_format(...)
  append_session_log("INFO", msg)
  if original_core_log then return original_core_log(...) end
end

local original_core_error = core.error
local error_rate = { last_msg = "", last_time = 0, count = 0 }

core.error = function(...)
  local msg = safe_format(...)
  local now = os.clock()

  -- Atualiza o quadro de incidentes do HUD
  local incidents = rawget(_G, "_DOXOADE_RUNTIME_INCIDENTS")
  if incidents then
    incidents.errors = incidents.errors + 1
    incidents.last_error = msg
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

  if original_core_error then
    return original_core_error(...)
  end
end

-- =============================================================================
-- 5. TELEMETRIA DE COMANDOS
-- =============================================================================
if command and command.perform then
  local original_command_perform = command.perform
  command.perform = function(cmd_name, ...)
    pcall(function()
      append_session_log("CMD", string.format("⚡ Disparado: '%s'", tostring(cmd_name)))
    end)
    return original_command_perform(cmd_name, ...)
  end
end

-- =============================================================================
-- 6. VACINAS DE LAYOUT E VIEWS ÓRFÃS (MA'AT)
-- =============================================================================

-- Vacina 1: Prevenção de nil em should_show_tabs (node.lua:271)
local original_should_show_tabs = Node.should_show_tabs
function Node:should_show_tabs()
  if not self.views or #self.views == 0 or self.views[1] == nil then
    return false
  end
  return original_should_show_tabs(self)
end

-- Vacina 2: update_layout protegido contra views corrompidas
local original_node_update_layout = Node.update_layout
function Node:update_layout(...)
  if self.type == "leaf" then
    if type(self.views) ~= "table" then
      self.views = {}
    end

    -- Expulsa views corrompidas sem geometria
    for i = #self.views, 1, -1 do
      local v = self.views[i]
      if not v or type(v) ~= "table" then
        table.remove(self.views, i)
      end
    end

    -- Injeta EmptyView segura se a folha estiver vazia
    if #self.views == 0 then
      local ok_ev, EmptyView = pcall(require, "core.emptyview")
      if ok_ev and EmptyView then
        local ok_new, ev = pcall(EmptyView)
        if ok_new and ev and self.add_view then
          pcall(self.add_view, self, ev)
        end
      end
    end
  end
  return original_node_update_layout(self, ...)
end

-- Vacina 3: Blindagem contínua no core.step
local original_core_step = core.step
function core.step()
  pcall(function()
    if core.root_view and core.root_view.root_node then
      local function sanitize_node(node)
        if not node then return end
        if node.type == "leaf" then
          for _, view in ipairs(node.views or {}) do
            if type(view) == "table" then
              if not view.get_name then view.get_name = function() return "Orphan View" end end
              if not view.get_title then view.get_title = function(self) return self:get_name() end end
              if not view.is then view.is = function() return false end end
            end
          end
        else
          sanitize_node(node.a)
          sanitize_node(node.b)
        end
      end
      sanitize_node(core.root_view.root_node)
    end
    if core.active_view and type(core.active_view) == "table" then
      if not core.active_view.get_name then core.active_view.get_name = function() return "Active Orphan" end end
      if not core.active_view.is then core.active_view.is = function() return false end end
    end
  end)
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
-- 7. BANNER DE ALERTA NO ROOTVIEW (BOOT SHIELD)
-- =============================================================================
local original_rootview_draw = RootView.draw
function RootView:draw(...)
  original_rootview_draw(self, ...)
  local report = rawget(_G, "_DOXOADE_BOOT_REPORT")
  if report and report.failed and report.failed > 0 then
    local font = require("core.style").font
    local w = self.size.x
    draw_rect_safe(0, 0, w, 4, { 220, 38, 38, 60 })
    local msg = string.format("🚨 [DOXOADE ALERT] %d módulo(s) falharam no boot! Verifique o log", report.failed)
    if rencache and rencache.draw_text then
      rencache.draw_text(font, msg, 14, 6, { 255, 255, 255, 255 })
    end
  end
end

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
