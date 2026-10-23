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

-- ═══════════════════════════════════════════════════════════════════════
-- VIEW (depois dos helpers)
-- ═══════════════════════════════════════════════════════════════════════

local SearchResultsView = View:extend()

function SearchResultsView:new()
  if SearchResultsView.super and SearchResultsView.super.new then
    pcall(SearchResultsView.super.new, self)
  end
  self.scrollable = true
  self.font = style.font or style.code_font
  self.line_h = 20
  self.header_h = 32
  self.hovered_idx = nil
  self.selected_idx = 0
end

-- 🛡️ INJEÇÃO DE UTILITÁRIO DE DIRETÓRIOS (Ma'at)
-- Garante que a chamada 'ensure_dir' exista e seja recursiva no Windows/Linux.
local function ensure_dir(target_dir)
    if not target_dir or target_dir == "" then return end
    local parts = {}
    for p in tostring(target_dir):gmatch("[^/\\]+") do
        table.insert(parts, p)
    end
    local cur = ""
    for i, p in ipairs(parts) do
        if i == 1 and p:find("^[a-zA-Z]:") then
            cur = p
        else
            cur = (cur == "" and "" or cur .. (PATHSEP or "/")) .. p
            if system and system.mkdir then
                pcall(system.mkdir, cur)
            end
        end
    end
end

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
  if not color[1] or not color[2] or not color[3] then
    color = { 255, 255, 255, 255 }
  end
  if not color[4] then color[4] = 255 end
  if rencache and rencache.draw_text then
    rencache.draw_text(font, text, x, y, color)
  elseif native_renderer and native_renderer.draw_text then
    native_renderer.draw_text(font, text, x, y, color)
  end
end

-- ═══════════════════════════════════════════════════════════════════════
-- SNIPPET HELPERS (devem estar DEPOIS de draw_text_safe e ANTES das Views)
-- ═══════════════════════════════════════════════════════════════════════

local function parse_snippet_markers(snippet)
    local segments = {}
    if not snippet or snippet == "" then return segments end

    local buf = {}
    local in_hit = false
    local i = 1
    local len = #snippet

    while i <= len do
        local c = snippet:sub(i, i)
        local next_c = snippet:sub(i + 1, i + 1)
        -- Aceita bytes reais (0x02 / 0x03) E escapes Lua "\2" / "\3"
        local is_start = (c == "\x02") or (c == "\\" and next_c == "2")
        local is_end   = (c == "\x03") or (c == "\\" and next_c == "3")

        if is_start then
            if #buf > 0 then
                table.insert(segments, { text = table.concat(buf), highlighted = in_hit })
                buf = {}
            end
            in_hit = true
            i = i + (c == "\\" and 2 or 1)
        elseif is_end then
            if #buf > 0 then
                table.insert(segments, { text = table.concat(buf), highlighted = true })
                buf = {}
            end
            in_hit = false
            i = i + (c == "\\" and 2 or 1)
        else
            table.insert(buf, c)
            i = i + 1
        end
    end
    if #buf > 0 then
        table.insert(segments, { text = table.concat(buf), highlighted = in_hit })
    end
    return segments
end

local function draw_rich_snippet(view, snippet, x, y, max_width)
    local segments = parse_snippet_markers(snippet)
    if #segments == 0 then return 0 end

    local font = style.code_font or style.font
    local line_height = font:get_height() + 2
    local cur_x = x
    local cur_y = y
    local line_count = 1
    local max_x = x + max_width

    local function newline()
        cur_x = x
        cur_y = cur_y + line_height
        line_count = line_count + 1
    end

    local function put_text(text, color, bg)
        if not text or text == "" then return end
        text = text:gsub("\\2", ""):gsub("\\3", ""):gsub("\x02", ""):gsub("\x03", "")
        if text == "" then return end
        if type(color) ~= "table" then color = { 220, 220, 225, 255 } end
        if not color[1] or not color[2] or not color[3] then color = { 220, 220, 225, 255 } end
        if not color[4] then color[4] = 255 end

        local w = font:get_width(text)
        -- Se cabe, desenha normal
        if cur_x + w <= max_x then
            if bg then
                draw_rect_safe(cur_x, cur_y, w, line_height, bg)
            end
            draw_text_safe(font, text, cur_x, cur_y, color)
            cur_x = cur_x + w
            return
        end

        -- Se não cabe, quebra palavra por palavra (space-aware)
        local remaining = text
        while remaining ~= "" and line_count <= 3 do
            -- Se cur_x == x (linha nova), pega o máximo que cabe
            local space_left = max_x - cur_x
            local fit_len = 0
            local len = #remaining
            for i = len, 1, -1 do
                if font:get_width(remaining:sub(1, i)) <= space_left then
                    fit_len = i
                    break
                end
            end
            if fit_len == 0 then
                -- Nada cabe, nova linha
                newline()
                space_left = max_x - cur_x
                for i = len, 1, -1 do
                    if font:get_width(remaining:sub(1, i)) <= space_left then
                        fit_len = i
                        break
                    end
                end
                if fit_len == 0 then
                    -- Palavra maior que a linha: força corte em max_width
                    fit_len = math.floor(max_width / (font:get_width("M")))
                    fit_len = math.min(fit_len, #remaining)
                end
            end

            local piece = remaining:sub(1, fit_len)
            local w_piece = font:get_width(piece)
            if bg then
                draw_rect_safe(cur_x, cur_y, w_piece, line_height, bg)
            end
            draw_text_safe(font, piece, cur_x, cur_y, color)
            cur_x = cur_x + w_piece
            remaining = remaining:sub(fit_len + 1)

            if remaining ~= "" then
                newline()
            end
        end
    end

    for _, seg in ipairs(segments) do
        if line_count > 3 then break end

        local base_color = seg.highlighted and style.accent or style.text
        local bg = seg.highlighted and style.background2 or nil

        local pos = 1
        while pos <= #seg.text do
            if line_count > 3 then break end

            local a, b = seg.text:find("`", pos)
            if not a then
                put_text(seg.text:sub(pos), base_color, bg)
                break
            end
            if a > pos then
                put_text(seg.text:sub(pos, a - 1), base_color, bg)
            end
            local c, d = seg.text:find("`", b + 1)
            if not c then
                put_text(seg.text:sub(b + 1), base_color, bg)
                break
            end
            put_text(seg.text:sub(b + 1, c - 1), style.syntax or {120,220,120,255}, bg)
            pos = d + 1
        end
    end

    return line_count * line_height
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
--      draw_text_safe(self.font_sub, path_str, card_x + 14, cur_y + 28, style.dim or { 140, 140, 150, 255 })

      -- Snippet com markers de busca e inline code
      local raw_snip = tostring(item.snippet or "")
      draw_rich_snippet(
          self,
          raw_snip,
          card_x + 14,
          cur_y + 48,
          card_w - 28
      )
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

-- =============================================================================
-- 4. AJUSTE DE MOUSE: Trava contra clique duplo concorrente
-- =============================================================================
function ConsultSearchView:on_mouse_pressed(button, px, py, clicks)
  local scrollbar_w = (style.scrollbar_size or 8) + 6
  if px >= (self.position.x + self.size.x - scrollbar_w) then
    return ConsultSearchView.super.on_mouse_pressed(self, button, px, py, clicks)
  end

  if button == "left" and self.hovered_idx then
    if self.is_loading_doc then return true end -- Trava reentrância
    self.selected_idx = self.hovered_idx
    self:open_selected(self.hovered_idx)
    return true
  end
  return ConsultSearchView.super.on_mouse_pressed(self, button, px, py, clicks)
end

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

local function style_line_markdown(line)
    if not line or line == "" then
        return { { text = "", style = {220,220,225,255} } }
    end

    -- Limpa bytes de controle residuais (0x02/0x03, escapes \2/\3)
    line = line:gsub("\x02", ""):gsub("\x03", ""):gsub("\\2", ""):gsub("\\3", "")

    local parts = {}

    -- Header: #, ##, ###
    local header_mark, header_text = line:match("^(#+)%s+(.+)$")
    if header_mark then
        local color = (#header_mark == 1) and {56,189,248,255}
                    or (#header_mark == 2) and {34,197,94,255}
                    or {251,191,36,255}
        table.insert(parts, { text = header_text, style = color })
        return parts
    end

    -- Blockquote: >
    local quote = line:match("^>%s?(.*)$")
    if quote then
        table.insert(parts, { text = quote, style = style.dim or {140,140,150,255} })
        return parts
    end

    -- Lista: -, *, +
    local list = line:match("^([%-%*%+])%s+(.*)$")
    if list then
        table.insert(parts, { text = "• ", style = {200,200,210,255} })
        line = list
    end

    -- Inline: `code`, **bold**
    local text_color = {220,220,225,255}
    local code_color = style.syntax or {120,220,120,255}
    local bold_color = {255,255,255,255}

    local pos = 1
    while pos <= #line do
        local a, b = line:find("`", pos)
        local c_bold = line:find("%*%*", pos)
        local next_special = a or c_bold or math.huge
        if c_bold and c_bold < next_special then next_special = c_bold end
        if a and a < next_special then next_special = a end

        if next_special == math.huge then
            table.insert(parts, { text = line:sub(pos), style = text_color })
            break
        end
        if next_special > pos then
            table.insert(parts, { text = line:sub(pos, next_special - 1), style = text_color })
        end

        if next_special == a then
            local d = line:find("`", b + 1)
            if d then
                table.insert(parts, { text = line:sub(b + 1, d - 1), style = code_color })
                pos = d + 1
            else
                table.insert(parts, { text = line:sub(b + 1), style = text_color })
                break
            end
        else
            local d = line:find("%*%*", next_special + 2)
            if d then
                table.insert(parts, { text = line:sub(next_special + 2, d - 1), style = bold_color })
                pos = d + 2
            else
                table.insert(parts, { text = line:sub(next_special), style = text_color })
                break
            end
        end
    end
    return parts
end

local function wrap_line(line, width)
  local parts = {}
  while #line > width do
    local seg, cut = line:sub(1, width), nil
    for i = width, 1, -1 do
      if seg:sub(i, i) == " " then cut = i break end
    end
    cut = cut or width
    parts[#parts + 1] = line:sub(1, cut)
    line = line:sub(cut + 1):gsub("^%s+", "")
  end
  parts[#parts + 1] = line
  return parts
end

function ConsultDocReaderView:reflow()
  local char_w = 7 -- largura média do glifo mono; ajuste p/ renderer.font:get_width("x")
  local cols = math.max(40, math.floor((self.size.x - 24) / char_w))
  if self._rf_cols == cols and self._rf_n == #self.md_lines then return end
  self._rf_cols, self._rf_n = cols, #self.md_lines

  local view, in_code = {}, false
  for _, raw in ipairs(self.md_lines) do
    local is_fence = raw:match("^%s*```") ~= nil
    local state = is_fence and true or in_code
    local pieces = (#raw > cols) and wrap_line(raw, cols) or { raw }
    for i, p in ipairs(pieces) do
      view[#view + 1] = { text = p, cont = (i > 1), code = state }
    end
    if is_fence then in_code = not in_code end
  end
  self.view_lines = view
end

function ConsultDocReaderView:get_scrollable_size()
  self:reflow()
  return (#self.view_lines + 1) * self.line_height
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

  -- 2. Renderização do Conteúdo
  core.push_clip_rect(x, y + self.header_h, w - scrollbar_w - 2, h - self.header_h)
  local cur_y = y + self.header_h + 10 - scroll_y
  local active = self:get_active_lines()

  local s_sel = self.sel_start_line and self.sel_end_line and math.min(self.sel_start_line, self.sel_end_line)
  local e_sel = self.sel_start_line and self.sel_end_line and math.max(self.sel_start_line, self.sel_end_line)

  local in_code_block = false

  for line_idx, line in ipairs(active) do
    local text = tostring(line or "")
    
    -- Atualiza estado do bloco de código (necessário para todas as linhas)
    if text:find("^```") then
      in_code_block = not in_code_block
      -- Opcional: desenhar a barra do fence se quiser
    end

    -- Culling de viewport: só desenha o que está visível
    if (cur_y + self.line_h) > (y + self.header_h) and cur_y < (y + h) then
      -- Highlight de seleção (por trás do texto)
      if s_sel and e_sel and line_idx >= s_sel and line_idx <= e_sel then
        draw_rect_safe(x + 10, cur_y, w - scrollbar_w - 20, self.line_h, { 56, 189, 248, 70 })
      end

      -- Renderização baseada no estado da linha
      if text:find("^```") then
        -- Fence: apenas uma linha decorativa
        draw_rect_safe(x + 14, cur_y + math.floor(self.line_h / 2), w - scrollbar_w - 28, 2, { 60, 60, 75, 255 })
      
      elseif in_code_block then
        -- Dentro de bloco de código
        draw_rect_safe(x + 14, cur_y, w - scrollbar_w - 28, self.line_h, { 14, 14, 18, 255 })
        draw_rect_safe(x + 14, cur_y, 2, self.line_h, self.raw_mode and { 34, 197, 94, 255 } or { 100, 100, 140, 255 })
        local code_color = text:find("^# ↳") and { 130, 140, 150, 255 } or { 230, 230, 140, 255 }
        draw_text_safe(font, text, x + 24, cur_y + 1, code_color)
      
      else
        -- Texto normal / markdown: usa style_line_markdown
        local parts = style_line_markdown(text)
        local cur_x = x + 18
        for _, p in ipairs(parts) do
          if p.text and p.text ~= "" then
            draw_text_safe(font, p.text, cur_x, cur_y + 1, p.style)
            cur_x = cur_x + font:get_width(p.text)
          end
        end
      end
    end

    -- Atualiza Y para a próxima linha (SEMPRE, independentemente do culling)
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
-- 5. TRANSIÇÃO: ABERTURA DO DOCUMENTO NO LEITOR (SQLite Direto < 30ms)
-- =============================================================================
function ConsultSearchView:open_selected(idx)
  local item = self.results[idx]
  if not item or not item.path then return end
  if self.is_loading_doc then return end
  self.is_loading_doc = true

  local py_exe = get_doxoade_python_exe()
  local udir = USERDIR or "."
  local p_sep = PATHSEP or "/"
  local doxoade_dir = udir .. p_sep .. ".doxoade"

  if system and system.mkdir then
    local clean = tostring(doxoade_dir):gsub("/", "\\")
    local sub = ""
    for part in clean:gmatch("[^\\]+") do
      if sub == "" and part:find("^[a-zA-Z]:") then sub = part
      else sub = (sub == "" and "" or sub .. "\\") .. part; pcall(system.mkdir, sub) end
    end
  end

  local out_md_win  = (doxoade_dir .. p_sep .. "consult_active_doc.md"):gsub("/", "\\")
  local out_md_py   = out_md_win:gsub("\\", "/")
  local runner_py   = (doxoade_dir .. p_sep .. "run_read.py"):gsub("/", "\\")
  local target_path = item.path

  pcall(os.remove, out_md_win)
  pcall(os.remove, runner_py)

  core.log(string.format("📄 [CONSULT READ] Abrindo: '%s'", tostring(item.title)))

  local f_run = io.open(runner_py, "w")
  if not f_run then
    self.is_loading_doc = false
    return
  end

  local script_content = string.format([=[# -*- coding: utf-8 -*-
import sys, traceback
from pathlib import Path

# Redireciona stderr para arquivo, para o Lua ler se falhar
stderr_path = Path(%q) / "run_read.stderr"
try:
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    _err_f = open(stderr_path, "w", encoding="utf-8")
    sys.stderr = _err_f
except Exception:
    pass

import sqlite3

db_path = Path.home() / ".doxoade" / "consult_docs_fts5.db"
doc_path = %q
out_path = Path(%q)

try:
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    row = conn.execute("SELECT title, content FROM docs WHERE path = ? LIMIT 1;", (doc_path,)).fetchone()
    if not row:
        alt_path = doc_path.replace("git/day_", "git/github/day_")
        row = conn.execute("SELECT title, content FROM docs WHERE path = ? LIMIT 1;", (alt_path,)).fetchone()
    if not row:
        row = conn.execute(
            "SELECT title, content FROM docs WHERE path LIKE ? ORDER BY length(path) LIMIT 1;",
            (f"%%{doc_path}%%",)
        ).fetchone()
    conn.close()

    if row and row[1]:
        title, content = row
        md = content if content.strip().startswith("#") else f"# 📖 {title}\n\n{content}\n"
    else:
        md = f"# ⚠️ Documento não localizado no banco.\n\n**Path buscado:** `{doc_path}`\n\n"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
except Exception as e:
    err_msg = f"EXCEPTION: {type(e).__name__}: {e}\n{traceback.format_exc()}"
    try:
        sys.stderr.write(err_msg)
        sys.stderr.flush()
    except Exception:
        pass
    # Escreve o erro no out_path também, para o Lua ver
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(f"# ⚠️ Erro no run_read.py\n\n```\n{err_msg}\n```\n", encoding="utf-8")
    except Exception:
        pass
]=], doxoade_dir, target_path, out_md_py)

  f_run:write(script_content)
  f_run:close()

  local t0 = os.clock()
  local python_used = py_exe
  local exec_cmd = string.format('"%s" "%s"', py_exe, runner_py)

  -- 🔍 LOG: captura o python e o comando exato
  if core.log then
    core.log(string.format("🔍 [CONSULT READ] Python: %s", tostring(python_used)))
    core.log(string.format("🔍 [CONSULT READ] Runner: %s", tostring(runner_py)))
    core.log(string.format("🔍 [CONSULT READ] Output: %s", tostring(out_md_win)))
    core.log(string.format("🔍 [CONSULT READ] Exec: %s", exec_cmd))
  end

  -- 🔍 LOG: verifica se os arquivos existem antes de rodar
  local py_info = system.get_file_info(python_used)
  local runner_info = system.get_file_info(runner_py)
  if not py_info then
    core.log("❌ [CONSULT READ] Python NÃO EXISTE no path: " .. tostring(python_used))
    self.is_loading_doc = false
    return
  end
  if not runner_info then
    core.log("❌ [CONSULT READ] Runner NÃO EXISTE: " .. tostring(runner_py))
    self.is_loading_doc = false
    return
  end
  core.log(string.format("🔍 [CONSULT READ] Python (%d bytes) e Runner (%d bytes) existem",
    py_info.size or 0, runner_info.size or 0))

  -- 🔍 EXEC: usa system.exec e captura o retorno
  local ok_exec, exec_result = pcall(system.exec, exec_cmd)
  if not ok_exec then
    core.log("❌ [CONSULT READ] system.exec FALHOU: " .. tostring(exec_result))
  else
    core.log("✅ [CONSULT READ] system.exec disparado (aguardando output...)")
  end

  local search_view = self
  core.add_thread(function()
    local found = false
    local last_size = 0
    for i = 1, 150 do  -- 7.5s (aumentado de 100 → 150)
      coroutine.yield(0.05)
      local info = system.get_file_info(out_md_win)
      if info and (info.size or 0) > 10 then
        found = true
        core.log(string.format("✅ [CONSULT READ] Output detectado (%d bytes) após %d iterações",
          info.size, i))
        break
      end
      -- log a cada 20 iterações (1s) pra não poluir
      if i % 20 == 0 then
        core.log(string.format("⏳ [CONSULT READ] Aguardando output... (%d/150)", i))
      end
    end

    search_view.is_loading_doc = false
    local elapsed_ms = math.floor((os.clock() - t0) * 1000)

    if not found then
      core.log(string.format("❌ [CONSULT READ] TIMEOUT após %dms. Verificando se o runner foi criado...", elapsed_ms))
      -- Tenta ler o stderr do python (se existir)
      local stderr_file = system.get_file_info((doxoade_dir .. p_sep .. "run_read.stderr"):gsub("/", "\\"))
      if stderr_file then
        local f_err = io.open((doxoade_dir .. p_sep .. "run_read.stderr"):gsub("/", "\\"), "r")
        if f_err then
          local err = f_err:read("*a")
          f_err:close()
          core.log("📋 STDERR do Python:\n" .. err)
        end
      end
      return
    end

    local md_lines = {}
    local f = io.open(out_md_win, "r")
    if f then
      for line in f:lines() do
        table.insert(md_lines, line)
      end
      f:close()
    end

    core.log(string.format("✔ [CONSULT READ] Sucesso em %dms! (%d linhas)", elapsed_ms, #md_lines))
    local reader = ConsultDocReaderView(item.title, item.path, md_lines, search_view)
    open_in_right_panel(reader, string.format("📖 %s", item.title:sub(1, 25)))
  end)
end

-- =============================================================================
-- 6. ORQUESTRAÇÃO DE BUSCA ULTRA-RÁPIDA (SQLite FTS5 Direto < 50ms)
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
  local udir = USERDIR or "."
  local p_sep = PATHSEP or "/"
  local doxoade_dir = udir .. p_sep .. ".doxoade"

  if system and system.mkdir then
    local clean = tostring(doxoade_dir):gsub("/", "\\")
    local sub = ""
    for part in clean:gmatch("[^\\]+") do
      if sub == "" and part:find("^[a-zA-Z]:") then sub = part
      else sub = (sub == "" and "" or sub .. "\\") .. part; pcall(system.mkdir, sub) end
    end
  end

  local out_file_win = (doxoade_dir .. p_sep .. "consult_search.lua"):gsub("/", "\\")
  local out_file_py  = out_file_win:gsub("\\", "/")
  local runner_py    = (doxoade_dir .. p_sep .. "run_consult.py"):gsub("/", "\\")

  pcall(os.remove, out_file_win)
  pcall(os.remove, runner_py)

  local f_run = io.open(runner_py, "w")
  if not f_run then return end

  -- Script Python Otimizado (Sem telemetria de disco excessiva)
  local script_content = string.format([=[# -*- coding: utf-8 -*-
import sqlite3, re
from pathlib import Path

db_path = Path.home() / ".doxoade" / "consult_docs_fts5.db"
query = %q
out_path = Path(%q)

try:
    conn = sqlite3.connect(str(db_path), timeout=15.0)
    clean_q = re.sub(r'[^\w\s]', ' ', query).strip()
    tokens = clean_q.split()
    fts_query = " OR ".join([f'"{tok}"*' for tok in tokens])
    
    sql = """
        SELECT path, title, snippet(docs_fts, 3, '\x02', '\x03', '...', 60)
        FROM docs_fts WHERE docs_fts MATCH ? ORDER BY rank LIMIT 25;
    """
    results = conn.execute(sql, (fts_query,)).fetchall()
    conn.close()
except Exception:
    results = []

def clean_lua_str(s):
    if not s: return ""
    # Protege os markers ANTES de remover control chars
    s = str(s).replace("\x02", "\u200B").replace("\x03", "\u200C")
    clean = s.replace("\r", "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    # Restaura os markers como escapes Lua
    clean = clean.replace("\u200B", "\\2").replace("\u200C", "\\3")
    return clean

lines = ["return {", f'  query = "{clean_lua_str(query)}",', f'  total = {len(results)},', '  results = {']
for path, title, snippet in results:
    safe_snip = clean_lua_str(snippet or title)
    lines.append('    {')
    lines.append(f'      title = "{clean_lua_str(title)}",')
    lines.append(f'      path = "{clean_lua_str(path)}",')
    lines.append(f'      snippet = "{safe_snip}"')
    lines.append('    },')
lines.extend(['  }', '}'])

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text('\n'.join(lines), encoding="utf-8")
]=], query, out_file_py)

  f_run:write(script_content)
  f_run:close()

  -- 🎯 CHAMADA DIRETA (Agora funciona pois o Lite XL é Admin)
  local exec_cmd = string.format('"%s" "%s"', py_exe, runner_py)
  system.exec(exec_cmd)

  core.add_thread(function()
    local t0 = os.clock()
    for _ = 1, 100 do -- 5 segundos de tolerância
      coroutine.yield(0.05)
      local info = system.get_file_info(out_file_win)
      if info and (info.size or 0) > 10 then
        local ok, data = pcall(dofile, out_file_win)
        if ok and type(data) == "table" and data.results then
          local elapsed_ms = math.floor((os.clock() - t0) * 1000)
          open_in_right_panel(ConsultSearchView(query, data),
            string.format("✔ %d resultado(s) em %dms.", data.total or #data.results, elapsed_ms))
        end
        return
      end
    end
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
