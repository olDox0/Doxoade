-- doxoade/commands/lite_xl_systems/template/template/02_blacklist.lua
-- =============================================================================
-- 02. BLACKLIST UNIVERSAL (IGNORA VENV EM QUALQUER NÍVEL DE SUBPASTA)
-- =============================================================================
local ignored_patterns = {
  "[/\\]%.venv[/\\]", "^%.venv[/\\]",
  "[/\\]venv[/\\]", "^venv[/\\]",
  "[/\\]env[/\\]", "^env[/\\]",
  "[/\\]%.env[/\\]", "^%.env[/\\]",
  "[/\\]__pycache__[/\\]", "^__pycache__[/\\]",
  "[/\\]%.pytest_cache[/\\]", "[/\\]%.mypy_cache[/\\]", "[/\\]%.ruff_cache[/\\]",
  "[/\\]%.git[/\\]", "^%.git[/\\]",
  "[/\\]%.idea[/\\]", "[/\\]%.vscode[/\\]",
  "[/\\]node_modules[/\\]", "^node_modules[/\\]",
  "[/\\]dist[/\\]", "[/\\]build[/\\]", "[/\\]%.egg%-info[/\\]",
  "%.pyc$", "%.pyo$", "%.pyd$",
  "%.DS_Store$", "Thumbs%.db$"
}

for _, pattern in ipairs(ignored_patterns) do
  table.insert(config.ignore_files, pattern)
end