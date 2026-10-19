# 🛡️ PLANO MESTRE DE EMANCIPAÇÃO (PLANO A, B E C)
**Protocolo:** ProDeNov v2.0 (Art. 1.2.1, 5.2, 5.3 e 5.4 — Redundância Tripla e Reversibilidade)  
**Ambiente:** `AMARANTH` (Positivo H14BT58, 2 GB RAM, SSD) ➔ Wi-Fi Local ➔ `BLUEBABY` (Windows, Cofre)

---

## CAPÍTULO 1: O BACKUP DO WINDOWS 10 (AMARANTH ➔ BLUEBABY)

O backup será feito **de dentro do próprio Windows do Amaranth antes de qualquer alteração**, usando a estabilidade nativa do driver de Wi-Fi e enviando diretamente para uma pasta compartilhada no Bluebaby.

### 🔹 PLANO A: Captura WIM Soberana via DISM (Recomendação #1)
* **Como funciona:** O Windows possui a ferramenta nativa `dism.exe` usada pela própria Microsoft para clonagem corporativa.
* **Execução:**
  1. No `bluebaby`: Cria uma pasta compartilhada na rede (ex: `C:\AmaranthBackup` compartilhada como `\\BLUEBABY\Backup`);
  2. No `AMARANTH` (prompt Admin): Mapeia a rede e executa a captura:
     ```cmd
     net use Z: \\BLUEBABY\Backup /user:SeuUsuario Senha
     dism /Capture-Image /ImageFile:Z:\amaranth_win10.wim /CaptureDir:C:\ /Name:"Windows10_Amaranth" /Compress:fast /CheckIntegrity /Verify
     ```
* **Vantagens:** Ignora automaticamente arquivos de swap (`pagefile.sys`, `swapfile.sys`) e temporários. Compacta os 24 GB para cerca de **8 a 9 GB**. Possui a flag `/Verify` que confere bit a bit contra quedas de pacote no Wi-Fi.

---

### 🔹 PLANO B: Imagem de Disco VHDX via Sysinternals Disk2vhd
* **Como funciona:** Uso do utilitário oficial gratuito da Microsoft `Disk2vhd` (~2 MB, portátil).
* **Execução:**
  1. Abre o `disk2vhd.exe` no Amaranth;
  2. Seleciona apenas o volume `C:`;
  3. Aponta o destino diretamente para a pasta de rede `\\BLUEBABY\Backup\amaranth_win10.vhdx`;
  4. Ativa o *Volume Shadow Copy* (VSS) para capturar o disco com integridade sem desligar o sistema.
* **Vantagens:** O arquivo `.vhdx` gerado pode ser montado com 2 cliques em qualquer Windows como se fosse um HD físico, permitindo verificar e restaurar arquivos individuais.

---

### 🔹 PLANO C: Stream de Bloco via Alpine Linux em RAM
* **Como funciona:** Caso o Windows do Amaranth apresente problemas de rede ou arquivos bloqueados.
* **Execução:**
  1. Boot no Alpine Linux (que já roda na RAM do Amaranth);
  2. Conecta ao Wi-Fi via `wpa_supplicant`;
  3. No `bluebaby`: Inicia um servidor Netcat ou receptor SMB;
  4. No Amaranth: Envia o bloco da partição do Windows via stream comprimido:
     ```sh
     dd if=/dev/sda3 bs=4M status=progress | gzip -1 | nc IP_DO_BLUEBABY 9999
     ```

---

## CAPÍTULO 2: VERIFICAÇÃO DE INTEGRIDADE E TESTE DE PROVA

**Invariante ProDeNov:** *Nenhuma partição do Windows será tocada até que o backup no Bluebaby seja provado como 100% íntegro e restaurável.*

### 🔹 PLANO A: Montagem Forense do WIM no Bluebaby
* **Execução:** No `bluebaby` (prompt Admin), tentamos montar a imagem capturada para leitura:
  ```cmd
  mkdir C:\TesteMount
  dism /Mount-Image /ImageFile:C:\AmaranthBackup\amaranth_win10.wim /Index:1 /MountDir:C:\TesteMount /ReadOnly
  ```
* **Critério de Sucesso:** Se o Bluebaby conseguir navegar nas pastas `C:\TesteMount\Windows`, `Program Files` e nos seus arquivos em `Users\olDox222`, a imagem está matematicamente perfeita. Desmonta com `dism /Unmount-Image /MountDir:C:\TesteMount /Discard`.

