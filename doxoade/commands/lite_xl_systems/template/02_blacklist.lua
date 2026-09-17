-- doxoade/commands/lite_xl_systems/template/02_blacklist.lua
-- =============================================================================
-- 🛡️ DOXOADE PROJECT BLACKLIST & SCAN RATE OPTIMIZER
-- Bloqueia a varredura desnecessária de backups, caches e lixo temporal pelo
-- project_scan_thread do Lite XL, reduzindo o I/O contínuo no disco a zero.
-- =============================================================================
local config = require "core.config"

-- Ajusta o intervalo de re-varredura para um regime inteligente (15s em vez de 5s)
config.project_scan_rate = 15
config.max_project_files = 15000

local ignored_patterns = {
  -- Bloqueio universal de pastas de infraestrutura (independente de onde o Lite XL foi aberto)
  "%.doxoade/",
  "%.doxoade$",
  "%.doxoade_cache/",
  "%.doxoade_cache$",
  "w64devkit/",
  "%.tar%.gz$",
  "%.bak$",
  "%.old$",
  "%.tmp$",
  "%.pot$",
  "%.rlebin$",

  -- Ambientes Virtuais e Dependências
  "venv/",
  "%.venv/",
  "env/",
  "node_modules/",

  -- Caches
  "__pycache__/",
  "%.pytest_cache/",
  "%.mypy_cache/",
  "%.ruff_cache/",
  "dist/",
  "build/",
  "%.egg%-info/",
  "%.pyc$",
  "%.DS_Store$",
  "Thumbs%.db$"
}

-- local ignored_patterns = {
--   -- Infraestrutura Doxoade e Backups pesados (FRENTE 1)
--   "^%.doxoade[/\\]",        "[/\\]%.doxoade[/\\]",
--   "^%.doxoade_cache[/\\]",  "[/\\]%.doxoade_cache[/\\]",
--   "%.tar%.gz$",             "%.bak$",
--   "%.old$",                 "%.tmp$",
--   "%.pot$",                 "%.rlebin$",

--   -- Ambientes Virtuais e Dependências
--   "^%.?venv[/\\]",          "^venv[/\\]",
--   "^%.?env[/\\]",           "^env[/\\]",
--   "[/\\]%.?venv[/\\]",      "[/\\]venv[/\\]",
--   "[/\\]%.?env[/\\]",       "[/\\]env[/\\]",
--   "[/\\]node_modules[/\\]", "^node_modules[/\\]",

--   -- Caches de Linguagem e Compilação
--   "[/\\]__pycache__[/\\]",  "^__pycache__[/\\]",
--   "[/\\]%.pytest_cache[/\\]", "[/\\]%.mypy_cache[/\\]", "[/\\]%.ruff_cache[/\\]",
--   "[/\\]dist[/\\]",         "[/\\]build[/\\]",
--   "[/\\]%.egg%-info[/\\]",
--   "%.pyc$", "%.pyo$", "%.pyd$",

--   -- Git e IDEs
--   "[/\\]%.git[/\\]",        "^%.git[/\\]",
--   "[/\\]%.idea[/\\]",       "[/\\]%.vscode[/\\]",
--   "%.DS_Store$", "Thumbs%.db$"
-- }

for _, pattern in ipairs(ignored_patterns) do
  table.insert(config.ignore_files, pattern)
end
