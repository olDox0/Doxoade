-- doxoade/commands/lite_xl_systems/template/13b_leap_toolbar.lua
--[[
⚡ DOXOADE LEAP SYS KVM TOOLBAR & CONTROLLER (V1.3 Fixed & Strict-Safe)
- 修复字符串截断语法错误。
- 显式注入 CLI 参数，防止 click.prompt 在无 TTY 后台调用时死锁。
- 状态同步基于 ~/.doxoade/leap_state.json (SysUtils Zeus <-> Doxly Hermes)。
]]
local core = require "core"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local StatusView = require "core.statusview"

if rawget(_G, "_DOXOADE_LEAP_TOOLBAR_LOADED") then return end
rawset(_G, "_DOXOADE_LEAP_TOOLBAR_LOADED", true)

local sep = PATHSEP or "/"
local home = os.getenv("USERPROFILE") or os.getenv("HOME") or "."
local state_file = home .. sep .. ".doxoade" .. sep .. "leap_state.json"

local LeapHUD = {
    active = false,
    mode = "idle",
    target = "",
    server_ip = "192.168.18.52", -- IP padrão do Amaranth (Host)
    last_toggle_time = 0,
}

local COLOR_HOST_BG   = { 25, 123, 63, 255 }
local COLOR_CLIENT_BG = { 30, 57, 92, 255 }
local COLOR_OFF_BG    = { 45, 45, 48, 255 }
local COLOR_TEXT      = { 250, 250, 250, 255 }

-- 📖 Leitura O(1) do contrato de estado gerado pelo SysUtils
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

-- ⚡ Despachante Soberano (Corrigido e Blindado contra Bloqueio de TTY)
local function toggle_leap_state()
    local now = os.clock()
    if (now - LeapHUD.last_toggle_time) < 0.8 then return end
    LeapHUD.last_toggle_time = now

    local hostname = os.getenv("COMPUTERNAME") or "UNKNOWN"
    local is_amaranth = hostname:upper():find("AMARANTH") ~= nil

    if LeapHUD.active then
        -- 🛑 STOP: Encerra todos os daemons
        pcall(system.exec, 'sysutils leap stop')
        LeapHUD.active = false
        LeapHUD.mode = "idle"
        core.redraw = true
        if core.log then core.log("🛑 [LEAP] Mouse/Teclado desconectado.") end
        return
    end

    if is_amaranth then
        -- 🚀 HOST (Amaranth -> Bluebaby)
        local cmd = 'sysutils leap host --client bluebaby --pos right --port 24800 --no-firewall'
        pcall(system.exec, cmd)
        LeapHUD.active = true
        LeapHUD.mode = "host"
        if core.log then core.log("🚀 [LEAP] Servidor Host iniciado (Amaranth -> Bluebaby)") end
    else
        -- 🔌 CLIENT (Bluebaby -> Amaranth)
        -- 🛡️ BLINDAGEM: IP e nome hardcoded para evitar falhas de resolução de DNS/Prompt
        local cmd = string.format('sysutils leap join %s --port 24800 --name bluebaby', LeapHUD.server_ip)
        pcall(system.exec, cmd)
        LeapHUD.active = true
        LeapHUD.mode = "client"
        if core.log then core.log("🚀 [LEAP] Conectando cliente ao Amaranth (" .. LeapHUD.server_ip .. ")") end
    end
    core.redraw = true
end

-- 🔄 Polling Assíncrono para sincronizar estado se o SysUtils for alterado externamente
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

-- 🎨 Registro na Status Bar (Hermes UI)
core.add_thread(function()
    coroutine.yield(0.05)
    if not core.status_view or not core.status_view.add_item then return end
    
    local existing = pcall(function() return core.status_view:get_item("doxoade:leap_status") end)
    if existing and type(existing) == "table" then return end

    local DIVIDER_COLOR = style.divider or { 76, 69, 82, 255 }
    
    pcall(function()
        core.status_view:add_item({
            name = "doxoade:leap_status",
            alignment = StatusView.Item.RIGHT, -- Alinhado à direita para não esmagar o código
            predicate = function() return true end,
            get_item = function()
                local label = "L:OFF"
                local color = COLOR_TEXT
                if LeapHUD.active then
                    if LeapHUD.mode == "host" then
                        label = "L:HST" -- Host/Servidor
                        color = { 100, 255, 150, 255 }
                    else
                        label = "L:CLI" -- Cliente
                        color = { 150, 200, 255, 255 }
                    end
                end
                return { color, " " .. label .. " ", DIVIDER_COLOR, "| " }
            end,
            command = function() toggle_leap_state() end,
            position = 4 -- Posição 4 no lado RIGHT
        })
    end)
end)

-- ⌨️ Comandos e Atalhos
command.add(nil, {
    ["doxoade:leap-toggle"] = function() toggle_leap_state() end,
    ["doxoade:leap-stop"] = function()
        pcall(system.exec, "sysutils leap stop")
        LeapHUD.active = false
        core.redraw = true
        if core.log then core.log("🛑 [LEAP] Processos encerrados.") end
    end
})

keymap.add { ["ctrl+alt+l"] = "doxoade:leap-toggle" }