### 🔹 PLANO B: Verificação por Checksum SHA-256
* **Execução:** Gera o hash SHA-256 no Amaranth antes do envio e confere no Bluebaby com `certutil -hashfile amaranth_win10.wim SHA256`. Se as strings baterem, zero pacotes foram corrompidos no Wi-Fi.

### 🔹 PLANO C: Montagem Nativa de VHDX (Se usado Plano B)
* **Execução:** No Bluebaby, duplo clique no `amaranth_win10.vhdx`. Se o Windows atribuir uma letra e listar os arquivos, a reversibilidade está homologada.

---

## CAPÍTULO 3: REMOÇÃO DO WINDOWS (PRESERVANDO A ILHA DE RESGATE)

Para garantir que o Amaranth **nunca perca a capacidade de dar boot sem pendrive**, aplicamos a técnica da **Ilha de Resgate**:

```
[ESTRUTURA DO SSD AMARANTH - 27 GB]
┌──────────────┬──────────────┬──────────────────────────────┬──────────────┐
│ Partição 1   │ Partição 2   │ Partição 3 (WINDOWS C:)      │ Partição 4   │ Partição M:  │
│ ESP (100 MB) │ MSR (16 MB)  │ ~24 GB (ALVO DA LIMPEZA)     │ Rec (556 MB) │ FAT32 (1 GB) │
│ [PRESERVADA] │ [PRESERVADA] │                              │ [EXCLUÍDA]   │ [PRESERVADA] │
└──────────────┴──────────────┴──────────────────────────────┴──────────────┘
```

* **A Salvaguarda:** A partição ESP (com o **Izanami**) e a partição `M:` (com o **Alpine Linux em RAM**) **NÃO SERÃO TOCADAS**.
* Mesmo que a máquina seja desligada no meio da formatação, o Izanami e o Alpine continuam no SSD e o computador continua ligando normalmente!

### 🔹 PLANO A: Formatação da Partição 3 via Alpine em RAM
* **Execução:** No Alpine em RAM:
  1. Identifica a partição do Windows (`/dev/sda3`);
  2. Apaga a partição de recuperação (`/dev/sda4`);
  3. Formata `/dev/sda3` em `ext4` rotulando como `LINUX_ROOT`.

### 🔹 PLANO B: Limpeza via Script Diskpart no Amaranth
* **Execução:** Um script do Diskpart que remove apenas o volume do Windows e a partição de recuperação, deixando o espaço livre contíguo para o Linux.

### 🔹 PLANO C: Restauração Imediata da Ilha
* Caso ocorra qualquer erro de particionamento, o `esp_manager` restaura a partição `M:` como prioridade máxima e nada se perde.

---

## CAPÍTULO 4: INSTALAÇÃO DO NOVO LINUX (antiX OU ALPINE FULL)

Com os ~25 GB livres no SSD e o backup no Bluebaby, instalamos o novo sistema:

### 🔹 PLANO A: Alpine Linux em Instalação Permanente no SSD (`setup-disk -m sys`)
* **Por que é o mais seguro:** O Alpine já está rodando perfeitamente na RAM do Amaranth.
* **Execução:**
  1. No Alpine em RAM, roda o instalador nativo oficial:
     ```sh
     setup-disk -m sys /dev/sda3
     ```
  2. Em **60 segundos**, ele instala o Alpine permanente no SSD, configura o kernel e cria o bootloader;
  3. **Consumo:** ~50 MB de RAM e ~1.5 GB de disco (sobram **23 GB livres** no SSD e **1.950 MB livres na RAM**).

### 🔹 PLANO B: antiX Linux via Descompactação de SquashFS / Rede
* **Execução:**
  1. No `bluebaby`, compartilha a ISO do antiX na rede local (via HTTP simples com `python -m http.server 8080`);
  2. No Amaranth (Alpine em RAM), baixa a ISO do antiX pela rede local a 10 MB/s (leva ~1 minuto);
  3. Extrai o sistema de arquivos base do antiX (`antiX/linuxfs`) direto para a partição `/dev/sda3` e instala o GRUB/EFI.

### 🔹 PLANO C: Reversão de Emergência (Restauração Total do Windows)
* **Se a instalação do Linux falhar ou você decidir voltar:**
  1. Boot no Alpine em RAM (que continua intacto no `M:`);
  2. Conecta ao Bluebaby e puxa a imagem WIM/disco de volta para `/dev/sda3`;
  3. O Windows 10 reaparece exatamente como estava antes da operação.

