-- doxoade/commands/lite_xl_systems/template/00_header_and_logger.lua
--[[
  Módulo de Inicialização, Logger Assíncrono, Telemetria e Alerta Visual de Boot.
  - Gravação persistente e assíncrona do session_log.txt.
  - Telemetria de despacho de comandos em tempo real protegida contra falhas.
  - Banner de quarentena superior em caso de falha de módulo.
]]
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

-- 🛡️ VACINA GLOBAL STRICT: Declara variáveis de conveniência no _G para evitar erro de variável indefinida
rawset(_G, "active_view", nil)
rawset(_G, "command_view", nil)
rawset(_G, "status_view", nil)
rawset(_G, "root_view", nil)

config.load_workspace = true
config.max_project_files = 50000

-- Polyfills Universais C
local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local function draw_rect_safe(x, y, w, h, color)
  if rencache and rencache.draw_rect then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

-- =============================================================================
-- 🛡️ ESTRATÉGIA VACINA + INVARIANTE (substitui os antigos "escudos")
-- =============================================================================
-- DIAGNÓSTICO RAIZ:
--   O crash "node.lua:271: attempt to call a nil value (method 'is')"
--   ocorre APENAS quando:
--     1) config.always_show_tabs == true, E
--     2) algum nó "leaf" fica com self.views == {} (vazio).
--   A linha fatal é:  return not self.views[1]:is(EmptyView)
--
-- VACINA 1: elimina o caminho de crash por configuração (zero monkey-patch).
-- Abas continuam aparecendo normalmente quando há mais de um documento.
config.always_show_tabs = false

-- VACINA 2 (INVARIANTE): nenhum nó leaf sobrevive com zero views.
-- Guard cirúrgico em update_layout usando a API oficial add_view + EmptyView,
-- restaurando o estado canônico que o Lite XL espera.
local original_node_update_layout = Node.update_layout
function Node:update_layout(...)
  if self.type == "leaf" then
    if type(self.views) ~= "table" then
      self.views = {}
    end
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

-- =============================================================================
-- 🛡️ VACINA MA'AT: BLINDAGEM ABSOLUTA CONTRA 'get_name' NIL (CRASH DO core.step)
-- =============================================================================
-- O crash ocorre no upvalue 'get_title_filename' do core.init.lua quando o loop
-- principal (core.step) itera sobre node.views e encontra uma tabela sem metatable.

-- 1. Saneamento Contínuo no Loop Principal (Antes de cada frame)
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
        -- Blindagem extra para a view ativa global
        if core.active_view and type(core.active_view) == "table" then
            if not core.active_view.get_name then core.active_view.get_name = function() return "Active Orphan" end end
            if not core.active_view.is then core.active_view.is = function() return false end end
        end
    end)
    return original_core_step()
end

-- 2. Hook no core.set_active_view (Proteção na promoção de views)
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

-- =============================================================================
-- 🛡️ VACINA MA'AT: BLINDAGEM ABSOLUTA CONTRA 'get_name' NIL (CRASH DO core.step)
-- =============================================================================
-- Intercepta a promoção de views e injeta métodos faltantes para evitar que
-- tabelas órfãs (sem metatable de View) crashem o upvalue 'get_title_filename'.

-- 1. Blindagem no core.set_active_view (Atualiza o hook existente)
local original_set_active_view = core.set_active_view
core.set_active_view = function(view)
	if view and type(view) == "table" then
		if not view.is then
			view.is = function(self, class) return false end
		end
		if not view.get_name then
			view.get_name = function(self) return "Orphan View" end
		end
		if not view.get_title then
			view.get_title = function(self) return self:get_name() end
		end
	end
	if original_set_active_view then
		return original_set_active_view(view)
	end
end

-- 2. Blindagem no Node:add_view (Impede que abas órfãs entrem na árvore de nós)
local original_node_add_view = Node.add_view
function Node:add_view(view)
	if view and type(view) == "table" then
		if not view.get_name then
			view.get_name = function(self) return "Orphan View" end
		end
		if not view.is then
			view.is = function(self, class) return false end
		end
	end
	return original_node_add_view(self, view)
end

-- =============================================================================
-- 🛡️ ESCUDO DE AUTO-CURA DA ÁRVORE DE NÓS (EXTINÇÃO UNIVERSAL DE CRASHES)
-- =============================================================================

-- 1. BLINDAGEM ABSOLUTA EM should_show_tabs (node.lua:271)
-- Previne "attempt to call a nil value (method 'is')" em QUALQUER cenário
-- onde self.views seja nil, vazio, ou tenha self.views[1] == nil.
local original_should_show_tabs = Node.should_show_tabs
function Node:should_show_tabs()
  if not self.views or #self.views == 0 or self.views[1] == nil then
    return false
  end
  return original_should_show_tabs(self)
end

