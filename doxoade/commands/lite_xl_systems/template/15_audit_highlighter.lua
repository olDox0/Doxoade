-- doxoade/commands/lite_xl_systems/template/15_audit_highlighter.lua
--[[
  ⚖️ DOXOADE AUDIT HIGHLIGHTER V3 — ALTA VISIBILIDADE & HOVER NO GUTTER
  - Destaque marcante de linha (Barra sólida de 4px + Faixa translúcida vívida).
  - Marcador de Gutter expandido (8px) e detecção de hover sobre o número da linha.
  - Cronômetro dinâmico de carregamento no rodapé (sem timeouts prematuros).
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = require "core"
local config = require "core.config"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local Doc = require "core.doc"
local DocView = require "core.docview"
local RootView = require "core.rootview"

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

-- =============================================================================
-- 🎨 PALETAS DE ALTA VISIBILIDADE (Cores Vivas e Tints Fortes)
-- =============================================================================
local CATEGORY_THEMES = {
  CRITICAL        = { color = { 239, 68, 68, 255 },   tint = { 239, 68, 68, 55 },   name = "CRÍTICO",      symbol = "🔴" },
  SYNTAX          = { color = { 248, 113, 113, 255 }, tint = { 239, 68, 68, 50 },   name = "SINTAXE",      symbol = "🔴" },
  SECURITY        = { color = { 59, 130, 246, 255 },  tint = { 59, 130, 246, 45 },  name = "SEGURANÇA",    symbol = "🛡️" },
  COMPLEXITY      = { color = { 249, 115, 22, 255 },  tint = { 249, 115, 22, 45 },  name = "COMPLEXO",     symbol = "⚠️" },
  WARNING         = { color = { 234, 179, 8, 255 },   tint = { 234, 179, 8, 45 },   name = "AVISO",        symbol = "🟡" },
  UNUSED          = { color = { 234, 179, 8, 255 },   tint = { 234, 179, 8, 40 },   name = "NÃO USADO",    symbol = "🟡" },
  STYLE           = { color = { 168, 85, 247, 255 },  tint = { 168, 85, 247, 40 },  name = "ESTILO/PEP8",  symbol = "🟣" },
  DEFAULT         = { color = { 156, 163, 175, 255 }, tint = { 156, 163, 175, 35 }, name = "NOTA",        symbol = "⚪" },
}

local function get_finding_theme(finding)
  if not finding then return CATEGORY_THEMES.DEFAULT end
  local cat = tostring(finding.category or ""):upper()
  local sev = tostring(finding.severity or ""):upper()

  if sev == "CRITICAL" or cat == "SYNTAX" or cat == "INDENT" then
    return CATEGORY_THEMES.CRITICAL
  elseif cat == "SECURITY" then
    return CATEGORY_THEMES.SECURITY
  elseif cat == "COMPLEXITY" then
    return CATEGORY_THEMES.COMPLEXITY
  elseif cat == "STYLE" and finding.message and finding.message:find("unused") then
    return CATEGORY_THEMES.UNUSED
  elseif cat == "STYLE" then
    return CATEGORY_THEMES.STYLE
  elseif sev == "WARNING" then
    return CATEGORY_THEMES.WARNING
  end
  return CATEGORY_THEMES[cat] or CATEGORY_THEMES.DEFAULT
end

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
  x = 0, y = 0, w = 200, h = 40,
}

local function clear_table_in_place(t)
  if not t then return end
  for k in pairs(t) do t[k] = nil end
end

local function normalize_path_clean(p)
  if not p then return "" end
  return tostring(system.absolute_path(p) or p):gsub("\\", "/"):lower():gsub("/+$", "")
end

local function is_target_doc(doc)
  if not doc or not doc.filename or not AuditState.active_file then
    return false
  end
  local doc_path = normalize_path_clean(doc.filename)
  local target_abs = normalize_path_clean(AuditState.active_file)
  local target_rel = normalize_path_clean(AuditState.relative_file)

  if doc_path == target_abs then return true end
  if target_rel ~= "" and doc_path:sub(-#target_rel) == target_rel then return true end
  local doc_name = doc_path:match("[^/]+$")
  local target_name = target_abs:match("[^/]+$")
  return doc_name and target_name and (doc_name == target_name)
end

local function find_project_root_for_file(file_path)
  if not file_path or file_path == "" then return nil end
  local cur = normalize_path_clean(file_path)
  local finfo = system.get_file_info(cur)
  if finfo and finfo.type == "file" then cur = cur:match("^(.*)/") or cur end

  for _ = 1, 15 do
    if not cur or cur == "" or cur:find("^[a-z]:$") or cur == "/" then break end
    local bridge_file = cur .. "/.doxoade/check_bridge.lua"
    if system.get_file_info(bridge_file) or system.get_file_info(cur .. "/pyproject.toml") or system.get_file_info(cur .. "/.git") then
      return cur
    end
    local parent = cur:match("^(.*)/")
    if not parent or parent == cur then break end
    cur = parent
  end
  return core.project_dir or "."
end

local function load_audit_bridge()
  local view = core.active_view
  local doc = view and view.doc
  local target_file = doc and doc.filename
  if not target_file or target_file == "" then return false end

  local root = find_project_root_for_file(target_file) or core.project_dir or "."
  local bridge_path = root .. "/.doxoade/check_bridge.lua"
  local info = system.get_file_info(bridge_path)

  if not info or info.mtime == AuditState.last_mtime then return false end
  AuditState.last_mtime = info.mtime

  local ok, data = pcall(dofile, bridge_path)
  if ok and type(data) == "table" and data.findings then
    clear_table_in_place(AuditState.findings_by_line)
    AuditState.active_file = data.active_file
    AuditState.relative_file = data.relative_file
    AuditState.summary = data.summary or { errors = 0, warnings = 0, info = 0, total = 0 }
    rawset(_G, "_DOXOADE_AUDIT_SUMMARY", AuditState.summary)
    rawset(_G, "_DOXOADE_AUDIT_CHECKED", true)

    local count = 0
    for _, f in ipairs(data.findings) do
      if f.line and f.line > 0 then
        AuditState.findings_by_line[f.line] = f
        count = count + 1
      end
    end

    core.redraw = true
    return true
  end
  return false
end

-- =============================================================================
-- 🔴 RENDERIZAÇÃO NO GUTTER (Bolinha Marcante de 8px + Tooltip no Número)
-- =============================================================================
local original_draw_line_gutter = DocView.draw_line_gutter
function DocView:draw_line_gutter(line, x, y, width)
  local res = original_draw_line_gutter and original_draw_line_gutter(self, line, x, y, width) or 0
  pcall(function()
    if not is_target_doc(self.doc) then return end
    local finding = AuditState.findings_by_line[line]
    if finding then
      local theme = get_finding_theme(finding)
      local dot_size = 8
      local line_h = self.get_line_height and self:get_line_height() or 16
      local dot_x = x + 4
      local dot_y = y + math.floor((line_h - dot_size) / 2)
      
      -- Bolinha sólida com borda sutil
      draw_rect_safe(dot_x, dot_y, dot_size, dot_size, theme.color)
      draw_rect_safe(dot_x, dot_y, dot_size, 1, { 255, 255, 255, 120 })
    end
  end)
  return res
end

-- =============================================================================
-- 🎨 RENDERIZAÇÃO NO CORPO DA LINHA (Barra Sólida de 4px + Faixa Vívida)
-- =============================================================================
local original_draw_line_body = DocView.draw_line_body
function DocView:draw_line_body(line, x, y)
  pcall(function()
    if not is_target_doc(self.doc) then return end
    local finding = AuditState.findings_by_line[line]
    if finding then
      local theme = get_finding_theme(finding)
      local line_h = self.get_line_height and self:get_line_height() or 16

      -- 1. Faixa translúcida vívida em toda a largura da linha
      draw_rect_safe(x, y, self.size.x, line_h, theme.tint)

      -- 2. Barra sólida de 4px na lateral esquerda da linha
      draw_rect_safe(x, y, 4, line_h, theme.color)

      -- 3. Linha inferior sutil para delimitar o erro
      draw_rect_safe(x, y + line_h - 1, self.size.x, 1, { theme.color[1], theme.color[2], theme.color[3], 60 })
    end
  end)
  return original_draw_line_body(self, line, x, y)
end

-- =============================================================================
-- 💬 MOUSE HOVER: Abre Tooltip ao passar no Gutter OU na Linha
-- =============================================================================
local original_docview_mouse_moved = DocView.on_mouse_moved
function DocView:on_mouse_moved(x, y, dx, dy)
  pcall(function()
    if is_target_doc(self.doc) then
      local line_h = self:get_line_height()
      local line = math.floor((y - self.position.y + self.scroll.y) / line_h) + 1
      local finding = AuditState.findings_by_line[line]

      -- Ativa se o mouse estiver sobre o Gutter OU sobre o texto da linha com erro
      if finding then
        local theme = get_finding_theme(finding)
        local font = style.font or style.code_font
        local main_text = string.format("%s [%s] %s", theme.symbol, theme.name, finding.message)
        local sub = (finding.suggestion and finding.suggestion ~= "") and ("💡 " .. finding.suggestion) or ""

        local max_w = font:get_width(main_text)
        if sub ~= "" then
          local sw = font:get_width(sub)
          if sw > max_w then max_w = sw end
        end

        local screen_w = core.root_view.size.x or 1200
        HoverTooltip.text = main_text
        HoverTooltip.sub_text = sub
        HoverTooltip.theme = theme
        HoverTooltip.x = math.min(math.max(x + 10, self.position.x + 30), screen_w - max_w - 24)
        HoverTooltip.y = y + 18
        HoverTooltip.w = max_w + 20
        HoverTooltip.h = (sub ~= "" and 42 or 26)
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

-- Renderizador do Card Tooltip Flutuante
local original_rootview_draw = RootView.draw
function RootView:draw()
  original_rootview_draw(self)
  if HoverTooltip.visible and HoverTooltip.text ~= "" then
    local hx, hy, hw, hh = HoverTooltip.x, HoverTooltip.y, HoverTooltip.w, HoverTooltip.h
    local theme = HoverTooltip.theme or CATEGORY_THEMES.DEFAULT
    local font = style.font or style.code_font

    -- Sombra, Fundo e Borda Colorida do Card
    draw_rect_safe(hx - 1, hy - 1, hw + 2, hh + 2, { 10, 10, 10, 220 })
    draw_rect_safe(hx, hy, hw, hh, { 22, 22, 26, 250 })
    draw_rect_safe(hx, hy, 4, hh, theme.color)

    -- Mensagem do Erro
    draw_text_safe(font, HoverTooltip.text, hx + 10, hy + 4, theme.color)
    -- Sugestão de Correção
    if HoverTooltip.sub_text ~= "" then
      draw_text_safe(font, HoverTooltip.sub_text, hx + 10, hy + 22, { 220, 220, 220, 255 })
    end
  end
end

-- =============================================================================
-- ⏱️ DISPARADOR ASSÍNCRONO COM CRONÔMETRO DINÂMICO
-- =============================================================================
local function detect_audit_python()
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local py_anchor = user_dir .. sep .. ".doxoade" .. sep .. "python_path.txt"
  local finfo = system and system.get_file_info and system.get_file_info(py_anchor)
  if finfo and finfo.type == "file" then
    local f = io.open(py_anchor, "r")
    if f then
      local l = f:read("*l") or ""
      f:close()
      l = l:gsub("[\r\n]", ""):gsub("^%s*", ""):gsub("%s*$", "")
      if l ~= "" and system.get_file_info(l) then return l:gsub("/", "\\") end
    end
  end
  if core.project_directories and #core.project_directories > 0 then
    local p0 = core.project_directories[1]
    local p_str = tostring(type(p0) == "table" and (p0.path or p0.name) or p0)
    local venv_py = p_str .. sep .. "venv" .. sep .. "Scripts" .. sep .. "python.exe"
    if system.get_file_info(venv_py) then return venv_py:gsub("/", "\\") end
  end
  return "python"
end


-- ═══════════════════════════════════════════════════════════
-- 4. NOVO CTRL + H INTUITIVO EM 2 ETAPAS & NAVEGAÇÃO F2
-- ═══════════════════════════════════════════════════════════
command.add("core.docview", {
  -- 🔍 Novo Ctrl + H Interativo: "O que mudar" -> "Para o que mudar"
  ["doxoade:interactive-find-replace"] = function()
    local doc = core.active_view and core.active_view.doc
    if not doc then return end

    local default_find = ""
    if doc and doc.has_selection and doc:has_selection() then
      local l1, c1, l2, c2 = doc:get_selection(true)
      if l1 == l2 then
        default_find = doc:get_text(l1, c1, l2, c2)
      end
    end

    core.command_view:enter("1/2 Localizar Texto (O que mudar):", {
      text = default_find,
      submit = function(find_text)
        if not find_text or find_text == "" then return end
        if find_text:find("\n") then
          core.error("Busca com quebra de linha não suportada neste modo.")
          return
        end

        local prompt_label = string.format("2/2 Substituir '%s' por:", find_text)
        core.command_view:enter(prompt_label, {
          submit = function(replace_text)
            replace_text = replace_text or ""
            local count = 0
            local escaped_pat = find_text:gsub("[%(%)%.%%%+%-%*%?%[%]%^%$]", "%%%1")
            for line_idx = 1, #doc.lines do
              local line_text = doc.lines[line_idx]
              local s, e = line_text:find(escaped_pat)
              if s then
                local new_text = line_text:gsub(escaped_pat, replace_text)
                doc.lines[line_idx] = new_text
                count = count + 1
              end
            end

            if count > 0 then
              doc.session_modified = doc.session_modified or {}
              core.log(string.format("✔ Substituídas %d ocorrência(s).", count))
              core.redraw = true
            else
              core.log("Nenhuma ocorrência encontrada.")
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
    local doc = view and view.doc
    if not doc or not doc.filename then
      core.log("⚠️ [CHECK] Abra um arquivo para auditar com Ma'at.")
      return
    end

    local file_path = doc.filename:gsub("\\", "/")
    local short_name = file_path:match("[^/]+$") or file_path

    local user_dir = USERDIR or "."
    local sep = PATHSEP or "/"
    local diag_dir = user_dir .. sep .. ".doxoade" .. sep .. "diagnostics"
    if system and system.mkdir then pcall(system.mkdir, diag_dir) end

    local out_log = diag_dir .. sep .. "check_exec_output.txt"
    pcall(os.remove, out_log)

    local py_exe = detect_audit_python()
    local full_cmd = string.format('"%s" -m doxoade check "%s" -fp --no-cache > "%s" 2>&1', py_exe, file_path, out_log)

    -- Inicia o cronômetro visual
    rawset(_G, "_DOXOADE_AUDIT_START_TIME", os.clock())
    rawset(_G, "_DOXOADE_AUDIT_RUNNING", true)
    core.redraw = true
    core.log("⏳ [MA'AT] Auditoria em andamento: " .. short_name .. "...")

    core.add_thread(function()
      local t0 = os.clock()
      pcall(system.exec, full_cmd)

      -- Teto generoso de até 60s com atualização dinâmica do cronômetro a cada 0.5s
      local finished = false
      for _ = 1, 120 do
        coroutine.yield(0.5)
        core.redraw = true -- Atualiza os segundos no rodapé a cada 0.5s!

        local f_chk = io.open(out_log, "r")
        if f_chk then
          local content = f_chk:read("*a") or ""
          f_chk:close()

          if content:find("%[check%]") or content:find("Traceback") or content:find("CRASH") then
            coroutine.yield(0.2)
            if load_audit_bridge() then
              finished = true
              break
            end
          end
        end
      end

      rawset(_G, "_DOXOADE_AUDIT_RUNNING", false)
      rawset(_G, "_DOXOADE_AUDIT_START_TIME", nil)
      local elapsed = math.floor((os.clock() - t0) * 10) / 10

      if finished then
        local count = 0
        for _ in pairs(AuditState.findings_by_line) do count = count + 1 end
        core.log(string.format("✔ [MA'AT] Auditoria concluída em %.1fs (%d linhas destacadas).", elapsed, count))
      else
        core.log(string.format("⚠️ [MA'AT] Tempo limite excedido (%.1fs).", elapsed))
      end

      core.redraw = true
    end)
  end,

  -- 2. 🎯 INJETOR DE PROVA VISUAL PRÉ-SETADO (Comprova na hora o Gutter e Linhas)
  ["doxoade:check-canary-test"] = function()
    local view = core.active_view
    local doc = view and view.doc
    if not doc or not doc.filename then
      core.log("⚠️ Abra um arquivo para testar os marcadores visuais.")
      return
    end

    clear_table_in_place(AuditState.findings_by_line)
    AuditState.active_file = doc.filename
    AuditState.relative_file = doc.filename:match("[^/\\]+$") or doc.filename
    AuditState.summary = { errors = 1, warnings = 1, info = 1, total = 3 }
    rawset(_G, "_DOXOADE_AUDIT_SUMMARY", AuditState.summary)
    rawset(_G, "_DOXOADE_AUDIT_CHECKED", true)

    -- Injeta 3 marcadores pré-setados para homologação visual imediata
    AuditState.findings_by_line[2] = {
      line = 2,
      severity = "CRITICAL",
      category = "SYNTAX",
      message = "🔴 [CANÁRIO] Erro Crítico Simulado (Gutter Vermelho)",
      suggestion = "Exemplo de sugestão de correção automática do Ma'at"
    }

    AuditState.findings_by_line[4] = {
      line = 4,
      severity = "WARNING",
      category = "UNUSED",
      message = "🟡 [CANÁRIO] Aviso de Variável Não Utilizada (Gutter Amarelo)",
      suggestion = "Remova a variável ou utilize-a no escopo"
    }

    AuditState.findings_by_line[6] = {
      line = 6,
      severity = "INFO",
      category = "STYLE",
      message = "🟣 [CANÁRIO] Aviso de Estilo/PEP8 (Gutter Roxo)",
      suggestion = "Ajuste o espaçamento de operadores"
    }

    core.redraw = true
    core.log("🎨 [CANÁRIO MA'AT] 3 marcadores pré-setados ativos: L-2 (Vermelho), L-4 (Amarelo), L-6 (Roxo).")
  end,
})

keymap.add {
  ["f2"]               = "doxoade:next-audit-incident",
  ["shift+f2"]         = "doxoade:prev-audit-incident",
  ["ctrl+h"]           = "doxoade:interactive-find-replace",
  ["ctrl+alt+k"]       = "doxoade:trigger-active-check",
  ["ctrl+alt+shift+k"] = "doxoade:check-canary-test",
}

core.log("=== SOVEREIGN BOOT OK ===")
