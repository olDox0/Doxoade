-- doxoade/commands/lite_xl_systems/template/14_doxnote_panel.lua
-- =============================================================================
-- 14. DOXOADE NOTE & AGENDA TASK HUB (INTEGRAÇÃO NATIVA COM DOXOADE NOTE)
-- =============================================================================
local core = require "core"
local common = require "core.common"
local command = require "core.command"
local keymap = require "core.keymap"
local DocView = require "core.docview"

-- 🛠️ Resolução de Diretórios do Projeto e do Note
local function get_project_root()
  if core.project_directories and #core.project_directories > 0 then
    local p = core.project_directories[1]
    return tostring(type(p) == "table" and (p.path or p.name) or p)
  end
  return "."
end

local function get_note_dir()
  local root = get_project_root()
  local doxoade_dir = root .. PATHSEP .. ".doxoade"
  local note_dir = doxoade_dir .. PATHSEP .. "note"
  pcall(function() system.mkdir(doxoade_dir) end)
  pcall(function() system.mkdir(note_dir) end)
  return note_dir
end

-- 📐 Gerador de ID Curto (Base36 - 5 chars no padrão do agenda.py)
local function generate_task_id()
  local chars = "0123456789abcdefghijklmnopqrstuvwxyz"
  local id = ""
  for _ = 1, 5 do
    local r = math.random(1, #chars)
    id = id .. chars:sub(r, r)
  end
  return id
end

-- 📅 Parser de Datas Relativas (+1d, +1w, amanha, hoje, YYYY-MM-DD)
local function parse_when_date(str)
  local s = tostring(str or ""):lower():gsub("^%s*", ""):gsub("%s*$", "")
  local now = os.time()
  local one_day = 86400

  if s == "" or s == "hoje" or s == "today" then
    return os.date("%Y-%m-%d", now)
  end
  if s == "amanha" or s == "amanhã" or s == "tomorrow" or s == "+1d" then
    return os.date("%Y-%m-%d", now + one_day)
  end

  local days = s:match("^%+(%d+)d$")
  if days then
    return os.date("%Y-%m-%d", now + (tonumber(days) * one_day))
  end

  local weeks = s:match("^%+(%d+)w$")
  if weeks then
    return os.date("%Y-%m-%d", now + (tonumber(weeks) * 7 * one_day))
  end

  local y, m, d = s:match("^(%d%d%d%d)[%-%/.](%d%d)[%-%/.](%d%d)$")
  if y and m and d then
    return string.format("%04d-%02d-%02d", tonumber(y), tonumber(m), tonumber(d))
  end

  return os.date("%Y-%m-%d", now)
end

-- 🔍 Coleta de Todas as Tarefas de Todas as Notas (.md)
local function collect_all_tasks()
  local note_dir = get_note_dir()
  local tasks = {}
  local files = system.list_dir(note_dir) or {}
  local today = os.date("%Y-%m-%d")

  for _, fn in ipairs(files) do
    if fn:match("%.md$") and not fn:match("^%.") then
      local fpath = note_dir .. PATHSEP .. fn
      local f = io.open(fpath, "r")
      if f then
        local line_no = 1
        for line in f:lines() do
          local done_mark, date_str, rest = line:match("^%s*%[([%sxX])%]%s*(%d%d%d%d[%-%/.%s]%d%d[%-%/.%s]%d%d)%s*(.*)$")
          if done_mark and date_str then
            local iso_date = parse_when_date(date_str)
            local is_done = (done_mark:lower() == "x")
            local tid = rest:match("%^id:(%w+)")
            local clean_text = rest:gsub("%^id:%w+", ""):gsub("^%s*", ""):gsub("%s*$", "")

            local category = "future"
            if is_done then
              category = "done"
            elseif iso_date < today then
              category = "overdue"
            elseif iso_date == today then
              category = "today"
            else
              category = "upcoming"
            end

            table.insert(tasks, {
              file = fn,
              path = fpath,
              line = line_no,
              done = is_done,
              date = iso_date,
              id = tid or ("L" .. line_no),
              text = clean_text,
              category = category,
              raw_line = line
            })
          end
          line_no = line_no + 1
        end
        f:close()
      end
    end
  end
  return tasks
end

-- 📑 Renderizador da Visualização Unificada de Agenda
local function generate_agenda_markdown()
  local tasks = collect_all_tasks()
  local today = os.date("%Y-%m-%d")

  local buckets = {
    today = {},
    overdue = {},
    upcoming = {},
    done = {}
  }

  for _, t in ipairs(tasks) do
    if t.done then
      table.insert(buckets.done, t)
    elseif t.category == "today" then
      table.insert(buckets.today, t)
    elseif t.category == "overdue" then
      table.insert(buckets.overdue, t)
    else
      table.insert(buckets.upcoming, t)
    end
  end

  local out = {
    "================================================================================",
    "          ⏰ DOXOADE AGENDA & TASK HUB — Visão Unificada de Tarefas",
    "================================================================================",
    string.format("[ Projeto: %s | Data: %s ]\n", get_project_root(), today),
    "## ⭐ HOJE (TODAY)"
  }

  if #buckets.today == 0 then
    table.insert(out, "  (Nenhuma tarefa agendada para hoje)")
  else
    for _, t in ipairs(buckets.today) do
      table.insert(out, string.format("  - [ ] %s | (%s:%d) %s ^id:%s", t.date, t.file, t.line, t.text, t.id))
    end
  end

  table.insert(out, "\n## 🔴 [!] VENCIDAS (OVERDUE)")
  if #buckets.overdue == 0 then
    table.insert(out, "  (Nenhuma tarefa vencida pendente)")
  else
    for _, t in ipairs(buckets.overdue) do
      table.insert(out, string.format("  - [!] %s | (%s:%d) %s ^id:%s", t.date, t.file, t.line, t.text, t.id))
    end
  end

  table.insert(out, "\n## 🟡 [>] PRÓXIMAS & FUTURAS (UPCOMING)")
  if #buckets.upcoming == 0 then
    table.insert(out, "  (Nenhuma tarefa futura cadastrada)")
  else
    for _, t in ipairs(buckets.upcoming) do
      table.insert(out, string.format("  - [>] %s | (%s:%d) %s ^id:%s", t.date, t.file, t.line, t.text, t.id))
    end
  end

  table.insert(out, "\n## 🟢 [x] CONCLUÍDAS (RECENT DONE)")
  if #buckets.done == 0 then
    table.insert(out, "  (Nenhuma tarefa concluída)")
  else
    for i = math.max(1, #buckets.done - 10), #buckets.done do
      local t = buckets.done[i]
      table.insert(out, string.format("  - [x] %s | (%s:%d) %s", t.date, t.file, t.line, t.text))
    end
  end

  table.insert(out, "\n================================================================================")
  return table.concat(out, "\n")
end

-- ═══════════════════════════════════════════════════════════
-- COMANDOS DOXOADE NOTE & AGENDA
-- ═══════════════════════════════════════════════════════════
command.add(nil, {
  -- 1. Abre a Agenda Unificada no Painel Direito
  ["doxoade:open-agenda-view"] = function()
    local note_dir = get_note_dir()
    local agenda_file = note_dir .. PATHSEP .. ".agenda_view.md"
    local content = generate_agenda_markdown()

    local f = io.open(agenda_file, "w")
    if f then
      f:write(content)
      f:close()
    end

    local doc = core.open_doc(agenda_file)
    core.root_view:open_doc(doc)
    core.log("Agenda Doxoade sincronizada e aberta.")
  end,

  -- 2. Adicionar Lembrete Rápido com Data
  ["doxoade:quick-add-task"] = function()
    core.command_view:enter("Descrição da Tarefa", {
      submit = function(task_text)
        if not task_text or not task_text:match("%S") then return end

        core.command_view:enter("Data do Lembrete (+1d, +3d, +1w, hoje, amanha, YYYY-MM-DD)", {
          submit = function(when_input)
            local when_iso = parse_when_date(when_input)
            local note_dir = get_note_dir()
            local target_file = note_dir .. PATHSEP .. "tarefas.md"
            local tid = generate_task_id()
            local task_line = string.format("- [ ] %s ^id:%s %s\n", when_iso, tid, task_text)

            local f = io.open(target_file, "a")
            if f then
              f:write(task_line)
              f:close()
            end

            core.log(string.format("Tarefa agendada [%s]: %s (id: %s)", when_iso, task_text, tid))
            command.perform("doxoade:open-agenda-view")
          end
        })
      end
    })
  end,

  -- 3. Marcar Tarefa como Concluída [x] Interativamente
  ["doxoade:mark-task-done"] = function()
    local tasks = collect_all_tasks()
    local open_tasks = {}
    local labels = {}
    local map = {}

    for _, t in ipairs(tasks) do
      if not t.done then
        local label = string.format("[%s] %s (%s) ^id:%s", t.date, t.text, t.file, t.id)
        table.insert(labels, label)
        map[label] = t
      end
    end

    if #labels == 0 then
      core.log("Parabéns! Nenhuma tarefa pendente no momento.")
      return
    end

    core.command_view:enter("Selecione a Tarefa para Marcar como Concluída [x]", {
      submit = function(selected_label)
        local t = map[selected_label]
        if t and t.path then
          local lines = {}
          local f = io.open(t.path, "r")
          if f then
            for line in f:lines() do
              table.insert(lines, line)
            end
            f:close()
          end

          if lines[t.line] then
            lines[t.line] = lines[t.line]:gsub("%[%s*%]", "[x]")
            local out_f = io.open(t.path, "w")
            if out_f then
              out_f:write(table.concat(lines, "\n") .. "\n")
              out_f:close()
            end
            core.log("✔ Concluída [x]: " .. t.text)
            command.perform("doxoade:open-agenda-view")
          end
        end
      end,
      suggest = function(text)
        return common.fuzzy_match(labels, text)
      end
    })
  end,

  -- 4. Criar Nova Nota Markdown (.md)
  ["doxoade:new-note-interactive"] = function()
    core.command_view:enter("Nome da Nova Nota (ex: reuniao, arquitetura, ideias)", {
      submit = function(name)
        if not name or not name:match("%S") then return end
        local clean_name = name:gsub("[^%w%-_]", "_") .. ".md"
        local note_dir = get_note_dir()
        local note_path = note_dir .. PATHSEP .. clean_name

        local f = io.open(note_path, "a")
        if f then
          f:write(string.format("# 📝 %s\n\nCriado em: %s\n\n", name, os.date("%Y-%m-%d %H:%M:%S")))
          f:close()
        end

        local doc = core.open_doc(note_path)
        core.root_view:open_doc(doc)
        core.log("Nota criada e aberta: " .. clean_name)
      end
    })
  end,

  -- 5. Listar e Abrir Qualquer Nota Existente
  ["doxoade:list-open-notes"] = function()
    local note_dir = get_note_dir()
    local files = system.list_dir(note_dir) or {}
    local md_files = {}

    for _, fn in ipairs(files) do
      if fn:match("%.md$") and not fn:match("^%.") then
        table.insert(md_files, fn)
      end
    end

    if #md_files == 0 then
      core.log("Nenhuma nota encontrada. Crie uma com [Nova Nota].")
      return
    end

    core.command_view:enter("Selecione a Nota para Abrir", {
      submit = function(fn)
        if fn and fn ~= "" then
          local note_path = note_dir .. PATHSEP .. fn
          local doc = core.open_doc(note_path)
          core.root_view:open_doc(doc)
          core.log("Nota aberta: " .. fn)
        end
      end,
      suggest = function(text)
        return common.fuzzy_match(md_files, text)
      end
    })
  end,

  -- 🌟 HUB PRINCIPAL DO NOTE (Disparado pelo botão [📝 Note] da Status Bar)
  ["doxoade:note-hub-menu"] = function()
    local options = {
      "⏰ [1] Agenda Unificada (Visualizar Tarefas & Prazos)",
      "➕ [2] Adicionar Lembrete Rápido (+1d, +1w, data)",
      "✔️ [3] Concluir Tarefa [x]",
      "📝 [4] Criar Nova Nota (.md)",
      "📚 [5] Abrir Nota Existente",
      "📋 [6] Fixar Dumppot na Direita (Scratchpad)",
    }

    core.command_view:enter("Doxoade Note & Task Hub", {
      submit = function(text)
        if text:find("%[1%]") or text:match("^1") then
          command.perform("doxoade:open-agenda-view")
        elseif text:find("%[2%]") or text:match("^2") then
          command.perform("doxoade:quick-add-task")
        elseif text:find("%[3%]") or text:match("^3") then
          command.perform("doxoade:mark-task-done")
        elseif text:find("%[4%]") or text:match("^4") then
          command.perform("doxoade:new-note-interactive")
        elseif text:find("%[5%]") or text:match("^5") then
          command.perform("doxoade:list-open-notes")
        elseif text:find("%[6%]") or text:match("^6") then
          command.perform("doxoade:open-pot-in-right-panel")
        end
      end,
      suggest = function(text)
        return common.fuzzy_match(options, text)
      end
    })
  end
})

-- ⌨️ Atalhos Globais do Note
keymap.add {
  ["ctrl+alt+m"] = "doxoade:note-hub-menu",
  ["ctrl+alt+a"] = "doxoade:open-agenda-view",
}
