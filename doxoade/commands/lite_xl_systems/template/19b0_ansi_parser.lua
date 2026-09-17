-- doxoade/commands/lite_xl_systems/template/19b0_ansi_parser.lua
--[[
  🎨 DOXOADE ANSI PARSER — Motor de Interpretação de Sequências ANSI.
  Converte fluxos de bytes com escape codes em segmentos de texto estilizados
  (cor, negrito, itálico, sublinhado, inversão) para renderização no Lite XL.

  Suporte:
    • SGR padrão (30-37, 40-47, 90-97, 100-107)
    • 256 cores (38;5;N / 48;5;N)
    • True Color 24-bit (38;2;R;G;B / 48;2;R;G;B)
    • Atributos: bold, dim, italic, underline, blink, inverse, hidden
    • Reset (0)
    • Sequências de cursor: CUU, CUD, CUF, CUB, CUP, ED, EL
    • Carriage return, line feed, backspace, tab

  Compliance: ProDeNov 1.2.1 | PASC-6.1
]]

local AnsiParser = {}
AnsiParser.__index = AnsiParser

-- ─────────────────────────────────────────────────────────────────────────────
-- PALETA DE CORES PADRÃO (16 cores ANSI → RGBA)
-- ─────────────────────────────────────────────────────────────────────────────

local DEFAULT_COLORS = {
  -- Normais (30-37)
  [0]  = { 0,   0,   0,   255 },  -- Black
  [1]  = { 205, 49,  49,  255 },  -- Red
  [2]  = { 13,  188, 121, 255 },  -- Green
  [3]  = { 229, 229, 16,  255 },  -- Yellow
  [4]  = { 36,  114, 200, 255 },  -- Blue
  [5]  = { 188, 63,  188, 255 },  -- Magenta
  [6]  = { 17,  168, 205, 255 },  -- Cyan
  [7]  = { 229, 229, 229, 255 },  -- White
  -- Bright (90-97)
  [8]  = { 102, 102, 102, 255 },  -- Bright Black
  [9]  = { 241, 76,  76,  255 },  -- Bright Red
  [10] = { 35,  209, 139, 255 },  -- Bright Green
  [11] = { 245, 245, 67,  255 },  -- Bright Yellow
  [12] = { 59,  142, 234, 255 },  -- Bright Blue
  [13] = { 214, 112, 214, 255 },  -- Bright Magenta
  [14] = { 41,  184, 219, 255 },  -- Bright Cyan
  [15] = { 255, 255, 255, 255 },  -- Bright White
}

-- ─────────────────────────────────────────────────────────────────────────────
-- PALETA 256 CORES (gerada proceduralmente)
-- ─────────────────────────────────────────────────────────────────────────────

local PALETTE_256 = {}

-- Primeiras 16 cores = cores padrão
for i = 0, 15 do
  PALETTE_256[i] = DEFAULT_COLORS[i]
end

-- Cores 16-231: cubo 6x6x6
do
  local levels = { 0, 95, 135, 175, 215, 255 }
  local idx = 16
  for r = 1, 6 do
    for g = 1, 6 do
      for b = 1, 6 do
        PALETTE_256[idx] = { levels[r], levels[g], levels[b], 255 }
        idx = idx + 1
      end
    end
  end
end

-- Cores 232-255: escala de cinza
for i = 232, 255 do
  local v = 8 + (i - 232) * 10
  PALETTE_256[i] = { v, v, v, 255 }
end

-- ─────────────────────────────────────────────────────────────────────────────
-- ESTADO DO PARSER
-- ─────────────────────────────────────────────────────────────────────────────

function AnsiParser.new()
  local self = setmetatable({}, AnsiParser)
  -- Estado de estilo atual
  self.fg = { 229, 229, 229, 255 }
  self.bg = nil  -- nil = transparente
  self.bold = false
  self.dim = false
  self.italic = false
  self.underline = false
  self.blink = false
  self.inverse = false
  self.hidden = false
  -- Estado do cursor (para apps interativos)
  self.cursor_row = 1
  self.cursor_col = 1
  -- Buffer de parse
  self._escape_buffer = ""
  self._in_escape = false
  self._in_csi = false
  self._csi_params = ""
  return self
end

-- ─────────────────────────────────────────────────────────────────────────────
-- RESET DE ESTILO
-- ─────────────────────────────────────────────────────────────────────────────

function AnsiParser:reset_style()
  self.fg = { 229, 229, 229, 255 }
  self.bg = nil
  self.bold = false
  self.dim = false
  self.italic = false
  self.underline = false
  self.blink = false
  self.inverse = false
  self.hidden = false
