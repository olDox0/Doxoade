-- doxoade/commands/lite_xl_systems/template/31_file_backup.lua
--[[
💾 FILE BACKUP (V1.0 — Camada A, estilo Notepad++)
Snapshot per-file em .doxoade/file_backups/ com rotação (10).
Gatilhos: Doc:save (save do usuário), core.quit/on_quit (fechar editor),
autosave periódico de buffers sujos. Diff é VIEW (F2.2), não storage.
]]
local core = require "core"
local config = require "core.config"
local Doc = require "core.doc"

if rawget(_G, "_DOXOADE_FILE_BACKUP_LOADED") then return end
rawset(_G, "_DOXOADE_FILE_BACKUP_LOADED", true)
if config.doxoade_file_backup == false then return end

local KEEP = config.doxoade_file_backup_keep or 10
local INTERVAL = config.doxoade_file_backup_interval or 30
local last_hash = {}
local seq = 0

local function norm(p)
  if type(p) ~= "string" or p == "" then return nil end
  return (system.absolute_path(p) or p):gsub("\\", "/"):gsub("/+$", "")
end
local function hash(s)
  local h = 5381
  for i = 1, #s do h = (h * 33 + s:byte(i)) % 2147483647 end
  return h .. ":" .. #s
end
local function mkdir_p(path)
  local clean = path:gsub("\\", "/")
  local cur = ""
  local drive = clean:match("^([a-zA-Z]:)")
  if drive then cur = drive; clean = clean:sub(#drive + 1) end
  for part in clean:gmatch("[^/]+") do
    cur = cur .. "/" .. part
    if not system.get_file_info(cur) then pcall(system.mkdir, cur) end
  end
end
local function project_root_for(filename)
  local abs = norm(filename)
  if not abs then return nil end
  local best, best_len = nil, 0
  for _, p in ipairs(core.project_directories or {}) do
    local rp = norm(type(p) == "table" and (p.path or p.name) or p)
    if rp and #rp > best_len and abs:sub(1, #rp):lower() == rp:lower() then
      best, best_len = rp, #rp
    end
  end
  return best
end
local function backup_key(rel)
  return (rel:gsub("[/\\]", "__"):gsub(":", ""))
end
local function write_backup(bdir, key, content)
  mkdir_p(bdir)
  seq = (seq + 1) % 10000
  local fname = string.format("%s.%s_%04d.bak", key, os.date("%Y%m%d_%H%M%S"), seq)
  local f = io.open(bdir .. "/" .. fname, "w")
  if f then f:write(content); f:flush(); f:close() end
  local mine = {}
  for _, n in ipairs(system.list_dir(bdir) or {}) do
    if n:sub(1, #key + 1) == key .. "." and n:match("%.bak$") then
      table.insert(mine, n)
    end
  end
  table.sort(mine)
  for i = 1, #mine - KEEP do pcall(os.remove, bdir .. "/" .. mine[i]) end
end
local function snapshot_doc(doc, reason, sync)
  if rawget(_G, "_DOXOADE_SHADOW_MODE") then return end
  if not doc or not doc.filename then return end
  local root = project_root_for(doc.filename)
  if not root then return end
  local ok, content = pcall(function() return table.concat(doc.lines) end)
  if not ok or not content then return end
  local h = hash(content)
  if last_hash[doc.filename] == h then return end
  last_hash[doc.filename] = h
  local rel = norm(doc.filename):sub(#root + 2)
  local key = backup_key(rel)
  local bdir = root .. "/.doxoade/file_backups"
  if sync then
    pcall(write_backup, bdir, key, content)
  else
    core.add_thread(function() pcall(write_backup, bdir, key, content) end)
  end
end
local function snapshot_all(reason, sync)
  for _, d in ipairs(core.docs or {}) do
    if d.filename then snapshot_doc(d, reason, sync) end
  end
end

-- Gatilho 1: save do usuário (async, zero freeze)
local orig_save = Doc.save
Doc.save = function(self, ...)
  local r = orig_save(self, ...)
  snapshot_doc(self, "save", false)
  return r
end
-- Gatilho 2: fechar o editor (SYNC — threads não rodam após quit)
local orig_quit = core.quit
core.quit = function(...)
  snapshot_all("quit", true)
  return orig_quit(...)
end
if type(core.on_quit) == "function" then
  local orig_on_quit = core.on_quit
  core.on_quit = function(...)
    snapshot_all("quit", true)
    return orig_on_quit(...)
  end
end
-- Gatilho 3: autosave periódico de buffers sujos
core.add_thread(function()
  while true do
    coroutine.yield(INTERVAL)
    for _, d in ipairs(core.docs or {}) do
      if d.filename and d.is_dirty and d:is_dirty() then
        snapshot_doc(d, "autosave", false)
      end
    end
  end
end)

-- API para F2.2 (timeline Alt+Z/Y + diff)
rawset(_G, "DOXOADE_FILE_BACKUP", {
  snapshot = snapshot_doc,
  dir_for = function(doc)
    local root = doc and project_root_for(doc.filename)
    return root and (root .. "/.doxoade/file_backups") or nil
  end,
  key_for = function(doc)
    local root = doc and project_root_for(doc.filename)
    if not root then return nil end
    return backup_key(norm(doc.filename):sub(#root + 2))
  end,
})
if core.log then
  core.log(string.format("💾 [FILE-BACKUP] Camada A ativa (save/quit/autosave %ds, rotação %d).", INTERVAL, KEEP))
end
