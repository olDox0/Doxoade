-- doxoade/commands/lite_xl_systems/template/13b_leap_toolbar.lua
--[[
  ⚡ DOXOADE LEAP SYS KVM TOOLBAR & CONTROLLER (V1.2 Idempotente & Strict-Safe)
  - Guarda estrita de reentrância (imune a duplo registro no StatusView).
  - Debounce de clique (impede duplo disparo acidental).
  - Leitura leve de estado O(1) imune a travamentos de frame rate.
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = require "core"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local StatusView = require "core.statusview"

-- 🛡️ GUARDA DE IDEMPOTÊNCIA: Nunca carrega duas vezes
if rawget(_G, "_DOXOADE_LEAP_TOOLBAR_LOADED") then return end
rawset(_G, "_DOXOADE_LEAP_TOOLBAR_LOADED", true)

local sep = PATHSEP or "/"
local home = os.getenv("USERPROFILE") or os.getenv("HOME") or "."
local state_file = home .. sep .. ".doxoade" .. sep .. "leap_state.json"

local LeapHUD = {
  active = false,
  mode = "idle",
  target = "",
  server_ip = "192.168.18.52",
  last_toggle_time = 0,
}

local COLOR_HOST_BG   = { 25, 123, 63, 255 }   -- Verde escuro
local COLOR_CLIENT_BG = { 30, 57, 92, 255 }    -- Azul escuro
local COLOR_OFF_BG    = { 45, 45, 48, 255 }    -- Cinza neutro
local COLOR_TEXT      = { 250, 250, 250, 255 }

local function read_leap_state()
  local f = io.open(state_file, "r")
  if not f then
    LeapHUD.active = false
    LeapHUD.mode = "idle"
    return
  end
  local content = f:read("*a") or ""
  f:close()
  
  LeapHUD.active = content:find('"active":%s*true') ~= nil
  LeapHUD.mode = content:match('"mode":%s*"([^"]+)"') or "idle"
  LeapHUD.target = content:match('"target":%s*"([^"]+)"') or ""
  local ip = content:match('"server_ip":%s*"([^"]+)"')
  if ip and ip ~= "" then
    LeapHUD.server_ip = ip
  end
end

local function toggle_leap_state()
  local now = os.clock()
  -- Debounce: ignora cliques com menos de 0.8s de intervalo
  if (now - LeapHUD.last_toggle_time) < 0.8 then
    return
  end
  LeapHUD.last_toggle_time = now

  local hostname = os.getenv("COMPUTERNAME") or "UNKNOWN"
  local is_amaranth = hostname:upper():find("AMARANTH") ~= nil
  
  -- 1. Se estiver ativo, encerra
  if LeapHUD.active then
    pcall(system.exec, "sysutils leap stop")
    LeapHUD.active = false
    LeapHUD.mode = "idle"
    core.redraw = true
    if core.log then core.log("🛑 [LEAP] Mouse/Teclado desconectado. Bluebaby liberado!") end
    return
  end

  -- 2. Se estiver desligado, aciona conforme o host
  if is_amaranth then
    local cmd = "sysutils leap host --client bluebaby --pos right"
    pcall(system.exec, cmd)
    LeapHUD.active = true
    LeapHUD.mode = "host"
    if core.log then core.log("🚀 [LEAP] Servidor Host iniciado (Amaranth -> Bluebaby)") end
  else
    local cmd = string.format("sysutils leap join %s --name bluebaby", LeapHUD.server_ip)
    pcall(system.exec, cmd)
    LeapHUD.active = true
    LeapHUD.mode = "client"
    if core.log then core.log("🚀 [LEAP] Conectando cliente ao Amaranth (" .. LeapHUD.server_ip .. ")") end
  end
  core.redraw = true
end

-- Corrotina de telemetria periódica
if core and core.add_thread then
  core.add_thread(function()
    while true do
      coroutine.yield(1.5)
      local prev_active = LeapHUD.active
      local prev_mode = LeapHUD.mode
      read_leap_state()
      if prev_active ~= LeapHUD.active or prev_mode ~= LeapHUD.mode then
        core.redraw = true
      end
    end
  end)
end

-- Registro protegido e único no StatusView
core.add_thread(function()
  coroutine.yield(0.05)
  if not core.status_view or not core.status_view.add_item then return end
  
  -- Se já existir por qualquer motivo, não adiciona novamente
  local existing = pcall(function() return core.status_view:get_item("doxoade:leap_status") end)
  if existing and type(existing) == "table" then return end

  local DIVIDER_COLOR = style.divider or { 76, 69, 82, 255 }
  
  pcall(function()
    core.status_view:add_item({
      name = "doxoade:leap_status",
      alignment = StatusView.Item.LEFT,
      predicate = function() return true end,
      get_item = function()
        local label = " [ LEAP: OFF ] "
        if LeapHUD.active then
          if LeapHUD.mode == "host" then
            label = " [ LEAP: HOST ] "
          else
            label = " [ LEAP: CLIENT ] "
          end
        end
        return {
          COLOR_TEXT, label,
          DIVIDER_COLOR, "| "
        }
      end,
      command = function()
        toggle_leap_state()
      end,
      position = 6
    })
  end)
end)

-- Comandos na Paleta e Atalho
command.add(nil, {
  ["doxoade:leap-toggle"] = function()
    toggle_leap_state()
  end,
  ["doxoade:leap-stop"] = function()
    pcall(system.exec, "sysutils leap stop")
    LeapHUD.active = false
    core.redraw = true
    if core.log then core.log("🛑 [LEAP] Processos encerrados.") end
  end
})

keymap.add {
  ["ctrl+alt+l"] = "doxoade:leap-toggle",
}