---

## CAPÍTULO 5: HOMOLOGAÇÃO E BOOT FINAL

### 🔹 PLANO A: Inicialização Gerenciada pelo Izanami Systems
* O Izanami atua como o bootloader soberano na tela LCD, oferecendo:
  * `[1] Izanami Kernel (Anel 0 / Eletrônica)`
  * `[2] Linux de Produção (Alpine Full ou antiX)`

### 🔹 PLANO B: Entrada Direta no Firmware da Placa-Mãe (NVRAM)
* O novo Linux é registrado no `{fwbootmgr}` como opção primária de boot do notebook.

### 🔹 PLANO C: Boot de Emergência pelo Built-in EFI Shell da ROM
* Caso o menu da placa-mãe se perca, entra no `UEFI: Built-in EFI Shell` (que você já tem na BIOS) e dispara manualmente o executável de boot.

---


# 🚀 PLANO OPERACIONAL: MISSÃO TRANS-AMARANTH
**Nós Envolvidos:** `PC-A (AMARANTH)` [Alvo] $\longleftrightarrow$ `Wi-Fi Local` $\longleftrightarrow$ `PC-B (BLUEBABY)` [Cofre]  
**Invariante Central:** *A integridade física e de boot do PC-A nunca dependerá do sucesso do envio pela rede; a capacidade de reinicialização deve ser mantida em 100% dos cenários de queda.*

---

## 1. O Fluxo Operacional de Ponta a Ponta

```
  [1. PRÉ-FLIGHT]          [2. COMUNICAÇÃO]         [3. VOO (CAPTURA)]
  • Auditoria de Cargas    • Handshake Wi-Fi       • Congelamento VSS
  • Fixação de Energia     • Trava de DHCP (IPs)   • Stream WIM/Compactado
  • Trava de Baterias      • SMB Auth Verificada   • Sem tocar no SSD do A
             │                        │                        │
             ▼                        ▼                        ▼
  [4. POUSO (GRAVAÇÃO)]    [5. CHEGADA (CHEQUE)]    [6. AÇÃO EM SOLO (A)]
  • Flush de Buffer no B   • Montagem Forense (B)  • Formatação de C:
  • Selagem de Imagem      • Hash SHA-256 OK       • Preservação da Ilha
  • Prova de Leitura       • Veredito: AUTORIZADO  • Deploy do Linux/antiX
```

1. **Pré-Flight:** Assegurar que ambos os computadores estão ligados na tomada (energia ininterrupta), com espaço em disco verificado no PC-B e serviços de cópia sombra (VSS) operantes no PC-A;
2. **Comunicação:** Estabelecer o túnel de rede local via SMB/compartilhamento com autenticação explícita, medindo a latência e fixando a rota;
3. **Voo (Captura e Envio):** O Windows do PC-A lê seu próprio volume `C:` em modo estritamente *somente-leitura* (via Shadow Copy / DISM), compacta os blocos na memória RAM e envia os pacotes pela interface Wi-Fi para o PC-B;
4. **Pouso (Gravação no PC-B):** O PC-B recebe os blocos no disco rígido, grava o contêiner `amaranth_win10.wim` e faz o flush de cache de disco;
5. **Chegada do Material (Prova de Vida):** O PC-B abre e monta a imagem gerada em modo somente-leitura. Se navegar pelas pastas de usuário e do Windows sem erros, emite o sinal: **"LUZ VERDE PARA FORMATAÇÃO"**;
6. **Ação em Solo (No PC-A):** Somente após a luz verde, entra-se no Alpine (em RAM) para limpar a partição antiga do Windows, **preservando a Ilha de Resgate (ESP + Partição M:)**.

---

## 2. A Invariante da "Ilha de Resgate" (A Blindagem Local)

Antes de analisar as falhas, consolidamos a regra de ouro que impede o PC-A de morrer:

