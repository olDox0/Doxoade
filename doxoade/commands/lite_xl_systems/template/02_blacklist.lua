-- doxoade/commands/lite_xl_systems/template/template/02_blacklist.lua
-- =============================================================================
-- 02. BLACKLIST DE PASTAS (PYTHON VENV, CACHE, GIT)
-- =============================================================================
local ignored_patterns = {
  "^%.venv/", "^%.venv\\",
  "^venv/", "^venv\\",
  "^env/", "^env\\",
  "^%.env/", "^%.env\\",
  "^__pycache__/", "^__pycache__\\",
  "%.pyc$", "%.pyo$", "%.pyd$",
  "^%.pytest_cache/", "^%.mypy_cache/", "^%.ruff_cache/",
  "%.egg%-info/", "^%.git/", "^%.idea/", "^%.vscode/",
  "^node_modules/", "^dist/", "^build/",
  "%.DS_Store$", "Thumbs%.db$"
}

for _, pattern in ipairs(ignored_patterns) do
  table.insert(config.ignore_files, pattern)
end