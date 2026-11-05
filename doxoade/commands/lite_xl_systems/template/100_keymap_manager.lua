local core = require "core"
local keymap = require "core.keymap"
local command = require "core.command"

if rawget(_G, "_DOXOADE_KEYMAP_MANAGER_APPLIED") then return end
rawset(_G, "_DOXOADE_KEYMAP_MANAGER_APPLIED", true)

-- ⏳ DEFERIMENTO: Espera o boot terminar e os módulos registrarem comandos
if core.add_thread then
  core.add_thread(function()
    -- 🛡️ [FASE 2] Retry: aguarda TODOS os comandos críticos (máx 5s)
    local max_wait = 5.0
    local waited = 0.0
    local step = 0.15
    local critical_cmds = {
      "doxoade:move-tab-to-opposite-panel",
      "doxoade:toggle-split-orientation",
      "doxoade:contextual-search",  -- ← ADICIONADO
      "doxoade:terminal-launch-real",
      "doxoade:toggle-bottom-shelf",
    }
    while waited < max_wait do
      coroutine.yield(step)
      waited = waited + step
      local ready = true
      for _, cmd_name in ipairs(critical_cmds) do
        if not (command.map and command.map[cmd_name]) then
          ready = false
          break
        end
      end
      if ready then break end
    end

    local DOXOADE_CANONICAL_KEYMAP = {
      ["ctrl+alt+d"]          = "doxoade:move-tab-to-opposite-panel",
      ["ctrl+alt+shift+d"]    = "doxoade:move-following-tabs-to-opposite",
      ["ctrl+l"]              = "doxoade:toggle-split-orientation",
      ["ctrl+shift+l"]        = "doxoade:swap-split-panels",
      ["f6"]                  = "doxoade:focus-opposite-panel",
      ["alt+f"]               = "doxoade:contextual-search",
      ["ctrl+alt+t"]          = "doxoade:terminal-launch-real",
      ["ctrl+j"]              = "doxoade:toggle-bottom-shelf",
      ["ctrl+alt+e"]          = "doxoade:tab-copy-filename",
      ["ctrl+shift+c"]        = "doxoade:tab-copy-relative-path",
    }

    local valid_keymap = {}
    local invalid_count = 0
    local valid_count = 0
    for shortcut, cmd_name in pairs(DOXOADE_CANONICAL_KEYMAP) do
      local cmd_entry = command.map and command.map[cmd_name]
      if cmd_entry then
        valid_keymap[shortcut] = cmd_name
        valid_count = valid_count + 1
      else
        invalid_count = invalid_count + 1
        if core.log then
          core.log(string.format("❌ [KEYMAP] Comando ainda não registrado: %s -> %s", shortcut, cmd_name))
        end
      end
    end

    if valid_count > 0 then
      keymap.add(valid_keymap, true)
      if core.log then
        core.log(string.format("🗺️ [KEYMAP] Keymap Manager carregado: %d/%d atalhos válidos (aguardou %.1fs).",
          valid_count, valid_count + invalid_count, waited))
      end
    end
  end)
end
