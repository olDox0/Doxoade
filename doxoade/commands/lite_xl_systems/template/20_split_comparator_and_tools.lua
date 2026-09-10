-- doxoade/commands/lite_xl_systems/template/20_split_comparator_and_tools.lua
--[[
  ⚖️ DOXOADE SPLIT COMPARATOR & SELECTION TOOLS (V22.0 NPP-Calibrada)
  - Paleta Notepad++ Compare: Verde (Igual), Amarelo (Diferente), Vermelho (Deletada), Cinza (Não encontrada).
  - Alinhador de operadores (=, +=, -=, :, etc.) e comentários (-- e #) com fix de índice op_len.
  - Sorter Alfabético Strip-Aware (ordena pelo conteúdo útil preservando indentação).
  - Sliding Window Block Matcher para localizar o par no Painel B se nada estiver selecionado.
]]
local core = require "core"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local DocView = require "core.docview"
local Doc = require "core.doc"

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

-- =============================================================================
-- 🎨 PALETA NOTEPAD++ COMPARE (VERDE, AMARELO, VERMELHO, CINZA)
-- =============================================================================
local NPP_DIFF_THEMES = {
  EQUAL     = { color = { 34, 197, 94, 255 },  tint = { 34, 197, 94, 30 },   symbol = "✔" }, -- Verde (Igual)
  MODIFIED  = { color = { 234, 179, 8, 255 },  tint = { 234, 179, 8, 38 },   symbol = "≠" }, -- Amarelo (Diferente)
  DELETED   = { color = { 239, 68, 68, 255 },  tint = { 239, 68, 68, 38 },   symbol = "✖" }, -- Vermelho (Deletada/Faltando)
  UNMATCHED = { color = { 120, 120, 130, 255 }, tint = { 100, 100, 110, 25 }, symbol = "·" }, -- Cinza (Não encontrada)
}

local ComparatorState = {
  active = false,
  doc_a = nil,
  doc_b = nil,
  lines_a = {}, -- [line_idx] = "EQUAL" | "MODIFIED" | "DELETED" | "UNMATCHED"
  lines_b = {}, -- [line_idx] = "EQUAL" | "MODIFIED" | "DELETED" | "UNMATCHED"
  telemetry = {
    comparisons_count = 0,
    last_latency_ms = 0.0,
    matched_score = 0
  }
}
rawset(_G, "_DOXOADE_COMPARATOR_STATE", ComparatorState)

-- =============================================================================
-- 🪟 LOCALIZADOR DE SPLITS
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

local function get_opposite_panel()
  if not core.root_view or not core.root_view.root_node then return nil end
  local leaves = get_doc_leaves(core.root_view.root_node)
  local active_node = core.root_view:get_active_node()
  if #leaves < 2 or not active_node then return nil end
  for _, leaf in ipairs(leaves) do
    if leaf ~= active_node and leaf.active_view and leaf.active_view.doc then
      return leaf.active_view
    end
  end
  return nil
end

-- =============================================================================
-- 🧠 MOTOR DE SIMILARIDADE E DIFF COMPLETO (SLIDING WINDOW & MATCHING)
-- =============================================================================
local function clean_compare_text(text)
  if not text then return "" end
  return text:gsub("^%s+", ""):gsub("%s+$", "")
end

local function find_most_similar_block(source_lines, target_doc)
  local t0 = os.clock()
  local target_lines = target_doc.lines or {}
  local src_len = #source_lines
  local tgt_len = #target_lines
  if src_len == 0 or tgt_len == 0 then return 1, math.min(tgt_len, 1) end

  local best_score = -1
  local best_start = 1
  local step = (tgt_len > 3000) and 2 or 1

  for start_idx = 1, math.max(1, tgt_len - src_len + 1), step do
    local match_count = 0
    for j = 1, src_len do
      local s_line = clean_compare_text(source_lines[j])
      local t_line = clean_compare_text(target_lines[start_idx + j - 1] or "")
      if s_line == t_line and s_line ~= "" then
        match_count = match_count + 1
      end
    end
    if match_count > best_score then
      best_score = match_count
      best_start = start_idx
    end
  end

  ComparatorState.telemetry.last_latency_ms = math.floor((os.clock() - t0) * 1000 * 100) / 100
  ComparatorState.telemetry.matched_score = best_score
  return best_start, math.min(tgt_len, best_start + src_len - 1)
end

local function compute_npp_diff(lines_a, lines_b, start_a, start_b)
  local map_a = {}
  local map_b = {}
  local max_len = math.max(#lines_a, #lines_b)

  -- Mapeamento cruzado para busca de linhas idênticas
  local lookup_b = {}
  for idx_b, text in ipairs(lines_b) do
    local c = clean_compare_text(text)
    if c ~= "" then
      lookup_b[c] = lookup_b[c] or {}
      table.insert(lookup_b[c], idx_b)
    end
  end

  local lookup_a = {}
  for idx_a, text in ipairs(lines_a) do
    local c = clean_compare_text(text)
    if c ~= "" then
      lookup_a[c] = lookup_a[c] or {}
      table.insert(lookup_a[c], idx_a)
    end
  end

  for i = 1, max_len do
    local line_a_idx = start_a + i - 1
    local line_b_idx = start_b + i - 1
    local text_a = lines_a[i] and clean_compare_text(lines_a[i]) or nil
    local text_b = lines_b[i] and clean_compare_text(lines_b[i]) or nil

    if text_a and text_b then
      if text_a == text_b then
        map_a[line_a_idx] = "EQUAL"
        map_b[line_b_idx] = "EQUAL"
      else
        map_a[line_a_idx] = "MODIFIED"
        map_b[line_b_idx] = "MODIFIED"
      end
    elseif text_a and not text_b then
      if lookup_b[text_a] and #lookup_b[text_a] > 0 then
        map_a[line_a_idx] = "MODIFIED"
      else
        map_a[line_a_idx] = "DELETED"
      end
    elseif text_b and not text_a then
      if lookup_a[text_b] and #lookup_a[text_b] > 0 then
        map_b[line_b_idx] = "MODIFIED"
      else
        map_b[line_b_idx] = "UNMATCHED"
      end
    end
  end

  return map_a, map_b
end

-- =============================================================================
-- 🔤 ORDENADOR DE LINHAS ALFABÉTICO (STRIP-AWARE)
-- =============================================================================
local function sort_selected_lines()
  local view = core.active_view
  local doc = view and view.doc
  if not doc or not doc.has_selection or not doc:has_selection() then
    if core.log then core.log("⚠ [SORT] Nenhuma linha selecionada para ordenar.") end
    return
  end

  local l1, c1, l2, c2 = doc:get_selection(true)
  if l1 == l2 and c1 == c2 then
    if core.log then core.log("⚠ [SORT] Seleção vazia. Selecione ao menos 2 linhas.") end
    return
  end

  local lines_to_sort = {}
  for line_idx = l1, l2 do
    local raw_text = (doc.lines[line_idx] or ""):gsub("[\r\n]+$", "")
    table.insert(lines_to_sort, {
      raw = raw_text,
      clean = clean_compare_text(raw_text):lower()
    })
  end

  table.sort(lines_to_sort, function(a, b)
    return a.clean < b.clean
  end)

  local sorted_text_lines = {}
  for _, item in ipairs(lines_to_sort) do
    table.insert(sorted_text_lines, item.raw)
  end

  local replacement = table.concat(sorted_text_lines, "\n")
  doc:remove(l1, 1, l2, #(doc.lines[l2] or ""))
  doc:insert(l1, 1, replacement)
  doc:set_selection(l1, 1, l2, #(sorted_text_lines[#sorted_text_lines] or "") + 1)
  core.redraw = true
  if core.log then
    core.log(string.format("✔ [SORT] %d linhas ordenadas com sucesso (Strip-Aware).", #sorted_text_lines))
  end
end

-- =============================================================================
-- 📐 ALINHADOR DE ATRIBUIÇÕES & COMENTÁRIOS (COM FIX DE OP_LEN)
-- =============================================================================
local function find_assignment_and_comment(line_text)
  if not line_text or line_text == "" then return nil end
  local in_str = false
  local str_char = nil
  local op_pos = nil
  local op_len = 1
  local com_pos = nil
  local len = #line_text
  local i = 1

  while i <= len do
    local c = line_text:sub(i, i)
    local next_c = line_text:sub(i + 1, i + 1)

    if not in_str then
      if c == '"' or c == "'" then
        in_str = true
        str_char = c
      elseif c == "-" and next_c == "-" then
        com_pos = i
        break
      elseif c == "#" then
        com_pos = i
        break
      elseif not op_pos then
        if (c == "+" or c == "-" or c == "*" or c == "/" or c == ".") and next_c == "=" then
          op_pos = i
          op_len = 2
          i = i + 1
        elseif c == "=" and next_c ~= "=" then
          op_pos = i
          op_len = 1
        elseif c == ":" and next_c ~= ":" and next_c ~= "=" then
          op_pos = i
          op_len = 1
        end
      end
    else
      if c == str_char and line_text:sub(i - 1, i - 1) ~= "\\" then
        in_str = false
        str_char = nil
      end
    end
    i = i + 1
  end

  if not op_pos and not com_pos then return nil end
  return {
    op_pos = op_pos,
    op_len = op_len or 1,
    com_pos = com_pos
  }
end

local function align_assignments_and_comments()
  local view = core.active_view
  local doc = view and view.doc
  if not doc or not doc.has_selection or not doc:has_selection() then
    if core.log then core.log("⚠ [ALIGN] Nenhuma linha selecionada para alinhar.") end
    return
  end

  local l1, c1, l2, c2 = doc:get_selection(true)
  local parsed_lines = {}
  local max_lhs_len = 0
  local has_any_op = false

  for line_idx = l1, l2 do
    local raw = (doc.lines[line_idx] or ""):gsub("[\r\n]+$", "")
    local info = find_assignment_and_comment(raw)
    local item = { raw = raw, info = info }

    if info and info.op_pos then
      has_any_op = true
      local o_len = info.op_len or 1
      local lhs = raw:sub(1, info.op_pos - 1):gsub("%s+$", "")
      local op = raw:sub(info.op_pos, info.op_pos + o_len - 1)
      local rhs = ""
      local com = ""

      if info.com_pos then
        rhs = raw:sub(info.op_pos + o_len, info.com_pos - 1):gsub("^%s+", ""):gsub("%s+$", "")
        com = raw:sub(info.com_pos):gsub("^%s+", "")
      else
        rhs = raw:sub(info.op_pos + o_len):gsub("^%s+", ""):gsub("%s+$", "")
      end

      item.lhs = lhs
      item.op = op
      item.rhs = rhs
      item.com = com
      if #lhs > max_lhs_len then max_lhs_len = #lhs end
    end
    table.insert(parsed_lines, item)
  end

  if not has_any_op then
    if core.log then core.log("⚠ [ALIGN] Nenhum operador de atribuição (=, :, etc.) encontrado na seleção.") end
    return
  end

  local aligned_lines = {}
  for _, item in ipairs(parsed_lines) do
    if item.info and item.info.op_pos then
      local padding = string.rep(" ", max_lhs_len - #item.lhs)
      local line = string.format("%s%s %s %s", item.lhs, padding, item.op, item.rhs)
      if item.com and item.com ~= "" then
        line = line .. "  " .. item.com
      end
      table.insert(aligned_lines, line)
    else
      table.insert(aligned_lines, item.raw)
    end
  end

  local replacement = table.concat(aligned_lines, "\n")
  doc:remove(l1, 1, l2, #(doc.lines[l2] or ""))
  doc:insert(l1, 1, replacement)
  doc:set_selection(l1, 1, l2, #(aligned_lines[#aligned_lines] or "") + 1)
  core.redraw = true
  if core.log then
    core.log(string.format("✔ [ALIGN] %d linhas alinhadas em coluna perfeitamente.", #aligned_lines))
  end
end

-- =============================================================================
-- 🔍 DISPARADOR DO COMPARADOR (SIDE-BY-SIDE HIGHLIGHT)
-- =============================================================================
local function compare_with_opposite_panel()
  local view_a = core.active_view
  local doc_a = view_a and view_a.doc
  if not doc_a or not doc_a.has_selection or not doc_a:has_selection() then
    if core.log then core.log("⚠ [DIFF] Selecione um bloco de texto no painel ativo para comparar.") end
    return
  end

  local view_b = get_opposite_panel()
  if not view_b or not view_b.doc then
    if core.log then core.log("⚠ [DIFF] Nenhum painel oposto ativo encontrado para comparação.") end
    return
  end
  local doc_b = view_b.doc

  local l1_a, _, l2_a, _ = doc_a:get_selection(true)
  local lines_a = {}
  for l = l1_a, l2_a do
    table.insert(lines_a, doc_a.lines[l] or "")
  end

  local l1_b, l2_b
  local lines_b = {}
  if doc_b.has_selection and doc_b:has_selection() then
    local b_l1, _, b_l2, _ = doc_b:get_selection(true)
    l1_b, l2_b = b_l1, b_l2
    for l = l1_b, l2_b do
      table.insert(lines_b, doc_b.lines[l] or "")
    end
    if core.log then core.log("🔍 [DIFF] Comparando seleção A vs seleção B.") end
  else
    l1_b, l2_b = find_most_similar_block(lines_a, doc_b)
    for l = l1_b, l2_b do
      table.insert(lines_b, doc_b.lines[l] or "")
    end
    if core.log then
      core.log(string.format("🔍 [DIFF] Bloco similar localizado no Painel B (Linhas %d a %d | %.2fms).",
        l1_b, l2_b, ComparatorState.telemetry.last_latency_ms))
    end
  end

  local diff_map_a, diff_map_b = compute_npp_diff(lines_a, lines_b, l1_a, l1_b)
  ComparatorState.active = true
  ComparatorState.doc_a = doc_a
  ComparatorState.doc_b = doc_b
  ComparatorState.lines_a = diff_map_a
  ComparatorState.lines_b = diff_map_b
  ComparatorState.telemetry.comparisons_count = ComparatorState.telemetry.comparisons_count + 1

  core.redraw = true
end

local function clear_diff_highlights()
  ComparatorState.active = false
  ComparatorState.doc_a = nil
  ComparatorState.doc_b = nil
  ComparatorState.lines_a = {}
  ComparatorState.lines_b = {}
  core.redraw = true
  if core.log then core.log("🧹 [DIFF] Realces de comparação limpos.") end
end

-- =============================================================================
-- 🖌️ HOOKS VISUAIS DOCVIEW (O(1) DRAW OVERLAY)
-- =============================================================================
local original_draw_line_gutter = DocView.draw_line_gutter
function DocView:draw_line_gutter(line_idx, x, y, width)
  local res = original_draw_line_gutter and original_draw_line_gutter(self, line_idx, x, y, width) or 0
  if ComparatorState.active and self.doc then
    local status = nil
    if self.doc == ComparatorState.doc_a then
      status = ComparatorState.lines_a[line_idx]
    elseif self.doc == ComparatorState.doc_b then
      status = ComparatorState.lines_b[line_idx]
    end

    if status and NPP_DIFF_THEMES[status] then
      local theme = NPP_DIFF_THEMES[status]
      local dot_size = 6
      local line_h = self.get_line_height and self:get_line_height() or 16
      local dot_x = x + width - dot_size - 3
      local dot_y = y + (line_h - dot_size) / 2
      draw_rect_safe(dot_x, dot_y, dot_size, dot_size, theme.color)
    end
  end
  return res
end

local original_draw_line_body = DocView.draw_line_body
function DocView:draw_line_body(line_idx, x, y)
  if ComparatorState.active and self.doc then
    local status = nil
    if self.doc == ComparatorState.doc_a then
      status = ComparatorState.lines_a[line_idx]
    elseif self.doc == ComparatorState.doc_b then
      status = ComparatorState.lines_b[line_idx]
    end

    if status and NPP_DIFF_THEMES[status] then
      local theme = NPP_DIFF_THEMES[status]
      local line_h = self.get_line_height and self:get_line_height() or 16
      draw_rect_safe(x, y, self.size.x, line_h, theme.tint)
      draw_rect_safe(x, y, 2, line_h, theme.color)
    end
  end
  return original_draw_line_body(self, line_idx, x, y)
end

-- =============================================================================
-- ⌨️ COMANDOS & KEYMAPS ATUALIZADOS
-- =============================================================================
command.add("core.docview", {
  ["doxoade:sort-selected-lines-alpha"] = function()
    sort_selected_lines()
  end,
  ["doxoade:align-assignments-and-comments"] = function()
    align_assignments_and_comments()
  end,
  ["doxoade:compare-selection-with-opposite-panel"] = function()
    compare_with_opposite_panel()
  end,
  ["doxoade:clear-diff-highlights"] = function()
    clear_diff_highlights()
  end,
})

keymap.add {
  ["alt+s"]            = "doxoade:sort-selected-lines-alpha",
  --["ctrl+alt+s"]       = "doxoade:sort-selected-lines-alpha",
  --["alt+="]            = "doxoade:align-assignments-and-comments",
  ["ctrl+alt+j"]       = "doxoade:align-assignments-and-comments",
  --["ctrl+alt+c"]       = "doxoade:compare-selection-with-opposite-panel",
  ["ctrl+alt+shift+j"] = "doxoade:compare-selection-with-opposite-panel",
  --["ctrl+alt+x"]       = "doxoade:clear-diff-highlights",
  ["ctrl+alt+shift+-"] = "doxoade:clear-diff-highlights",
}
