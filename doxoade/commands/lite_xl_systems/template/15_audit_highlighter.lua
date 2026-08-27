-- doxoade/commands/lite_xl_systems/template/15_audit_highlighter.lua
-- =============================================================================
-- 15. IN-EDITOR AUDIT HIGHLIGHTER (ISOLAMENTO POR ABA, TOOLTIPS & AUTO-CLEAR)
-- =============================================================================
-- local core = require "core"
local config = require "core.config"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local Doc = require "core.doc"
local DocView = require "core.docview"
local RootView = require "core.rootview"

-- 🛡️ Polyfill de Renderização
local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local function draw_rect_safe(x, y, w, h, color)
  if rencache and rencache.draw_rect then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

local function draw_text_safe(font, text, x, y, color)
  if rencache and rencache.draw_text then
    rencache.draw_text(font, text, x, y, color)
  elseif native_renderer and native_renderer.draw_text then
    native_renderer.draw_text(font, text, x, y, color)
  end
end

-- ═══════════════════════════════════════════════════════════
-- MATRIZ DE CORES SEMÂNTICAS
-- =============================================================
local CATEGORY_THEMES = {
  STYLE           = { color = { 168, 85, 247, 255 },  tint = { 168, 85, 247, 18 },  name = "Estilo",       symbol = "🟣" },
  UNUSED          = { color = { 234, 179, 8, 255 },   tint = { 234, 179, 8, 18 },   name = "Não Utilizado", symbol = "🟡" },
  COMPLEXITY      = { color = { 249, 115, 22, 255 },  tint = { 249, 115, 22, 18 },  name = "Complexidade", symbol = "⚠️" },
  SYNTAX          = { color = { 239, 68, 68, 255 },   tint = { 239, 68, 68, 25 },   name = "Sintaxe",      symbol = "🔴" },
  CRITICAL        = { color = { 220, 38, 38, 255 },   tint = { 220, 38, 38, 28 },   name = "Crítico",      symbol = "💥" },
  SECURITY        = { color = { 59, 130, 246, 255 },  tint = { 59, 130, 246, 22 },  name = "Segurança",    symbol = "🛡️" },
  ["QA-REMINDER"] = { color = { 6, 182, 212, 255 },   tint = { 6, 182, 212, 18 },   name = "QA/Todo",      symbol = "🔵" },
  DEFAULT         = { color = { 156, 163, 175, 255 }, tint = { 156, 163, 175, 18 }, name = "Aviso",        symbol = "⚪" },
}

local function get_finding_theme(finding)
  if not finding then return CATEGORY_THEMES.DEFAULT end
  local cat = tostring(finding.category or ""):upper()
  local sev = tostring(finding.severity or ""):upper()

  if sev == "CRITICAL" or cat == "SYNTAX" or cat == "SYNTAX_INDENT" or cat == "INDENT" then
    return CATEGORY_THEMES.SYNTAX
  elseif cat == "SECURITY" then
    return CATEGORY_THEMES.SECURITY
  elseif cat == "COMPLEXITY" then
    return CATEGORY_THEMES.COMPLEXITY
  elseif cat == "STYLE" or cat == "UNUSED" then
    return CATEGORY_THEMES.STYLE
  elseif cat == "QA-REMINDER" or cat == "TODO" then
    return CATEGORY_THEMES["QA-REMINDER"]
  end

  return CATEGORY_THEMES[cat] or (sev == "ERROR" and CATEGORY_THEMES.SYNTAX) or CATEGORY_THEMES.DEFAULT
end

-- ═══════════════════════════════════════════════════════════
-- ESTADO E CONTRATO DA PONTE
-- =============================================================
local AuditState = {
  active_file = nil,
  relative_file = nil,
  findings_by_line = {},
  summary = { errors = 0, warnings = 0, info = 0, total = 0 },
  last_mtime = 0,
}

local HoverTooltip = {
  visible = false,
  text = "",
  sub_text = "",
  theme = CATEGORY_THEMES.DEFAULT,
  x = 0,
  y = 0,
  w = 200,
  h = 40,
}

