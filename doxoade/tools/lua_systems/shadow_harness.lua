-- doxoade/tools/lua_systems/shadow_harness.lua
-- =============================================================================
-- 🐺 DOXOADE ACTIVE SHADOW HARNESS — MOCK RUNTIME V3 (COMPLETO)
-- =============================================================================
local is_windows = (package.config:sub(1, 1) == "\\")
rawset(_G, "PLATFORM", is_windows and "Windows" or "Linux")
rawset(_G, "PATHSEP", is_windows and "\\" or "/")
rawset(_G, "USERDIR", os.getenv("USERPROFILE") or os.getenv("HOME") or ".")
rawset(_G, "DATADIR", USERDIR .. PATHSEP .. "data")
rawset(_G, "VERSION", "2.1.8")
rawset(_G, "SCALE", 1.0)
rawset(_G, "ARGS", {})

local mock_font = {
  get_height = function() return 14 end,
  get_width = function(self, t) return #(tostring(t or "")) * 8 end,
}

local mock_style = {
  font = mock_font,
  code_font = mock_font,
  background = { 30, 30, 30, 255 },
  background2 = { 25, 25, 25, 255 },
  background3 = { 35, 35, 35, 255 },
  text = { 200, 200, 200, 255 },
  accent = { 0, 108, 255, 255 },
  dim = { 100, 100, 100, 255 },
  divider = { 50, 50, 50, 255 },
  line_number = { 100, 100, 100, 255 },
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
  draw_rect = function() end,
  draw_text = function() end,
}
rawset(_G, "renderer", mock_renderer)
rawset(_G, "rencache", mock_renderer)

-- Construtor com metamétodo __call (permite Cls(...) e Cls:new(...))
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
    __call = function(self, ...)
      return self:new(...)
    end
  })
end

local MockDoc = create_class()
function MockDoc:init(filename)
  self.filename = filename or "mock_file.lua"
  self.lines = { "local x = 1", "return x" }
end
function MockDoc:get_name() return self.filename or "mock_file.lua" end -- 👈 ADICIONE ESTA LINHA
function MockDoc:insert(...) end
function MockDoc:remove(...) end
function MockDoc:save(...) return true end
function MockDoc:get_text(...) return "" end
function MockDoc:has_selection() return false end
function MockDoc:get_selection() return 1, 1, 1, 1 end
function MockDoc:is_dirty() return false end

local MockView = create_class()
function MockView:init()
  self.position = { x=0, y=0 }
  self.size = { x=800, y=600 }
end
function MockView:draw() end
function MockView:draw_background() end
function MockView:get_name() return "MockView" end

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
  docs = { mock_doc },  -- 👈 Adicione esta linha
  root_view = {
    root_node = mock_root_node,
    get_active_node = function() return mock_root_node end,
    open_doc = function() return mock_active_view end,
  },
  active_view = mock_active_view,
  project_directories = { USERDIR },
  plugins = {},
  threads = {},
  log = function() end,
  error = function() end,
  warn = function() end,
  open_doc = function(fn) return MockDoc:new(fn) end,
  add_thread = function(fn) pcall(fn) end,
  set_active_view = function() end,
  add_project_directory = function() end,
  remove_project_directory = function() end,
  redraw = false,
  status_view = { add_item = function() end },
  command_view = {
    enter = function(self, prompt, opts)
      if opts and type(opts.submit) == "function" then
        pcall(opts.submit, "1")
      end
    end
  },
}
rawset(_G, "core", mock_core)

local mock_modules = {
  ["core"] = mock_core,
  ["core.style"] = mock_style,
  ["core.command"] = mock_command,
  ["core.keymap"] = { add = function() return true end },
  ["core.config"] = { ignore_files = {}, draw_indent_guides = true },
  ["core.common"] = {
    fuzzy_match = function(items) return items end,
    basename = function(p) return p:match("[/\\]([^/\\]+)$") or p end,
    dirname = function(p) return p:match("^(.*)[/\\]") or p end,
  },
  ["core.syntax"] = { items = {}, add = function() end },
  ["core.view"] = MockView,
  ["core.doc"] = MockDoc,
  ["core.docview"] = MockDocView,
  ["core.node"] = MockNode,
  ["core.rootview"] = MockView:extend(),
  ["core.statusview"] = MockView:extend(),
  ["core.rencache"] = mock_renderer,
  ["renderer"] = mock_renderer,
  ["plugins.contextmenu"] = { DIVIDER = "---", register = function() end }
}

for mod_name, mod_val in pairs(mock_modules) do
  package.preload[mod_name] = function() return mod_val end
end

-- =============================================================================
-- EXECUÇÃO DOS TEMPLATES + SONDAGEM ATIVA
-- =============================================================================
local results = {}
local total_failed = 0

for i = 1, #arg do
  local file_path = arg[i]
  local fname = file_path:match("[/\\]([^/\\]+)$") or file_path
  local t0 = os.clock()
  
  local f = io.open(file_path, "r")
  if not f then
    results[fname] = { status = "FAIL", error = "Arquivo inacessível", time_ms = 0 }
    total_failed = total_failed + 1
  else
    local source = f:read("*a")
    f:close()
    
    local chunk, load_err = load(source, "@" .. fname)
    if not chunk then
      results[fname] = { status = "FAIL", error = "Syntax Error: " .. tostring(load_err), time_ms = 0 }
      total_failed = total_failed + 1
    else
      local before_cmds = {}
      for k in pairs(registered_commands) do before_cmds[k] = true end
      
      local ok, exec_err = xpcall(chunk, debug.traceback)
      local elapsed = (os.clock() - t0) * 1000
      
      if not ok then
        results[fname] = { status = "FAIL", error = tostring(exec_err), time_ms = elapsed }
        total_failed = total_failed + 1
      else
        local cmd_error = nil
        for cmd_name, cmd_data in pairs(registered_commands) do
          if not before_cmds[cmd_name] and type(cmd_data.fn) == "function" then
            local cmd_ok, cmd_err = xpcall(function() cmd_data.fn() end, debug.traceback)
            if not cmd_ok then
              cmd_error = string.format("Comando '%s' falhou: %s", cmd_name, tostring(cmd_err))
              break
            end
          end
        end
        
        if cmd_error then
          results[fname] = { status = "FAIL", error = cmd_error, time_ms = elapsed }
          total_failed = total_failed + 1
        else
          results[fname] = { status = "PASS", time_ms = elapsed }
        end
      end
    end
  end
end

print("=== SHADOW_REPORT_START ===")
for fname, res in pairs(results) do
  if res.status == "PASS" then
    print(string.format("PASS|%s|%.2f", fname, res.time_ms))
  else
    local err_clean = res.error:gsub("\r", ""):gsub("\n", " -> ")
    print(string.format("FAIL|%s|%.2f|%s", fname, res.time_ms, err_clean))
  end
end
print("=== SHADOW_REPORT_END ===")
os.exit(total_failed == 0 and 0 or 1)
