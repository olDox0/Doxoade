-- doxoade/commands/lite_xl_systems/template/12_ui_forge.lua
-- =============================================================================
-- 12. UI FORGE (CLEAN / CANONICAL)
-- =============================================================================

local core = require "core"
local command = require "core.command"
local keymap = require "core.keymap"
local style = require "core.style"
local View = require "core.view"
local config = require "core.config"

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

-- =============================================================================
-- 🧱 SOVEREIGN DOCKED VIEW — CLASSE BASE REUTILIZÁVEL PARA INTERFACES
-- =============================================================================

local SovereignDockedView = View:extend()

function SovereignDockedView:new(config)
  SovereignDockedView.super.new(self)
  config = config or {}

  self.title = config.title or "Painel Soberano"
  self.height = config.height or 85
  self.visible = false
  self.inputs = config.inputs or {} -- Lista de { label = "...", text = "...", id = "..." }
  self.buttons = config.buttons or {} -- Lista de { label = "...", action = fn, key = "..." }
  self.active_input_idx = 1
  self.hovered_btn_idx = nil
  self.previous_active_view = nil
end

function SovereignDockedView:get_target_height()
  return self.visible and self.height or 0
end

function SovereignDockedView:show()
  if not self.visible then
    self.visible = true
    self.previous_active_view = core.active_view
    core.set_active_view(self)
    core.redraw = true
  end
end

function SovereignDockedView:hide()
  if self.visible then
    self.visible = false
    if self.previous_active_view then
      core.set_active_view(self.previous_active_view)
    end
    core.redraw = true
  end
end

function SovereignDockedView:toggle()
  if self.visible then self:hide() else self:show() end
end

-- Captura de Digitação Direta no Campo Ativo
function SovereignDockedView:on_text_input(text)
  if not self.visible or #self.inputs == 0 then return end
  local input = self.inputs[self.active_input_idx]
  if input then
    input.text = (input.text or "") .. text
    core.redraw = true
  end
end

-- Renderização Padrão de Alta Performance
function SovereignDockedView:draw()
  if not self.visible then return end
  self:draw_background(style.background2)

  local x, y = self.position.x, self.position.y
  local w, h = self.size.x, self.size.y
  local font = style.font

  -- 1. Borda Superior Esmeralda
  renderer.draw_rect(x, y, w, 1, style.divider or { 76, 69, 82, 255 })
  renderer.draw_rect(x, y, w, 2, style.accent or { 38, 188, 95, 255 })

  -- 2. Título do Painel
  renderer.draw_text(font, self.title, x + 14, y + 8, style.accent)

  -- 3. Renderização Dinâmica dos Inputs
  local input_y = y + 32
  for i, input in ipairs(self.inputs) do
    local is_active = (i == self.active_input_idx)
    local border_col = is_active and style.accent or style.divider
    local field_x = x + 120 + ((i - 1) * 240)

    renderer.draw_text(font, input.label .. ":", field_x - 100, input_y + 3, style.text)
    renderer.draw_rect(field_x, input_y, 220, 24, style.background3)
    renderer.draw_rect(field_x, input_y, 220, 1, border_col)
    renderer.draw_rect(field_x, input_y + 23, 220, 1, border_col)

    local txt = (input.text or "") .. (is_active and "_" or "")
    renderer.draw_text(font, txt, field_x + 6, input_y + 4, style.text)
  end

  -- 4. Renderização Dinâmica dos Botões
  local btn_x = x + w - 16
  for i = #self.buttons, 1, -1 do
    local btn = self.buttons[i]
    local btn_w = font:get_width(btn.label) + 20
    btn_x = btn_x - btn_w - 8
    btn._x, btn._w = btn_x, btn_w
    btn._y, btn._h = input_y, 24

    local is_hov = (self.hovered_btn_idx == i)
    local bg = is_hov and (style.accent or { 38, 188, 95, 255 }) or style.background3
    local fg = is_hov and { 0, 0, 0, 255 } or style.text

    renderer.draw_rect(btn_x, input_y, btn_w, 24, bg)
    renderer.draw_text(font, btn.label, btn_x + 10, input_y + 4, fg)
  end
end

-- =====================================================
-- KEYMAPS
-- =====================================================
-- Recomendação: deixar os atalhos principais no 07_keymaps_and_help.lua.
-- Portanto, o UIForge não deve registrar atalhos duplicados.
--
-- Se quiser um atalho dedicado aqui, use algo não conflitante:
-- UIForge.register_keymap("ctrl+alt+shift+c", "doxoade:tab-copy-full-path")

UIForge.build_all()
