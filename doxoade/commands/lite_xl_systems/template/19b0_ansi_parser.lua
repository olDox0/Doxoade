-- doxoade/commands/lite_xl_systems/template/19b0_ansi_parser.lua
--[[
  🎨 DOXOADE ANSI PARSER — MOTOR VT100 / OSC / CSI SOBERANO (V45.0)
  - Filtro total de títulos OSC (\x1b]0;...\x07 e \x1b]0;...\x1b\).
  - Consumo completo de sequências de cursor e modos do ConPTY (H, f, J, h, l, t, c, r).
  - Estado contínuo resiliente a quebra de pacotes entre chunks de I/O.
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]

local AnsiParser = {}
AnsiParser.__index = AnsiParser

local DEFAULT_COLORS = {
  [0]  = { 0,   0,   0,   255 },  -- Black
  [1]  = { 205, 49,  49,  255 },  -- Red
  [2]  = { 13,  188, 121, 255 },  -- Green
  [3]  = { 229, 229, 16,  255 },  -- Yellow
  [4]  = { 36,  114, 200, 255 },  -- Blue
  [5]  = { 188, 63,  188, 255 },  -- Magenta
  [6]  = { 17,  168, 205, 255 },  -- Cyan
  [7]  = { 229, 229, 229, 255 },  -- White
  [8]  = { 102, 102, 102, 255 },  -- Bright Black
  [9]  = { 241, 76,  76,  255 },  -- Bright Red
  [10] = { 35,  209, 139, 255 },  -- Bright Green
  [11] = { 245, 245, 67,  255 },  -- Bright Yellow
  [12] = { 59,  142, 234, 255 },  -- Bright Blue
  [13] = { 214, 112, 214, 255 },  -- Bright Magenta
  [14] = { 41,  184, 219, 255 },  -- Bright Cyan
  [15] = { 255, 255, 255, 255 },  -- Bright White
}

local PALETTE_256 = {}
for i = 0, 15 do PALETTE_256[i] = DEFAULT_COLORS[i] end

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

for i = 232, 255 do
  local v = 8 + (i - 232) * 10
  PALETTE_256[i] = { v, v, v, 255 }
end

function AnsiParser.new()
  local self = setmetatable({}, AnsiParser)
  self.fg = { 229, 229, 229, 255 }
  self.bg = nil
  self.bold = false
  self.dim = false
  self.italic = false
  self.underline = false
  self.blink = false
  self.inverse = false
  self.hidden = false

  -- Máquina de estados contínua entre leituras de chunks
  self._state = "TEXT" -- "TEXT" | "ESC" | "CSI" | "OSC" | "OSC_ESC"
  self._csi_params = ""
  return self
end

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

function AnsiParser:_apply_sgr(params)
  local i = 1
  if #params == 0 then
    self:reset_style()
    return
  end

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
    elseif p == 21 or p == 22 then
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
      self.fg = DEFAULT_COLORS[p - 30]
    elseif p == 38 then
      if params[i + 1] == 5 then
        local color_idx = params[i + 2] or 0
        self.fg = PALETTE_256[color_idx] or DEFAULT_COLORS[7]
        i = i + 2
      elseif params[i + 1] == 2 then
        local r = params[i + 2] or 0
        local g = params[i + 3] or 0
        local b = params[i + 4] or 0
        self.fg = { r, g, b, 255 }
        i = i + 4
      end
    elseif p == 39 then
      self.fg = { 229, 229, 229, 255 }
    elseif p >= 40 and p <= 47 then
      self.bg = DEFAULT_COLORS[p - 40]
    elseif p == 48 then
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
      self.bg = nil
    elseif p >= 90 and p <= 97 then
      self.fg = DEFAULT_COLORS[p - 90 + 8]
    elseif p >= 100 and p <= 107 then
      self.bg = DEFAULT_COLORS[p - 100 + 8]
    end

    i = i + 1
  end
end

