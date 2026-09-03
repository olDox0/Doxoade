-- doxoade/tools/lua_systems/shadow_harness.lua
-- =============================================================================
-- 🏛️ DOXOADE SHADOW HARNESS V2.0 (Chronos Profiler & Ma'at Command Simulator)
-- =============================================================================
local is_windows = (package.config:sub(1, 1) == "\\")
rawset(_G, "PLATFORM", is_windows and "Windows" or "Linux")
rawset(_G, "PATHSEP", is_windows and "\\" or "/")
rawset(_G, "USERDIR", os.getenv("USERPROFILE") or os.getenv("HOME") or ".")
rawset(_G, "DATADIR", USERDIR .. PATHSEP .. "data")
rawset(_G, "VERSION", "2.1.8")
rawset(_G, "SCALE", 1.0)
rawset(_G, "ARGS", {})

-- 1. Mocks de Sistema e Renderização
local mock_font = {
  get_height = function() return 14 end,
  get_width = function(self, t) return #(tostring(t or "")) * 8 end,
  copy = function(self) return self end,
}

local mock_style = {
  font = mock_font,
  code_font = mock_font,
  tree_font = mock_font,
  icon_font = mock_font,
  background = { 30, 30, 30, 255 },
  background2 = { 25, 25, 25, 255 },
  background3 = { 35, 35, 35, 255 },
  text = { 200, 200, 200, 255 },
  accent = { 0, 108, 255, 255 },
  dim = { 100, 100, 100, 255 },
  divider = { 50, 50, 50, 255 },
  line_number = { 100, 100, 100, 255 },
  syntax = {},
}

local mock_system = {
  mkdir = function() return true end,
  rmdir = function() return true end,
  get_file_info = function() return { type = "file", size = 100, mtime = os.time() } end,
  absolute_path = function(p) return tostring(p) end,
  list_dir = function() return {} end,
  set_clipboard = function() return true end,
  get_clipboard = function() return "" end,
  exec = function() return true end,
  show_in_file_manager = function() return true end,
  get_time = function() return os.clock() end,
}
rawset(_G, "system", mock_system)

local mock_renderer = {
  draw_rect = function(x, y, w, h, col) end,
  draw_text = function(font, text, x, y, col) end,
}
rawset(_G, "renderer", mock_renderer)
rawset(_G, "rencache", mock_renderer)

-- 2. Mock de Objetos e Classes (OOP Lite XL)
local function create_class()
  local cls = {}
  cls.__index = cls
  function cls:new(...)
    local inst = setmetatable({}, self)
    if inst.init then inst:init(...) end
    return inst
  end
  function cls:extend()
    local sub = create_class()
    for k, v in pairs(self) do sub[k] = v end
    sub.super = self
    return sub
  end
  return setmetatable(cls, {
    __call = function(self, ...) return self:new(...) end
  })
end

local MockDoc = create_class()
function MockDoc:init(filename)
  self.filename = filename or "mock_file.lua"
  self.lines = { "local x = 1", "return x" }
end
function MockDoc:get_name() return self.filename or "mock_file.lua" end
function MockDoc:insert(...) end
function MockDoc:remove(...) end
function MockDoc:save(...) return true end
function MockDoc:get_text(...) return "" end
function MockDoc:has_selection() return false end
function MockDoc:get_selection() return 1, 1, 1, 1 end
function MockDoc:set_selection(...) end
function MockDoc:is_dirty() return false end

local MockView = create_class()
function MockView:init()
  self.position = { x=0, y=0 }
  self.size = { x=800, y=600 }
end
function MockView:draw() end
function MockView:draw_background() end
function MockView:get_name() return "MockView" end
function MockView:is(class) return true end

local MockDocView = MockView:extend()
function MockDocView:init(doc)
  MockDocView.super.init(self)
  self.doc = doc or MockDoc:new()
end
function MockDocView:get_gutter_width() return 40 end
function MockDocView:get_line_height() return 16 end
function MockDocView:draw_line_gutter(...) end
function MockDocView:draw_line_body(...) end

local MockNode = create_class()
function MockNode:init()
  self.type = "leaf"
  self.views = {}
  self.position = { x=0, y=0 }
  self.size = { x=800, y=600 }
end
function MockNode:draw() end
function MockNode:draw_tab_title() end
function MockNode:split() return MockNode:new() end
function MockNode:close() end
function MockNode:add_view(v) table.insert(self.views, v) end
function MockNode:get_view_idx() return 1 end
function MockNode:get_primary_node() return self end

local mock_root_node = MockNode:new()
local mock_active_view = MockDocView:new()
local mock_doc = MockDoc:new("mock_script.lua")
mock_active_view.doc = mock_doc
mock_root_node:add_view(mock_active_view)

-- 3. Mock de Comandos e Core
local registered_commands = {}
local mock_command = {
  add = function(predicate, map)
    if type(map) == "table" then
      for cmd_name, fn in pairs(map) do
        registered_commands[cmd_name] = { fn = fn, predicate = predicate }
      end
    end
    return true
  end,
  perform = function(name, ...)
    if registered_commands[name] and type(registered_commands[name].fn) == "function" then
      return pcall(registered_commands[name].fn, ...)
    end
    return false
  end,
}

local mock_core = {
  docs = { mock_doc },
  root_view = {
    root_node = mock_root_node,
    get_active_node = function() return mock_root_node end,
    open_doc = function() return mock_active_view end,
  },
  active_view = mock_active_view,
  project_directories = { USERDIR },
  project_dir = USERDIR,
  plugins = {},
  threads = {},
  log = function() end,
  error = function() end,
  warn = function() end,
  open_doc = function() return mock_doc end,
  add_thread = function(fn) table.insert(mock_core.threads, fn) end,
  set_active_view = function(v) mock_core.active_view = v end,
  redraw = false,
  step = function() end,
  add_project_directory = function(p) end,
  remove_project_directory = function(p) end,
}

rawset(_G, "core", mock_core)
rawset(_G, "command", mock_command)

-- 4. Preload de Módulos Requeridos pelos Templates
local mock_modules = {
  ["core"] = mock_core,
  ["core.rootview"] = MockView:extend(),
  ["core.docview"] = MockDocView,
  ["core.doc"] = MockDoc,
  ["core.node"] = MockNode,
  ["core.view"] = MockView,
  ["core.style"] = mock_style,
  ["core.config"] = { load_workspace = true, ignore_files = {} },
  ["core.command"] = mock_command,
  ["core.keymap"] = { add = function() end, bind = function() end },
  ["core.common"] = {
    clamp = function(n, min, max) return math.max(min, math.min(max, n)) end,
    fuzzy_match = function() return true end,
  },
  ["core.syntax"] = { add = function() end },
  ["core.statusview"] = { Item = { LEFT = 1, RIGHT = 2 }, add_item = function() end },
  ["core.rencache"] = mock_renderer,
  ["renderer"] = mock_renderer,
  ["system"] = mock_system,
  ["plugins.contextmenu"] = { DIVIDER = "---", register = function() end },
  ["core.emptyview"] = MockView:extend(),
}

for mod_name, mod_val in pairs(mock_modules) do
  package.preload[mod_name] = function() return mod_val end
end

-- =============================================================================
-- 5. BENCHMARK DE MÓDULOS COM GC PROFILING & CALL HOOKS (CHRONOS V2)
-- =============================================================================
local raw_args = { ... }
local args = (#raw_args > 0) and raw_args or (type(arg) == "table" and arg or {})

for i = 1, #args do
  local template_path = args[i]
  local fname = template_path:match("([^/\\]+)$") or template_path

  -- Medição precisa de memória antes do carregamento
  collectgarbage("collect")
  local mem_before = collectgarbage("count")
  local t0 = os.clock()

  -- Hook para rastreamento de funções internas
  local funcs_map = {}
  local function call_hook(event)
    local info = debug.getinfo(2, "nSl")
    if info and info.what == "Lua" and info.linedefined and info.linedefined > 0 then
      local name = info.name or (info.namewhat ~= "" and info.namewhat) or string.format("closure:L%d", info.linedefined)
      local key = info.linedefined .. ":" .. name
      if not funcs_map[key] then
        funcs_map[key] = { name = name, line = info.linedefined, calls = 1 }
      else
        funcs_map[key].calls = funcs_map[key].calls + 1
      end
    end
  end

  debug.sethook(call_hook, "c")
  local chunk, load_err = loadfile(template_path)
  local ok = false
  if chunk then
    local run_ok, run_err = pcall(chunk)
    ok = run_ok
  end
  debug.sethook()

  local elapsed_ms = (os.clock() - t0) * 1000
  local mem_after = collectgarbage("count")
  local mem_delta = math.max(0.4, mem_after - mem_before)

  -- Emite SHADOW_MOD com a 5ª coluna (mem_kb)
  print(string.format("SHADOW_MOD|%s|%s|%.2f|%.1f", fname, ok and "PASS" or "FAIL", elapsed_ms, mem_delta))

  -- Emite SHADOW_FUNC para drill-down
  for _, f in pairs(funcs_map) do
    print(string.format("SHADOW_FUNC|%s|%s|%d|%d", fname, f.name, f.line, f.calls))
  end
end

-- =============================================================================
-- 6. SIMULAÇÃO DE COMANDOS REGISTRADOS (EXIGIDO PELO HEALTH-CHECK MA'AT)
-- =============================================================================
local total_cmds = 0
local passed_cmds = 0
local crashed_cmds = 0

for name, cmd in pairs(registered_commands) do
  total_cmds = total_cmds + 1
  local ok, err = pcall(cmd.fn)
  if ok then
    passed_cmds = passed_cmds + 1
  else
    crashed_cmds = crashed_cmds + 1
  end
end

print(string.format("SHADOW_CMD_COUNT|%d", total_cmds))
print(string.format("SHADOW_CMD_SIMULATION|%d|%d", passed_cmds, crashed_cmds))
