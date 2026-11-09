-- doxoade/commands/lite_xl_systems/template/26_doxly_flow_tracer.lua
-- 🌊 DOXLY FLOW TRACER V3.1 — Keys + Commands + Tree + Views + Marks + Divider Guard
if rawget(_G, "_DOXOADE_FLOW_TRACER_LOADED") then return end
rawset(_G, "_DOXOADE_FLOW_TRACER_LOADED", true)

local core     = require "core"
local command  = require "core.command"
local keymap   = require "core.keymap"
local RootView = require "core.rootview"
local Node     = require "core.node"

-- ═══════════════════════════════════════════════════════════════
-- RING BUFFER + FLUSH
-- ═══════════════════════════════════════════════════════════════
local _ring, _head, _count = {}, 1, 0
local RING_SIZE = 500
local _last_flush = os.clock()

local function jesc(s)
  if not s then return "" end
  return tostring(s):gsub("\\", "\\\\"):gsub('"', '\\"')
                  :gsub("\n", "\\n"):gsub("\r", "\\r")
end

local function resolve_aot_line(line_no)
  local sm = rawget(_G, "_DOXOADE_SOURCE_MAP")
  if not sm or not sm.resolve then return nil, 0 end
  local ok, seg = pcall(sm.resolve, line_no)
  if ok and seg and seg.name then
    return seg.name, (line_no - seg.start_line + 1)
  end
  return nil, 0
end

local function resolve_traceback(tb)
  if not tb then return "unknown", 0 end
  for line in tb:gmatch("[^\r\n]+") do
    local n_str = line:match("tmp[%w_]+%.lua:(%d+)")
    if n_str then
      local n = tonumber(n_str)
      if n then
        local tmpl, rel = resolve_aot_line(n)
        if tmpl then return tmpl, rel end
      end
    end
  end
  return "unknown", 0
end

local function resolve_caller(level)
  local info = debug.getinfo((level or 2) + 1, "Sl")
  if not info then return "unknown", 0 end
  local line = info.currentline or 0
  local tmpl, rel = resolve_aot_line(line)
  if tmpl then return tmpl, rel end
  return (info.short_src or "?"):match("[^/\\]+$") or "unknown", line
end