-- ── Parser Contínuo de Chunks ────────────────────────────────────────────────
function AnsiParser:parse(data)
  local segments = {}
  local current_text = ""
  local current_style = self:get_current_style()
  local len = #data
  local i = 1

  local function flush_text()
    if current_text ~= "" then
      table.insert(segments, { text = current_text, style = current_style })
      current_text = ""
    end
  end

  while i <= len do
    local byte = data:byte(i)

    -- 1. Dentro de sequência OSC (Títulos e Notificações do SO)
    if self._state == "OSC" then
      if byte == 0x07 then -- BEL (\x07) encerra OSC
        self._state = "TEXT"
      elseif byte == 0x1B then -- Possível início de String Terminator (\x1b\)
        self._state = "OSC_ESC"
      end
      i = i + 1

    elseif self._state == "OSC_ESC" then
      if byte == 0x5C then -- '\' encerra ST (\x1b\)
        self._state = "TEXT"
      else
        self._state = "OSC"
      end
      i = i + 1

    -- 2. Após receber o caractere ESC (\x1b)
    elseif self._state == "ESC" then
      if byte == 0x5B then -- '[' -> Inicia CSI
        self._state = "CSI"
        self._csi_params = ""
      elseif byte == 0x5D then -- ']' -> Inicia OSC
        self._state = "OSC"
      elseif byte == 0x28 or byte == 0x29 then -- Designação de charset (ex: \x1b(B)
        i = i + 1 -- Descarta o próximo caractere de charset
        self._state = "TEXT"
      else
        self._state = "TEXT"
      end
      i = i + 1

    -- 3. Dentro de sequência CSI (\x1b[...)
    elseif self._state == "CSI" then
      -- O caractere terminador do comando CSI fica entre 0x40 ('@') e 0x7E ('~')
      if byte >= 0x40 and byte <= 0x7E then
        local cmd = string.char(byte)

        if cmd == "m" then
          -- SGR: Cores e Estilos
          local params = {}
          for p in self._csi_params:gmatch("(%d+)") do
            table.insert(params, tonumber(p))
          end
          self:_apply_sgr(params)
          current_style = self:get_current_style()

        elseif cmd == "K" then
          -- EL: Erase in Line (Limpa linha atual)
          flush_text()
          table.insert(segments, { control = "erase_line" })

        elseif cmd == "J" then
          -- ED: Erase in Display (Limpeza de tela se for \x1b[2J)
          if self._csi_params:find("2") then
            flush_text()
            table.insert(segments, { control = "clear" })
          end

        elseif cmd == "A" then
          -- CUU: Cursor Up (Subir linha)
          flush_text()
          local lines_up = tonumber(self._csi_params:match("(%d+)")) or 1
          table.insert(segments, { control = "cursor_up", count = lines_up })

        -- Outros comandos de cursor (H, f, C, D, B, h, l, t, c, r) são consumidos
        -- e neutralizados silenciosamente sem vazar texto cru na tela.
        end

        self._state = "TEXT"
        self._csi_params = ""
      else
        -- Acumula parâmetros numéricos, ';' e '?' (modos privados)
        self._csi_params = self._csi_params .. string.char(byte)
      end
      i = i + 1

    -- 4. Fluxo normal de texto
    else
      if byte == 0x1B then -- \x1b (Início de escape)
        flush_text()
        self._state = "ESC"
        i = i + 1

      elseif byte == 0x0A then -- \n (LF)
        flush_text()
        table.insert(segments, { text = "\n", style = current_style, control = "lf" })
        i = i + 1

      elseif byte == 0x0D then -- \r (CR)
        flush_text()
        -- Se não for seguido imediatamente por \n, emite retorno de carro in-place
        if i + 1 > len or data:byte(i + 1) ~= 0x0A then
          table.insert(segments, { control = "cr" })
        end
        i = i + 1

      elseif byte == 0x09 then -- \t (Tab)
        current_text = current_text .. "    "
        i = i + 1

      elseif byte >= 32 or byte > 127 then -- Caracteres imprimíveis e UTF-8
        current_text = current_text .. string.char(byte)
        i = i + 1

      else
        -- Caracteres de controle ignorados (BEL 0x07, NULL 0x00, etc.)
        i = i + 1
      end
    end
  end

  flush_text()
  return segments
end

function AnsiParser.parse_line(line_data)
  local parser = AnsiParser.new()
  return parser:parse(line_data)
end

rawset(_G, "AnsiParser", AnsiParser)
rawset(_G, "_DOXOADE_ANSI_PARSER", AnsiParser)

return AnsiParser
