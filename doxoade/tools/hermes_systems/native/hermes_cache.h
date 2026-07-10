// doxoade/tools/hermes_systems/native/hermes_cache.h
#pragma once
#include <Python.h>
#include <stdint.h>

// ═══════════════════════════════════════════════════════════════════
// TIER 1: RAM LRU CACHE (Sessão Atual)
// ═══════════════════════════════════════════════════════════════════
void cache_ram_init(int max_size);
PyObject* cache_ram_get(const char* hermes_path);
void cache_ram_put(const char* hermes_path, PyObject* code_obj);

// ═══════════════════════════════════════════════════════════════════
// TIER 2: DISK MARSHAL CACHE (Persistente)
// ═══════════════════════════════════════════════════════════════════
// Tenta carregar do .hcache. Retorna NULL se MISS ou corrompido.
// Retorna NEW REFERENCE se HIT.
PyObject* cache_disk_load(const char* hermes_path);

// Salva o code_object no .hcache usando PyMarshal.
// Retorna 1 se sucesso, 0 se falha.
int cache_disk_save(const char* hermes_path, PyObject* code_obj);