# BLITZPLAN: Ambiente de Desenvolvimento Híbrido (Doxoade ↔ Termux)
**Documento:** `doxoade/docs/Protocols/Doxoade_Termux_Bridge.md`  
**Protocolo:** ProDeNov (Diretrizes 1.1, 1.2, 4.1 e 4.2 — Planejamento puro, sem codificação por restrição de prazo)  
**Objetivo:** Estabelecer a arquitetura de comunicação entre o ecossistema de ferramentas do PC (Doxly, Python 3.12, NeoVulcan) e o ambiente Linux do Termux (Android), com foco em ergonomia de IDE e resgate/sincronização do sistema de download de música.

---

## 1. Requisição e Diagnóstico Forense (W5+2H / ProDeNov 1)

* **O quê (What):** Criação de uma ponte de desenvolvimento remoto para permitir que editores do PC acessem, editem e executem o ambiente do Termux como se fosse um servidor Linux headless, além de viabilizar a extração rápida de projetos já desenvolvidos no smartphone.
* **Onde (Where):**
  - **No Android:** Ambiente sandbox do Termux (`/data/data/com.termux/files/home`).
  - **No PC:** IDE (Doxly / VS Code / Lite XL) e módulo `android_sys` no `Sysutils_proj`.
  - **Na Rede:** Túnel seguro do Tailscale (porta customizada `8022`).
* **Quem (Who):** Desenvolvedor operando o PC com tela grande, mouse e teclado físicos para programar no Termux.
* **Quando (When):** Planejado agora; implementação postergada para o próximo ciclo por restrição de prazo.
* **Por quê (Why):**
  1. **Ergonomia e Fadiga:** Programar na tela de toque do celular é lento, cansativo e suscetível a erros de digitação.
  2. **Isolamento de Sandbox do Android (SELinux):** O sistema de arquivos nativo do Termux fica oculto e protegido; o Windows Explorer e conexões MTP normais não conseguem enxergar a pasta `home` do Termux.
  3. **Restrição de Execução (`noexec`):** A pasta compartilhada `/sdcard` (armazenamento interno do celular) é montada com a flag `noexec` pelo Android, impedindo a execução de binários e scripts com permissão direta `chmod +x`. O código *precisa* viver dentro da partição privada do Termux.
  4. **Resgate de Conhecimento:** Existe uma ferramenta funcional desenvolvida no Termux (sistema de download de músicas e mídias) que precisa ser integrada ao repositório do PC.
* **Origem (Origin):** O ecossistema já possui Tailscale, KVM (Leap) e Web Hub ativos. O Termux é a última fronteira isolada.
* **Consequências (Impact):** Quando implementado, transformará o celular em um nó de computação Linux portátil integrado à malha de ferramentas do Doxoade.

---

## 2. Análise de Complexidade e Riscos Técnicos (ProDeNov 0)

| Fator ProDeNov | Risco | Mitigação Técnica no Plano |
| :--- | :---: | :--- |
| **0.0 Thirdparty** | Alto | O Android encerra processos de fundo agressivamente (Doze Mode). Mitigado com o comando nativo `termux-wake-lock`. |
| **0.1 Devflow** | Médio | Evitar ter que copiar arquivos manualmente toda vez que alterar uma linha de código. |
| **0.2 Rabbit Hole** | Alto | Tentar rodar interfaces gráficas pesadas (X11 / VNC / code-server) no celular drena bateria e esquenta o aparelho. **Decisão:** Manter 100% headless (apenas terminal e SSH). |
| **0.3 Sensibilidade** | Baixo | Tráfego restrito à malha fechada do Tailscale via chaves criptográficas assimétricas (ed25519). |

---

## 3. A Tríade de Planos de Ação (ProDeNov 1.2.1)

