# -*- coding: utf-8 -*-
# doxoade/tools/lua_systems/profiler/profiler_schema.py
"""
Esquemas e Estruturas de Dados de Telemetria de Performance.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any


@dataclass
class BootMetric:
    module: str
    status: str
    time_ms: float
    error: Optional[str] = None


@dataclass
class FrameMetric:
    timestamp: str
    duration_ms: float
    fps: float
    active_file: str
    lines_count: int
    is_spike: bool = False  # True se frame > 16.6ms (60 FPS drop)


@dataclass
class ThreadMetric:
    coroutine_id: str
    duration_ms: float
    status: str  # "OK" ou "BLOCKING" (> 5ms)
    time: str


@dataclass
class ProfilerReport:
    timestamp: str
    total_boot_time_ms: float
    boot_modules: List[BootMetric] = field(default_factory=list)
    frame_spikes: List[FrameMetric] = field(default_factory=list)
    thread_bottlenecks: List[ThreadMetric] = field(default_factory=list)
    gc_memory_kb: float = 0.0
    average_fps: float = 60.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProfilerReport:
        boot_list = [BootMetric(**m) for m in data.get("boot_modules", [])]
        frame_list = [FrameMetric(**f) for f in data.get("frame_spikes", [])]
        thread_list = [ThreadMetric(**t) for t in data.get("thread_bottlenecks", [])]
        return cls(
            timestamp=data.get("timestamp", ""),
            total_boot_time_ms=data.get("total_boot_time_ms", 0.0),
            boot_modules=boot_list,
            frame_spikes=frame_list,
            thread_bottlenecks=thread_list,
            gc_memory_kb=data.get("gc_memory_kb", 0.0),
            average_fps=data.get("average_fps", 60.0)
        )
