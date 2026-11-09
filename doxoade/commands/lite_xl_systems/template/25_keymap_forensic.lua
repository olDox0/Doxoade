-- doxoade/commands/lite_xl_systems/template/25_keymap_forensic.lua
--[[
  🔬 DOXOADE KEYMAP FORENSIC TRACKER (V1.0)
  ----------------------------------------------------------------------------
  Rastreia TUDO sobre atalhos:
    1. Todo keymap.add() com arquivo de origem
    2. Todo keymap.map em runtime
    3. Toda tecla pressionada (física vs lógica)
    4. Conflitos reais (mesma tecla → múltiplos comandos)
  
  Saída: .doxoade/diagnostics/keymap_forensic.json
]]

local core = require "core"
local keymap = require "core.keymap"
local command = require "core.command"

-- 25_keymap_forensic.lua — topo
if rawget(_G, "_DOXOADE_KEYMAP_FORENSIC_APPLIED") then return end
rawset(_G, "_DOXOADE_KEYMAP_FORENSIC_APPLIED", true)

local user_dir = USERDIR or "."
local sep = PATHSEP or "/"
local diag_dir = user_dir .. sep .. ".doxoade" .. sep .. "diagnostics"
local forensic_file = diag_dir .. sep .. "keymap_forensic.json"

pcall(function() if system and system.mkdir then system.mkdir(diag_dir) end end)

-- ── Registry: rastrear quem registrou cada tecla ────────────────────────────
local _keymap_registry = {}  -- { [key] = { commands = {}, sources = {} } }

local function track_registration(key, command_name, source_file)
  if not _keymap_registry[key] then
    _keymap_registry[key] = { commands = {}, sources = {} }
  end
  table.insert(_keymap_registry[key].commands, command_name)
  table.insert(_keymap_registry[key].sources, source_file or "unknown")
end

-- ── Hook: keymap.add() ──────────────────────────────────────────────────────
local _orig_keymap_add = keymap.add
keymap.add = function(map, overwrite)
  local tb = debug.traceback("", 2) or ""
  local source_file = "unknown"
  local m = tb:match("template[/\\]([%w_]+%.lua)")
  if m then source_file = m end
  
  for key, cmd in pairs(map or {}) do
    local commands = type(cmd) == "table" and cmd or { cmd }
    for _, c in ipairs(commands) do
      track_registration(key, c, source_file)
    end
  end
  
  return _orig_keymap_add(map, overwrite)
end

-- ── Hook: keymap.unbind() ───────────────────────────────────────────────────
local _orig_keymap_unbind = keymap.unbind
if _orig_keymap_unbind then
  keymap.unbind = function(key)
    if _keymap_registry[key] then
      _keymap_registry[key].commands = {}
      _keymap_registry[key].sources = {}
    end
    return _orig_keymap_unbind(key)
  end
end

-- ── Hook: keymap.on_key_pressed (rastrear teclas físicas) ───────────────────
local _last_key = nil
local _last_key_time = 0

if core.on_event then
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
      _last_key = { key = key_name, mods = mods }
      _last_key_time = os.clock()
      
      -- 📊 Loga teclas que começam com "ctrl+l" ou "l"
      if mods:find("ctrl") and (key_name == "l" or mods:find("alt")) then
        if core.log then
          core.log(string.format("🔬 [KEYMAP-FORENSIC] Tecla: %s | Mods: %s",
            key_name, mods ~= "" and mods or "none"))
        end
      end
    end
    return _orig_on_event(event_type, ...)
  end
end

-- ── Hook: command.perform (rastrear qual comando executou) ──────────────────
local _orig_perform = command.perform
command.perform = function(cmd_name, ...)
  if _last_key and (os.clock() - _last_key_time) < 0.5 then
    local tb = debug.traceback("", 2) or ""
    local source_file = "unknown"
    local m = tb:match("template[/\\]([%w_]+%.lua)")
    if m then source_file = m end
    
    -- 📊 Loga apenas comandos relacionados a split/leap
    if cmd_name:find("split") or cmd_name:find("leap") or 
       cmd_name:find("move-tab") or cmd_name:find("focus-opposite") or
       cmd_name:find("toggle-split") then
      if core.log then
        core.log(string.format(
          "🔬 [KEYMAP-FORENSIC] Comando '%s' executado | Tecla: %s | Mods: %s | Fonte: %s",
          cmd_name, _last_key.key, _last_key.mods, source_file
        ))
      end
    end
  end
  return _orig_perform(cmd_name, ...)