-- 🎯 Validador: Garante que os marcadores só apareçam no arquivo auditado
local function is_target_doc(doc)
  if not doc or not doc.filename or not AuditState.active_file then
    return false
  end
  local doc_path = tostring(system.absolute_path(doc.filename) or doc.filename):gsub("\\", "/"):lower()
  local target_abs = tostring(AuditState.active_file):gsub("\\", "/"):lower()
  local target_rel = tostring(AuditState.relative_file or ""):gsub("\\", "/"):lower()

  if doc_path == target_abs then
    return true
  end
  if target_rel ~= "" and doc_path:sub(-#target_rel) == target_rel then
    return true
  end
  return false
end

-- 🔄 Carregador Nativo do check_bridge.lua
local function load_audit_bridge()
  if not core.project_directories or #core.project_directories == 0 then return end
  local p = core.project_directories[1]
  local root = tostring(type(p) == "table" and (p.path or p.name) or p)
  local bridge_path = root .. PATHSEP .. ".doxoade" .. PATHSEP .. "check_bridge.lua"

  local info = system.get_file_info(bridge_path)
  if not info or info.mtime == AuditState.last_mtime then return end

  AuditState.last_mtime = info.mtime

  -- 🛡️ Política de confiança (Ma'at): nenhum código de projeto
  -- não confiável é executado dentro do Lite XL.
  local trust_marker = root .. PATHSEP .. ".doxoade" .. PATHSEP .. "TRUSTED"
  if not system.get_file_info(trust_marker) then
    return
  end
  
  local ok, data = pcall(dofile, bridge_path)
  if ok and type(data) == "table" and data.findings then
    AuditState.findings_by_line = {}
    AuditState.active_file = data.active_file
    AuditState.relative_file = data.relative_file
    AuditState.summary = data.summary or { errors = 0, warnings = 0, info = 0, total = 0 }

    rawset(_G, "_DOXOADE_AUDIT_SUMMARY", AuditState.summary)
    rawset(_G, "_DOXOADE_AUDIT_CHECKED", true)

    for _, f in ipairs(data.findings) do
      if f.line and f.line > 0 then
        AuditState.findings_by_line[f.line] = f
      end
    end
    core.redraw = true
  end
end

core.add_thread(function()
  while true do
    pcall(load_audit_bridge)
    coroutine.yield(0.3)
  end
end)

-- 🧹 Remoção Dinâmica do Erro ao Alterar/Digitar na Linha
local original_doc_insert = Doc.insert
function Doc:insert(line, col, text)
  if is_target_doc(self) and AuditState.findings_by_line[line] then
    AuditState.findings_by_line[line] = nil
    core.redraw = true
  end
  return original_doc_insert(self, line, col, text)
end

local original_doc_remove = Doc.remove
function Doc:remove(line1, col1, line2, col2)
  if is_target_doc(self) then
    for l = line1, line2 do
      if AuditState.findings_by_line[l] then
        AuditState.findings_by_line[l] = nil
        core.redraw = true
      end
    end
  end
  return original_doc_remove(self, line1, col1, line2, col2)
end

-- ═══════════════════════════════════════════════════════════
-- 1. RENDERIZADOR NO GUTTER (ISOLADO POR ABA)
-- =============================================================
local original_draw_line_gutter = DocView.draw_line_gutter
function DocView:draw_line_gutter(line, x, y, width)
  local res = original_draw_line_gutter and original_draw_line_gutter(self, line, x, y, width) or 0

  pcall(function()
    if not is_target_doc(self.doc) then return end

    local finding = AuditState.findings_by_line[line]
    if finding then
      local theme = get_finding_theme(finding)
      local dot_size = 6
      local line_h = self.get_line_height and self:get_line_height() or 16
      local dot_x = x + 3
      local dot_y = y + (line_h - dot_size) / 2

      draw_rect_safe(dot_x, dot_y, dot_size, dot_size, theme.color)
    end
  end)

  return res
end

-- ═══════════════════════════════════════════════════════════
-- 2. RENDERIZADOR NO CORPO DA LINHA (ISOLADO POR ABA)
-- =============================================================
local original_draw_line_body = DocView.draw_line_body
function DocView:draw_line_body(line, x, y)
  pcall(function()
    if not is_target_doc(self.doc) then return end

    local finding = AuditState.findings_by_line[line]
    if finding then
      local theme = get_finding_theme(finding)
      local line_h = self.get_line_height and self:get_line_height() or 16

      draw_rect_safe(x, y, self.size.x, line_h, theme.tint)
      draw_rect_safe(x, y, 2, line_h, theme.color)
    end
  end)

  return original_draw_line_body(self, line, x, y)
end

-- ═══════════════════════════════════════════════════════════
-- 3. TOOLTIP NO HOVER DO MOUSE (GUTTER & LINHA)
-- =============================================================
local original_docview_mouse_moved = DocView.on_mouse_moved
function DocView:on_mouse_moved(x, y, dx, dy)
  pcall(function()
    if is_target_doc(self.doc) then
      local line_h = self:get_line_height()
      local line = math.floor((y - self.position.y + self.scroll.y) / line_h) + 1
      local finding = AuditState.findings_by_line[line]

      if finding then
        local theme = get_finding_theme(finding)
        local font = style.font or style.code_font
        local main_text = string.format("%s [%s] %s", theme.symbol, theme.name:upper(), finding.message)
        local sub = finding.suggestion and finding.suggestion ~= "" and ("🔧 " .. finding.suggestion) or ""

        local max_w = font:get_width(main_text)
        if sub ~= "" then
          local sw = font:get_width(sub)
          if sw > max_w then max_w = sw end
        end

        HoverTooltip.text = main_text
        HoverTooltip.sub_text = sub
        HoverTooltip.theme = theme
        HoverTooltip.x = math.min(x + 12, (core.root_view.size.x or 1200) - max_w - 24)
        HoverTooltip.y = y + 16
        HoverTooltip.w = max_w + 20
        HoverTooltip.h = (sub ~= "" and 38 or 22)
        HoverTooltip.visible = true
        core.redraw = true
        return
      end
    end
    if HoverTooltip.visible then
      HoverTooltip.visible = false
      core.redraw = true
    end
  end)
  return original_docview_mouse_moved(self, x, y, dx, dy)
end

local original_rootview_draw = RootView.draw
function RootView:draw()
  original_rootview_draw(self)

  if HoverTooltip.visible and HoverTooltip.text ~= "" then
    local hx = HoverTooltip.x
    local hy = HoverTooltip.y
    local hw = HoverTooltip.w
    local hh = HoverTooltip.h
    local theme = HoverTooltip.theme
    local font = style.font or style.code_font

    -- Sombra, Fundo Piano Black e Borda Temática
    draw_rect_safe(hx - 1, hy - 1, hw + 2, hh + 2, { 10, 10, 10, 220 })
    draw_rect_safe(hx, hy, hw, hh, { 25, 23, 26, 250 })
    draw_rect_safe(hx, hy, 3, hh, theme.color)

    draw_text_safe(font, HoverTooltip.text, hx + 8, hy + 4, { 255, 255, 255, 255 })
    if HoverTooltip.sub_text ~= "" then
      draw_text_safe(font, HoverTooltip.sub_text, hx + 8, hy + 20, theme.color)
    end
  end
end

-- ═══════════════════════════════════════════════════════════
-- 4. NOVO CTRL + H INTUITIVO EM 2 ETAPAS & NAVEGAÇÃO F2
-- =============================================================
command.add("core.docview", {
  -- 🔍 Novo Ctrl + H Interativo: "O que mudar" -> "Para o que mudar"
  ["doxoade:interactive-find-replace"] = function()
    local doc = core.active_view and core.active_view.doc
    if not doc then return end

    local initial_query = ""
    if doc:has_selection() then
      local l1, c1, l2, c2 = doc:get_selection(true)
      if l1 == l2 then
        initial_query = doc:get_text(l1, c1, l2, c2)
      end
    end

    core.command_view:enter("1/2 Localizar Texto (O que mudar):", {
      text = initial_query,
      submit = function(find_text)
        if not find_text or find_text == "" then return end

        core.command_view:enter(string.format("2/2 Substituir '%s' por (Para o que mudar):", find_text), {
          submit = function(replace_text)
            replace_text = replace_text or ""
            local count = 0

            for i = 1, #doc.lines do
              local line = doc.lines[i]
              if line:find(find_text, 1, true) then
                local new_line, n = line:gsub(find_text:gsub("[%(%)%.%%%+%-%*%?%[%]%^%$]", "%%%1"), replace_text)
                if n > 0 then
                  doc.lines[i] = new_line
                  count = count + n
                end
              end
            end

            if count > 0 then
              doc.modified_lines = doc.modified_lines or {}
              for i = 1, #doc.lines do doc.modified_lines[i] = true end
              core.log(string.format("✔ Substituídas %d ocorrências de '%s' por '%s'", count, find_text, replace_text))
              core.redraw = true
            else
              core.log(string.format("Nenhuma ocorrência de '%s' encontrada.", find_text))
            end
          end
        })
      end
    })
  end,

  -- Navegação entre incidentes (F2 / Shift + F2)
  ["doxoade:next-audit-incident"] = function()
    local doc = core.active_view and core.active_view.doc
    if not doc or not is_target_doc(doc) then
      core.log("Nenhum incidente de auditoria no arquivo ativo.")
      return
    end
    local cur_line = doc:get_selection(true)
    local target_line = nil

    for ln = cur_line + 1, #doc.lines do
      if AuditState.findings_by_line[ln] then
        target_line = ln
        break
      end
    end
    if not target_line then
      for ln = 1, cur_line do
        if AuditState.findings_by_line[ln] then
          target_line = ln
          break
        end
      end
    end

    if target_line then
      doc:set_selection(target_line, 1)
      core.active_view:scroll_to_line(target_line, true)
      local f = AuditState.findings_by_line[target_line]
      local theme = get_finding_theme(f)
      core.log(string.format("%s [%s] %s (Linha %d)", theme.symbol, theme.name:upper(), f.message, target_line))
    end
  end,

  ["doxoade:prev-audit-incident"] = function()
    local doc = core.active_view and core.active_view.doc
    if not doc or not is_target_doc(doc) then return end
    local cur_line = doc:get_selection(true)
    local target_line = nil

    for ln = cur_line - 1, 1, -1 do
      if AuditState.findings_by_line[ln] then
        target_line = ln
        break
      end
    end
    if not target_line then
      for ln = #doc.lines, cur_line, -1 do
        if AuditState.findings_by_line[ln] then
          target_line = ln
          break
        end
      end
    end

    if target_line then
      doc:set_selection(target_line, 1)
      core.active_view:scroll_to_line(target_line, true)
      local f = AuditState.findings_by_line[target_line]
      local theme = get_finding_theme(f)
      core.log(string.format("%s [%s] %s (Linha %d)", theme.symbol, theme.name:upper(), f.message, target_line))
    end
  end,

  ["doxoade:trigger-active-check"] = function()
    local view = core.active_view
    if not view or not view.doc or not view.doc.filename then
      core.error("Nenhum arquivo ativo para auditar.")
      return
    end
    local abs_path = system.absolute_path(view.doc.filename) or view.doc.filename
    core.log("⚖️ Tribunal de Ma'at: Executando check em " .. tostring(abs_path))
    if PLATFORM == "Windows" then
      system.exec(string.format('doxoade check "%s"', abs_path:gsub('/', '\\')))
    else
      system.exec(string.format('doxoade check "%s"', abs_path))
    end
  end,
})

keymap.add {
  ["f2"]         = "doxoade:next-audit-incident",
  ["shift+f2"]   = "doxoade:prev-audit-incident",
  ["ctrl+h"]     = "doxoade:interactive-find-replace",
  ["ctrl+alt+k"] = "doxoade:trigger-active-check",
}

core.log("=== SOVEREIGN BOOT OK ===")
