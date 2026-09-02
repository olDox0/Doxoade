-- doxoade/commands/lite_xl_systems/template/16_open_editors_dock.lua
--[[ Painel Soberano de "Open Editors" (Arquivos Abertos em Escadaria Vertical).
- Resolve a dor de "não querer olhar a TreeView" para gerenciar abas.
- Lista todos os documentos abertos em uma "escadaria" vertical (Dock).
- Cache inteligente de travessia de nós para garantir 60 FPS (Hórus).
- Permite navegação rápida, scroll e indica arquivos modificados (Dirty). ]]
local core = require "core"
local View = require "core.view"
local command = require "core.command"
local style = require "core.style"
local config = require "core.config"

-- 🛡️ Polyfills Universais C (Doxoade Standard)
local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local function draw_rect_safe(x, y, w, h, color)
    if rencache and rencache.draw_rect then rencache.draw_rect(x, y, w, h, color)
    elseif native_renderer and native_renderer.draw_rect then native_renderer.draw_rect(x, y, w, h, color) end
end

local function draw_text_safe(font, text, x, y, color)
    if rencache and rencache.draw_text then rencache.draw_text(font, text, x, y, color)
    elseif native_renderer and native_renderer.draw_text then native_renderer.draw_text(font, text, x, y, color) end
end

-- =============================================================================
-- 🏛️ CLASSE SOBERANA: OPEN EDITORS VIEW
-- =============================================================================
local OpenEditorsView = View:extend()

function OpenEditorsView:new()
    -- 🛡️ Inicialização manual resiliente (contorna falha de 'super' no Shadow Harness headless)
    self.scrollable = true
    self.font = style.font
    self.line_height = 26
    self.header_height = 32
    self.hovered_idx = nil
    self.cached_docs = {}
    self.cache_version = 0
    self.last_node_structure = ""
    
    -- Tenta delegar para a classe base APENAS se o método existir (Lite XL real)
    if View.init then
        pcall(View.init, self)
    elseif OpenEditorsView.super and OpenEditorsView.super.new then
        pcall(OpenEditorsView.super.new, self)
    end
end

function OpenEditorsView:get_name()
    return "Open Editors"
end

-- =============================================================================
-- 🔄 MOTOR DE CACHE (TRAVESSIA DA ÁRVORE SEM FRAME SPIKES)
-- =============================================================================
function OpenEditorsView:get_open_docs()
    -- 1. Gera uma "assinatura" rápida da estrutura atual da árvore
    -- (Conta nós folha e views. Muito mais rápido que comparar tabelas profundas)
    local leaf_count = 0
    local view_count = 0
    local function count_structure(node)
        if not node then return end
        if node.type == "leaf" then
            leaf_count = leaf_count + 1
            view_count = view_count + #(node.views or {})
        else
            count_structure(node.a)
            count_structure(node.b)
        end
    end
    count_structure(core.root_view.root_node)
    
    local current_signature = leaf_count .. ":" .. view_count
    
    -- 2. Se a estrutura não mudou, retorna o cache (O(1))
    if current_signature == self.last_node_structure and #self.cached_docs > 0 then
        return self.cached_docs
    end
    
    -- 3. Estrutura mudou: reconstrói o cache (O(N))
    self.last_node_structure = current_signature
    local docs = {}
    local seen = {}
    
    local function traverse(node)
        if not node then return end
        if node.type == "leaf" then
            for _, view in ipairs(node.views or {}) do
                if view and view.doc and not seen[view.doc] then
                    seen[view.doc] = true
                    table.insert(docs, { 
                        doc = view.doc, 
                        node = node, 
                        view = view,
                        rect = nil -- Será preenchido no draw
                    })
                end
            end
        else
            traverse(node.a)
            traverse(node.b)
        end
    end
    traverse(core.root_view.root_node)
    
    self.cached_docs = docs
    return docs
end

