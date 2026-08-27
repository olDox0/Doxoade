-- doxoade/commands/lite_xl_systems/template/12_ui_forge.lua
-- =============================================================================
-- 12. UI FORGE (CLEAN / CANONICAL)
-- =============================================================================

local core = require "core"
local command = require "core.command"
local keymap = require "core.keymap"

local UIForge = {
  commands = {},
  keymaps = {},
  panels = {},
}

local function table_count(tbl)
  local n = 0

  for _ in pairs(tbl or {}) do
    n = n + 1
  end

  return n
end

function UIForge.register_command(name, handler)
  UIForge.commands[name] = handler
end

function UIForge.register_keymap(keys, command_name)
  UIForge.keymaps[keys] = command_name
end

function UIForge.register_panel(spec)
  table.insert(UIForge.panels, spec)
end

function UIForge.build_all()
  local cmd_table = {}

  for name, handler in pairs(UIForge.commands) do
    cmd_table[name] = handler
  end

  if next(cmd_table) then
    command.add(nil, cmd_table)
  end

  if next(UIForge.keymaps) then
    keymap.add(UIForge.keymaps)
  end

  core.log(string.format(
    "UIForge: %d painéis, %d comandos, %d atalhos registrados.",
    table_count(UIForge.panels),
    table_count(UIForge.commands),
    table_count(UIForge.keymaps)
  ))
end

-- =====================================================
-- 🧂 QUOTING E ABERTURA SEGURA EM FILE MANAGER
-- =====================================================
local function quote_windows_path(path)
  return '"' .. tostring(path):gsub('"', '""') .. '"'
end

local function quote_posix_path(path)
  return "'" .. tostring(path):gsub("'", "'\\''") .. "'"
end

local function open_in_file_manager(path)
  if system.show_in_file_manager then
    system.show_in_file_manager(path)
    return
  end

  if PLATFORM == "Windows" then
    system.exec("explorer.exe /select," .. quote_windows_path(path))
  else
    local dir_path = tostring(path):match("^(.*)[/\\]") or path
    system.exec("xdg-open " .. quote_posix_path(dir_path))
  end
end

-- =====================================================
-- COMANDOS DE CAMINHO / EXPLORER
-- =====================================================
UIForge.register_command("doxoade:tab-copy-filename", function()
  local view = core.active_view

  if view and view.doc and view.doc.filename then
    local fname = view.doc.filename:match("[/\\]([^/\\]+)$") or view.doc.filename

    if system.set_clipboard then
      system.set_clipboard(fname)
      core.log("Copiado (Nome): " .. fname)
    end
  elseif view and view.get_name then
    local fname = view:get_name()

    if system.set_clipboard then
      system.set_clipboard(fname)
      core.log("Copiado (Nome): " .. fname)
    end
  end
end)

UIForge.register_command("doxoade:tab-copy-relative-path", function()
  local view = core.active_view

  if not view or not view.doc or not view.doc.filename then
    core.error("Nenhum arquivo ativo para copiar endereço.")
    return
  end

  local abs_path = (system.absolute_path(view.doc.filename) or view.doc.filename):gsub("\\", "/")
  local rel = abs_path

  if core.project_directories then
    for _, proj in ipairs(core.project_directories) do
      local ppath = tostring(
        type(proj) == "table" and (proj.path or proj.name) or proj or ""
      ):gsub("\\", "/")

      if ppath ~= "" and abs_path:sub(1, #ppath) == ppath then
        rel = abs_path:sub(#ppath + 1):gsub("^/", "")
        break
      end
    end
  end

  rel = rel:gsub("/", PATHSEP or "\\")

  if system.set_clipboard then
    system.set_clipboard(rel)
    core.log("Copiado (Proj. Address): " .. rel)
  end
end)

UIForge.register_command("doxoade:tab-copy-full-path", function()
  local view = core.active_view

  if not view or not view.doc or not view.doc.filename then
    core.error("Nenhum arquivo ativo para copiar endereço.")
    return
  end

  local abs_path = system.absolute_path(view.doc.filename) or view.doc.filename
  abs_path = abs_path:gsub("[/\\]", PATHSEP or "\\")

  if system.set_clipboard then
    system.set_clipboard(abs_path)
    core.log("Copiado (Total Address): " .. abs_path)
  end
end)

UIForge.register_command("doxoade:tab-open-in-explorer", function()
  local view = core.active_view

  if not view or not view.doc or not view.doc.filename then
    core.error("Nenhum arquivo ativo.")
    return
  end

  local abs_path = system.absolute_path(view.doc.filename) or view.doc.filename
  local dir_path = abs_path:match("^(.*)[/\\]") or abs_path

  open_in_file_manager(abs_path)

  core.log("Explorer aberto em: " .. dir_path)
end)

-- =====================================================
-- KEYMAPS
-- =====================================================
-- Recomendação: deixar os atalhos principais no 07_keymaps_and_help.lua.
-- Portanto, o UIForge não deve registrar atalhos duplicados.
--
-- Se quiser um atalho dedicado aqui, use algo não conflitante:
-- UIForge.register_keymap("ctrl+alt+shift+c", "doxoade:tab-copy-full-path")

UIForge.build_all()
