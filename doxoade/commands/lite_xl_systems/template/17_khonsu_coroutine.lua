-- doxoade/commands/lite_xl_systems/template/17_khonsu_coroutine.lua
--[[
  🌙 KHONSU ADAPTIVE SCHEDULER & FRAME GOVERNOR (V2.0 Pilar 2)
  - Frame Deadline Scheduling: Orçamento de tempo dinâmico calculado por frame.
  - Regimes Reativos: 0.5ms durante digitação ativa e até 8.0ms em repouso.
  - Khonsu.should_yield(): Sonda universal O(1) de cooperação para corrotinas.
  - Debounce & Throttle com preservação de estado.
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = require "core"
local config = require "core.config"

local Khonsu = {
  active_jobs = {},
  job_generations = {},
  debounce_timers = {},
  throttle_timers = {},
  
  -- Métricas de Frame do Governador
  frame_start_clock = os.clock(),
  last_user_activity = os.clock(),
  default_budget_ms = 2.0,
  min_budget_ms = 0.5,
  max_budget_ms = 8.0,
  reserved_render_ms = 3.5,
}
rawset(_G, "Khonsu", Khonsu)

-- =============================================================================
-- ⏱️ GOVERNADOR TEMPORAL ADAPTATIVO (PILAR 2)
-- =============================================================================

function Khonsu.on_frame_start()
  Khonsu.frame_start_clock = os.clock()
end

function Khonsu.notify_user_activity()
  Khonsu.last_user_activity = os.clock()
end

function Khonsu.is_user_active()
  -- Usuário é considerado ativo por 0.35s após o último toque
  return (os.clock() - Khonsu.last_user_activity) < 0.35
end

function Khonsu.get_adaptive_budget()
  local target_fps = config.fps or 60
  local frame_limit_ms = 1000.0 / target_fps
  
  -- Se o usuário estiver digitando ou rolando, impõe orçamento mínimo para blindar 60 FPS
  if Khonsu.is_user_active() then
    return Khonsu.min_budget_ms / 1000.0
  end

  local elapsed_in_frame_ms = (os.clock() - Khonsu.frame_start_clock) * 1000.0
  local available_ms = frame_limit_ms - elapsed_in_frame_ms - Khonsu.reserved_render_ms

  local clamped_ms = math.max(Khonsu.min_budget_ms, math.min(Khonsu.max_budget_ms, available_ms))
  return clamped_ms / 1000.0
end

function Khonsu.should_yield(slice_t0, custom_max_sec)
  local t0 = slice_t0 or os.clock()
  local max_sec = custom_max_sec or Khonsu.get_adaptive_budget()
  
  -- Cede a CPU se o lote ultrapassou a folga do frame
  if (os.clock() - t0) >= max_sec then
    return true
  end

  -- Cede forçadamente se o frame global estiver próximo do estouro de 16.6ms
  local frame_elapsed_sec = os.clock() - Khonsu.frame_start_clock
  local frame_deadline_sec = (1000.0 / (config.fps or 60)) / 1000.0
  if (frame_deadline_sec - frame_elapsed_sec) <= (Khonsu.reserved_render_ms / 1000.0) then
    return true
  end

  return false
end

-- =============================================================================
-- 🔄 DEBOUNCE E THROTTLE REATIVOS
-- =============================================================================

function Khonsu.debounce(id, delay_sec, action_fn)
  Khonsu.debounce_timers[id] = {
    target_time = os.clock() + (delay_sec or 0.08),
    action = action_fn,
  }
end

function Khonsu.throttle(id, interval_sec, action_fn)
  local now = os.clock()
  local last = Khonsu.throttle_timers[id] or 0
  if (now - last) >= (interval_sec or 0.25) then
    Khonsu.throttle_timers[id] = now
    pcall(action_fn)
  end
end

-- =============================================================================
-- 🌙 THREADS DO KHONSU & HOOK DO FRAME
-- =============================================================================

-- Sincroniza o início do frame no loop do core.step
if core and core.step then
  local original_step = core.step
  core.step = function(...)
    Khonsu.on_frame_start()
    return original_step(...)
  end
end

-- Loop de Debounce escalonado
if core and core.add_thread then
  core.add_thread(function()
    while true do
      if next(Khonsu.debounce_timers) == nil then
        coroutine.yield(0.25)  -- Sono profundo quando não há timers
      else
        coroutine.yield(0.02)
        local now = os.clock()
        local expired = {}
        for id, timer in pairs(Khonsu.debounce_timers) do
          if now >= timer.target_time then
            table.insert(expired, timer.action)
            Khonsu.debounce_timers[id] = nil
          end
        end
        for i = 1, #expired do
          pcall(expired[i])
        end
      end
    end
  end)
end

if core.log then
  core.log("🌙 [KHONSU V2] Governador Adaptativo de Frame ativo (Pilar 2).")
end

return Khonsu