end

-- ── Análise de conflitos + dump ─────────────────────────────────────────────
local function analyze_and_dump()
  local conflicts = {}
  local keymap_map = keymap.map or {}
  
  -- Análise de conflitos
  for key, cmds in pairs(keymap_map) do
    local commands = type(cmds) == "table" and cmds or { cmds }
    if #commands > 1 then
      table.insert(conflicts, {
        key = key,
        commands = commands,
        sources = _keymap_registry[key] and _keymap_registry[key].sources or {},
      })
    end
  end
  
  -- Filtra apenas conflitos "reais" (2+ comandos do Doxoade)
  local real_conflicts = {}
  for _, c in ipairs(conflicts) do
    local doxoade_count = 0
    for _, cmd in ipairs(c.commands) do
      if cmd:find("doxoade:") then doxoade_count = doxoade_count + 1 end
    end
    if doxoade_count >= 2 then
      table.insert(real_conflicts, c)
    end
  end
  
  -- Escreve arquivo JSON
  pcall(function()
    local f = io.open(forensic_file, "w")
    if not f then return end
    
    f:write("{\n")
    f:write(string.format('  "timestamp": %q,\n', os.date("%Y-%m-%d %H:%M:%S")))
    f:write(string.format('  "total_keys": %d,\n', (function()
      local n = 0
      for _ in pairs(keymap_map) do n = n + 1 end
      return n
    end)()))
    f:write(string.format('  "total_conflicts": %d,\n', #conflicts))
    f:write(string.format('  "real_conflicts": %d,\n', #real_conflicts))
    
    f:write('  "conflicts": [\n')
    local first = true
    for _, c in ipairs(conflicts) do
      if not first then f:write(",\n") end
      first = false
      f:write(string.format('    {"key": %q, "commands": [%q], "sources": [%q]}',
        c.key,
        table.concat(c.commands, ", "),
        table.concat(c.sources, ", ")
      ))
    end
    f:write("\n  ],\n")
    
    f:write('  "real_conflicts_detail": [\n')
    first = true
    for _, c in ipairs(real_conflicts) do
      if not first then f:write(",\n") end
      first = false
      f:write(string.format('    {"key": %q, "commands": [%q], "sources": [%q]}',
        c.key,
        table.concat(c.commands, ", "),
        table.concat(c.sources, ", ")
      ))
    end
    f:write("\n  ],\n")
    
    -- Registro de quem registrou cada tecla
    f:write('  "keymap_registry": {\n')
    first = true
    for key, entry in pairs(_keymap_registry) do
      if #entry.commands > 0 then
        if not first then f:write(",\n") end
        first = false
        f:write(string.format('    %q: {"commands": [%q], "sources": [%q]}',
          key,
          table.concat(entry.commands, ", "),
          table.concat(entry.sources, ", ")
        ))
      end
    end
    f:write("\n  }\n")
    
    f:write("}\n")
    f:flush()
    f:close()
  end)
  
  -- Loga resumo
  if core.log then
    core.log(string.format("🔬 [KEYMAP-FORENSIC] Análise concluída: %d conflitos totais, %d reais",
      #conflicts, #real_conflicts))
    for _, c in ipairs(real_conflicts) do
      local src_str = #c.sources > 0 and (" ← " .. c.sources[1]) or ""
      core.log(string.format("  🔴 %s → %s%s", c.key, table.concat(c.commands, " | "), src_str))
    end
  end
  
  return {
    total_keys = (function() local n = 0; for _ in pairs(keymap_map) do n = n + 1 end; return n end)(),
    total_conflicts = #conflicts,
    real_conflicts = real_conflicts,
    file = forensic_file,
  }
end

-- ── Thread: analisa após boot ───────────────────────────────────────────────
if core.add_thread then
  core.add_thread(function()
    coroutine.yield(3.0)  -- Aguarda todos os templates carregarem
    analyze_and_dump()
  end)
end

-- ── Comando CLI: analyze-keymap-forensic ────────────────────────────────────
command.add(nil, {
  ["doxoade:analyze-keymap-forensic"] = function()
    local result = analyze_and_dump()
    if core.log then
      core.log(string.format("🔬 [KEYMAP-FORENSIC] Dados salvos em: %s", result.file))
    end
  end,
})

-- Atalho para análise sob demanda
keymap.add({
  ["ctrl+alt+shift+m"] = "doxoade:analyze-keymap-forensic",
}, true)

if core.log then
  core.log("🔬 [KEYMAP-FORENSIC] Tracker V1.0 ativo. Saída: " .. forensic_file)
end

-- ── Comando: scan-all-keymaps ──────────────────────────────────────────────
command.add(nil, {
  ["doxoade:scan-all-keymaps"] = function()
    local template_dir = USERDIR .. sep .. ".doxoade" .. sep .. "test_deploy" .. sep .. "template"
    local all_keys = {}
    
    -- Tenta abrir o diretório de templates (test)
    local finfo = system.get_file_info(template_dir)
    if not finfo or finfo.type ~= "dir" then
      -- Fallback: usa o próprio diretório atual do projeto
      template_dir = "doxoade" .. sep .. "commands" .. sep .. "lite_xl_systems" .. sep .. "template"
      finfo = system.get_file_info(template_dir)
      if not finfo then
        if core.log then core.log("🔬 [KEYMAP-FORENSIC] Diretório de templates não encontrado.") end
        return
      end
    end
    
    local items = system.list_dir(template_dir) or {}
    local lua_files = 0
    for _, fname in ipairs(items) do
      if fname:match("%.lua$") then
        lua_files = lua_files + 1
        local fpath = template_dir .. sep .. fname
        local f = io.open(fpath, "r")
        if f then
          local content = f:read("*a") or ""
          f:close()
          -- Regex para capturar keymaps: ["ctrl+x"] = "cmd" e ["ctrl+x"] = { ... }
          for key, cmd in content:gmatch('%[%s*["\']([^"\']+)["\']%s*%]%s*=%s*["\']([^"\']+)["\']') do
            if key:find("ctrl") or key:find("alt") or key:find("shift") or key:find("^f%d") then
              all_keys[key] = all_keys[key] or {}
              table.insert(all_keys[key], { cmd = cmd, source = fname })
            end
          end
        end
      end
    end
    
    -- Imprime resultado
    if core.log then
      core.log(string.format("🔬 [KEYMAP-FORENSIC] Scan estático: %d arquivos .lua, %d teclas",
        lua_files, (function() local n = 0; for _ in pairs(all_keys) do n = n + 1 end; return n end)()))
      
      -- Ordena e imprime
      local sorted_keys = {}
      for k in pairs(all_keys) do table.insert(sorted_keys, k) end
      table.sort(sorted_keys)
      
      for _, key in ipairs(sorted_keys) do
        local cmds = all_keys[key]
        if #cmds >= 2 then
          core.log(string.format("  🔴 [%s] → %d registros:", key, #cmds))
          for _, c in ipairs(cmds) do
            core.log(string.format("      • %s ← %s", c.cmd, c.source))
          end
        end
      end
    end
  end,
})

-- keymap.add({
--   ["ctrl+alt+shift+n"] = "doxoade:scan-all-keymaps",
-- }, true)

-- ── Detector: teclas com modificadores "fantasma" ───────────────────────────
if core.add_thread then
  core.add_thread(function()
    coroutine.yield(10.0)  -- Aguarda 10s de uso
    
    if core.log then
      core.log("🔬 [KEYMAP-FORENSIC] Verificando teclas com Alt fantasma...")
    end
    
    -- Lê o session_log.txt para detectar padrões suspeitos
    local session_path = user_dir .. sep .. "session_log.txt"
    local f = io.open(session_path, "r")
    if not f then return end
    
    local alt_ctrl_count = 0
    local ctrl_l_count = 0
    local alt_ctrl_l_count = 0
    local lines = {}
    
    for line in f:lines() do
      table.insert(lines, line)
      if line:find("key=l mods=ctrl+$") then
        ctrl_l_count = ctrl_l_count + 1
      end
      if line:find("key=l mods=alt%+ctrl%+") then
        alt_ctrl_l_count = alt_ctrl_l_count + 1
      end
      if line:find("key=left alt mods=ctrl%+") or line:find("key=left alt mods=alt%+ctrl%+") then
        alt_ctrl_count = alt_ctrl_count + 1
      end
    end
    f:close()
    
    if core.log then
      core.log(string.format("🔬 [KEYMAP-FORENSIC] Estatísticas:"))
      core.log(string.format("  • Ctrl+L puro (correto): %d", ctrl_l_count))
      core.log(string.format("  • Alt+Ctrl+L (fantasma): %d", alt_ctrl_l_count))
      core.log(string.format("  • Alt+Ctrl (spam): %d", alt_ctrl_count))
      
      if alt_ctrl_l_count > 0 then
        core.log("  🔴 ALERTA: Alt+Ctrl+L detectado! SDL2 está injetando Alt nos eventos.")
        core.log("  💡 Diagnóstico: Sticky Keys ou AltGr do teclado ABNT2.")
      elseif ctrl_l_count > 0 then
        core.log("  ✅ Ctrl+L puro detectado. Keymap está correto.")
      end
    end
  end)
end

command.add(nil, {
  ["doxoade:diagnose-alt-phantom"] = function()
    if core.log then
      core.log("🔬 [ALT-PHANTOM] Iniciando diagnóstico...")
      core.log("  Pressione Ctrl+L 3 vezes (uma por segundo)...")
    end
    
    local baseline = {
      ctrl_l = 0,
      alt_ctrl_l = 0,
      alt_spam = 0,
    }
    
    -- Monitora 5 segundos
    local start = os.clock()
    local _orig_on_event = core.on_event
    core.on_event = function(event_type, ...)
      if event_type == "keypressed" and (os.clock() - start) < 5.0 then
        local args = { ... }
        local key = tostring(args[1] or "?")
        local mods = ""
        if keymap and keymap.modkeys then
          for mod, active in pairs(keymap.modkeys) do
            if active then mods = mods .. mod .. "+" end
          end
        end
        
        if key == "l" then
          if mods == "ctrl+" then
            baseline.ctrl_l = baseline.ctrl_l + 1
          elseif mods == "alt+ctrl+" then
            baseline.alt_ctrl_l = baseline.alt_ctrl_l + 1
          end
        elseif key == "left alt" then
          if mods:find("ctrl") then
            baseline.alt_spam = baseline.alt_spam + 1
          end
        end
      end
      return _orig_on_event(event_type, ...)
    end
    
    if core.add_thread then
      core.add_thread(function()
        coroutine.yield(5.5)
        core.on_event = _orig_on_event
        if core.log then
          core.log("🔬 [ALT-PHANTOM] Resultado:")
          core.log(string.format("  • Ctrl+L puro (correto): %d", baseline.ctrl_l))
          core.log(string.format("  • Alt+Ctrl+L (fantasma): %d", baseline.alt_ctrl_l))
          core.log(string.format("  • Alt+Ctrl spam: %d", baseline.alt_spam))
          
          if baseline.alt_ctrl_l > 0 or baseline.alt_spam > 5 then
            core.log("  🔴 DIAGNÓSTICO: SDL2 está injetando Alt. Causa: Sticky Keys OU teclado ABNT2 AltGr.")
          else
            core.log("  ✅ DIAGNÓSTICO: Nenhum Alt fantasma detectado!")
          end
        end
      end)
    end
  end,
})

keymap.add({
  ["ctrl+alt+shift+a"] = "doxoade:diagnose-alt-phantom",
}, true)
