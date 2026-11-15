-- doxoade/commands/lite_xl_systems/template/32_backup_timeline.lua
--[[
🕰️ BACKUP TIMELINE & DIFF ENGINE (F2.2 — Camada B, V1.0)
- Alt+Z: timeline de backups do arquivo ativo (snapshots da Camada A).
- Enter num snapshot: diff inline (amarelo = difere do backup) + dossiê
  unified .md aberto em aba com a história completa (+ / - / ~).
- Alt+Shift+B: restaura o backup ativo com guard Ma'at (snapshot
  pre-restore) e undo nativo (Ctrl+Z reverte a restauração).
- Alt+Shift+Z: fecha o diff inline.
Diff Lua puro: trim prefixo/sufixo + LCS fatiado (yield a cada 50 linhas)
com teto de 300 linhas no miolo; acima disso, modo bloco sinalizado.
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = require "core"
local command = require "core.command"
local keymap = require "core.keymap"
local common = require "core.common"

local FB = rawget(_G, "DOXOADE_FILE_BACKUP")
if not FB then
  if core.log then core.log("⚠ [BACKUP-TL] Camada A (31_file_backup) ausente — timeline desativada.") end
  return
end

local MAX_MID = 300
local MAX_BYTES = 2 * 1024 * 1024
local CONTEXT = 3
local MD_BUDGET = 800

local TL = { doc = nil, item = nil, computing = false }
rawset(_G, "_DOXOADE_BACKUP_TIMELINE", TL)

-- ── Utilidades ────────────────────────────────────────────────
local function clean_line(l)
  return (tostring(l):gsub("[\r\n]+$", ""))
end

local function split_lines(content)
  local out, pos = {}, 1
  while true do
    local nl = content:find("\n", pos, true)
    if not nl then
      if pos <= #content then out[#out + 1] = content:sub(pos):gsub("\r$", "") end
      break
    end
    out[#out + 1] = content:sub(pos, nl - 1):gsub("\r$", "")
    pos = nl + 1
  end
  return out
end

local function parse_stamp(stamp)
  local y, mo, d, h, mi, s = stamp:match("^(%d%d%d%d)(%d%d)(%d%d)_(%d%d)(%d%d)(%d%d)$")
  if not y then return nil, stamp end
  return os.time({ year = tonumber(y), month = tonumber(mo), day = tonumber(d),
                   hour = tonumber(h), min = tonumber(mi), sec = tonumber(s) }),
         string.format("%s-%s-%s %s:%s:%s", y, mo, d, h, mi, s)
end

local function age_str(epoch)
  if not epoch then return "?" end
  local dt = math.max(0, os.time() - epoch)
  if dt < 90 then return string.format("%ds atrás", dt) end
  if dt < 5400 then return string.format("%dmin atrás", math.floor(dt / 60)) end
  if dt < 172800 then return string.format("%.1fh atrás", dt / 3600) end
  return string.format("%.1fd atrás", dt / 86400)
end

local function size_str(n)
  if not n then return "?" end
  if n < 1024 then return n .. " B" end
  if n < 1048576 then return string.format("%.1f KB", n / 1024) end
  return string.format("%.2f MB", n / 1048576)
end

-- ── Motor de Diff (trim + LCS fatiado) ────────────────────────
local function trim_common(a, b)
  local n, m = #a, #b
  local p = 0
  while p < n and p < m and a[p + 1] == b[p + 1] do p = p + 1 end
  local s = 0
  while s < (n - p) and s < (m - p) and a[n - s] == b[m - s] do s = s + 1 end
  return p, s
end

local function lcs_middle(a, a0, a1, b, b0, b1)
  local na, nb = a1 - a0 + 1, b1 - b0 + 1
  if na <= 0 and nb <= 0 then return {} end
  if na > MAX_MID or nb > MAX_MID then return nil end
  local dp = {}
  for i = 0, na do
    local row = {}
    for j = 0, nb do row[j] = 0 end
    dp[i] = row
  end
  for i = 1, na do
    local ai, prev, cur = a[a0 + i], dp[i - 1], dp[i]
    for j = 1, nb do
      if ai == b[b0 + j] then cur[j] = prev[j - 1] + 1
      else local u, l = prev[j], cur[j - 1]; cur[j] = (u >= l) and u or l end
    end
    if (i % 50) == 0 then coroutine.yield() end
  end
  local ops = {}
  local i, j = na, nb
  while i > 0 and j > 0 do
    if a[a0 + i] == b[b0 + j] then ops[#ops + 1] = { op = "same", i = a0 + i, j = b0 + j }; i, j = i - 1, j - 1
    elseif dp[i - 1][j] >= dp[i][j - 1] then ops[#ops + 1] = { op = "del", i = a0 + i }; i = i - 1
    else ops[#ops + 1] = { op = "ins", j = b0 + j }; j = j - 1 end
  end
  while i > 0 do ops[#ops + 1] = { op = "del", i = a0 + i }; i = i - 1 end
  while j > 0 do ops[#ops + 1] = { op = "ins", j = b0 + j }; j = j - 1 end
  local rev = {}
  for k = #ops, 1, -1 do rev[#rev + 1] = ops[k] end
  return rev
end

local function build_script(a, b)
  local p, s = trim_common(a, b)
  local script = {}
  for i = 1, p do script[#script + 1] = { op = "same", i = i, j = i } end
  local a0, a1, b0, b1 = p + 1, #a - s, p + 1, #b - s
  local mid = lcs_middle(a, a0, a1, b, b0, b1)
  local coarse = (mid == nil)
  if coarse then
    mid = {}
    for i = a0, a1 do mid[#mid + 1] = { op = "del", i = i } end
    for j = b0, b1 do mid[#mid + 1] = { op = "ins", j = j } end
  end
  for _, o in ipairs(mid) do script[#script + 1] = o end
  for i = 1, s do script[#script + 1] = { op = "same", i = #a - s + i, j = #b - s + i } end
  return script, coarse
end

local function render_unified(script, a, b, coarse)
  local flat, maps_a = {}, {}
  local counts = { same = 0, mod = 0, new = 0, gone = 0 }
  local k = 1
  while k <= #script do
    local o = script[k]
    if o.op == "same" then
      flat[#flat + 1] = { mark = " ", text = a[o.i] }
      counts.same = counts.same + 1
      k = k + 1
    else
      local dels, inss = {}, {}
      while k <= #script and script[k].op ~= "same" do
        if script[k].op == "del" then dels[#dels + 1] = script[k].i
        else inss[#inss + 1] = script[k].j end
        k = k + 1
      end
      local pair = math.min(#dels, #inss)
      counts.mod = counts.mod + pair
      counts.new = counts.new + (#dels - pair)
      counts.gone = counts.gone + (#inss - pair)
      for t = 1, pair do
        flat[#flat + 1] = { mark = "-", text = b[inss[t]] }
        flat[#flat + 1] = { mark = "+", text = a[dels[t]] }
        maps_a[dels[t]] = "MODIFIED"
      end
      for t = pair + 1, #dels do
        flat[#flat + 1] = { mark = "+", text = a[dels[t]] }
        maps_a[dels[t]] = "MODIFIED"
      end
      for t = pair + 1, #inss do
        flat[#flat + 1] = { mark = "-", text = b[inss[t]] }
      end
    end
  end
  local n = #flat
  local pa, pb = {}, {}
  local ca, cb = 0, 0
  for i = 1, n do
    pa[i], pb[i] = ca, cb
    local m = flat[i].mark
    if m == " " then ca, cb = ca + 1, cb + 1
    elseif m == "+" then ca = ca + 1
    else cb = cb + 1 end
  end
  local change_pos = {}
  for i = 1, n do if flat[i].mark ~= " " then change_pos[#change_pos + 1] = i end end
  local md, budget = {}, MD_BUDGET
  if #change_pos == 0 then
    md[#md + 1] = "(nenhuma diferença — arquivo idêntico ao backup)"
  else
    local ci = 1
    while ci <= #change_pos and budget > 0 do
      local c1, c2 = change_pos[ci], change_pos[ci]
      while ci + 1 <= #change_pos and change_pos[ci + 1] - c2 <= 2 * CONTEXT + 1 do
        ci = ci + 1; c2 = change_pos[ci]
      end
      local h1, h2 = math.max(1, c1 - CONTEXT), math.min(n, c2 + CONTEXT)
      local a_len, b_len = 0, 0
      for i = h1, h2 do
        local m = flat[i].mark
        if m == " " then a_len, b_len = a_len + 1, b_len + 1
        elseif m == "+" then a_len = a_len + 1
        else b_len = b_len + 1 end
      end
      md[#md + 1] = string.format("@@ -%d,%d +%d,%d @@", pb[h1] + 1, b_len, pa[h1] + 1, a_len)
      for i = h1, h2 do
        md[#md + 1] = flat[i].mark .. flat[i].text
        budget = budget - 1
        if budget <= 0 then md[#md + 1] = "... (dossiê truncado em 800 linhas de mudança)"; break end
      end
      ci = ci + 1
    end
  end
  if coarse then
    table.insert(md, 1, "⚠ Miolo > 300 linhas: LCS fino substituído por comparação em bloco.")
  end
  return maps_a, counts, md
end

local function write_dossier(doc, item, md, counts)
  local bdir, key = FB.dir_for(doc), FB.key_for(doc)
  if not bdir or not key then return nil end
  local ddir = bdir .. "/_diffs"
  pcall(function() system.mkdir(ddir) end)
  local path = ddir .. "/" .. key .. "." .. item.stamp .. ".diff.md"
  local _, pretty = parse_stamp(item.stamp)
  local head = {
    "# 🕰️ BACKUP DIFF — " .. (doc.filename:match("[^/\\]+$") or doc.filename),
    "",
    "- **Atual (A/new):** " .. #doc.lines .. " linhas",
    "- **Backup (B/old):** #" .. item.seq .. " · " .. pretty .. " · " .. size_str(item.size),
    string.format("- **Resumo:** ~%d modificadas · +%d novas no atual · -%d sumiram · %d iguais",
      counts.mod, counts.new, counts.gone, counts.same),
    "- **Direção:** `-` estava no backup e sumiu · `+` é novo no atual · par -/+ = modificado",
    "",
    "```diff",
  }
  local all = {}
  for _, l in ipairs(head) do all[#all + 1] = l end
  for _, l in ipairs(md) do all[#all + 1] = l end
  all[#all + 1] = "```"
  local f = io.open(path, "w")
  if not f then return nil end
  f:write(table.concat(all, "\n"))
  f:flush(); f:close()
  return path
end

local function open_doc_safe(path)
  pcall(function()
    local d = core.open_doc(path)
    if not d then return end
    local opener = rawget(_G, "DOXOADE_OPEN_IN_NEW_TAB")
    if type(opener) == "function" then opener(d)
    elseif core.root_view and core.root_view.open_doc then core.root_view:open_doc(d) end
  end)
end

local function run_diff(doc, item)
  if TL.computing then
    core.log("⏳ [BACKUP-TL] Já computando um diff — aguarde.")
    return
  end
  TL.computing = true
  core.add_thread(function()
    local ok, err = pcall(function()
      local content = FB.read(item.path)
      if not content then error("backup ilegível: " .. item.path) end
      if #content > MAX_BYTES then error("backup > 2 MB — diff abortado por segurança") end
      local a, b = {}, split_lines(content)
      for i, l in ipairs(doc.lines) do a[i] = clean_line(l) end
      local script, coarse = build_script(a, b)
      local maps_a, counts, md = render_unified(script, a, b, coarse)
      local setv = rawget(_G, "DOXOADE_COMPARATOR_SET_VIRTUAL")
      if setv then setv(doc, maps_a, item.name) end
      local md_path = write_dossier(doc, item, md, counts)
      if md_path then open_doc_safe(md_path) end
      TL.doc, TL.item = doc, item
      local _, pretty = parse_stamp(item.stamp)
      core.log(string.format(
        "🕰️ [BACKUP-TL] Diff vs #%s (%s): ~%d mod · +%d novas · -%d sumiram · %d iguais%s",
        item.seq, pretty, counts.mod, counts.new, counts.gone, counts.same,
        coarse and " [coarse]" or ""))
    end)
    if not ok then core.log("⚠ [BACKUP-TL] " .. tostring(err)) end
    TL.computing = false
  end, doc)
end

-- ── Comandos ──────────────────────────────────────────────────
command.add("core.docview", {
  ["doxoade:backup-timeline"] = function()
    local doc = core.active_view and core.active_view.doc
    if not doc or not doc.filename then
      core.log("⚠ [BACKUP-TL] Nenhum arquivo ativo.")
      return
    end
    local items = FB.list_for(doc)
    if #items == 0 then
      core.log("🕰️ [BACKUP-TL] Sem backups deste arquivo ainda (salve uma vez para criar o primeiro).")
      return
    end
    local labels, map = {}, {}
    for _, it in ipairs(items) do
      local epoch, pretty = parse_stamp(it.stamp)
      local label = string.format("[#%s] %s · %s · %s", it.seq, pretty, size_str(it.size), age_str(epoch))
      labels[#labels + 1] = label
      map[label] = it
    end
    core.command_view:enter("🕰️ Backup Timeline — escolha o snapshot para diff:", {
      submit = function(sel)
        local it = map[sel]
        if not it then
          for lbl, item in pairs(map) do
            if lbl:find(sel, 1, true) then it = item; break end
          end
        end
        if not it then core.log("⚠ [BACKUP-TL] Snapshot não encontrado.") return end
        run_diff(doc, it)
      end,
      suggest = function(text) return common.fuzzy_match(labels, text) end,
    })
  end,

  ["doxoade:backup-restore-active"] = function()
    local doc = core.active_view and core.active_view.doc
    if not TL.item or not TL.doc or TL.doc ~= doc then
      core.log("⚠ [BACKUP-TL] Abra a timeline (Alt+Z) e escolha um snapshot antes de restaurar.")
      return
    end
    local it = TL.item
    local _, pretty = parse_stamp(it.stamp)
    core.command_view:enter(string.format(
      "⚠ Restaurar #%s (%s) sobre %s? Digite 's' para confirmar:",
      it.seq, pretty, (doc.filename:match("[^/\\]+$") or doc.filename)), {
      submit = function(ans)
        if not ans or ans:lower():sub(1, 1) ~= "s" then
          core.log("🕰️ [BACKUP-TL] Restauração cancelada.")
          return
        end
        local ok, err = pcall(function()
          FB.restore_guard(doc)
          local content = FB.read(it.path)
          if not content then error("backup ilegível") end
          local last = #doc.lines
          if last >= 1 then
            doc:remove(1, 1, last, #doc.lines[last] + 1)
          end
          doc:insert(1, 1, content)
          doc:save()
        end)
        if ok then
          local clr = rawget(_G, "DOXOADE_COMPARATOR_CLEAR")
          if clr then clr() end
          TL.doc, TL.item = nil, nil
          core.redraw = true
          core.log(string.format("✔ [BACKUP-TL] Restaurado #%s e salvo. Ctrl+Z desfaz a restauração.", it.seq))
        else
          core.log("⚠ [BACKUP-TL] Falha na restauração: " .. tostring(err))
        end
      end,
    })
  end,

  ["doxoade:clear-backup-diff"] = function()
    local clr = rawget(_G, "DOXOADE_COMPARATOR_CLEAR")
    if clr then clr() end
    TL.doc, TL.item = nil, nil
    core.log("🧹 [BACKUP-TL] Diff de backup fechado.")
  end,
})

keymap.add({
  ["alt+z"] = "doxoade:backup-timeline",
  ["alt+shift+z"] = "doxoade:clear-backup-diff",
  ["alt+shift+b"] = "doxoade:backup-restore-active",
}, true)

if core.log then
  core.log("🕰️ [BACKUP-TL] Timeline & Diff Engine V1.0 registrado (Alt+Z / Alt+Shift+B / Alt+Shift+Z).")
end