```
[DISCO DO PC-A (AMARANTH) - 27.84 GB]
┌──────────────────┬─────────────────┬──────────────────────────────┬──────────────────┐
│ Partição 1 (ESP) │ Partição 2      │ Partição 3 (WINDOWS C:)      │ Partição 5 (M:)  │
│ 100 MB - FAT32   │ 16 MB - MSR     │ ~24 GB - NTFS                │ 1 GB - FAT32     │
│ [IZANAMI X64]    │ [PRESERVADA]    │ ⚠️ [ÚNICO ALVO DE LIMPEZA]    │ [ALPINE EM RAM]  │
│ 🛡️ NUNCA TOCADA  │                 │                              │ 🛡️ NUNCA TOCADA  │
└──────────────────┴─────────────────┴──────────────────────────────┴──────────────────┘
```

Mesmo que o cabo de rede seja cortado, o Wi-Fi caia ou ocorra um blecaute total, **o PC-A sempre ligará**:
* O **Izanami** está na Partição 1;
* O **Alpine Linux** está na Partição 5 (`M:`);
* A placa-mãe continua com capacidade de boot autônomo sem pendrive.

---

## 3. Matriz de Risco & Tabela de Possibilidades de Falha (Err Table)

Abaixo está o mapeamento exaustivo de todas as falhas possíveis durante a missão, com a causa raiz técnica, as consequências e os procedimentos de contingência (**Planos A, B e C**):

| Fase | Cenário de Falha | Causa Raiz Técnica | Consequência no Sistema | Ação de Mitigação / Contingência (A, B e C) |
| :--- | :--- | :--- | :--- | :--- |
| **Pré-Flight** | **Falta de espaço no PC-B** | O PC-B não possui os ~10-15 GB livres para o contêiner. | O backup trava no meio por disco cheio. | **Plano A:** Checar espaço no PC-B com `Get-PSDrive`.<br>**Plano B:** Limpar arquivos temporários no PC-B.<br>**Plano C:** Ativar compressão máxima no DISM (`/Compress:max`). |
| **Pré-Flight** | **Arquivos travados no PC-A** | Antivírus ou serviço mantendo arquivos com *exclusive lock*. | DISM aborta com erro de acesso a arquivo. | **Plano A:** O DISM usa VSS nativo automaticamente.<br>**Plano B:** Pausar antivírus e softwares de terceiros.<br>**Plano C:** Usar o `Disk2vhd` (Plano B do capítulo anterior). |
| **Comunicação** | **Queda / Oscilação do Wi-Fi** | Roteador desassocia ou canal 2.4 GHz sofre interferência. | O fluxo de dados congela ou a conexão SMB cai. | **Plano A:** O DISM possui verificação de integridade e pode retomar.<br>**Plano B:** Fixar canal estático no roteador.<br>**Plano C:** Criar um Hotspot Wi-Fi direto do PC-B para o PC-A (Ponto a Ponto sem passar pelo roteador). |
| **Comunicação** | **Renovação de IP (DHCP)** | O roteador altera o IP do PC-B no meio da transmissão. | Perda do destino `\\BLUEBABY`. | **Plano A:** Conectar via Nome de Rede (`\\BLUEBABY`) via NetBIOS/mDNS.<br>**Plano B:** Fixar IP estático no PC-B (ex: `192.168.18.200`). |
| **Comunicação** | **Bloqueio de Firewall (SMB)** | Porta 445 (SMB) bloqueada no Windows do PC-B. | O PC-A recebe erro "Caminho de rede não encontrado". | **Plano A:** Liberar temporariamente Compartilhamento de Arquivo no Firewall do PC-B.<br>**Plano B:** Mapear via `net use Z: \\IP_DO_B\Compartilhamento`. |
| **Voo (Captura)** | **Esgotamento de RAM no PC-A** | O buffer de compactação consome os últimos 150 MB de RAM. | O Windows do PC-A trava com *Out of Memory* (OOM). | **Plano A:** Usar `/Compress:fast` (usa pouca RAM e foca em velocidade).<br>**Plano B:** Fechar navegador e todos os programas no PC-A antes do voo.<br>**Plano C:** Fazer a captura a frio através do Alpine em RAM. |
| **Voo (Captura)** | **Corrupção silenciosa de pacotes** | Pacotes perdidos em camada de transporte Wi-Fi. | O WIM chega ao PC-B com hash corrompido. | **Plano A:** Flag `/CheckIntegrity` e `/Verify` ativas no comando DISM.<br>**Plano B:** Geração de checksum SHA-256 no PC-A e validação no PC-B. |
| **Pouso (Gravação)** | **Falha de gravação no disco do B** | Setor defeituoso no PC-B ou I/O timeout. | Imagem truncada no cofre. | **Plano A:** Salvar na partição principal do PC-B.<br>**Plano B:** O teste de montagem forense (Capítulo 2) rejeitará o arquivo e impedirá qualquer formatação no PC-A. |
| **Chegada** | **WIM incompleto ou ilegível** | A captura foi cortada antes do final do índice. | A imagem não pode ser restaurada. | **Invariante ProDeNov:** Se o comando `dism /Mount-Image` no PC-B falhar, a operação é **CANCELADA IMEDIATAMENTE**. O Windows do PC-A não é tocado. |
| **EMERGÊNCIA** | **QUEDA DO PC-B (Cofre) no meio do envio** | Blecaute, tela azul ou reinício acidental do PC-B. | O envio falha e o WIM fica corrompido no PC-B. | **Impacto no PC-A:** **ZERO.** O Windows `C:` no PC-A estava apenas sendo lido; continua 100% íntegro. Basta religar o PC-B e reiniciar o voo. |
| **EMERGÊNCIA** | **QUEDA DO PC-A no meio do envio do backup** | Desligamento por bateria ou congelamento no PC-A. | O backup é abortado no PC-B. | **Impacto no PC-A:** **ZERO.** Nenhum dado foi apagado. Ao ligar o PC-A, o Windows sobe normalmente. |
| **EMERGÊNCIA** | **QUEDA DO PC-A no meio da FORMATAÇÃO/DEPLOY** | Queda de energia enquanto apagava `C:` ou gravava Linux. | O `C:` fica vazio, sem sistema operacional instalado. | **Impacto no Boot:** **REDUZIDO.** A Partição 1 (Izanami) e a Partição 5 (Alpine) não foram tocadas. O PC-A liga, abre o Izanami/Alpine em RAM e você formata novamente pela RAM. |

