-- doxoade/commands/lite_xl_systems/template/13c_scroll_lock_guard.lua
--[[
🛡️ DOXOADE SCROLL LOCK GUARD (V1.0 Zero-Flash & Strict-Safe)
- Monitora o estado da tecla Scroll Lock via Win32 API (GetKeyState).
- Usa pythonw.exe para execução 100% silenciosa (Zero CMD Flash).
- Exibe badge de alerta na Status Bar e notifica o usuário em tempo real.
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
Panteões: Khonsu (Agendamento), Hermes (Telemetria), Apolo (UX).
]]
local core = require "core"
local style = require "core.style"
local StatusView = require "core.statusview"

if rawget(_G, "_DOXOADE_SCROLL_LOCK_GUARD_LOADED") then return end
rawset(_G, "_DOXOADE_SCROLL_LOCK_GUARD_LOADED", true)

local sep = PATHSEP or "/"
local temp_dir = os.getenv("TEMP") or os.getenv("TMP") or "."
local state_file = temp_dir .. sep .. "doxoade_scroll_lock.txt"

local ScrollGuard = {
    is_active = false,
    last_state = nil,
    last_check = 0,
    check_interval = 1.5, -- Segundos entre cada sondagem
}

local COLOR_WARN_BG = { 220, 50, 40, 255 } -- Vermelho de Alerta
local COLOR_OK_BG   = { 35, 120, 65, 255 } -- Verde de Segurança
local COLOR_TEXT    = { 250, 250, 250, 255 }
local DIVIDER_COLOR = style.divider or { 76, 69, 82, 255 }

-- ⚡ Despachante Silencioso (Usa pythonw para não criar janela de console)
local function trigger_silent_check()
    -- O ctypes consulta a API Win32 GetKeyState(0x91 = VK_SCROLL)
    -- O bit 0 (low-order) indica se a tecla está toggled (ativa).
    local py_cmd = string.format(
        'pythonw -c "import ctypes,pathlib;pathlib.Path(r\'%s\').write_text(\'1\' if ctypes.windll.user32.GetKeyState(0x91) & 1 else \'0\')"',
        state_file
    )
    -- system.exec é assíncrono e não bloqueia o frame do SDL2
    pcall(system.exec, py_cmd)
end

-- 📖 Leitura O(1) do estado gravado pelo Python
local function read_state()
    local f = io.open(state_file, "r")
    if not f then return nil end
    local content = f:read("*l") or ""
    f:close()
    return content == "1"
end

-- 🔄 Loop de Monitoramento Assíncrono (Khonsu-safe)
if core and core.add_thread then
    core.add_thread(function()
        coroutine.yield(2.0) -- Aguarda o boot e o carregamento dos outros módulos
        
        while true do
            local now = os.clock()
            if (now - ScrollGuard.last_check) >= ScrollGuard.check_interval then
                ScrollGuard.last_check = now
                trigger_silent_check()

                -- Pausa mínima para garantir que o pythonw gravou o arquivo
                coroutine.yield(0.15)

                local current_state = read_state()
                if current_state ~= nil and current_state ~= ScrollGuard.last_state then
                    ScrollGuard.last_state = current_state
                    ScrollGuard.is_active = current_state

                    -- 🚨 Notificação de Transição de Estado
                    if current_state then
                        core.log("⚠️ [GUARD] Scroll Lock ATIVADO! (Isso pode bloquear o Leap/KVM e atalhos globais)")
                    else
                        core.log("🟢 [GUARD] Scroll Lock desativado. Roteamento de teclado normalizado.")
                    end
                    core.redraw = true
                end
            end
            coroutine.yield(0.5)
        end
    end)
end

-- 🎨 Registro na Status Bar (Hermes UI)
core.add_thread(function()
    coroutine.yield(0.1)
    if not core.status_view or not core.status_view.add_item then return end

    pcall(function()
        core.status_view:add_item({
            name = "doxoade:scroll_lock_status",
            alignment = StatusView.Item.LEFT,
            predicate = function() return true end,
            get_item = function()
                if ScrollGuard.is_active then
                    return {
                        COLOR_WARN_BG, " [ ⚠️ SCROLL LOCK ] ",
                        DIVIDER_COLOR, "| "
                    }
                else
                    return {
                        COLOR_OK_BG, " [ 🔒 Scroll ] ",
                        DIVIDER_COLOR, "| "
                    }
                end
            end,
            command = function()
                core.log("💡 Dica: Pressione a tecla 'Scroll Lock' no seu teclado para alternar o estado.")
            end,
            position = 7 -- Posicionado logo após o badge do Leap e Note
        })
    end)
end)
