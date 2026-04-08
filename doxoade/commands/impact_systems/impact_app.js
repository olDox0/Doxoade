// impact_app.js

// ── Callback global chamado pelo Mermaid (click nodeId callbackName) ──────────
// Mermaid 10 passa o ID do nó (ex: "n_doxoade_commands_impact_analysis")
// como primeiro argumento, não o nome do módulo diretamente.
window.nexusNodeClick = function(nodeId) {
    const modName = window.NexusApp.Graph._nodeIdToModule(nodeId);
    if (modName) window.NexusApp.UI.Sidebar.renderModule(modName);
};

// Chamado pelo botão "👁 Ocultar" dentro do painel lateral.
window.nexusNodeToggleHide = function(modName) {
    const targetId = 'n_' + modName.replace(/\./g, '_').replace(/-/g, '_');
    document.querySelectorAll('g.node').forEach(g => {
        if (g.id && g.id.includes(targetId)) {
            g.classList.toggle('nexus-hidden-node');
        }
    });
};

// ── Aplicação principal ───────────────────────────────────────────────────────
window.NexusApp = {
    data: window.BACKEND_DATA,
    elements: {
        graphContainer: document.getElementById('graph-view'),
        sidebar:        document.getElementById('sidebar'),
        rawMermaid:     document.getElementById('raw-mermaid')
    },
    panZoomInstance: null,

    async init() {
        this.UI.Sidebar.renderSummary();
        await this.Graph.render();
    },

    // ── Grafo ─────────────────────────────────────────────────────────────────
    Graph: {

        /**
         * Converte o ID do nó Mermaid (ex: "flowchart-n_doxoade_commands-12")
         * de volta para o nome do módulo Python (ex: "doxoade.commands").
         * Usa os dados já embutidos no HTML via BACKEND_DATA.
         */
        _nodeIdToModule(rawId) {
            for (const node of window.NexusApp.data.nodes) {
                const expected = 'n_' + node.id.replace(/\./g, '_').replace(/-/g, '_');
                if (rawId === expected || rawId.includes(expected)) {
                    return node.id;
                }
            }
            return null;
        },

        async render() {
            const graphDef = window.NexusApp.elements.rawMermaid.textContent.trim();

            mermaid.initialize({
                startOnLoad: false,
                theme: 'base',
                themeVariables: { lineColor: '#5e5c5e', primaryTextColor: '#d2dce6' },
                securityLevel: 'loose',
                maxTextSize: 900000
            });

            try {
                const { svg } = await mermaid.render('the-mermaid-svg', graphDef);
                window.NexusApp.elements.graphContainer.innerHTML = svg;

                const svgEl = document.getElementById('the-mermaid-svg');
                svgEl.style.maxWidth = 'none';
                svgEl.style.width    = '100%';
                svgEl.style.height   = '100%';

                window.NexusApp.panZoomInstance = svgPanZoom(svgEl, {
                    zoomEnabled: true, controlIconsEnabled: true,
                    fit: true, center: true, minZoom: 0.1, maxZoom: 10
                });

                // ── Listener no CONTAINER (div), não no svgEl ─────────────────
                // O svg-pan-zoom opera dentro do SVG; eventos do SVG ainda sobem
                // normalmente até o div pai. Ouvindo aqui evitamos qualquer
                // interferência do svg-pan-zoom com cliques nos nós.
                window.NexusApp.elements.graphContainer.addEventListener('click', (e) => {
                    const gNode = e.target.closest('g.node');
                    if (gNode) {
                        const modName = window.NexusApp.Graph._nodeIdToModule(gNode.id);
                        if (modName) window.NexusApp.UI.Sidebar.renderModule(modName);
                    } else {
                        window.NexusApp.UI.Sidebar.renderSummary();
                    }
                });

                // Botão direito no nó → oculta/exibe
                window.NexusApp.elements.graphContainer.addEventListener('contextmenu', (e) => {
                    const gNode = e.target.closest('g.node');
                    if (gNode) {
                        e.preventDefault();
                        const modName = window.NexusApp.Graph._nodeIdToModule(gNode.id);
                        if (modName) window.nexusNodeToggleHide(modName);
                    }
                });

            } catch (err) {
                window.NexusApp.elements.graphContainer.innerHTML =
                    `<div style="color:var(--target);padding:20px;">[FATAL ERROR] Falha no Grafo:<br>${err}</div>`;
            }
        },
    },

    // ── UI ────────────────────────────────────────────────────────────────────
    UI: {
        Sidebar: {

            renderModule(moduleName) {
                const node = window.NexusApp.data.nodes.find(n => n.id === moduleName);
                if (!node) return;

                const isExternal = node.external;
                const tagClass   = isExternal ? 'tag-external' : 'tag-internal';
                const typeLabel  = isExternal ? 'Externa / Stdlib' : 'Módulo Interno';

                const imports    = window.NexusApp.data.edges.filter(e => e.source === node.id).map(e => e.target);
                const importedBy = window.NexusApp.data.edges.filter(e => e.target === node.id).map(e => e.source);

                const buildExpandableList = (moduleList, icon, dir) => {
                    if (!moduleList || moduleList.length === 0) {
                        return `<div style="color:var(--text-muted);font-size:0.8rem;padding-top:5px;">Nenhuma dependência</div>`;
                    }
                    return `<ul class="item-list">` + moduleList.sort().map(modId => {
                        const edge = window.NexusApp.data.edges.find(e =>
                            dir === 'out'
                                ? (e.source === node.id && e.target === modId)
                                : (e.source === modId  && e.target === node.id)
                        );
                        const importNames = (edge && edge.imports && edge.imports.length > 0) ? edge.imports : [];
                        const safeId      = `nexus-imp-${dir}-${modId.replace(/[.\-]/g, '_')}`;

                        return `
                        <li onclick="const d=document.getElementById('${safeId}');if(d)d.classList.toggle('nexus-open')"
                            title="Clique para ver os nomes importados">
                            <span class="nexus-imp-row">
                                <span>${icon} ${modId}</span>
                                ${importNames.length > 0
                                    ? `<span class="nexus-imp-count">${importNames.length}</span>`
                                    : ''}
                            </span>
                            ${importNames.length > 0
                                ? `<div id="${safeId}" class="nexus-imp-detail">
                                       ${importNames.map(n => `<span class="nexus-imp-name">ƒ ${n}</span>`).join('')}
                                   </div>`
                                : ''}
                        </li>`;
                    }).join('') + `</ul>`;
                };

                let functionsHtml = '';
                if (node.metadata && Object.keys(node.metadata).length > 0) {
                    const funcItems = Object.entries(node.metadata)
                        .sort((a, b) => a[1].line - b[1].line)
                        .map(([fName, meta]) => {
                            const callCount = meta.calls ? meta.calls.length : 0;
                            return `<li>
                                <span style="color:var(--target);font-weight:bold;">Linha ${meta.line}</span>
                                <span style="color:var(--text-muted)"> | </span>
                                <b>${fName}()</b>
                                <div style="font-size:0.7rem;color:var(--text-muted);margin-top:3px;padding-left:5px;">
                                    ${callCount > 0
                                        ? '↳ Dispara ' + callCount + ' chamadas'
                                        : '· Sem chamadas aninhadas'}
                                </div>
                            </li>`;
                        }).join('');
                    functionsHtml = `
                        <div class="panel-section">
                            <h3>Estrutura Interna (Linhas)</h3>
                            <ul class="item-list">${funcItems}</ul>
                        </div>`;
                } else if (!isExternal) {
                    functionsHtml = `<div class="panel-section"><h3 style="color:var(--text-muted)">Nenhuma função extraída</h3></div>`;
                }

                window.NexusApp.elements.sidebar.innerHTML = `
                    <div class="sidebar-header">
                        <h2>${node.id}</h2>
                        <div style="margin-top:8px;display:flex;align-items:center;gap:10px;">
                            <span class="tag ${tagClass}">${typeLabel}</span>
                            <button
                                onclick="window.nexusNodeToggleHide('${node.id}')"
                                title="Ocultar / Exibir este nó no grafo"
                                style="background:var(--panel-light);border:1px solid var(--border);
                                       color:var(--text-muted);border-radius:4px;padding:3px 10px;
                                       cursor:pointer;font-size:0.75rem;transition:all 0.2s;"
                                onmouseover="this.style.color='var(--warning)';this.style.borderColor='var(--warning)'"
                                onmouseout ="this.style.color='var(--text-muted)';this.style.borderColor='var(--border)'"
                            >👁 Ocultar no grafo</button>
                        </div>
                        ${node.path ? `<div class="file-path">📄 ${node.path}</div>` : ''}
                    </div>
                    <div class="sidebar-content">
                        <div class="panel-section">
                            <h3 style="color:var(--pastel-blue)">Importa / Consome (${imports.length})</h3>
                            ${buildExpandableList(imports, '→', 'out')}
                        </div>
                        <div class="panel-section">
                            <h3 style="color:var(--pastel-orange)">Usado por / Dependentes (${importedBy.length})</h3>
                            ${buildExpandableList(importedBy, '←', 'in')}
                        </div>
                        ${functionsHtml}
                    </div>
                `;
            },

            renderSummary() {
                if (!window.NexusApp.data || !window.NexusApp.data.stats) return;
                const s = window.NexusApp.data.stats;
                window.NexusApp.elements.sidebar.innerHTML = `
                    <div class="sidebar-header">
                        <h2 style="color:var(--accent-primary);">Ecossistema Global</h2>
                    </div>
                    <div class="sidebar-content">
                        <div class="panel-section">
                            <h3>Métricas de Acoplamento</h3>
                            <ul class="item-list">
                                <li style="cursor:default;">Total de Módulos:
                                    <strong style="color:var(--pastel-blue)">${s.nodes}</strong></li>
                                <li style="cursor:default;">Conexões (Imports):
                                    <strong style="color:var(--pastel-orange)">${s.edges}</strong></li>
                                <li style="cursor:default;">Módulos Isolados:
                                    <strong style="color:var(--warning)">${s.isolated.length}</strong></li>
                            </ul>
                        </div>
                        <div class="empty-state">
                            <span style="font-size:2rem;">🔍</span><br><br>
                            <b>Clique esquerdo</b> em um nó para analisar.<br>
                            <b>Clique direito</b> para ocultar/exibir o nó.<br><br>
                            <span style="font-size:0.8rem;color:var(--text-muted)">
                                Botão 👁 no painel também oculta o nó.
                            </span>
                        </div>
                    </div>
                `;
            }
        }
    }
};

// ── Inicialização ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => window.NexusApp.init());