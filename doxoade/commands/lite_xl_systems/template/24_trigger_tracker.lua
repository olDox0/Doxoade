-- doxoade/commands/lite_xl_systems/template/24_trigger_tracker.lua
--[[
  🎯 DOXOADE TRIGGER TRACKER (V2.0 — Hórus Trigger Recorder)
  ----------------------------------------------------------------------------
  Rastreia TUDO:
    - Teclas físicas (keydown/keyup)
    - Comandos acionados (command.perform)
    - Modifiers ativos
    - Conflitos de keymap
    - Comandos que falham
]]

local core = require "core"
local command = require "core.command"
local keymap = require "core.keymap"

-- 24_trigger_tracker.lua — topo
if rawget(_G, "_DOXOADE_TRIGGER_TRACKER_APPLIED") then return end
rawset(_G, "_DOXOADE_TRIGGER_TRACKER_APPLIED", true)

local user_dir = USERDIR or "."
local sep = PATHSEP or "/"
local diag_dir = user_dir .. sep .. ".doxoade" .. sep .. "diagnostics"
local tracker_file = diag_dir .. sep .. "trigger_tracker.ndjson"

pcall(function() if system and system.mkdir then system.mkdir(diag_dir) end end)

-- Ring buffer
local RING_SIZE = 300
local _ring = {}
local _head = 1
local _count = 0
local _last_flush = os.clock()

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
  -- 🛡️ [FASE 5.3-FIX] Só loga EXECUTE no console (KEY/CONFLICT vão só para NDJSON)
  if core.log and cat == "EXECUTE" then
    core.log(string.format("🎯 [TRIGGER] [%s] %s", cat, act))
  end
end

local function flush_to_disk()
  if _count == 0 then return end
  local f = io.open(tracker_file, "a")
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

-- ── Hook 1: Teclas físicas ────────────────────────────────────────────────
local _orig_on_event = core.on_event
core.on_event = function(event_type, ...)
  if event_type == "keypressed" then
    local args = { ... }
    local key_name = tostring(args[1] or "?")
    local mods = ""
    if keymap and keymap.modkeys then
      for mod, active in pairs(keymap.modkeys) do
        if active then mods = mods .. mod .. "+" end
      end
    end
    -- Registra sem poluir muito o log (só se mods contém algo ou tecla especial)
    local is_important = (mods ~= "") or (key_name:find("f%d") ~= nil) or (key_name == "escape")
    if is_important then
      record("KEY", key_name, { mods = mods }, "")
    end
  end
  return _orig_on_event(event_type, ...)
end

-- ── Hook 2: Comandos acionados ────────────────────────────────────────────
local _orig_perform = command.perform
command.perform = function(cmd_name, ...)
  local tb = debug.traceback("", 2) or ""
  local blame = tb:match("\t([^%r\n]+)") or "unknown"
  -- Extrai módulo culpado
  local module = "unknown"
  local m = blame:match("template[/\\]([%w_]+%.lua)")
  if m then module = m end
  -- Verifica se a chave está no keymap
  local key_for_cmd = nil
  if keymap and keymap.map then
    for k, v in pairs(keymap.map) do
      if type(v) == "table" and #v > 1 then
        record("CONFLICT", "same_key_multiple_commands", {
          key = k,
          commands = table.concat(v, " | "),
        }, "keymap.map")
      end
    end
  end
  record("EXECUTE", cmd_name, {
    module = module,
    key = key_for_cmd or "?",
  }, blame)
  return _orig_perform(cmd_name, ...)
end

-- ── Hook 3: Análise do keymap — UMA VEZ APENAS ────────────────────────────
if core.add_thread then
  core.add_thread(function()
    coroutine.yield(2.0)
    if not keymap or not keymap.map then return end
    
    -- 🛡️ [FASE 5.3-FIX] Filtra conflitos legítimos (doxoade sobrescrevendo core)
    local real_conflicts = {}
    for k, v in pairs(keymap.map) do
      if type(v) == "table" and #v > 1 then
        -- Verifica se é conflito real (2+ comandos do Doxoade)
        local doxoade_count = 0
        for _, cmd in ipairs(v) do
          if cmd:find("doxoade:") then doxoade_count = doxoade_count + 1 end
        end
        if doxoade_count >= 2 then
          table.insert(real_conflicts, { key = k, commands = v })
        end
      end
    end
    
    if core.log and #real_conflicts > 0 then
      core.log(string.format("🎯 [TRIGGER] %d conflito(s) REAIS (doxoade→doxoade):", #real_conflicts))
      for i, c in ipairs(real_conflicts) do
        if i <= 10 then
          core.log(string.format("  • %s → %s", c.key, table.concat(c.commands, " | ")))
        end
      end
    end
  end)
  
  -- Thread de flush — 1x a cada 5s
  core.add_thread(function()
    while true do
      coroutine.yield(5.0)
      if _count > 0 then flush_to_disk() end
    end
  end)
end

-- Comando CLI para análise
command.add(nil, {
  ["doxoade:analyze-triggers"] = function()
    flush_to_disk()
    if core.log then
      core.log("🎯 [TRIGGER] Dados em: " .. tracker_file)
    end
  end,
  ["doxoade:audit-keymap"] = function()
    if not keymap or not keymap.map then return end
    local conflicts = {}
    for k, v in pairs(keymap.map) do
      if type(v) == "table" and #v > 1 then
        table.insert(conflicts, { key = k, commands = v })
      end
    end
    
    if #conflicts == 0 then
      if core.log then core.log("🎯 [KEYMAP] Nenhum conflito detectado.") end
      return
    end
    
    if core.log then
      core.log(string.format("🎯 [KEYMAP] %d conflitos detectados:", #conflicts))
      for _, c in ipairs(conflicts) do
        core.log(string.format("  • %s → %s", c.key, table.concat(c.commands, " | ")))
      end
    end
  end,
})

-- 🛡️ [FASE 5.2] Keymap unificado com o manager
-- pcall(function()
--   if keymap and keymap.unbind then
--     keymap.unbind("ctrl+alt+shift+y")
--   end
--   keymap.add({["ctrl+alt+shift+y"]  = "doxoade:analyze-triggers",}, true)
--   keymap.add({ ["ctrl+alt+shift+k"] = "doxoade:audit-keymap" }, true)
--   keymap.add({["ctrl+alt+shift+q"]  = "doxoade:analyze-triggers",}, true)
-- end)

if core.log then
  core.log("🎯 [TRIGGER] Trigger Tracker V2.0 ativo. Saída: " .. tracker_file)
end
