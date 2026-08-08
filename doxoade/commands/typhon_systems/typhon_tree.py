# doxoade/doxoade/commands/typhon_systems/typhon_tree.py
# -*- coding: utf-8 -*-
"""
TYPHON CHAOS — árvore de diagnóstico do Doxoade.

Sistemas → modos de falha → sintomas + comentário do dev + mitigação.

Typhon não apenas lista falhas: ele prova sensibilidade contra falhas
injetáveis e entrega probes para falhas silenciosas.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class FailureMode:
    id: str
    name: str
    severity: str = "high"
    symptoms: tuple = ()
    dev_comment: str = ""
    mitigation: str = ""


@dataclass
class Node:
    id: str
    name: str
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)
    failures: List[FailureMode] = field(default_factory=list)


class DiagnosticTree:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.failures: Dict[str, FailureMode] = {}

    def node(self, nid, name, parent=None):
        n = Node(nid, name, parent)
        self.nodes[nid] = n
        if parent in self.nodes:
            self.nodes[parent].children.append(nid)
        return n

    def failure(self, nid, **kw):
        fm = FailureMode(**kw)
        self.nodes[nid].failures.append(fm)
        self.failures[fm.id] = fm
        return fm


TREE = DiagnosticTree()

TREE.node("doxoade", "Doxoade (raiz)")
TREE.node("locator", "Locator · descoberta do doxoade.db", "doxoade")
TREE.node("persist", "Persistência · SQLite", "doxoade")
TREE.node("horus", "Horus · operational_logs", "persist")
TREE.node("soteria", "Soteria · envelopes", "doxoade")
TREE.node("runtime", "Runtime · env/processo", "doxoade")


TREE.failure(
    "locator",
    id="doxoade.db.missing",
    name="DB do Doxoade ausente",
    severity="critical",
    symptoms=(
        r"doxoade\.db ausente",
        r"doxoade\.db não localizado",
    ),
    dev_comment=(
        "O Typhon precisa localizar o doxoade.db para escrever/ler "
        "heartbeats e validar o estado do Horus. Sem DB, a observabilidade "
        "fica cega."
    ),
    mitigation=(
        "Verificar DOXOADE_GLOBAL_DB, DOXOADE_ROOT e data/doxoade.db. "
        "Rodar migration/bootstrap se o banco não existir."
    ),
)


TREE.failure(
    "runtime",
    id="doxoade.env.invalid",
    name="DOXOADE_GLOBAL_DB inválido",
    severity="high",
    symptoms=(r"DOXOADE_GLOBAL_DB inválido",),
    dev_comment=(
        "A env DOXOADE_GLOBAL_DB aponta para um caminho inexistente ou "
        "não legível. Isso pode fazer o locator escolher outro DB ou falhar."
    ),
    mitigation="Corrigir a env ou remover a variável para usar o default.",
)


TREE.failure(
    "horus",
    id="doxoade.op_logs.missing",
    name="Tabela operational_logs ausente",
    severity="critical",
    symptoms=(r"operational_logs ausente",),
    dev_comment=(
        "O Horus depende da tabela operational_logs. Sem ela, heartbeats "
        "não persistem e o Typhon perde memória de eventos."
    ),
    mitigation="Rodar migration do operational_logs ou criar tabela base.",
)


TREE.failure(
    "persist",
    id="doxoade.db.locked",
    name="SQLite locked",
    severity="high",
    symptoms=(r"database is locked",),
    dev_comment=(
        "SQLite pode travar em escrita concorrente, timeout curto ou "
        "journal mode inadequado."
    ),
    mitigation=(
        "Usar timeout maior, WAL se adequado, transações curtas e "
        "evitar writes longos dentro de loops."
    ),
)


TREE.failure(
    "persist",
    id="doxoade.sqlite.integrity",
    name="SQLite integrity_check falhou",
    severity="critical",
    symptoms=(r"integrity_check",),
    dev_comment=(
        "PRAGMA integrity_check diferente de ok indica corrupção ou "
        "problema grave no arquivo SQLite."
    ),
    mitigation="Backup imediato, dump/rebuild do banco e investigação de I/O.",
)


TREE.failure(
    "horus",
    id="doxoade.heartbeat.write_failed",
    name="Falha ao escrever heartbeat",
    severity="high",
    symptoms=(r"heartbeat write failed",),
    dev_comment=(
        "O heartbeat pode falhar por DB ausente, schema errado, permissão "
        "ou lock. O Typhon deve cair para fallback local e emitir sinal."
    ),
    mitigation=(
        "Manter fallback local em data/logs/typhon_heartbeats.jsonl e "
        "investigar operational_logs."
    ),
)


TREE.failure(
    "soteria",
    id="soteria.envelope.malformed",
    name="Envelope Soteria malformado",
    severity="medium",
    symptoms=(r"envelope malformado",),
    dev_comment=(
        "Envelope sem TAG_MOTIVO ou com BEGIN/END quebrado não pode ser "
        "diagnosticado corretamente."
    ),
    mitigation="Validar emissão de envelopes e normalizar TAG_MOTIVO.",
)


TREE.failure(
    "horus",
    id="doxoade.census.divergence",
    name="Censo de heartbeats divergente",
    severity="critical",
    symptoms=(r"censo: .* evaporados",),
    dev_comment=(
        "Heartbeats locais existem, mas não aparecem no operational_logs, "
        "ou eventos esperados não foram persistidos. É a versão Doxoade do "
        "censo de três vias do Thoth."
    ),
    mitigation=(
        "Comparar heartbeats locais, inserts no operational_logs e eventos "
        "esperados pelo pipeline. Ativar probes sob demanda."
    ),
)