```text
       ┌──────────────────────────────────────────────────────────────┐
       │                   PC (AMARANTH / BLUEBABY)                   │
       │           IDE (Doxly / VS Code) + Windows Terminal           │
       └──────────────────────────────┬───────────────────────────────┘
                                      │
                         Túnel Seguro Tailscale Mesh
                               (100.64.0.0/10)
                                      │
       ┌──────────────────────────────┴───────────────────────────────┐
       │                    ANDROID (TERMUX LINUX)                    │
       │                   IP: 100.x.y.z | Porta: 8022                │
       └──────┬───────────────────────┬───────────────────────┬───────┘
              │                       │                       │
              ▼                       ▼                       ▼
     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
     │  PLANO A (IDE)  │     │ PLANO B (Drive) │     │ PLANO C (ADB)   │
     │  OpenSSH Server │     │   SFTP / SSHFS  │     │  ADB Pull / Push│
     │  Remote Editing │     │  Mapeado em T:  │     │ (Já pareado via │
     │  Terminal Nativo│     │  Arrastar/Soltar│     │     Scrcpy)     │
     └─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 3.1. Plano A (Principal) — Ponte OpenSSH Headless via Tailscale
* **Conceito:** O Termux roda o daemon `sshd` nativo na porta padrão `8022`. A IDE do PC conecta diretamente nele.
* **Como funciona:**
  - O PC enxerga o Termux como um servidor Linux padrão através do IP Tailscale do celular (`100.x.y.z:8022`).
  - No editor do PC (Doxly/VS Code com extensão SSH), você abre a pasta `/data/data/com.termux/files/home/` diretamente.
  - Você edita com syntax highlighting, atalhos do teclado físico e autocompletion no monitor grande.
  - Ao salvar no PC, o arquivo já está salvo dentro do Linux do celular.
  - Um terminal integrado na IDE executa os comandos diretamente no processador do Android.

### 3.2. Plano B (Alternativo) — Montagem de Unidade de Rede (SFTP / SSHFS)
* **Conceito:** Mapear o sistema de arquivos do Termux como uma letra de disco no Windows (ex: Unidade `T:`).
* **Como funciona:**
  - Utiliza o utilitário leve `sshfs-win` ou `rclone mount` no Windows.
  - A pasta raiz do Termux aparece dentro do Windows Explorer, ao lado de `C:`, `Y:` e `Z:`.
  - Permite arrastar, soltar, copiar e comparar pastas usando ferramentas visuais de diff sem abrir linha de comando.

### 3.3. Plano C (Contingência Rápida) — Bridge via ADB (Aproveitando o Scrcpy Ativo)
* **Conceito:** Utilizar a ponte ADB que já está aberta no seu PC (como vimos na janela `SM-A225M`).
* **Como funciona:**
  - Dispensa qualquer configuração de rede ou pacotes no Termux.
  - O módulo `android_sys` dispara comandos diretos:
    `adb pull /sdcard/Download/meu_projeto ./projetos_resgatados/`
  - Ideal para resgates emergenciais de código quando o Termux estiver sem rede.

---

## 4. Guia Tático: Como Resgatar o Sistema de Música AGORA (Sem Esperar a Implementação)

Como você precisa pegar o código do sistema de download de música que já está pronto no Termux e o prazo não permite criar comandos novos hoje, use este procedimento cirúrgico de **2 passos**:

### Passo 1: No Termux do Celular
Copie a pasta do projeto de música para a área de armazenamento acessível do Android:
```bash
# 1. Garante permissão de acesso ao armazenamento comum
termux-setup-storage

# 2. Compacta o seu projeto em um arquivo .tar.gz ou .zip
tar -czvf ~/projeto_musica.tar.gz -C ~/ CAMINHO_DA_PASTA_DO_SEU_PROJETO

# 3. Move para a pasta Download do Android
cp ~/projeto_musica.tar.gz /sdcard/Download/
```

### Passo 2: Pelo Navegador do Celular (Usando o Hub que Criamos Hoje!)
1. No PC, abra o hub:
   ```bash
   sysutils sync android web
   ```
2. No navegador do celular (`http://100.113.157.27:8080/`):
   - Toque em **Escolher Arquivo** ➔ Selecione `projeto_musica.tar.gz` da sua pasta `Download`.
   - Toque em **Enviar para o Computador**.
3. O código cairá intacto dentro de `C:\SysUtils_Shared\Android\Inbox\` no PC no mesmo instante.

---

## 5. Próximos Passos (Para a Próxima Sprint)

Quando o prazo permitir o desenvolvimento da ferramenta completa, o roteiro será:
1. Criar o comando `sysutils android termux-setup` (para gerar chaves SSH e script de auto-inicialização no Termux).
2. Criar `sysutils android termux-connect` (para abrir a sessão interativa SSH direta no terminal do SysUtils).
3. Integrar o sistema de música resgatado ao catálogo de ferramentas do ecossistema Doxoade.

O planejamento está formalizado e registrado conforme as diretrizes do ProDeNov.