---

## 4. O Teste de "Hotspot Direto" (Redundância para o Wi-Fi)

Como não temos cabo de rede, a maior ameaça à estabilidade é o **roteador da casa engasgar com 10 GB de tráfego contínuo**.

Para mitigar isso no Plano B de Comunicação:
* O **PC-B (Bluebaby)** pode ativar a função nativa do Windows: **"Hotspot Móvel"** (Ponto de Acesso Wi-Fi);
* O **PC-A (Amaranth)** se conecta diretamente à rede Wi-Fi gerada pelo PC-B;
* **Resultado:** Os dados viajam direto de placa Wi-Fi para placa Wi-Fi, sem passar pelo roteador, reduzindo a latência, eliminando quedas de internet e dobrando a velocidade de transferência!

---

## 5. Checklist de Decisão (Go / No-Go)

A operação só avança para o estágio de exclusão de dados se **todos os 5 itens abaixo forem VERDADEIROS**:

- [ ] **1. Alimentação:** Ambos os computadores estão conectados aos carregadores na tomada?
- [ ] **2. Integridade do PC-A:** O `C:` possui pelo menos 2.5 GB livres e o VSS está funcionando?
- [ ] **3. Espaço no PC-B:** O Bluebaby possui mais de 20 GB livres para armazenar a imagem?
- [ ] **4. Conexão:** O comando `net use` conseguiu mapear a pasta do PC-B com sucesso e baixa latência?
- [ ] **5. A Prova de Vida:** O comando de montagem forense (`dism /Mount-Image`) abriu as pastas do usuário no PC-B sem nenhum erro?

---

# 🛫 ARQUITETURA SOVEREIGN FLIGHT ENGINE (SFE)
**Modelo:** Aeroespacial / Logística de Carga Crítica (*Flight-Cargo Architecture*)  
**Protocolo Base:** `ProDeNov.md` (v2.0)  
**Ecossistema:** Doxoade Core Systems  
**Nós Operacionais:** `PC-A (AMARANTH)` $\longleftrightarrow$ `PC-B (BLUEBABY)`

---

## 1. Mapeamento dos Pilares com o Panteão Doxoade

A sua divisão em 8 pilares traduz a transição de dados para uma disciplina militar/aeroespacial. No ecossistema Doxoade, cada pilar é governado por um arquétipo com responsabilidades, contratos e invariantes estritas:

