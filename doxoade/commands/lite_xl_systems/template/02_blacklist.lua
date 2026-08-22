-- doxoade/commands/lite_xl_systems/template/02_blacklist.lua
-- =============================================================================
-- 02. BLACKLIST UNIVERSAL (BLOQUEIA PASTAS ANTES DO SCANNER DO FILESYSTEM)
-- =============================================================================
local ignored_patterns = {
  -- Bloqueio de Venvs (Raiz e Subpastas)
  "^%.?venv[/\\]",          "^venv[/\\]",
  "^%.?env[/\\]",           "^env[/\\]",
  "[/\\]%.?venv[/\\]",      "[/\\]venv[/\\]",
  "[/\\]%.?env[/\\]",       "[/\\]env[/\\]",
  
  -- Caches e VCS
  "[/\\]__pycache__[/\\]",  "^__pycache__[/\\]",
  "[/\\]%.pytest_cache[/\\]", "[/\\]%.mypy_cache[/\\]", "[/\\]%.ruff_cache[/\\]",
  "[/\\]%.git[/\\]",        "^%.git[/\\]",
  "[/\\]%.idea[/\\]",       "[/\\]%.vscode[/\\]",
  
  -- Node e Builds
  "[/\\]node_modules[/\\]", "^node_modules[/\\]",
  "[/\\]dist[/\\]",         "[/\\]build[/\\]",
  "[/\\]%.egg%-info[/\\]",
  
  -- Arquivos de Lixo
  "%.pyc$", "%.pyo$", "%.pyd$",
  "%.DS_Store$", "Thumbs%.db$"
}

for _, pattern in ipairs(ignored_patterns) do
  table.insert(config.ignore_files, pattern)
end
