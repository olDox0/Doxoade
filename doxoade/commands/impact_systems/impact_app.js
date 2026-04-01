// impact_app.js

// 1. Expor a aplicação na window IMEDIATAMENTE para o HTML nativo poder achá-la
window.NexusApp = {
    data: window.BACKEND_DATA,
    elements: {
        graphContainer: document.getElementById('graph-view'),
        sidebar: document.getElementById('sidebar'),
        rawMermaid: document.getElementById('raw-mermaid')
    },
    panZoomInstance: null,

    async init() {
        this.UI.Sidebar.renderSummary();
        await this.Graph.render();
    },

    Graph: {
        async render() {
            const graphDef = window.NexusApp.elements.rawMermaid.textContent.trim();
            mermaid.initialize({
                startOnLoad: false, 
                theme: 'base',
                themeVariables: { lineColor: '#5e5c5e', primaryTextColor: '#d2dce6' },
                securityLevel: 'loose', // Exige 'loose' para aceitar divs clicáveis
                maxTextSize: 900000
            });

            try {
                const { svg } = await mermaid.render('the-mermaid-svg', graphDef);
                window.NexusApp.elements.graphContainer.innerHTML = svg;
                
                const svgEl = document.getElementById('the-mermaid-svg');
                svgEl.style.maxWidth = 'none';
                svgEl.style.width = '100%';
                svgEl.style.height = '100%';

                // Ativa o zoom (ele não vai mais engolir nossos cliques nativos!)
                window.NexusApp.panZoomInstance = svgPanZoom(svgEl, {
                    zoomEnabled: true, controlIconsEnabled: true, fit: true, center: true, minZoom: 0.1, maxZoom: 10
                });

                // AQUI NÃO TEM MAIS "bindNodeClicks"! O próprio HTML cuida disso.

            } catch (err) {
                window.NexusApp.elements.graphContainer.innerHTML = `<div style="color: var(--target); padding:20px;">[FATAL ERROR] Falha no Grafo:<br>${err}</div>`;
            }
        }
    },

    UI: {
        Sidebar: {
            renderModule(moduleName) {
                const node = window.NexusApp.data.nodes.find(n => n.id === moduleName);
                if (!node) return;

                const isExternal = node.external;
                const tagClass = isExternal ? 'tag-external' : 'tag-internal';
                const typeLabel = isExternal ? 'Externa / Stdlib' : 'Módulo Interno';
                
                const imports = window.NexusApp.data.edges.filter(e => e.source === node.id).map(e => e.target);
                const importedBy = window.NexusApp.data.edges.filter(e => e.target === node.id).map(e => e.source);

                let html = `
                    <div class="sidebar-header">
                        <h2 style="color: var(--accent-primary); font-size: 1.1rem; word-break: break-all;">${node.id}</h2>
                        <div style="margin-top: 5px;"><span class="tag ${tagClass}">${typeLabel}</span></div>
                        ${node.path ? `<div class="file-path">🖫 ${node.path}</div>` : ''}
                    </div>
                    <div class="sidebar-content">
                        <div class="panel-section">
                          <h3>Importa / Consome (${imports.length})</h3>
                          ${this.buildList(imports)}
                        </div>
                        <div class="panel-section">
                          <h3>Usado por / Dependem (${importedBy.length})</h3>
                          ${this.buildList(importedBy)}
                        </div>
                        ${node.defines && node.defines.length > 0 ? 
                            `<div class="panel-section">
                              <h3>Funções / Objetos</h3>
                              ${this.buildList(node.defines, false)}
                            </div>` : ''}
                    </div>
                `;
                window.NexusApp.elements.sidebar.innerHTML = html;
            },

            renderSummary() {
                if (!window.NexusApp.data.stats) return;
                const html = `
                    <div class="sidebar-header"><h2 style="color: var(--accent-primary);">Ecossistema Global</h2></div>
                    <div class="sidebar-content">
                        <div class="panel-section">
                            <h3>Métricas de Acoplamento</h3>
                            <ul class="item-list">
                                <li style="cursor:default;">Total de Nós: <strong style="color:var(--accent-primary)">${window.NexusApp.data.stats.nodes}</strong></li>
                                <li style="cursor:default;">Arestas: <strong style="color:var(--accent-primary)">${window.NexusApp.data.stats.edges}</strong></li>
                            </ul>
                        </div>
                        <div class="empty-state">O painel aguarda conexão.<br><br>Clique em um módulo no ecossistema ao lado para escanear.</div>
                    </div>
                `;
                window.NexusApp.elements.sidebar.innerHTML = html;
            },

            buildList(items, clickable = true) {
                if (!items || items.length === 0) return '<div style="color:var(--text-muted); font-size:0.8rem;">[ Vazio / Nenhum ]</div>';
                const liItems = items.map(item => {
                    return clickable 
                        ? `<li onclick="window.NexusApp.UI.Sidebar.renderModule('${item}')">▶ ${item}</li>`
                        : `<li style="cursor:default;">• ${item}</li>`;
                }).join('');
                return `<ul class="item-list">${liItems}</ul>`;
            }
        }
    }
};

// 2. Inicia tudo quando a página carrega
document.addEventListener('DOMContentLoaded', () => window.NexusApp.init());