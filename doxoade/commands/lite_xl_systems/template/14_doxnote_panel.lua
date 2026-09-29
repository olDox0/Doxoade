-- doxoade/commands/lite_xl_systems/template/14_doxnote_panel.lua
--[[
  📝 DOXOADE UNIFIED NOTES & MESH ENGINE (V24.0 Sovereign Unification)
  - Unificação total: Shared Notes P2P (PC-A <-> PC-B) + Notas Locais do Projeto.
  - Auto-start seguro do daemon P2P (doxoade lan-git note service).
  - Recarregamento automático de buffer em tempo real quando o outro PC sincroniza.
  - Parent Walk idêntico ao Python filesystem.py para encontrar notas reais.
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = require "core"
local common = require "core.common"
local command = require "core.command"
local keymap = require "core.keymap"
local DocView = require "core.docview"
local Doc = require "core.doc"

local sep = PATHSEP or "/"

-- if core and core.nag_verify then
--   local orig_nag_verify = core.nag_verify
--   core.nag_verify = function(title, msg, ...)
--     if msg and (msg:find("shared_notes%.md") or msg:find("/%.doxoade/note/")) then
--       return false
--     end
--     return orig_nag_verify(title, msg, ...)
--   end
-- end

-- ═════════════════════════════════════════════════════════════════════════════
-- 1. LOCALIZAÇÃO E RESOLUÇÃO DE DIRETÓRIOS (PARENT WALK)
-- ═════════════════════════════════════════════════════════════════════════════

local function is_test_dir(p)
  local clean = tostring(p or ""):gsub("\\", "/"):lower()
  return clean:find("test_deploy") or clean:find("sandbox")
end

local function walk_up_project_root(start_path)
  if not start_path or start_path == "" then return nil end
  local cur = (system.absolute_path(start_path) or start_path):gsub("\\", "/"):gsub("/+$", "")

  local finfo = system.get_file_info(cur)
  if finfo and finfo.type == "file" then
    cur = cur:match("^(.*)/") or cur
  end

  for _ = 1, 15 do
    if not cur or cur == "" or cur:find("^[a-zA-Z]:/?$") or cur == "/" then break end
    if not is_test_dir(cur) then
      local toml = cur .. "/pyproject.toml"
      local git_dir = cur .. "/.git"
      local note_dir = cur .. "/.doxoade/note"
      if system.get_file_info(toml) or system.get_file_info(git_dir) or system.get_file_info(note_dir) then
        return cur
      end
    end
    local parent = cur:match("^(.*)/")
    if not parent or parent == cur then break end
    cur = parent
  end
  return nil
end

local function resolve_all_note_directories()
  local dirs = {}
  local seen = {}

  local function register_dir(d_path)
    if not d_path or d_path == "" then return end
    local clean = (system.absolute_path(d_path) or d_path):gsub("\\", "/"):gsub("/+$", "")
    if not seen[clean:lower()] and not is_test_dir(clean) then
      seen[clean:lower()] = true
      pcall(system.mkdir, clean)
      table.insert(dirs, clean)
    end
  end

  local user_dir = USERDIR or "."
  local py_anchor = user_dir .. sep .. ".doxoade" .. sep .. "python_path.txt"
  local finfo = system.get_file_info(py_anchor)
  if finfo and finfo.type == "file" then
    local f = io.open(py_anchor, "r")
    if f then
      local py_exe = f:read("*l") or ""
      f:close()
      py_exe = py_exe:gsub("[\r\n]", "")
      if py_exe ~= "" then
        local pdir = py_exe:match("^(.*)[/\\]Scripts[/\\]") or py_exe:match("^(.*)[/\\]bin[/\\]") or py_exe:match("^(.*)[/\\]")
        if pdir then
          local proj_root = pdir:gsub("[/\\]+$", ""):match("^(.*)[/\\][%.%w_-]*venv$") or pdir:match("^(.*)[/\\]env$") or pdir
          local root_clean = walk_up_project_root(proj_root) or proj_root
          register_dir(root_clean .. "/.doxoade/note")
        end
      end
    end
  end

  local last_proj = user_dir .. sep .. ".doxoade" .. sep .. "last_project.txt"
  if system.get_file_info(last_proj) then
    local f = io.open(last_proj, "r")
    if f then
      local lp = f:read("*l") or ""
      f:close()
      if lp ~= "" then
        local root_clean = walk_up_project_root(lp) or lp
        register_dir(root_clean .. "/.doxoade/note")
      end
    end
  end

  if core.docs then
    for _, doc in ipairs(core.docs) do
      if doc.filename and not is_test_dir(doc.filename) then
        local found = walk_up_project_root(doc.filename)
        if found then register_dir(found .. "/.doxoade/note") end
      end
    end
  end

  if core.project_directories then
    for _, p in ipairs(core.project_directories) do
      local p_str = tostring(type(p) == "table" and (p.path or p.name) or p or "")
      if p_str ~= "" and not is_test_dir(p_str) then
        local found = walk_up_project_root(p_str) or p_str
        register_dir(found .. "/.doxoade/note")
      end
    end
  end

  register_dir(user_dir .. "/.doxoade/note")
  local home = os.getenv("USERPROFILE") or os.getenv("HOME")
  if home then
    register_dir(home:gsub("\\", "/") .. "/.doxoade/note")
  end

  return dirs
end

local function get_primary_note_dir()
  local dirs = resolve_all_note_directories()
  return dirs[1] or ((USERDIR or ".") .. "/.doxoade/note")
end

local function get_shared_note_path()
  local home = os.getenv("USERPROFILE") or os.getenv("HOME") or "."
  return (home .. sep .. ".doxoade" .. sep .. "shared_notes.md"):gsub("\\", "/")
end

-- ═════════════════════════════════════════════════════════════════════════════
-- 2. GERENCIAMENTO AUTÔNOMO DA MALHA P2P (DOXNOTE MESH)
-- ═════════════════════════════════════════════════════════════════════════════

local function is_mesh_service_alive()
  local home = os.getenv("USERPROFILE") or os.getenv("HOME") or "."
  local state_path = home .. sep .. ".doxoade" .. sep .. "mesh_state.json"
  local finfo = system and system.get_file_info and system.get_file_info(state_path)
  if finfo and finfo.type == "file" then
    local f = io.open(state_path, "r")
    if f then
      local data = f:read("*a") or ""
      f:close()
      local updated_at = tonumber(data:match('"updated_at":%s*([%d%.]+)')) or 0
      local status = data:match('"status":%s*"([^"]+)"')
      if (os.time() - updated_at) < 6 and status ~= "offline" then
        return true, status, data:match('"peer_name":%s*"([^"]+)"')
      end
    end
  end
  return false, "offline", nil
end

local function launch_mesh_service_safe()
  local user_dir = USERDIR or "."
  local py_anchor = user_dir .. sep .. ".doxoade" .. sep .. "python_path.txt"
  local py_exe = "python"
  local finfo = system.get_file_info(py_anchor)
  if finfo and finfo.type == "file" then
    local f = io.open(py_anchor, "r")
    if f then
      local l = f:read("*l") or ""
      f:close()
      if l ~= "" then py_exe = l:gsub("[\r\n]", "") end
    end
  end

  -- Dispara o daemon em segundo plano com a flag -d (desacoplada)
  local cmd = string.format('start /b "" "%s" -m doxoade lan-git note service -d', py_exe)
  pcall(system.exec, cmd)
end

-- 🚀 AUTO-IGNIÇÃO: Dispara a verificação 1 segundo após o boot do Doxly
if core and core.add_thread then
  core.add_thread(function()
    coroutine.yield(1.0)
    -- Só dispara se o serviço ainda não estiver respondendo no estado
    local alive = is_mesh_service_alive()
    if not alive then
      launch_mesh_service_safe()
    end
  end)
end

-- ═════════════════════════════════════════════════════════════════════════════
-- 3. SENTINELA IMORTAL COM GUARDA DE SALVAMENTO (ZERO CRASH / BIDIRECIONAL)
-- ═════════════════════════════════════════════════════════════════════════════

local function calc_clean_hash(str)
  if not str or str == "" then return 0 end
  local clean = str:gsub("\r\n", "\n"):gsub("\r", "\n"):gsub("%s+$", "")
  local h = 5381
  for i = 1, #clean do
    h = ((h * 33) + clean:byte(i)) % 2147483647
  end
  return h
end

local _last_local_save_time = 0

local _shared_doc_mtimes = {}
local _last_known_disk_hash = {}

-- 🛡️ REGRA 1: Ao salvar com Ctrl+S, o Doxly grava no disco e guarda o hash dele mesmo
if Doc and Doc.save then
  local orig_doc_save = Doc.save
  Doc.save = function(self, ...)
    local res = orig_doc_save(self, ...)
    if self.filename and (self.filename:find("shared_notes%.md$") or self.filename:find("shared_notes%.txt$")) then
      pcall(function()
        local f = io.open(self.filename, "r")
        if f then
          local text = f:read("*a")
          f:close()
          _last_known_disk_hash[self.filename] = calc_clean_hash(text)
        end
      end)
    end
    return res
  end
end

-- 🛡️ REGRA 2: Corrotina "CHECK ➔ ATUALIZA" (Respeito sagrado ao usuário digitando)
if core and core.add_thread then
  core.add_thread(function()
    while true do
      coroutine.yield(1.5)
      
      local is_enabled = rawget(_G, "_DOXOADE_NOTE_SYNC_ACTIVE") == true
      if is_enabled then
        pcall(function()
          for _, doc in ipairs(core.docs or {}) do
            if doc.filename then
              local fn_clean = doc.filename:gsub("\\", "/"):lower()
              if fn_clean:find("shared_notes%.md$") or fn_clean:find("shared_notes%.txt$") then
                
                -- Se você está digitando (buffer dirty), NUNCA sobrescreva!
                if not doc:is_dirty() then
                  local finfo = system.get_file_info and system.get_file_info(doc.filename)
                  if finfo and finfo.type == "file" and (finfo.size or 0) > 0 then
                    
                    local f = io.open(doc.filename, "r")
                    if f then
                      local disk_raw = f:read("*a")
                      f:close()
                      
                      if disk_raw and disk_raw ~= "" then
                        local disk_hash = calc_clean_hash(disk_raw)
                        
                        -- Inicializa no boot
                        if not _last_known_disk_hash[doc.filename] then
                          _last_known_disk_hash[doc.filename] = disk_hash
                        
                        -- SÓ RECARREGA SE O DISCO REALMENTE MUDOU POR FORA (PELA REDE)
                        elseif disk_hash ~= _last_known_disk_hash[doc.filename] then
                          _last_known_disk_hash[doc.filename] = disk_hash
                          
                          local l1, c1, l2, c2 = 1, 1, 1, 1
                          if doc.get_selection then l1, c1, l2, c2 = doc:get_selection() end
                          
                          doc:remove(1, 1, #doc.lines, #doc.lines[#doc.lines] + 1)
                          doc:insert(1, 1, disk_raw)
                          doc:clean()
                          
                          if doc.set_selection then pcall(doc.set_selection, doc, l1, c1, l2, c2) end
                          
                          core.redraw = true
                          if core.log then core.log("⚡ [DOXNOTE] Nota sincronizada da rede com sucesso!") end
                        end
                      end
                    end
                  end
                end
              end
            end
          end
        end)
      end
    end
  end)
end

-- ═════════════════════════════════════════════════════════════════════════════
-- 4. COLETOR DE NOTAS E TAREFAS (COMPATIBILIDADE AGENDA.PY)
-- ═════════════════════════════════════════════════════════════════════════════

local function extract_note_preview(lines)
  for _, l in ipairs(lines) do
    local s = l:gsub("^%s+", ""):gsub("%s+$", "")
    if s ~= "" and not s:match("^#") and not s:match("^%-%-%-") then
      if #s > 48 then return s:sub(1, 48) .. "..." end
      return s
    end
  end
  return "(vazia)"
end

local function get_all_existing_notes()
  local notes = {}
  local seen = {}

  -- 1. Inclui o shared_notes.md global como primeira nota se existir
  local shared_path = get_shared_note_path()
  local shared_info = system.get_file_info(shared_path)
  if shared_info and shared_info.type == "file" then
    seen[shared_path:lower()] = true
    table.insert(notes, {
      filename = "shared_notes.md",
      title = "Notas Compartilhadas P2P (Malha LAN)",
      preview = "Bloco de notas global sincronizado entre máquinas",
      path = shared_path,
      origin = "Rede P2P",
      task_count = 0,
      mtime = shared_info.mtime or 0,
      is_shared = true
    })
  end

  -- 2. Coleta as notas locais de projeto (.doxoade/note/*.md)
  for _, dir in ipairs(resolve_all_note_directories()) do
    local info = system.get_file_info(dir)
    if info and info.type == "dir" then
      local files = system.list_dir(dir) or {}
      for _, fn in ipairs(files) do
        if (fn:match("%.md$") or fn:match("%.txt$")) and not fn:match("^%.") then
          local full_path = dir .. "/" .. fn
          local finfo = system.get_file_info(full_path)
          if finfo and finfo.type == "file" and not seen[full_path:lower()] then
            seen[full_path:lower()] = true

            local title = fn
            local task_count = 0
            local lines = {}
            local f = io.open(full_path, "r")
            if f then
              for line in f:lines() do
                table.insert(lines, line)
                if title == fn and line:match("^#+%s*(.+)") then
                  title = line:match("^#+%s*(.+)")
                end
                if line:match("%[%s*%]") then
                  task_count = task_count + 1
                end
              end
              f:close()
            end

            local proj_name = dir:match("([^/]+)/%.doxoade/note$") or "projeto"

            table.insert(notes, {
              filename = fn,
              title = title,
              preview = extract_note_preview(lines),
              path = full_path,
              dir = dir,
              origin = proj_name,
              task_count = task_count,
              mtime = finfo.mtime or 0,
              size = finfo.size or 0,
            })
          end
        end
      end
    end
  end

  table.sort(notes, function(a, b)
    if a.is_shared then return true end
    if b.is_shared then return false end
    return (a.mtime or 0) > (b.mtime or 0)
  end)
  return notes
end

local function generate_task_id()
  local chars = "0123456789abcdefghijklmnopqrstuvwxyz"
  local id = ""
  for _ = 1, 5 do
    local r = math.random(1, #chars)
    id = id .. chars:sub(r, r)
  end
  return id
end

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

local function collect_all_tasks()
  local tasks = {}
  local today = os.date("%Y-%m-%d")

  for _, n in ipairs(get_all_existing_notes()) do
    local f = io.open(n.path, "r")
    if f then
      local line_no = 1
      for line in f:lines() do
        local done_mark, date_str, rest = line:match("^%s*[%-%*]?%s*%[([%sxX])%]%s*(%d%d%d%d[%-%/.%s]%d%d[%-%/.%s]%d%d)%s*(.*)$")
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
            file = n.filename,
            path = n.path,
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

  return tasks
end

local function generate_agenda_markdown()
  local tasks = collect_all_tasks()
  local today = os.date("%Y-%m-%d")
  local buckets = { today = {}, overdue = {}, upcoming = {}, done = {} }

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
    string.format("[ Data: %s | Total de Tarefas: %d ]\n", today, #tasks),
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

  table.insert(out, "\n## 🟢 [x] CONCLUÍDAS RECENTES")
  if #buckets.done == 0 then
    table.insert(out, "  (Nenhuma tarefa concluída)")
  else
    for i = math.max(1, #buckets.done - 12), #buckets.done do
      local t = buckets.done[i]
      table.insert(out, string.format("  - [x] %s | (%s:%d) %s", t.date, t.file, t.line, t.text))
    end
  end

  table.insert(out, "\n================================================================================")
  return table.concat(out, "\n")
end

local function get_or_create_note_split()
  local function get_leaves(n, list)
    list = list or {}
    if not n then return list end
    if n.type == "leaf" and not n.locked then table.insert(list, n)
    elseif n.type ~= "leaf" then get_leaves(n.a, list); get_leaves(n.b, list) end
    return list
  end
  local leaves = get_leaves(core.root_view.root_node)
  if #leaves >= 2 then
    return leaves[#leaves]
  elseif #leaves == 1 then
    return leaves[1]:split("right")
  end
  return core.root_view.root_node:get_primary_node()
end

local function open_note_in_split(file_path, log_msg)
  local target_node = get_or_create_note_split()
  local doc = type(file_path) == "string" and core.open_doc(file_path) or file_path
  if not doc then return nil end

  for _, v in ipairs(target_node.views or {}) do
    if v and v.doc == doc then
      target_node.active_view = v
      core.set_active_view(v)
      core.redraw = true
      return v
    end
  end

  local ok_v, view = pcall(DocView, doc)
  if ok_v and view then
    if target_node.add_view then target_node:add_view(view) end
    core.set_active_view(view)
    if log_msg then core.log(log_msg) end
    core.redraw = true
    return view
  end
  return nil
end

-- ═════════════════════════════════════════════════════════════════════════════
-- 4. COMANDOS SOBERANOS DO SISTEMA DE NOTAS
-- ═════════════════════════════════════════════════════════════════════════════
command.add(nil, {
  -- 📂 ABRIR NOTA (SHARED OU LOCAL DO PROJETO)
  ["doxoade:open-note"] = function()
    local notes = get_all_existing_notes()
    if #notes == 0 then
      core.log("⚠ Nenhuma nota encontrada. Criando nova nota...")
      command.perform("doxoade:new-note-interactive")
      return
    end

    local labels = {}
    local path_map = {}

    for _, n in ipairs(notes) do
      local task_badge = (n.task_count and n.task_count > 0) and string.format(" [%d tarefas]", n.task_count) or ""
      local icon = n.is_shared and "🌐" or "📝"
      local label = string.format("%s %-18s %s — %q (%s)", icon, n.filename, task_badge, n.preview or "", n.origin or "")
      table.insert(labels, label)
      path_map[label] = n.path
    end

    core.command_view:enter("Abrir Nota (DoxNote Sovereign Hub)", {
      submit = function(selected)
        local target = path_map[selected]
        if not target then
          for lbl, p in pairs(path_map) do
            if lbl:lower():find(selected:lower(), 1, true) then
              target = p
              break
            end
          end
        end

        if target and system.get_file_info(target) then
          local doc = core.open_doc(target)
          if doc then
            core.root_view:open_doc(doc)
            core.log(string.format("📝 Aberto: %s", target:match("[^/]+$") or target))
          end
        else
          core.error(string.format("Nota não localizada: %s", tostring(selected)))
        end
      end,
      suggest = function(text)
        return common.fuzzy_match(labels, text)
      end
    })
  end,

  -- ➕ CRIAR NOVA NOTA INTERATIVA
  ["doxoade:new-note-interactive"] = function()
    core.command_view:enter("Nome da Nova Nota (ex: reuniao, arquitetura, sprint)", {
      submit = function(name)
        if not name or not name:match("%S") then return end
        local clean_name = name:gsub("[^%w%-_]", "_")
        if not clean_name:match("%.md$") and not clean_name:match("%.txt$") then
          clean_name = clean_name .. ".md"
        end

        local note_dir = get_primary_note_dir()
        local note_path = note_dir .. "/" .. clean_name

        if not system.get_file_info(note_path) then
          local f = io.open(note_path, "w")
          if f then
            f:write(string.format("# 📝 %s\n\nCriado em: %s\n\n", name, os.date("%Y-%m-%d %H:%M:%S")))
            f:close()
          end
        end

        local doc = core.open_doc(note_path)
        if doc then
          core.root_view:open_doc(doc)
          core.log("✔ Nova nota criada e aberta: " .. clean_name)
        end
      end
    })
  end,

  ["doxoade:lan-hub-menu"] = function()
    local cache = rawget(_G, "_DOXOADE_MESH_STATUS_CACHE") or { text = "Offline" }
    local options = {
      "[1] Iniciar Host Live Mirror (lan-git share --live)",
      "[2] Puxar do Host Remoto (lan-git pull --live -f)",
      "[3] Abrir shared_notes.md (Bloco Sincronizado)",
      "[4] Reiniciar Serviço Mesh P2P",
      "[5] Status da Rede: " .. tostring(cache.text)
    }

    core.command_view:enter("LAN-Git Live Control Hub", {
      submit = function(choice)
        local home_dir = os.getenv("USERPROFILE") or os.getenv("HOME") or "."
        local sep = PATHSEP or "/"

        if choice:find("%[1%]") then
          local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
          local shelf = rawget(_G, "_DOXOADE_SHELF_HUB")
          if shelf then shelf.visible = true; shelf.active_tab = "terminal" end
          if term then term:ensure_started(); term:execute_command("doxoade lan-git share --live") end
        elseif choice:find("%[2%]") then
          local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
          local shelf = rawget(_G, "_DOXOADE_SHELF_HUB")
          if shelf then shelf.visible = true; shelf.active_tab = "terminal" end
          if term then term:ensure_started(); term:execute_command("doxoade lan-git pull --live -f") end
        elseif choice:find("%[3%]") then
          local shared_path = home_dir .. sep .. ".doxoade" .. sep .. "shared_notes.md"
          local doc = core.open_doc(shared_path)
          if doc then core.root_view:open_doc(doc) end
        elseif choice:find("%[4%]") then
          launch_mesh_service_safe()
          core.log("⚡ [DOXNOTE MESH] Serviço P2P reiniciado.")
        end
      end,
      suggest = function(text) return common.fuzzy_match(options, text) end
    })
  end,

  -- 📋 MENU CENTRAL UNIFICADO: SHARED NOTES + NOTAS DO PROJETO + AGENDA
  -- 📋 MENU CENTRAL UNIFICADO: SHARED NOTES + NOTAS DO PROJETO + CONTROLE DE SYNC
  ["doxoade:note-hub-menu"] = function()
    local is_active = rawget(_G, "_DOXOADE_NOTE_SYNC_ACTIVE") == true
    local sync_toggle_label = is_active and "🛑 [1] Desativar Sincronização (Modo Local / Fundo Vermelho)"
                                         or "⚡ [1] Ativar Sincronização (Modo Rede / Fundo Verde)"

    local options = {
      sync_toggle_label,
      "📝 [2] Abrir shared_notes.md (Painel Dividido)",
      "📂 [3] Abrir Notas do Projeto (Painel Dividido)",
      "➕ [4] Criar Nova Nota no Projeto...",
      "⏰ [5] Ver Agenda & Tarefas Sincronizadas",
      "⚡ [6] Adicionar Tarefa Rápida (+1d, hoje...)",
      "✔️ [7] Marcar Tarefa Concluída [x]",
      "🔄 [8] Puxar do Host Remoto (lan-git pull --live -f)",
      "🚀 [9] Iniciar Host Live Mirror (lan-git share --live)"
    }

    core.command_view:enter("Shared Note Hub — Gestão de Notas & Sincronização", {
      submit = function(choice)
        local home_dir = os.getenv("USERPROFILE") or os.getenv("HOME") or "."
        local sep = PATHSEP or "/"
        local shared_path = home_dir .. sep .. ".doxoade" .. sep .. "shared_notes.md"

        -- 1. Alterna o estado da Sincronização (Muda a cor do Badge no Rodapé)
        if choice:find("%[1%]") then
          local new_state = not (rawget(_G, "_DOXOADE_NOTE_SYNC_ACTIVE") == true)
          rawset(_G, "_DOXOADE_NOTE_SYNC_ACTIVE", new_state)

          if new_state then
            -- Dispara o daemon único de background (protegido pelo Singleton Lock)
            launch_mesh_service_safe()
            core.log("🟢 [NOTE MESH] Sincronização ATIVADA e Daemon de Rede iniciado.")
          else
            core.log("🔴 [NOTE MESH] Sincronização DESATIVADA (Modo Local).")
          end
          core.redraw = true

        -- 2. Abrir shared_notes no split lateral
        elseif choice:find("%[2%]") then
          open_note_in_split(shared_path, "🌐 shared_notes.md aberto no painel lateral.")

        -- 3. Abrir notas do projeto no split lateral
        elseif choice:find("%[3%]") then
          local notes = get_all_existing_notes()
          local labels, path_map = {}, {}
          for _, n in ipairs(notes) do
            local label = string.format("📝 %-18s — %q (%s)", n.filename, n.preview or "", n.origin or "")
            table.insert(labels, label)
            path_map[label] = n.path
          end
          core.command_view:enter("Selecione a Nota para abrir no Painel Dividido", {
            submit = function(sel)
              local target = path_map[sel]
              if target then open_note_in_split(target, "📝 " .. sel .. " aberta à direita.") end
            end,
            suggest = function(text) return common.fuzzy_match(labels, text) end
          })

        -- 4. Nova nota
        elseif choice:find("%[4%]") then
          command.perform("doxoade:new-note-interactive")

        -- 5. Agenda
        elseif choice:find("%[5%]") then
          local note_dir = get_primary_note_dir()
          open_note_in_split(note_dir .. "/.agenda_view.md", "⏰ Agenda aberta à direita.")

        -- 6. Adicionar tarefa
        elseif choice:find("%[6%]") then
          command.perform("doxoade:quick-add-task")

        -- 7. Concluir tarefa
        elseif choice:find("%[7%]") then
          command.perform("doxoade:mark-task-done")

        -- 8. Puxar do host remoto
        elseif choice:find("%[8%]") then
          local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
          local shelf = rawget(_G, "_DOXOADE_SHELF_HUB")
          if shelf then shelf.visible = true; shelf.active_tab = "terminal" end
          if term then term:ensure_started(); term:execute_command("doxoade lan-git pull --live -f") end

        -- 9. Iniciar host live mirror
        elseif choice:find("%[9%]") then
          local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
          local shelf = rawget(_G, "_DOXOADE_SHELF_HUB")
          if shelf then shelf.visible = true; shelf.active_tab = "terminal" end
          if term then term:ensure_started(); term:execute_command("doxoade lan-git share --live") end
        end
      end,
      suggest = function(text) return common.fuzzy_match(options, text) end
    })
  end,

  -- 📅 AGENDA VIEW
  ["doxoade:open-agenda-view"] = function()
    local note_dir = get_primary_note_dir()
    local agenda_file = note_dir .. "/.agenda_view.md"
    local content = generate_agenda_markdown()
    local f = io.open(agenda_file, "w")
    if f then
      f:write(content)
      f:close()
    end
    local doc = core.open_doc(agenda_file)
    if doc then
      core.root_view:open_doc(doc)
      core.log("⏰ Agenda sincronizada e aberta.")
    end
  end,

  -- ⚡ ADICIONAR TAREFA RÁPIDA
  ["doxoade:quick-add-task"] = function()
    core.command_view:enter("Descrição da Tarefa", {
      submit = function(task_text)
        if not task_text or not task_text:match("%S") then return end
        core.command_view:enter("Data do Lembrete (+1d, +3d, +1w, hoje, amanha, YYYY-MM-DD)", {
          submit = function(when_input)
            local when_iso = parse_when_date(when_input)
            local note_dir = get_primary_note_dir()
            local target_file = note_dir .. "/tarefas.md"
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

  -- ✔ CONCLUIR TAREFA
  ["doxoade:mark-task-done"] = function()
    local tasks = collect_all_tasks()
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
            for line in f:lines() do table.insert(lines, line) end
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
  end
})

-- ═════════════════════════════════════════════════════════════════════════════
-- 6. ATALHOS DE TECLADO SOBERANOS
-- ═════════════════════════════════════════════════════════════════════════════

keymap.add {
  ["ctrl+alt+shift+n"] = "doxoade:note-hub-menu",
  ["ctrl+alt+shift+o"] = "doxoade:open-note",
}