local function snapshot_tree(node, depth)
  if not node then return "NIL" end
  depth = depth or 0
  if depth > 8 then return "…" end
  if node.type == "leaf" then
    return string.format("L[%d]", #(node.views or {}))
  end
  return string.format("%s(%s,%s)", tostring(node.type):sub(1, 4),
    snapshot_tree(node.a, depth + 1), snapshot_tree(node.b, depth + 1))
end

local function record(ev)
  ev.ts = os.time()
  _ring[_head] = ev
  _head = (_head % RING_SIZE) + 1
  if _count < RING_SIZE then _count = _count + 1 end
end

local function flush()
  if _count == 0 then return end
  local udir = USERDIR or "."
  local sep  = PATHSEP or "/"
  local path = udir .. sep .. ".doxoade" .. sep .. "diagnostics" .. sep .. "flow_trace.ndjson"
  local f = io.open(path, "a")
  if not f then return end
  local start = _head - _count
  if start <= 0 then start = start + RING_SIZE end
  for i = 1, _count do
    local idx = ((start + i - 2) % RING_SIZE) + 1
    local e = _ring[idx]
    if e then
      f:write(string.format(
        '{"ts":%d,"phase":"%s","cmd":"%s","src":"%s","line":%d,"pre":"%s","post":"%s","info":%s,"viol":%s}\n',
        e.ts, e.phase or "?", jesc(e.cmd), jesc(e.src), e.line or 0,
        jesc(e.pre or ""), jesc(e.post or ""), e.info or "null", e.viol or "[]"))
    end
  end
  f:close()
  _ring, _head, _count = {}, 1, 0
  _last_flush = os.clock()
end

-- ═══════════════════════════════════════════════════════════════
-- KEY TRACKING
-- ═══════════════════════════════════════════════════════════════
local _last_key, _last_key_time = nil, 0
local _orig_on_event = core.on_event
core.on_event = function(event_type, ...)
  if event_type == "keypressed" then
    local a = ...
    local kname = tostring(a or "?")
    local mods = ""
    if keymap and keymap.modkeys then
      for mod, active in pairs(keymap.modkeys) do
        if active then mods = mods .. mod .. "+" end
      end
    end
    _last_key = mods .. kname
    _last_key_time = os.clock()
    if mods ~= "" or kname:match("^f%d") then
      record({
        phase = "KEY",
        cmd = mods .. kname,
        src = "core.on_event",
        line = 0,
        info = string.format('{"key":"%s","mods":"%s"}', jesc(kname), jesc(mods)),
        viol = "[]",
      })
    end
  end
  return _orig_on_event(event_type, ...)
end

-- ═══════════════════════════════════════════════════════════════
-- CHECK & REPAIR
-- ═══════════════════════════════════════════════════════════════
local function check_invariants(node, path)
  if not node then return {} end
  path = path or "root"
  local v = {}
  if not node.position then
    table.insert(v, { node = path, inv = "position=nil", fixable = true })
  elseif not node.position.x or not node.position.y then
    table.insert(v, { node = path, inv = "position.xy=nil", fixable = true })
  end
  if not node.size then
    table.insert(v, { node = path, inv = "size=nil", fixable = true })
  elseif not node.size.x or not node.size.y then
    table.insert(v, { node = path, inv = "size.xy=nil", fixable = true })
  end
  if node.type ~= "leaf" then
    if not node.a then
      table.insert(v, { node = path, inv = "split.a=nil", fixable = false })
    end
    if not node.b then
      table.insert(v, { node = path, inv = "split.b=nil", fixable = false })
    end
    for _, c in ipairs(check_invariants(node.a, path .. ".a")) do table.insert(v, c) end
    for _, c in ipairs(check_invariants(node.b, path .. ".b")) do table.insert(v, c) end
  else
    if #(node.views or {}) == 0 then
      table.insert(v, { node = path, inv = "leaf-empty", fixable = true })
    end
  end
  return v
end

local function repair_tree(node, path)
  if not node then return 0 end
  path = path or "root"
  local repairs = 0
  if not node.position then
    node.position = { x = 0, y = 0 }; repairs = repairs + 1
  else
    if not node.position.x then node.position.x = 0; repairs = repairs + 1 end
    if not node.position.y then node.position.y = 0; repairs = repairs + 1 end
  end
  if not node.size then
    node.size = { x = 0, y = 0 }; repairs = repairs + 1
  else
    if not node.size.x then node.size.x = 0; repairs = repairs + 1 end
    if not node.size.y then node.size.y = 0; repairs = repairs + 1 end
  end
  if node.type == "leaf" then
    if #(node.views or {}) == 0 then
      local ok_ev, EmptyView = pcall(require, "core.emptyview")
      if ok_ev and EmptyView then
        local ok_new, ev = pcall(EmptyView)
        if ok_new and ev then
          node:add_view(ev)
          node.active_view = ev
          repairs = repairs + 1
        end
      end
    end
  else
    repairs = repairs + repair_tree(node.a, path .. ".a")
    repairs = repairs + repair_tree(node.b, path .. ".b")
  end
  return repairs
end

-- ═══════════════════════════════════════════════════════════════
-- HOOK on_mouse_moved
-- ═══════════════════════════════════════════════════════════════
local _orig_mouse = RootView.on_mouse_moved
RootView.on_mouse_moved = function(self, x, y, dx, dy)
  if self.root_node then
    local viols = check_invariants(self.root_node)
    if #viols > 0 then
      local viol_summary = {}
      for _, v in ipairs(viols) do table.insert(viol_summary, v.inv) end
      record({
        phase = "MOUSE_PRECHECK",
        cmd = "on_mouse_moved",
        src = "core.rootview",
        line = 0,
        info = string.format('{"violations":%d,"types":["%s"]}',
          #viols, table.concat(viol_summary, '","')),
        viol = "[]",
      })
      local repaired = repair_tree(self.root_node)
      if core.log then
        if repaired > 0 then
          core.log(string.format("🌊 [FLOW] 🔧 Self-healing: %d reparo(s) antes do mouse", repaired))
        else
          core.log("🌊 [FLOW] 💀 Reparo falhou — crash iminente")
        end
      end
      core.redraw = true
    end
  end
  return _orig_mouse(self, x, y, dx, dy)
end

-- ═══════════════════════════════════════════════════════════════
-- HOOK Node:update_layout
-- ═══════════════════════════════════════════════════════════════
local _orig_update_layout = Node.update_layout
Node.update_layout = function(self, ...)
  local results = { pcall(_orig_update_layout, self, ...) }
  if not results[1] then
    record({
      phase = "LAYOUT_ERROR",
      cmd = "Node:update_layout",
      src = "core.node",
      line = 0,
      info = string.format('{"err":"%s","type":"%s"}',
        jesc(tostring(results[2]):sub(1, 150)), tostring(self.type)),
      viol = "[]",
    })
    if core.log then
      core.log(string.format("🌊 [FLOW] 💥 update_layout FALHOU (type=%s): %s",
        tostring(self.type), tostring(results[2]):sub(1, 100)))
    end
  end
  return table.unpack(results, 2)
end

-- ═══════════════════════════════════════════════════════════════
-- HOOK Node:get_divider_overlapping_point — guarda-corpo
-- ═══════════════════════════════════════════════════════════════
local _orig_divider = Node.get_divider_overlapping_point
if _orig_divider then
  Node.get_divider_overlapping_point = function(self, ...)
    local root = core.root_view and core.root_view.root_node
    if root then
      local viols = check_invariants(root)
      if #viols > 0 then
        local repaired = repair_tree(root)
        record({
          phase = "MOUSE_PRECHECK",
          cmd = "get_divider_overlapping_point",
          src = "core.node",
          line = 0,
          info = string.format('{"violations":%d,"repaired":%d,"node_type":"%s"}',
            #viols, repaired, tostring(self and self.type)),
          viol = "[]",
        })
        if repaired > 0 and core.log then
          core.log(string.format("🌊 [FLOW] 🔧 Self-healing (divider): %d reparo(s)", repaired))
        end
      end
    end
    return _orig_divider(self, ...)
  end
end

-- ═══════════════════════════════════════════════════════════════
-- HOOK Node:get_child_overlapping_point — guarda-corpo do crash REAL
-- (crash em node.lua:321 via rootview.lua:292)
-- ═══════════════════════════════════════════════════════════════
local _orig_child_overlap = Node.get_child_overlapping_point
if _orig_child_overlap then
  Node.get_child_overlapping_point = function(self, ...)
    -- Pre-check: nó atual tem a/b válidos?
    if self and self.type ~= "leaf" then
      if not self.a or not self.b then
        record({
          phase = "CHILD_OVERLAP_PRE",
          cmd = "get_child_overlapping_point",
          src = "core.node", line = 0,
          info = string.format('{"bad":"split_with_nil_child","has_a":%s,"has_b":%s,"type":"%s"}',
            tostring(self.a ~= nil), tostring(self.b ~= nil), tostring(self.type)),
          viol = "[]",
        })
        if core.log then
          core.log("🌊 [FLOW] ⚠ get_child_overlapping_point chamado em split com child nil")
        end
      end
    end
    -- Pre-check invariantes do root
    local root = core.root_view and core.root_view.root_node
    if root then
      local viols = check_invariants(root)
      if #viols > 0 then
        local repaired = repair_tree(root)
        record({
          phase = "MOUSE_PRECHECK",
          cmd = "get_child_overlapping_point",
          src = "core.node", line = 0,
          info = string.format('{"violations":%d,"repaired":%d}',
            #viols, repaired),
          viol = "[]",
        })
      end
    end
    return _orig_child_overlap(self, ...)
  end
end

-- ═══════════════════════════════════════════════════════════════
-- DOXOADE_FLOW.mark()
-- ═══════════════════════════════════════════════════════════════
rawset(_G, "DOXOADE_FLOW", {
  mark = function(category, action, details)
    local src, line = resolve_caller(2)
    record({
      phase = "MARK",
      cmd = tostring(category or "?") .. ":" .. tostring(action or "?"),
      src = src, line = line,
      info = string.format('{"details":"%s","key":"%s"}',
        jesc(details or ""),
        jesc((_last_key and (os.clock() - _last_key_time) < 2) and _last_key or "")),
      viol = "[]",
    })
  end,
  flush = flush,
})

-- ═══════════════════════════════════════════════════════════════
-- HOOK command.perform
-- ═══════════════════════════════════════════════════════════════
local _orig_perform = command.perform
command.perform = function(cmd_name, ...)
  local tb = debug.traceback("", 2) or ""
  local src, rel = resolve_traceback(tb)
  local pre = "NIL"
  if core.root_view and core.root_view.root_node then
    pre = snapshot_tree(core.root_view.root_node)
  end
  local t0 = os.clock()
  local ok, err = pcall(_orig_perform, cmd_name, ...)
  local ms = (os.clock() - t0) * 1000
  local post = "NIL"
  if core.root_view and core.root_view.root_node then
    post = snapshot_tree(core.root_view.root_node)
  end
  local relevant = cmd_name:match("^doxoade:") or cmd_name:match("^treeview:") or
                   cmd_name:match("^doc:") or cmd_name:match("^root:") or not ok
  if relevant then
    record({
      phase = ok and "EXEC" or "ERR",
      cmd = cmd_name, src = src or "unknown", line = rel or 0,
      pre = pre, post = post,
      info = string.format('{"ms":%.2f,"ok":%s,"key":"%s","err":"%s"}',
        ms, tostring(ok), jesc(_last_key or ""),
        ok and "" or jesc(tostring(err):sub(1, 100))),
      viol = "[]",
    })
  end
  if _count >= 20 then flush() end
  if not ok then error(err, 0) end
end

-- ═══════════════════════════════════════════════════════════════
-- HOOK tree primitives
-- ═══════════════════════════════════════════════════════════════
local function _hook_tree(name, wrap)
  local orig = Node[name]
  if not orig then return end
  Node[name] = wrap(orig)
end

_hook_tree("split", function(orig)
  return function(self, ...)
    local res = orig(self, ...)
    record({
      phase = "TREE", cmd = "Node:split", src = "core.node", line = 0,
      info = string.format('{"ok":%s,"new_type":"%s"}',
        tostring(res ~= nil), tostring(res and res.type or "nil")),
      viol = "[]",
    })
    return res
  end
end)

_hook_tree("add_view", function(orig)
  return function(self, view)
    local before = #(self.views or {})
    local res = orig(self, view)
    record({
      phase = "TREE", cmd = "Node:add_view", src = "core.node", line = 0,
      info = string.format('{"before":%d,"after":%d}', before, #(self.views or {})),
      viol = "[]",
    })
    return res
  end
end)

_hook_tree("consume", function(orig)
  return function(self, other)
    record({
      phase = "TREE", cmd = "Node:consume", src = "core.node", line = 0,
      info = string.format('{"self":"%s","other":"%s"}',
        tostring(self and self.type), tostring(other and other.type)),
      viol = "[]",
    })
    return orig(self, other)
  end
end)

-- ═══════════════════════════════════════════════════════════════
-- HOOK set_active_view / set_active_node
-- ═══════════════════════════════════════════════════════════════
local _orig_active_view = core.set_active_view
core.set_active_view = function(view)
  local name = "?"
  if view and view.get_name then
    local ok, n = pcall(view.get_name, view)
    name = ok and tostring(n) or "?"
  end
  record({
    phase = "VIEW", cmd = "set_active_view", src = "core", line = 0,
    info = string.format('{"name":"%s"}', jesc(name)), viol = "[]",
  })
  return _orig_active_view(view)
end

if RootView.set_active_node then
  local _orig_active_node = RootView.set_active_node
  RootView.set_active_node = function(self, node, ...)
    record({
      phase = "VIEW", cmd = "set_active_node", src = "core.rootview", line = 0,
      info = string.format('{"type":"%s"}', tostring(node and node.type)),
      viol = "[]",
    })
    return _orig_active_node(self, node, ...)
  end
end

-- ═══════════════════════════════════════════════════════════════
-- HOOK core.error
-- ═══════════════════════════════════════════════════════════════
local _orig_error = core.error
core.error = function(...)
  local msg = table.concat({...}, " ")
  local tb = debug.traceback("", 2) or ""
  local src, rel = resolve_traceback(tb)
  record({
    phase = "ERROR", cmd = "", src = src or "unknown", line = rel or 0,
    pre = "", post = "", viol = "[]",
    info = string.format('{"msg":"%s"}', jesc(tostring(msg)):sub(1, 300)),
  })
  flush()
  return _orig_error(...)
end

-- ═══════════════════════════════════════════════════════════════
-- FLUSH PERIÓDICO + QUIT
-- ═══════════════════════════════════════════════════════════════
if core.add_thread then
  core.add_thread(function()
    while true do
      coroutine.yield(0.5)
      if _count > 0 then flush() end
    end
  end)
end

local _orig_quit = core.quit
if _orig_quit then
  core.quit = function(...)
    if _count > 0 then flush() end
    return _orig_quit(...)
  end
end

core.log("🌊 [FLOW TRACER V3.1] Keys + Commands + Tree + Views + Marks + Divider Guard + Auto-flush.")