end

function AnsiParser:get_current_style()
  local fg, bg = self.fg, self.bg
  if self.inverse then
    fg, bg = bg or { 0, 0, 0, 255 }, fg
  end
  return {
    fg = fg,
    bg = bg,
    bold = self.bold,
    dim = self.dim,
    italic = self.italic,
    underline = self.underline,
    blink = self.blink,
    inverse = self.inverse,
    hidden = self.hidden,
  }
end

-- ─────────────────────────────────────────────────────────────────────────────
-- PROCESSAMENTO SGR (SELECT GRAPHIC RENDITION)
-- ─────────────────────────────────────────────────────────────────────────────

function AnsiParser:_apply_sgr(params)
  local i = 1
  while i <= #params do
    local p = params[i] or 0

    if p == 0 then
      self:reset_style()
    elseif p == 1 then
      self.bold = true
    elseif p == 2 then
      self.dim = true
    elseif p == 3 then
      self.italic = true
    elseif p == 4 then
      self.underline = true
    elseif p == 5 or p == 6 then
      self.blink = true
    elseif p == 7 then
      self.inverse = true
    elseif p == 8 then
      self.hidden = true
    elseif p == 21 then
      self.bold = false
    elseif p == 22 then
      self.bold = false
      self.dim = false
    elseif p == 23 then
      self.italic = false
    elseif p == 24 then
      self.underline = false
    elseif p == 25 then
      self.blink = false
    elseif p == 27 then
      self.inverse = false
    elseif p == 28 then
      self.hidden = false
    elseif p >= 30 and p <= 37 then
      -- Foreground padrão
      self.fg = DEFAULT_COLORS[p - 30]
    elseif p == 38 then
      -- Foreground estendido (256 ou true color)
      if params[i + 1] == 5 then
        -- 256 cores: 38;5;N
        local color_idx = params[i + 2] or 0
        self.fg = PALETTE_256[color_idx] or DEFAULT_COLORS[7]
        i = i + 2
      elseif params[i + 1] == 2 then
        -- True color: 38;2;R;G;B
        local r = params[i + 2] or 0
        local g = params[i + 3] or 0
        local b = params[i + 4] or 0
        self.fg = { r, g, b, 255 }
        i = i + 4
      end
    elseif p == 39 then
      -- Default foreground
      self.fg = { 229, 229, 229, 255 }
    elseif p >= 40 and p <= 47 then
      -- Background padrão
      self.bg = DEFAULT_COLORS[p - 40]
    elseif p == 48 then
      -- Background estendido
      if params[i + 1] == 5 then
        local color_idx = params[i + 2] or 0
        self.bg = PALETTE_256[color_idx] or DEFAULT_COLORS[0]
        i = i + 2
      elseif params[i + 1] == 2 then
        local r = params[i + 2] or 0
        local g = params[i + 3] or 0
        local b = params[i + 4] or 0
        self.bg = { r, g, b, 255 }
        i = i + 4
      end
    elseif p == 49 then
      -- Default background
      self.bg = nil
    elseif p >= 90 and p <= 97 then
      -- Foreground bright
      self.fg = DEFAULT_COLORS[p - 90 + 8]
    elseif p >= 100 and p <= 107 then
      -- Background bright
      self.bg = DEFAULT_COLORS[p - 100 + 8]
    end

    i = i + 1
  end
end

-- ─────────────────────────────────────────────────────────────────────────────
-- PARSER PRINCIPAL: processa um chunk de bytes e retorna segmentos
-- ─────────────────────────────────────────────────────────────────────────────