```
┌───────────────────────────────────────────────────────────────────────────┐
│                      BASE (⚡ ZEUS: ORQUESTRADOR RAIZ)                    │
│                 control / command / mission_orchestration                 │
└──────┬─────────────────────────────────────────────────────────────┬──────┘
       │                                                             │
       ▼                                                             ▼
┌──────────────────────────────┐                             ┌──────────────────────────────┐
│  PRÉ-VOO (🏹 ÁRTEMIS/ANÚBIS)  │                             │   ERRO (🌱 OSÍRIS / ⚖️ MA'AT)  │
│ pre_flight_stage / readiness │                             │ err_detection / reversibility│
└──────────────┬───────────────┘                             └──────────────┬───────────────┘
               │                                                            │
               ▼                                                            │
┌──────────────────────────────┐                                            │
│    CUSTO (📖 THOTH ENGINE)   │                                            │
│ freight_cost / dry_run       │                                            │
└──────────────┬───────────────┘                                            │
               │                                                            │
               ▼                                                            │
┌──────────────────────────────┐                                            │
│      VOO (🪽 HERMES/HÓRUS)    │◄─── Interrupção Crítica / Abort ───────────┘
│ in_flight_tracking / manifest│
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│     CHEGADA (💀 HADES)       │
│ cargo_receipt / arrival_proc │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ EXAME INTEGRIDADE (🐺 ANÚBIS)│───► Falha de Integridade ──► Disparo de Rollback
│ integrity_check / Go-NoGo    │
└──────────────┬───────────────┘
               │ (Veredito: LUZ VERDE)
               ▼
┌──────────────────────────────┐
│ PÓS-VOO (🔨 HEFESTO/VULCAN)  │
│ cargo_unloading / post_flight│
└──────────────────────────────┘
```

---

## 2. Especificação Técnica dos 8 Módulos de Voo

### I. Base: Orquestração e Comando (`mission_control`)
* **Papel:** Máquina de estados soberana. Controla o ciclo de vida da missão do início ao fim, coordenando o envio, as travas de segurança e as decisões de avanço ou aborto.
* **Componente:** `FlightOrchestrator`
* **Contrato:**
  * Não permite transição de fase sem confirmação formal (token criptográfico/booleano) da fase anterior;
  * Mantém o log de telemetria da missão em tempo real.

---

### II. Custo: Estimativa de Frete e Simulação (`freight_cost`)
* **Papel:** Avalia o impacto e o custo operacional antes de qualquer tráfego na rede ou no disco.
* **Componente:** `FreightEstimator`
* **Métricas Avaliadas:**
  * **Payload Real:** Tamanho dos dados utilizados no volume `C:` (ex: 20 GB de dados brutos);
  * **Payload Compactado Estimado:** Fator de compressão (ex: taxa 2.2:1 $\rightarrow$ ~9 GB de carga útil);
  * **Custo de Largura de Banda Wi-Fi:** Estimativa de tempo baseada na taxa real de transferência (ex: 8 MB/s $\rightarrow$ ~18 minutos de voo);
  * **Sobrecarga de RAM:** Avaliação se o buffer de compressão respeita o teto de 150 MB livres do Amaranth;
  * **Modo `--dry-run` Nativo:** Simula todo o plano de voo sem gravar nenhum byte.

---

### III. Pré-voo: Auditoria e Prontidão de Solo (`pre_flight_stage`)
* **Papel:** Verificação de solo e checagem de invariantes. Se um único sensor falhar, o voo é cancelado (*Abort at Gate*).
* **Componente:** `PreFlightInspector`
* **Bateria de Testes Mandatórios:**
  1. **Energia:** Validação de alimentação AC (conectado na tomada, sem risco de queda por bateria);
  2. **Espaço no Destino:** Confirmação de que o PC-B (`BLUEBABY`) possui $\ge 1.5\times$ o tamanho da carga estimada;
  3. **Estabilidade de Rota:** Ping local contínuo (5 pacotes) com jitter $< 15\text{ ms}$ e zero perda;
  4. **Serviço de Sombra (VSS):** Verificação de que o *Volume Shadow Copy* está operante no Windows do PC-A para permitir a leitura consistente de arquivos em uso.

---

