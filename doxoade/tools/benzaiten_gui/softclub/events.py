# -*- coding: utf-8 -*-
# doxoade/tools/benzaiten_gui/softclub/events.py
"""
SOFTCLUB EVENTS — base mínima para migração para eventos.

Doutrina:
- não criar thread nova;
- não introduzir loop Python concorrente;
- apenas centralizar publicação/escuta de eventos;
- permitir repaint coalescido no futuro.
"""

from collections import defaultdict


class EventBus:
    def __init__(self):
        self._handlers = defaultdict(list)

    def on(self, event, handler):
        self._handlers[event].append(handler)
        return handler

    def off(self, event, handler=None):
        if handler is None:
            self._handlers.pop(event, None)
            return

        if event in self._handlers:
            try:
                self._handlers[event].remove(handler)
            except ValueError:
                pass

    def emit(self, event, *args, **kwargs):
        for fn in list(self._handlers.get(event, [])):
            try:
                fn(*args, **kwargs)
            except Exception:
                # UI não pode morrer por causa de um listener.
                pass