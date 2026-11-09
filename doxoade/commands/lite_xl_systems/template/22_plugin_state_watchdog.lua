-- doxoade/commands/lite_xl_systems/template/22_plugin_state_watchdog.lua
--[[
  🐕 DOXOADE PLUGIN STATE WATCHDOG (V1.0 — Sensor Passivo)
  ----------------------------------------------------------------------------
  Captura mutações ilegais de views, set_active_view(nil), frame spikes e
  comandos de plugins nativos. Saída em NDJSON para auditoria.
  Não bloqueia nada. Custo < 0.05ms/frame.
]]

local core = require "core"
local RootView = require "core.rootview"
local Node = require "core.node"
local command = require "core.command"
local config = require "core.config"

-- Kill Switch
if config.doxoade_plugin_watchdog == false then
  if core.log then core.log("🐕 [WATCHDOG] Desativado via config.doxoade_plugin_watchdog=false") end
  return
end

local user_dir = USERDIR or "."
local sep = PATHSEP or "/"
local diag_dir = user_dir .. sep .. ".doxoade" .. sep .. "diagnostics"
local audit_file = diag_dir .. sep .. "plugin_state_audit.ndjson"

pcall(function() if system and system.mkdir then system.mkdir(diag_dir) end end)

-- ── Ring Buffer ────────────────────────────────────────────────────────────
local RING_SIZE = 100
local _ring = {}
local _head = 1
local _count = 0
local _last_flush = os.clock()
local FLUSH_INTERVAL = 5.0

local function json_escape(s)
  if not s then return "" end
  return tostring(s):gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n"):gsub("\r", "\\r")
end

local function record(cat, act, ctx, blame)
  local entry = {
    ts = os.time(),
    ts_iso = os.date("%Y-%m-%d %H:%M:%S"),
    cat = cat, act = act, ctx = ctx or {}, blame = blame or "",
  }
  _ring[_head] = entry
  _head = (_head % RING_SIZE) + 1
  if _count < RING_SIZE then _count = _count + 1 end
  if core.log and cat ~= "PERF" then
    core.log(string.format("🐕 [WATCHDOG] [%s] %s %s", cat, act, blame))
  end
end

local function flush_to_disk()
  if _count == 0 then return end
  local f = io.open(audit_file, "a")
  if not f then return end
  local start_idx = _head - _count
  if start_idx <= 0 then start_idx = start_idx + RING_SIZE end
  for i = 1, _count do
    local idx = ((start_idx + i - 2) % RING_SIZE) + 1
    local e = _ring[idx]
    if e then
      local ctx_json = "{"
      local first = true
      for k, v in pairs(e.ctx) do
        if not first then ctx_json = ctx_json .. "," end
        first = false
        ctx_json = ctx_json .. string.format('"%s":"%s"', json_escape(k), json_escape(v))
      end
      ctx_json = ctx_json .. "}"
      f:write(string.format(
        '{"ts":%d,"ts_iso":"%s","cat":"%s","act":"%s","ctx":%s,"blame":"%s"}\n',
        e.ts, e.ts_iso, json_escape(e.cat), json_escape(e.act), ctx_json, json_escape(e.blame)
      ))
    end
  end
  f:flush(); f:close()
  _ring = {}; _head = 1; _count = 0; _last_flush = os.clock()
end

-- ── Sensor 1: Mutation during draw ────────────────────────────────────────
local function hash_views(node)
  if not node then return "" end
  local parts = {}
  local function traverse(n)
    if not n then return end
    if n.type == "leaf" then
      local count = #(n.views or {})
      table.insert(parts, tostring(count))
      for i = 1, count do
        if n.views[i] then table.insert(parts, tostring(n.views[i])) end
      end
    else
      traverse(n.a); traverse(n.b)
    end
  end
  traverse(node)
  return table.concat(parts, "|")
end