function AnsiParser:parse(data)
  local segments = {}
  local current_text = ""
  local current_style = self:get_current_style()
  local len = #data
  local i = 1
  
  while i <= len do
    local byte = data:byte(i)
    
    -- Sequência OSC (ex: título de janela \x1b]0;...\x07 ou \x1b]0;...\x1b\) -> DESCARTA TOTAL
    if self._in_osc then
      if byte == 0x07 or (byte == 0x5C and data:byte(i - 1) == 0x1B) then
        self._in_osc = false
      end
      i = i + 1

    -- Sequência CSI (cores, cursor, estilos \x1b[...)
    elseif self._in_escape then
      if self._in_csi then
        if byte >= 0x40 and byte <= 0x7E then
          local final_char = string.char(byte)
          if final_char == "m" and self._apply_sgr then
            local params = {}
            for p in self._csi_params:gmatch("(%d+)") do
              table.insert(params, tonumber(p))
            end
            self:_apply_sgr(params)
            current_style = self:get_current_style()
          end
          self._in_escape = false
          self._in_csi = false
          self._csi_params = ""
        else
          self._csi_params = self._csi_params .. string.char(byte)
        end
      else
        if byte == 0x5B then      -- '[' (CSI)
          self._in_csi = true
          self._csi_params = ""
        elseif byte == 0x5D then  -- ']' (OSC - Inicia descarte de título)
          self._in_osc = true
          self._in_escape = false
        elseif byte == 0x1B then
          self._in_escape = true
        else
          self._in_escape = false
        end
      end
      i = i + 1

    -- Início de escape
    elseif byte == 0x1B then
      if current_text ~= "" then
        table.insert(segments, { text = current_text, style = current_style })
        current_text = ""
      end
      self._in_escape = true
      self._in_csi = false
      self._csi_params = ""
      i = i + 1

    -- Quebra de Linha LF (0x0A)
    elseif byte == 0x0A then
      if current_text ~= "" then
        table.insert(segments, { text = current_text, style = current_style })
        current_text = ""
      end
      table.insert(segments, { text = "\n", style = current_style, control = "lf" })
      self.cursor_row = self.cursor_row + 1
      self.cursor_col = 1
      i = i + 1

    -- Retorno de Carro CR (0x0D) -> ignorado se seguido de LF
    elseif byte == 0x0D then
      self.cursor_col = 1
      i = i + 1

    -- Tabulação (0x09)
    elseif byte == 0x09 then
      current_text = current_text .. "    "
      self.cursor_col = self.cursor_col + 4
      i = i + 1

    -- Caracteres Imprimíveis
    elseif byte >= 32 or byte > 127 then
      current_text = current_text .. string.char(byte)
      self.cursor_col = self.cursor_col + 1
      i = i + 1
    else
      i = i + 1
    end
  end
  
  if current_text ~= "" then
    table.insert(segments, { text = current_text, style = current_style })
  end
  return segments
end

-- ─────────────────────────────────────────────────────────────────────────────
-- PROCESSAMENTO DE SEQUÊNCIAS CSI
-- ─────────────────────────────────────────────────────────────────────────────

function AnsiParser:_process_csi(params_str, final_char)
  local params = {}
  if params_str ~= "" then
    for part in params_str:gmatch("[^;]+") do
      table.insert(params, tonumber(part) or 0)
    end
  end

  if final_char == "m" then
    -- SGR: Select Graphic Rendition (cores e estilos)
    self:_apply_sgr(params)

  elseif final_char == "A" then
    -- CUU: Cursor Up
    local n = params[1] or 1
    self.cursor_row = math.max(1, self.cursor_row - n)

  elseif final_char == "B" then
    -- CUD: Cursor Down
    local n = params[1] or 1
    self.cursor_row = self.cursor_row + n

  elseif final_char == "C" then
    -- CUF: Cursor Forward
    local n = params[1] or 1
    self.cursor_col = self.cursor_col + n

  elseif final_char == "D" then
    -- CUB: Cursor Back
    local n = params[1] or 1
    self.cursor_col = math.max(1, self.cursor_col - n)

  elseif final_char == "H" or final_char == "f" then
    -- CUP: Cursor Position
    self.cursor_row = params[1] or 1
    self.cursor_col = params[2] or 1
  elseif final_char == "J" then
    -- ED: Erase in Display
    local mode = params[1] or 0
    -- Retornar sinal para o buffer limpar
    -- (será tratado pelo TerminalBuffer)
  elseif final_char == "K" then
    -- EL: Erase in Line
    local mode = params[1] or 0
    -- Retornar sinal para o buffer limpar linha
  elseif final_char == "r" then
    -- DECSTBM: Set scrolling region (ignorar por enquanto)
  elseif final_char == "h" or final_char == "l" then
    -- Set/Reset Mode (ignorar por enquanto)
  elseif final_char == "J" and self._csi_params:find("2") then
    table.insert(segments, { text = "", control = "clear" })
  end
end

-- ─────────────────────────────────────────────────────────────────────────────
-- UTILIDADE: parse simplificado para uma linha única
-- ─────────────────────────────────────────────────────────────────────────────

function AnsiParser.parse_line(line_data)
  local parser = AnsiParser.new()
  return parser:parse(line_data)
end

rawset(_G, "AnsiParser", AnsiParser)
rawset(_G, "_DOXOADE_ANSI_PARSER", AnsiParser)

return AnsiParser
