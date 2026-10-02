-- doxoade/commands/lite_xl_systems/template/08_pot_panel.lua
--[[
  Módulo de Painel Dumppot, Markdown Dinâmico e Consult Studio V3.8.
  - Scratchpad persistente integrado (.doxoade/dumppot.txt).
  - ConsultSearchView: Cards de busca, hover suave e scrollbar nativa.
  - ConsultDocReaderView: Leitor Markdown com Scrollbar isolada (sem disparar seleção),
    Seleção por Mouse (Ctrl+C), Tracking Global de Cores e Modo Raw para códigos Python.
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core    = require "core"
local common  = require "core.common"
local View    = require "core.view"
local DocView = require "core.docview"
local command = require "core.command"
local keymap  = require "core.keymap"
local style   = require "core.style"

local system = rawget(_G, "system") or (pcall(require, "system") and require("system") or nil)
local PLATFORM = rawget(_G, "PLATFORM") or (package.config:sub(1, 1) == "\\" and "Windows" or "Linux")

local user_dir = USERDIR or "."
local sep = PATHSEP or "/"
local doxoade_cfg_dir = user_dir .. sep .. ".doxoade"
pcall(function() if system and system.mkdir then system.mkdir(doxoade_cfg_dir) end end)

local dumppot_file = doxoade_cfg_dir .. sep .. "dumppot.txt"
local cheat_sheet_file = doxoade_cfg_dir .. sep .. "cheat_sheet.txt"
local log_path = user_dir .. sep .. "session_log.txt"

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local function draw_rect_safe(x, y, w, h, color)
  if not color or type(color) ~= "table" then color = { 128, 128, 128, 255 } end
  if rencache and rencache.draw_rect then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

local function draw_text_safe(font, text, x, y, color)
  if not font or not text or text == "" then return end
  if type(color) ~= "table" then color = { 255, 255, 255, 255 } end
  if rencache and rencache.draw_text then
    rencache.draw_text(font, text, x, y, color)
  elseif native_renderer and native_renderer.draw_text then
    native_renderer.draw_text(font, text, x, y, color)
  end
end

-- =============================================================================
-- 1. SINTAXE DUMPPOT MARKDOWN
-- =============================================================================
pcall(function()
  local syntax = require "core.syntax"
  syntax.add {
    name = "Dumppot Markdown",
    files = { "dumppot%.txt$", "cheat_sheet%.txt$", "%.doxpot$", "%.pot$", "%.md$", "%[Docs%]" },
    comment = "#",
    patterns = {
      { pattern = { "```%s*lua", "```" },        type = "string",   syntax = ".lua" },
      { pattern = { "```%s*python", "```" },     type = "string",   syntax = ".py" },
      { pattern = { "```%s*py", "```" },         type = "string",   syntax = ".py" },
      { pattern = { "```%s*c", "```" },          type = "string",   syntax = ".c" },
      { pattern = { "```%s*cpp", "```" },        type = "string",   syntax = ".cpp" },
      { pattern = { "```%s*json", "```" },       type = "string",   syntax = ".json" },
      { pattern = { "```%s*diff", "```" },       type = "string",   syntax = ".diff" },
      { pattern = { "```", "```" },              type = "string" },
      { pattern = "^#+%s.*",                     type = "keyword" },
      { pattern = "`.-`",                        type = "keyword2" },
      { pattern = "%*%*.-%*%*",                  type = "keyword" },
      { pattern = "https?://%S+",                type = "operator" },
      { pattern = "^===+.*===+",                 type = "keyword" },
      { pattern = "^%-%-%-+.*",                  type = "comment" },
      { pattern = "^>%s.*",                      type = "string" },
    },
    symbols = {}
  }
end)

-- =============================================================================
-- 2. GESTÃO DO PAINEL DIREITO
-- =============================================================================
local function get_doc_leaves(n, list)
  list = list or {}
  if not n then return list end
  if n.type == "leaf" and not n.locked then
    table.insert(list, n)
  elseif n.type ~= "leaf" then
    get_doc_leaves(n.a, list)
    get_doc_leaves(n.b, list)
  end
  return list
end

local function get_or_create_right_panel()
  local leaves = get_doc_leaves(core.root_view.root_node)
  if #leaves >= 2 then
    return leaves[#leaves]
  elseif #leaves == 1 then
    return leaves[1]:split("right")
  end
  return core.root_view.root_node:get_primary_node()
end

local function open_in_right_panel(file_or_view, log_msg)
  local right_node = get_or_create_right_panel()
  local view = nil

  if type(file_or_view) == "string" then
    local doc = core.open_doc(file_or_view)
    if not doc then return nil end
    view = DocView(doc)
  elseif type(file_or_view) == "table" and file_or_view.doc then
    view = DocView(file_or_view)
  elseif type(file_or_view) == "table" and file_or_view.is then
    view = file_or_view
  end

  if not view then return nil end

  for _, v in ipairs(right_node.views or {}) do
    if v == view or (v.doc and view.doc and v.doc == view.doc) then
      right_node.active_view = v
      core.set_active_view(v)
      core.redraw = true
      return v
    end
  end

  if right_node.add_view then
    right_node:add_view(view)
  end
  core.set_active_view(view)
  if log_msg and core.log then core.log(log_msg) end
  core.redraw = true
  return view
end

local function get_doxoade_python_exe()
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"

  local candidates = {
    user_dir .. sep .. ".doxoade" .. sep .. "python_path.txt",
    user_dir .. sep .. "python_path.txt",
    user_dir .. sep .. ".." .. sep .. "python_path.txt",
    user_dir .. sep .. ".." .. sep .. ".doxoade" .. sep .. "python_path.txt",
    (os.getenv("USERPROFILE") or os.getenv("HOME") or ".") .. sep .. ".doxoade" .. sep .. "python_path.txt",
    (os.getenv("USERPROFILE") or os.getenv("HOME") or ".") .. sep .. "python_path.txt",
  }

  for _, py_anchor in ipairs(candidates) do
    local finfo = system and system.get_file_info and system.get_file_info(py_anchor)
    if finfo and finfo.type == "file" then
      local f = io.open(py_anchor, "r")
      if f then
        local line = f:read("*l") or ""
        f:close()
        line = line:gsub("[\r\n]", ""):match("^%s*(.-)%s*$")
        if line ~= "" and system.get_file_info(line) then
          return line:gsub("/", "\\")
        end
      end
    end
  end

  -- Fallback de detecção pelo diretório de trabalho do Windows
  local is_win = (PLATFORM == "Windows" or package.config:sub(1, 1) == "\\")
  local cwd = system.absolute_path(".") or "."
  local venv_py = cwd .. sep .. "venv" .. sep .. (is_win and "Scripts\\python.exe" or "bin/python")
  if system and system.get_file_info and system.get_file_info(venv_py) then
    return venv_py:gsub("/", "\\")
  end

  return "python"
end

-- =============================================================================
-- 3. CONSULT SEARCH VIEW
-- =============================================================================
local ConsultSearchView = View:extend()

function ConsultSearchView:new(query, search_data)
  ConsultSearchView.super.new(self)
  self.scrollable = true
  self.query = query or ""
  self.results = (search_data and search_data.results) or {}
  self.total = (search_data and search_data.total) or #self.results
  self.hovered_idx = nil
  self.selected_idx = 1
  self.header_h = 42
  self.card_h = 76
  self.font_title = style.font or style.code_font
  self.font_sub = style.font or style.code_font
end

function ConsultSearchView:get_name()
  return string.format("🔍 Docs: %s (%d)", self.query, self.total)
end

function ConsultSearchView:get_scrollable_size()
  return self.header_h + (#self.results * (self.card_h + 6)) + 30
end

function ConsultSearchView:draw()
  self:draw_background(style.background2 or { 24, 24, 28, 255 })
  local x, y, w, h = self.position.x, self.position.y, self.size.x, self.size.y
  local scroll_y = self.scroll.y or 0
  local scrollbar_w = style.scrollbar_size or 8

  -- Cabeçalho Fixo
  draw_rect_safe(x, y, w, self.header_h, style.background3 or { 32, 32, 38, 255 })
  draw_rect_safe(x, y + self.header_h - 1, w, 1, style.divider or { 60, 60, 70, 255 })
  draw_rect_safe(x, y, w, 2, style.accent or { 56, 189, 248, 255 })

  local header_text = string.format("🔍 Resultados para: %q — %d documento(s) offline", self.query, self.total)
  draw_text_safe(self.font_title, header_text, x + 14, y + 12, style.accent or { 56, 189, 248, 255 })

  if #self.results == 0 then
    draw_text_safe(self.font_sub, "Nenhum documento encontrado. Tente termos mais amplos.", x + 14, y + self.header_h + 20, style.dim)
    return
  end

  core.push_clip_rect(x, y + self.header_h, w - scrollbar_w - 2, h - self.header_h)
  local cur_y = y + self.header_h + 8 - scroll_y

  for i, item in ipairs(self.results) do
    if (cur_y + self.card_h) > y + self.header_h and cur_y < (y + h) then
      local is_hovered = (self.hovered_idx == i)
      local is_selected = (self.selected_idx == i)
      local card_x = x + 10
      local card_w = w - scrollbar_w - 24

      local bg_col = style.background or { 18, 18, 22, 255 }
      if is_selected then
        bg_col = { 35, 45, 60, 255 }
      elseif is_hovered then
        bg_col = style.background3 or { 32, 32, 38, 255 }
      end

      draw_rect_safe(card_x, cur_y, card_w, self.card_h, bg_col)
      draw_rect_safe(card_x, cur_y, card_w, 1, { 50, 50, 60, 255 })
      draw_rect_safe(card_x, cur_y + self.card_h - 1, card_w, 1, { 20, 20, 25, 255 })

      if is_selected or is_hovered then
        draw_rect_safe(card_x, cur_y, 3, self.card_h, style.accent or { 56, 189, 248, 255 })
      end

      local title_str = string.format("📄 %d. %s", i, item.title or "Sem título")
      draw_text_safe(self.font_title, title_str, card_x + 12, cur_y + 8, is_hovered and { 255, 255, 255, 255 } or (style.accent or { 56, 189, 248, 255 }))

      local path_str = "↳ " .. tostring(item.path or "")
      draw_text_safe(self.font_sub, path_str, card_x + 14, cur_y + 28, style.dim or { 140, 140, 150, 255 })

      local snip = tostring(item.snippet or ""):gsub("[\r\n]+", " ")
      if #snip > 110 then snip = snip:sub(1, 110) .. "..." end
      draw_text_safe(self.font_sub, snip, card_x + 14, cur_y + 48, { 200, 200, 210, 255 })

      item.rect = { x = card_x, y = cur_y, w = card_w, h = self.card_h }
    end
    cur_y = cur_y + self.card_h + 6
  end

  core.pop_clip_rect()

  self:draw_scrollbar()
end

function ConsultSearchView:on_mouse_moved(px, py, dx, dy)
  ConsultSearchView.super.on_mouse_moved(self, px, py, dx, dy)
  local prev = self.hovered_idx
  self.hovered_idx = nil
  for i, item in ipairs(self.results) do
    if item.rect and px >= item.rect.x and px <= (item.rect.x + item.rect.w) and
       py >= item.rect.y and py <= (item.rect.y + item.rect.h) then
      self.hovered_idx = i
      break
    end
  end
  if prev ~= self.hovered_idx then core.redraw = true end
end

function ConsultSearchView:on_mouse_pressed(button, px, py, clicks)
  local scrollbar_w = (style.scrollbar_size or 8) + 6
  if px >= (self.position.x + self.size.x - scrollbar_w) then
    return ConsultSearchView.super.on_mouse_pressed(self, button, px, py, clicks)
  end

  if button == "left" and self.hovered_idx then
    self.selected_idx = self.hovered_idx
    self:open_selected(self.hovered_idx)
    return true
  end
  return ConsultSearchView.super.on_mouse_pressed(self, button, px, py, clicks)
end

-- =============================================================================
-- 4. CONSULT DOC READER VIEW (Com Isolamento de Scroll, Tracking de Cores & Raw)
-- =============================================================================
local ConsultDocReaderView = View:extend()

function ConsultDocReaderView:new(title, doc_path, md_lines, parent_search_view)
  ConsultDocReaderView.super.new(self)
  self.scrollable = true
  self.doc_title = title or "Documentação"
  self.doc_path = doc_path or ""
  self.lines_formatted = md_lines or {}
  self.parent_search_view = parent_search_view
  self.header_h = 38
  self.line_h = 19
  self.hovered_back = false
  self.hovered_raw_btn = false
  self.hovered_copy_btn = false
  self.raw_mode = false
  self.lines_raw = self:generate_raw_lines(self.lines_formatted)

  self.is_selecting = false
  self.sel_start_line = nil
  self.sel_end_line = nil
end

function ConsultDocReaderView:generate_raw_lines(source_lines)
  local raw_lines = {}
  local in_code = false
  for _, line in ipairs(source_lines) do
    local text = tostring(line or "")
    if text:find("^```") then
      in_code = not in_code
      table.insert(raw_lines, text)
    elseif in_code then
      if text:find("^>>> ") then
        table.insert(raw_lines, text:sub(5))
      elseif text:find("^%.%.%. ") then
        table.insert(raw_lines, text:sub(5))
      elseif text:find("^>>>") then
        table.insert(raw_lines, text:sub(4))
      elseif text:find("^%.%.%.") then
        table.insert(raw_lines, text:sub(4))
      else
        table.insert(raw_lines, "# ↳ " .. text)
      end
    else
      table.insert(raw_lines, text)
    end
  end
  return raw_lines
end

function ConsultDocReaderView:get_active_lines()
  return self.raw_mode and self.lines_raw or self.lines_formatted
end

function ConsultDocReaderView:get_name()
  return "📖 " .. (self.doc_title:sub(1, 24))
end

function ConsultDocReaderView:get_scrollable_size()
  local active = self:get_active_lines()
  return self.header_h + (#active * self.line_h) + 60
end

function ConsultDocReaderView:copy_selection_to_clipboard()
  if not self.sel_start_line or not self.sel_end_line then
    local active = self:get_active_lines()
    local code_lines = {}
    local in_code = false
    for _, l in ipairs(active) do
      if l:find("^```") then
        in_code = not in_code
      elseif in_code then
        table.insert(code_lines, l)
      end
    end
    if #code_lines > 0 then
      system.set_clipboard(table.concat(code_lines, "\n"))
      if core.log then core.log("✔ Códigos do documento copiados!") end
    end
    return
  end

  local active = self:get_active_lines()
  local s = math.min(self.sel_start_line, self.sel_end_line)
  local e = math.max(self.sel_start_line, self.sel_end_line)
  local copied = {}
  for i = s, math.min(e, #active) do
    table.insert(copied, active[i] or "")
  end
  system.set_clipboard(table.concat(copied, "\n"))
  if core.log then core.log(string.format("✔ %d linha(s) copiada(s)!", #copied)) end
end

function ConsultDocReaderView:draw()
  self:draw_background(style.background2 or { 20, 20, 24, 255 })
  local x, y, w, h = self.position.x, self.position.y, self.size.x, self.size.y
  local scroll_y = self.scroll.y or 0
  local scrollbar_w = style.scrollbar_size or 8
  local font = style.code_font or style.font

  -- 1. Barra de Ações Superior
  draw_rect_safe(x, y, w, self.header_h, style.background3 or { 30, 30, 36, 255 })
  draw_rect_safe(x, y + self.header_h - 1, w, 1, style.divider or { 60, 60, 70, 255 })
  draw_rect_safe(x, y, w, 2, { 34, 197, 94, 255 })

  local back_w = 145
  local back_rect = { x = x + 8, y = y + 6, w = back_w, h = 26 }
  self.back_rect = back_rect
  draw_rect_safe(back_rect.x, back_rect.y, back_rect.w, back_rect.h, self.hovered_back and { 50, 60, 75, 255 } or { 40, 40, 48, 255 })
  draw_text_safe(font, "⬅ Voltar à Busca", back_rect.x + 10, back_rect.y + 5, self.hovered_back and { 255, 255, 255, 255 } or style.accent)

  local raw_w = 150
  local raw_x = back_rect.x + back_w + 8
  local raw_rect = { x = raw_x, y = y + 6, w = raw_w, h = 26 }
  self.raw_btn_rect = raw_rect
  local raw_bg = self.raw_mode and { 34, 197, 94, 200 } or (self.hovered_raw_btn and { 50, 60, 75, 255 } or { 40, 40, 48, 255 })
  local raw_fg = self.raw_mode and { 0, 0, 0, 255 } or (self.hovered_raw_btn and { 255, 255, 255, 255 } or { 200, 200, 210, 255 })
  draw_rect_safe(raw_rect.x, raw_rect.y, raw_rect.w, raw_rect.h, raw_bg)
  draw_text_safe(font, self.raw_mode and "⚡ Modo Raw: ATIVO" or "⚡ Modo Raw: OFF", raw_rect.x + 10, raw_rect.y + 5, raw_fg)

  local copy_w = 90
  local copy_x = raw_x + raw_w + 8
  local copy_rect = { x = copy_x, y = y + 6, w = copy_w, h = 26 }
  self.copy_btn_rect = copy_rect
  draw_rect_safe(copy_rect.x, copy_rect.y, copy_rect.w, copy_rect.h, self.hovered_copy_btn and { 50, 60, 75, 255 } or { 40, 40, 48, 255 })
  draw_text_safe(font, "📋 Copiar", copy_rect.x + 10, copy_rect.y + 5, self.hovered_copy_btn and { 255, 255, 255, 255 } or style.dim)

  local path_label = "📄 " .. self.doc_path
  draw_text_safe(font, path_label, copy_x + copy_w + 14, y + 10, style.dim)

  -- 2. Renderização do Conteúdo com Tracking de Cores Blindado
  core.push_clip_rect(x, y + self.header_h, w - scrollbar_w - 2, h - self.header_h)
  local cur_y = y + self.header_h + 10 - scroll_y
  local active = self:get_active_lines()

  local s_sel = self.sel_start_line and self.sel_end_line and math.min(self.sel_start_line, self.sel_end_line)
  local e_sel = self.sel_start_line and self.sel_end_line and math.max(self.sel_start_line, self.sel_end_line)

  -- O tracking de in_code_block roda LINEARMENTE sobre todas as linhas para NUNCA inverter cores no scroll
  local in_code_block = false

  for line_idx, line in ipairs(active) do
    local text = tostring(line or "")
    local is_fence = text:find("^```")

    if is_fence then
      in_code_block = not in_code_block
    end

    -- Culling de viewport estritamente na chamada de desenho
    if (cur_y + self.line_h) > (y + self.header_h) and cur_y < (y + h) then
      if s_sel and e_sel and line_idx >= s_sel and line_idx <= e_sel then
        draw_rect_safe(x + 10, cur_y, w - scrollbar_w - 20, self.line_h, { 56, 189, 248, 70 })
      end

      if is_fence then
        draw_rect_safe(x + 14, cur_y + math.floor(self.line_h / 2), w - scrollbar_w - 28, 2, { 60, 60, 75, 255 })
      elseif in_code_block then
        draw_rect_safe(x + 14, cur_y, w - scrollbar_w - 28, self.line_h, { 14, 14, 18, 255 })
        draw_rect_safe(x + 14, cur_y, 2, self.line_h, self.raw_mode and { 34, 197, 94, 255 } or { 100, 100, 140, 255 })
        local code_color = text:find("^# ↳") and { 130, 140, 150, 255 } or { 230, 230, 140, 255 }
        draw_text_safe(font, text, x + 24, cur_y + 1, code_color)
      elseif text:find("^# ") then
        draw_rect_safe(x + 14, cur_y, w - scrollbar_w - 28, self.line_h + 4, { 30, 45, 60, 180 })
        draw_text_safe(font, text, x + 18, cur_y + 2, { 56, 189, 248, 255 })
      elseif text:find("^## ") then
        draw_text_safe(font, text, x + 18, cur_y + 1, { 34, 197, 94, 255 })
      elseif text:find("^### ") then
        draw_text_safe(font, text, x + 20, cur_y + 1, { 251, 191, 36, 255 })
      elseif text:find("^> ") then
        draw_rect_safe(x + 14, cur_y, 3, self.line_h, style.accent)
        draw_text_safe(font, text:sub(3), x + 24, cur_y + 1, style.dim)
      else
        draw_text_safe(font, text, x + 18, cur_y + 1, { 220, 220, 225, 255 })
      end
    end
    cur_y = cur_y + self.line_h
  end

  core.pop_clip_rect()

  -- 3. Renderiza Scrollbar Nativa
  self:draw_scrollbar()
end

function ConsultDocReaderView:on_mouse_moved(px, py, dx, dy)
  ConsultDocReaderView.super.on_mouse_moved(self, px, py, dx, dy)
  local prev_b = self.hovered_back
  local prev_r = self.hovered_raw_btn
  local prev_c = self.hovered_copy_btn

  self.hovered_back = false
  self.hovered_raw_btn = false
  self.hovered_copy_btn = false

  if self.back_rect and px >= self.back_rect.x and px <= (self.back_rect.x + self.back_rect.w) and
     py >= self.back_rect.y and py <= (self.back_rect.y + self.back_rect.h) then
    self.hovered_back = true
  end

  if self.raw_btn_rect and px >= self.raw_btn_rect.x and px <= (self.raw_btn_rect.x + self.raw_btn_rect.w) and
     py >= self.raw_btn_rect.y and py <= (self.raw_btn_rect.y + self.raw_btn_rect.h) then
    self.hovered_raw_btn = true
  end

  if self.copy_btn_rect and px >= self.copy_btn_rect.x and px <= (self.copy_btn_rect.x + self.copy_btn_rect.w) and
     py >= self.copy_btn_rect.y and py <= (self.copy_btn_rect.y + self.copy_btn_rect.h) then
    self.hovered_copy_btn = true
  end

  -- Atualiza seleção com o mouse apenas no conteúdo e fora do scrollbar
  local scrollbar_w = (style.scrollbar_size or 8) + 6
  if self.is_selecting and py > (self.position.y + self.header_h) and px < (self.position.x + self.size.x - scrollbar_w) then
    local line_idx = math.floor((py - self.position.y - self.header_h + self.scroll.y) / self.line_h) + 1
    self.sel_end_line = math.max(1, math.min(#self:get_active_lines(), line_idx))
    core.redraw = true
  end

  if prev_b ~= self.hovered_back or prev_r ~= self.hovered_raw_btn or prev_c ~= self.hovered_copy_btn then
    core.redraw = true
  end
end

function ConsultDocReaderView:on_mouse_pressed(button, px, py, clicks)
  local scrollbar_w = (style.scrollbar_size or 8) + 6
  -- Se clicou na calha ou botão da scrollbar, delega para a superclasse sem ativar seleção
  if px >= (self.position.x + self.size.x - scrollbar_w) then
    self.is_selecting = false
    return ConsultDocReaderView.super.on_mouse_pressed(self, button, px, py, clicks)
  end

  if button == "left" then
    if self.hovered_back and self.parent_search_view then
      open_in_right_panel(self.parent_search_view, "🔍 Retornado aos resultados da pesquisa.")
      return true
    end

    if self.hovered_raw_btn then
      self.raw_mode = not self.raw_mode
      if core.log then core.log(self.raw_mode and "⚡ Modo Raw ativado (código limpo sem '>>>')." or "📖 Modo formatado restaurado.") end
      core.redraw = true
      return true
    end

    if self.hovered_copy_btn then
      self:copy_selection_to_clipboard()
      return true
    end

    -- Inicia seleção de texto por clique
    if py > (self.position.y + self.header_h) then
      local line_idx = math.floor((py - self.position.y - self.header_h + self.scroll.y) / self.line_h) + 1
      self.is_selecting = true
      self.sel_start_line = math.max(1, math.min(#self:get_active_lines(), line_idx))
      self.sel_end_line = self.sel_start_line
      core.redraw = true
    end
  end

  return ConsultDocReaderView.super.on_mouse_pressed(self, button, px, py, clicks)
end

function ConsultDocReaderView:on_mouse_released(button, px, py)
  if button == "left" and self.is_selecting then
    self.is_selecting = false
  end
  return ConsultDocReaderView.super.on_mouse_released(self, button, px, py)
end

-- =============================================================================
-- 5. TRANSIÇÃO: ABERTURA DO DOCUMENTO NO LEITOR
-- =============================================================================
function ConsultSearchView:open_selected(idx)
  local item = self.results[idx]
  if not item or not item.path then return end

  local py_exe = get_doxoade_python_exe()
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local doxoade_dir = user_dir .. sep .. ".doxoade"
  
  ensure_dir(doxoade_dir)

  local out_md = doxoade_dir .. sep .. "consult_active_doc.md"
  local runner_py = doxoade_dir .. sep .. "run_read.py"
  local err_log = doxoade_dir .. sep .. "read_error.log"
  local target_path = item.path

  pcall(os.remove, out_md)
  pcall(os.remove, runner_py)
  pcall(os.remove, err_log)

  core.log(string.format("📄 [CONSULT READ] Solicitando leitura de: '%s' (%s)", tostring(item.title), target_path))
  core.log(string.format("🐍 [CONSULT READ] Interpretador: %s", py_exe))

  -- Script Python autônomo para extração instantânea do Markdown (HTML ou Docstring)
  local f_run = io.open(runner_py, "w")
  if f_run then
    f_run:write(string.format([[
import sys
from pathlib import Path

doc_path = %q
out_path = Path(%q)
err_path = Path(%q)
db_path = Path.home() / ".doxoade" / "consult_docs_fts5.db"

md_content = None

# 1. Tenta converter HTML indexado
if db_path.exists():
    try:
        from doxoade.commands.consult_systems.doc_indexer import DocIndexer
        indexer = DocIndexer(db_path)
        md_content = indexer.read_doc_as_markdown(doc_path)
    except Exception as e:
        err_path.write_text(f"Erro no DocIndexer: {e}\n", encoding="utf-8")

# 2. Se não era HTML, tenta resolver como módulo Python do venv
if not md_content:
    try:
        from doxoade.commands.consult_systems.consult_engine import ConsultEngine
        engine = ConsultEngine()
        obj = engine.resolve_object(doc_path)
        if obj:
            doc_text = engine.get_docstring(obj)
            src_text = engine.get_source(obj)
            md_content = f"# 📖 `{doc_path}`\n\n```python\n{doc_text}\n```\n"
            if src_text:
                md_content += f"\n## 💻 Código Fonte\n\n```python\n{src_text}\n```\n"
    except Exception as e:
        err_path.write_text(f"Erro no ConsultEngine: {e}\n", encoding="utf-8")

if not md_content:
    md_content = f"# ⚠️ Não foi possível carregar `{doc_path}`\n\nDocumentação não localizada no índice local."

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(md_content, encoding="utf-8")
]], target_path, out_md, err_log))
    f_run:close()
  end

  local t0 = os.clock()
  system.exec(string.format('"%s" "%s"', py_exe, runner_py))

  local search_view = self
  core.add_thread(function()
    local found = false
    local final_size = 0
    for _ = 1, 60 do
      coroutine.yield(0.1)
      local info = system.get_file_info(out_md)
      if info and (info.size or 0) > 10 then
        found = true
        final_size = info.size
        break
      end
    end

    local elapsed_ms = math.floor((os.clock() - t0) * 1000)

    if not found then
      local err_msg = "Timeout ao gerar Markdown."
      local ef = io.open(err_log, "r")
      if ef then
        err_msg = ef:read("*a") or err_msg
        ef:close()
      end
      core.log(string.format("❌ [CONSULT READ] Falha após %dms: %s", elapsed_ms, err_msg:sub(1, 120)))
      return
    end

    local md_lines = {}
    local f = io.open(out_md, "r")
    if f then
      for line in f:lines() do
        table.insert(md_lines, line)
      end
      f:close()
    end

    core.log(string.format("✔ [CONSULT READ] Sucesso em %dms! (%d bytes | %d linhas)",
      elapsed_ms, final_size, #md_lines))

    local reader = ConsultDocReaderView(item.title, item.path, md_lines, search_view)
    open_in_right_panel(reader, string.format("📖 %s (%d linhas)", item.title:sub(1, 25), #md_lines))
  end)
end

-- =============================================================================
-- 6. ORQUESTRAÇÃO DE BUSCA E COMANDOS
-- =============================================================================
local function ensure_dir(dir_path)
  if not system or not system.mkdir then return end
  local clean = tostring(dir_path):gsub("/", "\\")
  local sub = ""
  for part in clean:gmatch("[^\\]+") do
    if sub == "" and part:find("^[a-zA-Z]:") then
      sub = part
    else
      sub = (sub == "" and "" or sub .. "\\") .. part
      pcall(system.mkdir, sub)
    end
  end
end

local function execute_docs_search_interactive(query)
  if not query or query:match("^%s*$") then return end
  local py_exe = get_doxoade_python_exe()
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local doxoade_dir = user_dir .. sep .. ".doxoade"

  ensure_dir(doxoade_dir)

  local out_file = doxoade_dir .. sep .. "consult_search.lua"
  local runner_py = doxoade_dir .. sep .. "run_consult.py"
  pcall(os.remove, out_file)
  pcall(os.remove, runner_py)

  core.log(string.format("🔍 Consultando docs: '%s'...", query))
  core.log(string.format("🐍 [CONSULT] Interpretador: %s", py_exe))

  -- Script Python autônomo: consulta diretamente o FTS5 e grava a tabela Lua em 50ms
  local f_run = io.open(runner_py, "w")
  if f_run then
    f_run:write(string.format([[
import re
from pathlib import Path

query = %q
out_path = Path(%q)
db_path = Path.home() / ".doxoade" / "consult_docs_fts5.db"

results = []
if db_path.exists():
    try:
        from doxoade.commands.consult_systems.doc_indexer import DocIndexer
        results = DocIndexer(db_path).search(query, limit=20)
    except Exception:
        results = []

if not results:
    try:
        from doxoade.commands.consult_systems.consult_engine import ConsultEngine
        mod_results = ConsultEngine().search_modules(query)
        results = [(m, m, desc or m) for m, desc in mod_results]
    except Exception:
        results = []

lines = [
    "return {",
    f'  query = "{query}",',
    f'  total = {len(results)},',
    '  results = {'
]

for path, title, snippet in results:
    clean_snip = re.sub(r'[\x02\x03]', '', str(snippet or title)).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')
    clean_title = str(title).replace('\\', '\\\\').replace('"', '\\"')
    clean_path = str(path).replace('\\', '\\\\').replace('"', '\\"')
    lines.append('    {')
    lines.append(f'      title = "{clean_title}",')
    lines.append(f'      path = "{clean_path}",')
    lines.append(f'      snippet = "{clean_snip}"')
    lines.append('    },')

lines.append('  }')
lines.append('}')

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text('\n'.join(lines), encoding="utf-8")
]], query, out_file))
    f_run:close()
  end

  -- Executa diretamente o script Python sem depender de Click ou console
  system.exec(string.format('"%s" "%s"', py_exe, runner_py))

  core.add_thread(function()
    local found = false
    for _ = 1, 50 do
      coroutine.yield(0.1)
      local info = system.get_file_info(out_file)
      if info and (info.size or 0) > 10 then
        found = true
        break
      end
    end

    if found then
      local ok, data = pcall(dofile, out_file)
      if ok and type(data) == "table" and data.results then
        open_in_right_panel(ConsultSearchView(query, data),
          string.format("✔ %d resultado(s) para %q.", data.total or #data.results, query))
        return
      end
    end

    core.log("⚠️ Nenhum resultado encontrado para a pesquisa.")
  end)
end

command.add(nil, {
  ["doxoade:open-pot-in-right-panel"] = function()
    open_in_right_panel(dumppot_file, "📋 Dumppot aberto no painel direito.")
  end,
  ["doxoade:open-init-lua"] = function()
    local init_file = user_dir .. sep .. "init.lua"
    open_in_right_panel(init_file, "⚡ init.lua aberto no painel direito.")
  end,
  ["doxoade:open-workspace-hub"] = function()
    open_in_right_panel(dumppot_file, "📂 Workspace Hub aberto.")
  end,
  ["doxoade:open-pantheon"] = function()
    local init_file = (USERDIR or ".") .. (PATHSEP or "/") .. "init.lua"
    local settings_file = (USERDIR or ".") .. (PATHSEP or "/") .. "user_settings.lua"
    open_in_right_panel(init_file, "⚡ init.lua aberto no Panteão.")
    open_in_right_panel(log_path, "📜 session_log.txt aberto no Panteão.")
    open_in_right_panel(dumppot_file, "📋 Dumppot aberto no Panteão.")
    open_in_right_panel(cheat_sheet_file, "📖 Cheat Sheet aberto no Panteão.")
    open_in_right_panel(settings_file, "⚙️ user_settings.lua aberto no Panteão.") -- ✅ CORRIGIDO
    core.log("🏛️ Panteão Soberano invocado. 5 abas de diagnóstico abertas à direita.")
  end,
  ["doxoade:open-log"] = function()
    open_in_right_panel(log_path, "📜 session_log.txt aberto.")
  end,
  ["doxoade:show-shortcuts-cheat-sheet"] = function()
    open_in_right_panel(cheat_sheet_file, "📖 Cheat Sheet aberto.")
  end,
  ["doxoade:open-user-settings"] = function()
    local settings_file = user_dir .. sep .. "user_settings.lua"
    pcall(function()
      local f = io.open(settings_file, "a")
      if f then f:close() end
    end)
    open_in_right_panel(settings_file, "⚙️ user_settings.lua aberto no painel direito.")
  end,

  ["doxoade:open-search-docs-hub"] = function()
    core.command_view:enter("🔍 Buscar Documentação Python (Ex: asyncio, json, socket):", {
      submit = function(text)
        execute_docs_search_interactive(text)
      end
    })
  end,
  ["doxoade:find-selection-in-opposite-split"] = function()
    local view = core.active_view
    local doc = view and view.doc
    if not doc or not doc.has_selection or not doc:has_selection() then
      core.log("Selecione um texto para buscar no painel oposto.")
      return
    end
    local l1, c1, l2, c2 = doc:get_selection(true)
    local query = doc:get_text(l1, c1, l2, c2)
    if not query or query == "" then return end
    local leaves = get_doc_leaves(core.root_view.root_node)
    local active_node = core.root_view:get_active_node()
    local target_node = nil
    for _, leaf in ipairs(leaves) do
      if leaf ~= active_node then
        target_node = leaf
        break
      end
    end
    if not target_node or not target_node.active_view or not target_node.active_view.doc then
      core.error("Nenhum documento aberto no painel oposto.")
      return
    end
    local target_doc = target_node.active_view.doc
    local found_line = nil
    for line_idx, line_text in ipairs(target_doc.lines or {}) do
      if line_text:find(query, 1, true) then
        found_line = line_idx
        break
      end
    end
    if found_line then
      core.set_active_view(target_node.active_view)
      target_doc:set_selection(found_line, 1, found_line, 1)
      core.log(string.format("Encontrado na linha %d: '%s'", found_line, query))
      core.redraw = true
    else
      core.log(string.format("Termo '%s' não encontrado no painel oposto.", query))
    end
  end,
  ["doxoade:consult-selection-or-word"] = function()
    local view = core.active_view
    local doc = view and view.doc
    local query = nil
    if doc and doc.has_selection and doc:has_selection() then
      local l1, c1, l2, c2 = doc:get_selection(true)
      query = doc:get_text(l1, c1, l2, c2)
    elseif doc and doc.get_selection then
      local line, col = doc:get_selection(true)
      if line and doc.lines then
        local text = doc.lines[line] or ""
        local s = col or 1
        while s > 1 and text:sub(s - 1, s - 1):match("[%w_%.]") do s = s - 1 end
        local e = col or 1
        while e <= #text and text:sub(e, e):match("[%w_%.]") do e = e + 1 end
        if s < e then query = text:sub(s, e - 1) end
      end
    end

    if query and query ~= "" then
      execute_docs_search_interactive(query)
    else
      command.perform("doxoade:open-search-docs-hub")
    end
  end
})

command.add("core.docview", {
  ["doxoade:follow-docs-link"] = function()
    local view = core.active_view
    local doc = view and view.doc
    if not doc or not doc.get_selection then return false end

    local line = doc:get_selection(true)
    if not line or not doc.lines then return false end
    local line_text = doc.lines[line] or ""

    local target_path = line_text:match("↳%s*`?([%w_%-/]+%.html)`?") or
                        line_text:match("%(([%w_%-/]+%.html)%)") or
                        line_text:match("`([%w_%-/]+%.html)`")

    if target_path then
      local search_view = ConsultSearchView("Link", { results = {{ path = target_path, title = target_path }} })
      search_view:open_selected(1)
      return true
    end
    return false
  end
})

-- Intercepta Ctrl+C no Leitor de Documentos com predicado estritamente blindado
command.add(function()
  local av = core.active_view
  return av and type(av.is) == "function" and av:is(ConsultDocReaderView)
end, {
  ["doxoade:copy-reader-selection"] = function()
    if core.active_view and core.active_view.copy_selection_to_clipboard then
      core.active_view:copy_selection_to_clipboard()
    end
  end
})

keymap.add {
  ["ctrl+alt+h"] = "doxoade:consult-selection-or-word",
  ["f1"]          = "doxoade:consult-selection-or-word",
  ["ctrl+return"] = "doxoade:follow-docs-link",
  ["ctrl+c"]      = "doxoade:copy-reader-selection",
}