local _original_draw = RootView.draw
local _in_draw = false
function RootView:draw(...)
  if _in_draw then return _original_draw(self, ...) end
  _in_draw = true
  local hash_before = hash_views(self.root_node)
  local res = _original_draw(self, ...)
  local hash_after = hash_views(self.root_node)
  _in_draw = false
  if hash_before ~= hash_after then
    local blame = debug.traceback("", 2):match("\t([^\r\n]+)") or "unknown"
    record("MUTATION", "view_tree_changed_during_draw", { before = #hash_before, after = #hash_after }, blame)
  end
  return res
end

-- ── Sensor 2: NIL Active View ─────────────────────────────────────────────
local _original_set_active_view = core.set_active_view
core.set_active_view = function(view)
  if view == nil then
    local blame = debug.traceback("", 2):match("\t([^\r\n]+)") or "unknown"
    record("NIL_ACTIVE_VIEW", "set_active_view(nil)_intercepted", {}, blame)
  end
  return _original_set_active_view(view)
end

-- ── Sensor 3: Layout Spike ────────────────────────────────────────────────
local _boot_time = os.clock()
local _original_update_layout = Node.update_layout
function Node:update_layout(...)
  local t0 = os.clock()
  local res = _original_update_layout(self, ...)
  local elapsed_ms = (os.clock() - t0) * 1000
  
  -- 🛡️ [FASE 5.2] Silencia spikes nos primeiros 3s (boot init)
  if (os.clock() - _boot_time) > 3.0 and elapsed_ms > 16.0 then
    local tb = debug.traceback("", 2) or ""
    local blame = tb:match("\t([^%r\n]+)") or "unknown"
    record("LAYOUT_SPIKE", "update_layout_slow", {
      elapsed_ms = string.format("%.2f", elapsed_ms),
      node_type = tostring(self.type),
    }, blame)
  end
  return res
end

-- ── Sensor 4: Plugin Commands ─────────────────────────────────────────────
local _original_command_perform = command.perform
local PLUGIN_CMDS = {
  ["core:"] = "core", ["root:"] = "core", ["doc:"] = "core",
  ["find-replace:"] = "core.findreplace", ["autocomplete:"] = "core.autocomplete",
  ["context:"] = "plugins.contextmenu", ["treeview:"] = "plugins.treeview",
  ["macro:"] = "plugins.macro", ["settings:"] = "plugins.settings",
  ["autoreload:"] = "plugins.autoreload", ["project-search:"] = "plugins.projectsearch",
}
command.perform = function(cmd_name, ...)
  local category = "doxoade"
  for prefix, plugin in pairs(PLUGIN_CMDS) do
    if cmd_name:sub(1, #prefix) == prefix then
      category = plugin; break
    end
  end
  if category ~= "doxoade" then
    record("PLUGIN_COMMAND", cmd_name, {}, category)
  end
  return _original_command_perform(cmd_name, ...)
end

-- ── Thread de Flush ───────────────────────────────────────────────────────
if core.add_thread then
  core.add_thread(function()
    while true do
      coroutine.yield(1.0)
      if _count > 0 and (os.clock() - _last_flush) >= FLUSH_INTERVAL then flush_to_disk() end
      if _count >= RING_SIZE - 1 then flush_to_disk() end
    end
  end)
end

if core.log then
  core.log("🐕 [WATCHDOG] Plugin State Watchdog V1.0 ativo (sensor passivo).")
end

rawset(_G, "_DOXOADE_PLUGIN_AUDIT", { flush = flush_to_disk, record = record })

-- ═══════════════════════════════════════════════════════════════════════════
-- 🛡️ [FASE 5.1] SENSORES AVANÇADOS (detectam destruição de views e foco roubado)
-- ═══════════════════════════════════════════════════════════════════════════

-- ── Sensor 5: Node:consume ───────────────────────────────────────────────
local _original_consume = Node.consume
if _original_consume and type(_original_consume) == "function" then
  Node.consume = function(self, other)
    local tb = debug.traceback("", 2) or ""
    
    -- 🛡️ [FASE 5.2-FIX] Filtro agressivo: só registra se for plugin externo
    local is_legit = (
      tb:find("core[/\\]node%.lua")      -- Lite XL interno
      or tb:find("core[/\\]rootview")     -- RootView interno
      or tb:find("core[/\\]init")         -- init do Lite XL
      or tb:find("05_split_mover")        -- Doxoade split mover
      or tb:find("09_panel_manager")      -- Doxoade panel manager
      or tb:find("18_search_results_dock") -- Doxoade search dock
    )
    
    if not is_legit then
      local blame = tb:match("\t([^%r\n]+)") or "unknown"
      record("ILLEGAL_CONSUME", "node_consume_outside_split_mover", {
        node_type = tostring(self.type),
        other_type = tostring(other and other.type or "nil"),
      }, blame)
    end
    
    return _original_consume(self, other)
  end
end

-- ── Sensor 6: RootView:set_active_node (foco roubado) ────────────────────
-- 🛡️ [FASE 5.2-FIX] Blindagem: verifica se a função existe antes de hookar
if RootView.set_active_node and type(RootView.set_active_node) == "function" then
  local _original_set_active_node = RootView.set_active_node
  RootView.set_active_node = function(self, node, ...)
    if node ~= nil then
      local prev = self.active_node
      if prev and prev ~= node then
        local tb = debug.traceback("", 2) or ""
        local blame = tb:match("\t([^\r\n]+)") or "unknown"
        if not (blame:find("05_split_mover") or blame:find("21_selection")) then
          record("NODE_FOCUS_CHANGE", "active_node_changed", {
            from_type = tostring(prev.type),
            to_type = tostring(node.type),
          }, blame)
        end
      end
    end
    return _original_set_active_node(self, node, ...)
  end
end

-- ── Sensor 7: DocView:on_doc_change (mudança de doc em view existente) ───
-- Detecta se algum plugin tenta trocar o doc de uma view (o que causou o bug do 18_search)
local DocView = pcall(require, "core.docview") and require("core.docview") or nil
if DocView and DocView.on_doc_change then
  local _original_on_doc_change = DocView.on_doc_change
  DocView.on_doc_change = function(self, ...)
    local blame = debug.traceback("", 2):match("\t([^\r\n]+)") or "unknown"
    record("DOC_CHANGE", "docview_on_doc_change", {
      new_doc = tostring(self.doc and self.doc.filename or "nil"),
    }, blame)
    return _original_on_doc_change(self, ...)
  end
end