### IV. Voo: Rastreamento em Trânsito e Manifesto (`in_flight_tracking`)
* **Papel:** Monitoramento da transmissão ao vivo, telemetria de rede e manifesto de voo.
* **Componente:** `FlightTracker` & `FlightManifest`
* **Dados do Manifesto de Voo (`flight_manifest.json`):**
  * ID da Missão, nó de origem (`AMARANTH`), nó de destino (`BLUEBABY`);
  * Algoritmo de compressão (`fast` / LZ4 / XPRESS);
  * Bytes transmitidos vs Bytes totais;
  * Velocidade média (MB/s) e Tempo Estimado de Chegada (ETA);
  * Heartbeat ativo: se o fluxo estagnar por $> 30\text{ segundos}$, o voo entra em estado de contingência.

---

### V. Chegada: Recepção de Carga (`cargo_receipt`)
* **Papel:** Handshake de finalização no nó de destino (PC-B) e persistência em mídia segura.
* **Componente:** `ArrivalProcessor`
* **Operações:**
  * Fechamento do pipe de rede no PC-B;
  * Flush forçado do cache de gravação no disco do Bluebaby (`Sync-Disk` / Commit de I/O);
  * Bloqueio do contêiner recebido (`amaranth_win10.wim`) em modo somente-leitura contra alterações acidentais.

---

### VI. Exame de Integridade: Veredito Go / No-Go (`cargo_integrity_check`)
* **Papel:** O tribunal da carga. É a barreira matemática que autoriza ou proíbe a destruição da partição do Windows no PC-A.
* **Componente:** `IntegrityInspector`
* **Bateria de Exames:**
  1. **Exame Criptográfico:** Comparação do checksum SHA-256 gerado pelo PC-A com o arquivo gravado no PC-B;
  2. **Exame Forense de Montagem (Prova de Vida):** O PC-B executa `dism /Mount-Image` em modo somente-leitura e valida se as pastas `Windows\System32`, `Program Files` e o perfil `Users\olDox222` são legíveis;
  3. **Emissão do Veredito:**
     * **GO (Luz Verde):** Emite o token assinado autorizando a Fase de Solo no PC-A;
     * **NO-GO (Luz Vermelha):** Aborta a missão. O Windows do PC-A permanece intocado.

---

### VII. Erro: Detecção e Operações de Reversibilidade (`reversibility_ops`)
* **Papel:** O motor de escape e retorno. Garante reversibilidade em qualquer ponto do ciclo.
* **Componente:** `ReversibilityEngine`
* **Matriz de Resgate por Fase:**
  * **Queda no Pré-Voo / Voo:** Aborto limpo. O SSD do PC-A esteve sempre em modo somente-leitura; nada mudou.
  * **Queda do PC-B durante o Voo:** O PC-A apenas fecha o processo; o Windows local continua 100% íntegro.
  * **Queda do PC-A durante a Ação de Solo (Formatação):** A **Ilha de Resgate** (Partição 1 com Izanami e Partição 5 com Alpine em RAM) garante o boot da máquina. Pelo Alpine na RAM, o PC-A conecta ao PC-B e restaura o WIM/imagem pela rede com a operação inversa (*Inverted Flight*).

---

### VIII. Pós-voo / Descarregamento: Materialização em Solo (`cargo_unloading`)
* **Papel:** Uma vez confirmada a vitória e emitido o veredito Go, executa a aplicação do novo sistema operacional.
* **Componente:** `CargoUnloader`
* **Operações:**
  * Limpeza atômica da partição antiga do Windows (`/dev/sda3`);
  * Despejo do novo sistema (antiX / Alpine Full) na partição principal de ~25 GB;
  * Atualização da tabela de boot no **Izanami Systems**;
  * Desmontagem de unidades temporárias e reinicialização no novo sistema.

---

## 3. Estrutura Proposta no Código (`doxoade`)

Essa arquitetura se organizará sob o pacote `doxoade/tools/flight_systems/` de forma limpa e modular:

```text
doxoade/tools/flight_systems/
├── __init__.py               # Fachada de exportação do sistema
├── flight_orchestrator.py    # ⚡ Base / Máquina de Estados
├── freight_estimator.py      # 📖 Custo / Dry-Run / Cálculo de Banda
├── pre_flight.py             # 🏹 Pré-voo / Verificação de Sensores
├── flight_tracker.py         # 🪽 Voo / Telemetria / Manifesto
├── cargo_receipt.py          # 💀 Chegada / Recepção no PC-B
├── integrity_inspector.py    # 🐺 Exame de Integridade / Go-NoGo
├── reversibility_engine.py   # ⚖️ Erro / Reversão e Rollback
└── cargo_unloader.py         # 🔨 Pós-voo / Implantação no SSD
```

---