-- 2. CORREÇÃO DE update_layout PARA EVITAR "attempt to compare number with nil" (rootview.lua:144)
-- Aplica a sanitização em QUALQUER nó que possua self.views, não apenas folhas.
local original_node_update_layout = Node.update_layout
function Node:update_layout(...)
  if self.views then
    -- Expulsa views corrompidas sem geometria (position)
    for i = #self.views, 1, -1 do
      local v = self.views[i]
      if not v or type(v) ~= "table" or not v.position then
        table.remove(self.views, i)
      end
    end
    
    -- Garante que active_view seja válido e tenha posição
    if not self.active_view or not self.active_view.position then
      for _, v in ipairs(self.views) do
        if v and v.position then
          self.active_view = v
          break
        end
      end
    end
    
    -- SE AINDA ESTIVER VAZIO, INJETA UM PLACEHOLDER VÁLIDO (Última linha de defesa)
    if #self.views == 0 then
      local ok, EmptyView = pcall(require, "core.emptyview")
      local placeholder = ok and EmptyView() or {
        position = { x = 0, y = 0 },
        size = { x = 0, y = 0 },
        draw = function() end,
        update = function() end,
        is = function(_, t) 
          return t == "View" or (type(t) == "string" and t:match("Empty")) 
        end,
        context = "session"
      }
      table.insert(self.views, placeholder)
      self.active_view = placeholder
    end
  end
  
  return original_node_update_layout(self, ...)
end

-- 3. WRAPPER SEGURO EM Node.update (MANTÉM O CICLO DE VIDA ORIGINAL)
local original_node_update = Node.update
function Node:update(...)
  -- Cura nós quebrados (ex: splits fechados incorretamente)
  if self.type ~= "leaf" and (not self.a or not self.b) then
    self.type = "leaf"
    local inherited = (self.a and self.a.views) or (self.b and self.b.views)
    self.views = (inherited and #inherited > 0) and inherited or {}
    self.a = nil
    self.b = nil
  end

  -- Chama o update original do Lite XL (CRUCIAL para o funcionamento correto)
  if original_node_update then
    local ok, err = pcall(original_node_update, self, ...)
    if not ok then
      -- Fallback mínimo apenas se o original falhar catastróficamente
      if self.views then
        for _, view in ipairs(self.views) do
          if view and view.update then pcall(view.update, view, ...) end
        end
      end
    end
  end
end

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

-- =============================================================================
-- 🦅 TELEMETRIA DE COMANDOS (BLINDADA CONTRA FALHAS)
-- =============================================================================
if command and command.perform then
  local original_command_perform = command.perform
  command.perform = function(cmd_name, ...)
    pcall(function()
      append_session_log("CMD", string.format("⚡ Disparado: '%s'", tostring(cmd_name)))
      flush_session_log() -- Força escrita imediata para debug live
    end)
    return original_command_perform(cmd_name, ...)
  end
end

-- =============================================================================
-- 🚨 BANNER DE ALERTA NO ROOTVIEW (BOOT SHIELD)
-- =============================================================================
local original_rootview_draw = RootView.draw
function RootView:draw(...)
  original_rootview_draw(self, ...)
  local report = rawget(_G, "_DOXOADE_BOOT_REPORT")
  if report and report.failed and report.failed > 0 then
    local font = require("core.style").font
    local w = self.size.x
    local banner_h = 4
    draw_rect_safe(0, 0, w, banner_h, { 220, 38, 38, 60 })
    local msg = string.format("🚨 [DOXOADE ALERT] %d módulo(s) falharam no boot! Verifique o log", report.failed)
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
local _log_buffer = {}
local _log_dirty = false
local session_log_file = (USERDIR or ".") .. (PATHSEP or "/") .. "session_log.txt"
local LOG_FLUSH_THRESHOLD = 30


local function flush_session_log()
  if #_log_buffer == 0 then return end
  pcall(function()
    local f = io.open(session_log_file, "a")
    if f then
      f:write(table.concat(_log_buffer))
      f:flush()
      f:close()
    end
  end)
  _log_buffer = {}
end

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
  if inside_append_log then return end
  inside_append_log = true
  pcall(function()
    local ts = os.date("%H:%M:%S")
    table.insert(_log_buffer, string.format("[%s] [%s] %s\n", ts, tostring(level), tostring(msg)))
    if #_log_buffer >= LOG_FLUSH_THRESHOLD then
      flush_session_log()
    end
  end)
  inside_append_log = false
end

-- Thread de flush periódico (a cada 5s)
if core.add_thread then
  core.add_thread(function()
    while true do
      coroutine.yield(2.5)
      flush_session_log()
    end
  end)
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
-- HOOKS NO CORE.LOG E CORE.ERROR
-- =============================================================================
local original_core_log = core.log
function core.log(...)
  local msg = safe_format(...)
  append_session_log("INFO", msg)
  if original_core_log then return original_core_log(...) end
end

local original_core_error = core.error
function core.error(...)
  local msg = safe_format(...)
  append_session_log("ERROR", msg)
  if original_core_error then return original_core_error(...) end
end

-- Reset do log no início de cada sessão
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