-- =============================================================================
-- 🎨 RENDERIZAÇÃO (EFEITO ESCADARIA / EMPILHAMENTO VERTICAL)
-- =============================================================================
function OpenEditorsView:draw()
    self:draw_background(style.background2)
    
    local x, y = self.position.x, self.position.y
    local w, h = self.size.x, self.size.y
    local font = self.font
    local scroll_y = self.scroll and self.scroll.y or 0
    
    -- 1. Cabeçalho Fixo (Não rola com o scroll)
    draw_rect_safe(x, y, w, self.header_height, style.background)
    draw_text_safe(font, "⚡ OPEN EDITORS (Escadaria)", x + 12, y + 10, style.accent)
    draw_rect_safe(x, y + self.header_height - 1, w, 1, style.divider)
    
    local current_y = y + self.header_height - scroll_y
    local docs = self:get_open_docs()
    local active_doc = core.active_view and core.active_view.doc
    
    for i, item in ipairs(docs) do
        local doc = item.doc
        local is_active = (doc == active_doc)
        local is_hovered = (self.hovered_idx == i)
        
        -- 🪜 EFEITO ESCADARIA (Indentação progressiva + Camadas)
        local indent = math.min(i * 3, 15) -- Máximo 15px de indentação
        local row_w = w - indent
        
        -- Fundo da "Camada"
        local bg_color = style.background2
        if is_active then bg_color = style.background3
        elseif is_hovered then bg_color = style.background3 end
        
        -- Desenha o fundo da aba empilhada
        draw_rect_safe(x + indent, current_y, row_w, self.line_height, bg_color)
        
        -- 🌑 SOMBRA DE PROFUNDIDADE (Efeito de pilha de papéis)
        draw_rect_safe(x + indent, current_y + self.line_height - 2, row_w, 2, { 0, 0, 0, 40 })
        
        -- 🟡 INDICADOR DE MODIFICADO (Dirty)
        local is_dirty = false
        pcall(function() is_dirty = doc:is_dirty() end)
        if is_dirty then
            draw_rect_safe(x + indent, current_y, 3, self.line_height, { 234, 179, 8, 255 })
        end
        
        -- 📝 TEXTO (Nome do Arquivo)
        local fname = doc.filename and doc.filename:match("[/\\]([^/\\]+)$") or "Untitled"
        local text_color = is_active and style.accent or style.text
        draw_text_safe(font, fname, x + indent + 12, current_y + 6, text_color)
        
        -- Salva o retângulo para interação do mouse (ajustado com o scroll)
        item.rect = { 
            x = x + indent, 
            y = current_y, 
            w = row_w, 
            h = self.line_height 
        }
        
        current_y = current_y + self.line_height
    end
    
    -- Atualiza o tamanho virtual para o scroll do Lite XL
    local total_content_h = (#docs * self.line_height) + self.header_height
    self.size.y = h -- Mantém o tamanho real da viewport
    if self.scroll then
        self.scroll.to = math.max(0, total_content_h - h)
    end
end

-- =============================================================================
-- 🖱️ INTERAÇÃO (MOUSE E SCROLL)
-- =============================================================================
function OpenEditorsView:on_mouse_moved(px, py, dx, dy)
    self.hovered_idx = nil
    local docs = self.cached_docs
    for i, item in ipairs(docs) do
        if item.rect then
            if px >= item.rect.x and px < item.rect.x + item.rect.w and
               py >= item.rect.y and py < item.rect.y + item.rect.h then
                self.hovered_idx = i
                break
            end
        end
    end
end

function OpenEditorsView:on_mouse_pressed(button, px, py, clicks)
    if button == "left" and self.hovered_idx then
        local item = self.cached_docs[self.hovered_idx]
        if item and item.node and item.view then
            -- Foca na view e garante que o nó seja o ativo
            core.set_active_view(item.view)
            if item.node and core.root_view and core.root_view.set_active_node then
                core.root_view:set_active_node(item.node)
            end
            core.redraw = true
        end
    end
end

function OpenEditorsView:on_mouse_wheel(delta)
    -- Delegate to default scroll behavior if available, else manual
    if self.scroll then
        self.scroll.to = (self.scroll.to or 0) - (delta * 40)
    end
end

-- =============================================================================
-- 🚀 COMANDO SOBERANO DE TOGGLE (BLINDADO)
-- =============================================================================
command.add(nil, {
    ["doxoade:toggle-open-editors-dock"] = function()
        core.log("⚡ [16] Comando 'toggle-open-editors-dock' foi ACIONADO!")
        
        -- 1. Verifica se o Dock já está aberto em algum nó
        local dock_view = nil
        local dock_node = nil
        
        local function find_dock(node)
            if not node then return end
            if node.type == "leaf" then
                for _, v in ipairs(node.views or {}) do
                    -- Verifica se é a nossa classe de Dock
                    if v.class and v.class == OpenEditorsView then
                        dock_view = v
                        dock_node = node
                        return
                    end
                end
            else
                find_dock(node.a)
                find_dock(node.b)
            end
        end
        find_dock(core.root_view.root_node)

        if dock_view then
            -- Se já existe, fecha o dock
            if dock_node then
                local idx = dock_node:get_view_idx(dock_view)
                if idx then
                    table.remove(dock_node.views, idx)
                end
                if #dock_node.views == 0 then
                    dock_node:close()
                else
                    dock_node:set_active_view(dock_node.views[1])
                end
            end
            core.log("⚡ [16] Dock fechado.")
        else
            -- Se não existe, cria um split e adiciona a view corretamente
            core.log("⚡ [16] Criando novo split à esquerda para o Dock...")
            local active_node = core.root_view:get_active_node()
            local new_node = active_node:split("left")
            
            -- INSTANCIA A VIEW DO DOCK (Corrige o 'set_active_view(nil)')
            local new_dock = OpenEditorsView:new()
            
            -- ADICIONA AO NÓ (Isso define new_node.active_view automaticamente)
            if new_node.add_view then
                new_node:add_view(new_dock)
            end
            
            -- Foca no dock
            core.set_active_view(new_dock)
            core.log("⚡ [16] Dock aberto com sucesso.")
        end
        core.redraw = true
    end
})

-- Atalho alternativo (Ctrl+Alt+E para evitar conflito com outros plugins)
local keymap = require "core.keymap"
keymap.add {
    ["ctrl+alt+e"] = "doxoade:toggle-open-editors-dock"
}

core.log("🏛️ [16] Open Editors Dock Engine registrado e pronto.")
