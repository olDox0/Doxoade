-- doxoade/commands/lite_xl_systems/template/100_keymap_manager.lua
--[[
  🏛️ DOXOADE SOVEREIGN KEYMAP MASTER (V51.0 — Matriz Centralizada)
  ----------------------------------------------------------------------------
  ÚNICO ponto de autoridade para mapeamento de atalhos em todo o Doxly.
  Todos os outros templates apenas registram comandos via command.add.
  Aqui são resolvidas todas as colisões e garantida a paridade Notepad++.
]]

local core = require "core"
local keymap = require "core.keymap"
local command = require "core.command"

if rawget(_G, "_DOXOADE_KEYMAP_MASTER_APPLIED") then return end
rawset(_G, "_DOXOADE_KEYMAP_MASTER_APPLIED", true)

-- 1. Unbind prévio de teclas críticas para evitar herança de plugins nativos
pcall(function()
  if keymap.unbind then
    local keys_to_clean = {
      "ctrl+l", "ctrl+shift+l", "ctrl+alt+d", "ctrl+alt+shift+d", "ctrl+alt+x",
      "f1", "f2", "shift+f2", "f3", "shift+f3", "f4", "shift+f4", "f5", "f6",
      "ctrl+alt+e", "ctrl+shift+e", "ctrl+tab", "ctrl+shift+tab",
      "ctrl+alt+shift+k", "ctrl+alt+shift+n"
    }
    for _, k in ipairs(keys_to_clean) do
      keymap.unbind(k)
    end
  end
end)

-- 2. Tabela Mestre Canônica (Zero Conflitos)
local SOVEREIGN_KEYMAP = {
  -- ── Split & Layout (Flip & Painéis) ────────────────────────────────────────
  ["ctrl+l"]              = "doxoade:toggle-split-orientation",
  ["ctrl+shift+l"]        = "doxoade:swap-split-panels",
  ["ctrl+alt+d"]          = "doxoade:move-tab-to-opposite-panel",
  ["ctrl+alt+shift+d"]    = "doxoade:move-following-tabs-to-opposite",
  ["alt+shift+x"]          = "root:close-following-tabs",
  ["f6"]                  = "doxoade:focus-opposite-panel",
  ["alt+d"]               = "root:split-right",
  ["alt+shift+d"]         = "root:split-down",
  ["ctrl+alt+="]          = "doxoade:equalize-splits",
  ["ctrl+alt+0"]          = "doxoade:equalize-splits",

  -- ── Edição Básica & Paridade Notepad++ ────────────────────────────────────
  ["ctrl+n"]              = "doxoade:new-doc",
  ["ctrl+o"]              = "doxoade:open-file",
  ["ctrl+s"]              = "doc:save",
  ["ctrl+shift+s"]        = "doc:save-all",
  ["ctrl+w"]              = "root:close",
  ["ctrl+d"]              = "doc:duplicate-lines",
  ["ctrl+q"]              = "doc:toggle-line-comments",
  ["ctrl+g"]              = "doc:go-to-line",
  ["ctrl+f"]              = "find-replace:find",
  ["ctrl+h"]              = "doxoade:interactive-find-replace",
  ["f3"]                  = "find-replace:repeat-find",
  ["shift+f3"]            = "find-replace:previous-find",
  ["ctrl+tab"]            = "root:switch-to-next-tab",
  ["ctrl+shift+tab"]      = "root:switch-to-previous-tab",

  -- ── Ferramentas & Docks ───────────────────────────────────────────────────
  ["ctrl+`"]              = "doxoade:toggle-bottom-shelf",
  ["ctrl+j"]              = "doxoade:toggle-bottom-shelf",
  ["ctrl+alt+t"]          = "doxoade:terminal-launch-real",
  ["ctrl+alt+shift+t"]    = "doxoade:terminal-launch-admin",
  ["ctrl+shift+t"]        = "doxoade:terminal-new-tab",
  ["ctrl+shift+e"]        = "doxoade:toggle-open-editors-dock",
--  ["ctrl+alt+e"]          = "doxoade:tab-copy-filename",
  ["ctrl+alt+c"]          = "doxoade:copy-path-menu",
  ["ctrl+shift+c"]        = "doxoade:tab-copy-relative-path",
  ["alt+f"]               = "doxoade:contextual-search",
  ["ctrl+alt+shift+f"]    = "doxoade:global-project-search",
  ["f4"]                  = "doxoade:search-next-result",
  ["shift+f4"]            = "doxoade:search-prev-result",

  -- ── Consultoria, Notas & Ajuda ────────────────────────────────────────────
  ["f1"]                  = "doxoade:consult-selection-or-word",
  ["ctrl+shift+/"]        = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+r"]              = "doxoade:reload-shared-notes",
  ["ctrl+alt+n"]          = "doxoade:create-file-interactive",
  ["ctrl+alt+shift+n"]    = "doxoade:note-hub-menu",
  ["ctrl+alt+a"]          = "doxoade:open-agenda-view",
  ["ctrl+alt+p"]          = "doxoade:open-pot-in-right-panel",
  ["ctrl+,"]              = "doxoade:open-init-lua",
  ["ctrl+shift+u"]        = "doxoade:open-user-settings",

  -- ── Auditoria & Diagnóstico ───────────────────────────────────────────────
  ["f2"]                  = "doxoade:next-audit-incident",
  ["shift+f2"]            = "doxoade:prev-audit-incident",
  ["ctrl+alt+k"]          = "doxoade:trigger-active-check",
  ["ctrl+alt+shift+k"]    = "doxoade:diagnose-live",

  -- ── Imagem & Diff ─────────────────────────────────────────────────────────
  ["ctrl+shift+v"]        = "doxoade:paste-image-from-clipboard",
  ["alt+s"]               = "doxoade:sort-selected-lines-alpha",
  ["ctrl+alt+j"]          = "doxoade:align-assignments-and-comments",
  ["ctrl+alt+shift+j"]    = "doxoade:compare-selection-with-opposite-panel",
  ["ctrl+alt+shift+-"]    = "doxoade:clear-diff-highlights",
  ["alt+t"]               = "doxoade:toggle-toolbar-layout",
}

-- 3. Injeção atômica com sobrescrita forçada
keymap.add(SOVEREIGN_KEYMAP, true)

if core.log then
  local total = 0
  for _ in pairs(SOVEREIGN_KEYMAP) do total = total + 1 end
  core.log(string.format("🏛️ [KEYMAP MASTER] %d atalhos soberanos consolidados sem colisões.", total))
end
