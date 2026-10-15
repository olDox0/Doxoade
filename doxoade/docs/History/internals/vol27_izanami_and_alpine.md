Seguindo o protocolo **ProDeNov (Art. 5.6.4 — Revisão, Manutenibilidade e Escalabilidade)**, documentamos aqui o **Dossiê Completo de Emancipação do Hardware e Gênese do Izanami Systems**. 

Este documento foi formatado para ser salvo como um registro oficial dentro da sua árvore de documentação (por exemplo, em `doxoade/docs/architecture/dossier_izanami_genesis.md` ou na raiz do projeto).

---

# 📜 DOSSIÊ ARQUITETURAL: GÊNESE DO IZANAMI & EMANCIPAÇÃO DO AMARANTH
**Projeto:** `Doxoade Low-Level Tooling` / `Izanami Systems`  
**Data de Homologação:** 13/10/2026 | **Protocolo:** ProDeNov v2.0  
**Hardware Alvo:** Positivo Informática SA — H14BT58 (PC-A Amaranth)  
**Processador:** Intel Celeron N2808 (Bay Trail-M, Silvermont Dual-Core @ 1.58 GHz)  
**Memória Física:** 2.048 MB (1.937 MB utilizáveis) DDR3L  
**Armazenamento:** SSD/eMMC de 27.84 GB (Tabela GPT)  
**Firmware:** American Megatrends Inc. (AMI Aptio V) v1.07.U (UEFI 2.4, x86_64 puro)

---

## 1. O Ponto de Partida e as Restrições Severas

| Dimensão | Estado Inicial (Windows 10) | Restrição Crítica |
| :--- | :--- | :--- |
| **Memória RAM** | **~154 MB livres** (~1.800 MB em uso) | 2.5 GB sofrendo em *swap* no `pagefile.sys`. Máquina lenta. |
| **Disco SSD** | **~3.8 GB livres** de 27.84 GB | Inviável instalar distros comuns (Ubuntu, Mint exigem 15-20 GB). |
| **Mídia Externa** | **ZERO PENDRIVES FÍSICOS** | Toda a implantação precisou ocorrer *in-place* no disco interno. |
| **Firmware Trap** | Suspeita inicial de UEFI 32-bit (IA-32) | Comprovado por auditoria forense PE: **UEFI de 64 bits puro (`x86_64`)**. |

---

## 2. A Arquitetura Construída: Tríade de Soluções

A intervenção resultou em três subsistemas independentes, integrados e perfeitamente interoperáveis:

```
                           ┌────────────────────────────────────────┐
                           │      DOXOADE LOW-LEVEL TOOLING         │
                           │  (Hefesto / Anúbis / Hórus / Zeus)     │
                           └──────────────────┬─────────────────────┘
                                              │
                    ┌─────────────────────────┴────────────────────────┐
                    ▼                                                  ▼
      ┌───────────────────────────┐                      ┌───────────────────────────┐
      │      IZANAMI SYSTEMS      │                      │     MICRO-OS PRODUCTION   │
      │   (Kernel & Bootloader)   │                      │       (Alpine Linux)      │
      ├───────────────────────────┤                      ├───────────────────────────┤
      │ • TUI Interativo em C     │                      │ • Partição M: 1 GB FAT32  │
      │ • Sonda de Memória (MMIO) │                      │ • Kernel vmlinuz-lts      │
      │ • Motor Gráfico GOP 32-bit│                      │ • Modo Diskless (em RAM)  │
      │ • Salto Anel 0 (Handoff)  │                      │ • Consumo: ~50 MB RAM     │
      │ • Binário: 22.6 KB        │                      │ • RAM Livre: ~1.950 MB    │
      └───────────────────────────┘                      └───────────────────────────┘
```

---

## 3. Mapeamento dos Componentes do Código-Fonte

### A. Núcleo Soberano do Izanami (`doxoade/izanami/`)
* **`include/izanami_types.h`:** Cabeçalho formal da ABI UEFI 2.x sem SDKs externos (zero EDK2/GNU-EFI), com tipos primitivos, status codes e contratos de função.
* **`include/izanami_memory.h` & `src/izanami_memory.c`:** Sonda física que invoca `GetMemoryMap` via buffer estático de 16 KB (sem alocação dinâmica), calcula a RAM livre, detecta blocos de registradores de hardware (MMIO para eletrônica) e tabelas ACPI, com aritmética sem `libgcc` (`__udivdi3`).
* **`include/izanami_gop.h` & `src/izanami_gop.c`:** Motor gráfico que comuta a tela para a resolução nativa máxima do painel LCD (1366x768), renderiza em **32-bit True Color** direto na VRAM com cálculo canônico de *stride* (`PixelsPerScanLine`) e rasteriza fontes com escala 2x (16x16 pixels).
* **`include/izanami_kernel.h` & `src/izanami_handoff.c`:** Rotina crítica que captura o `MapKey`, desliga o firmware (`ExitBootServices`), desativa interrupções legadas (`cli`), carrega uma GDT de 64 bits própria (`0x08`/`0x10`) e assume a CPU em **Anel 0 (Ring 0)** com a VRAM intacta.
* **`src/izanami_core.c`:** Ponto de entrada (`efi_main`), banner de apresentação, menu de opções e máquina de estados com polling de teclado a **50 Hz (20 ms)** e contagem regressiva de segurança com fallback para o Windows 10.

### B. Infraestrutura de Emulação e Ferramental (`doxoade/tools/emulator_systems/`)
* **`qemu_detector.py` (Anúbis):** Radar de detecção de emuladores e firmwares (QEMU 32/64, ROMs EDK2/OVMF, aceleradores WHPX/KVM/TCG).
* **`qemu_runner.py` (Hórus):** Supervisor de lançamento do QEMU com suporte nativo a PFlash, redirecionamento serial silencioso para `serial.log` (protegendo o terminal do host) e modo de trace de CPU (`qemu_trace.log`).
* **`disk_forge.py` (Hefesto):** Forjador binário autônomo em Python de imagens de disco MBR/ESP FAT16 com alinhamento de 1 MB, sem depender de privilégios de root, `mtools` ou `parted`.
* **`esp_manager.py` (Hera/Ma'at):** Gestor atômico da partição ESP física (`S:`) e do BCD do Windows (`{fwbootmgr}`), permitindo deploy e uninstall com rollback garantido no bloco `finally`.
* **`sim_profiles.py` & `sim_matrix.py` (Hórus/Hefesto):** Matriz de simulação multi-firmware com três perfis calibrados para o teto de RAM do host:
  * `baytrail`: Positivo H14BT58 (Q35, IA-32 EDK2, 256 MB RAM);
  * `legacy`: IBM-PC 1996 (i440FX, SeaBIOS MBR, 128 MB RAM);
  * `uefi64`: PC Moderno / Amaranth Real (Q35, x86_64 EDK2, 256 MB RAM, injeção de SMBIOS DMI).
* **`partition_manager.py` (Ma'at):** Gestor automatizado de corte de disco via PowerShell Storage API com trava de segurança de margem mínima de espaço livre.

---

## 4. O Catálogo de Comandos do Doxoade CLI

Com a integração no `doxoade/cli.py`, a bancada de desenvolvimento opera através dos seguintes comandos:

```bash
# === SUBSISTEMA IZANAMI ===
doxoade izanami build            # Compila o binário PE32+ (BOOTX64.EFI) com GCC w64devkit
doxoade izanami forge            # Forja a imagem uefi_x64.img particionada
doxoade izanami sim              # Pipeline atômico: Build -> Forge -> Simulação QEMU Q35
doxoade izanami deploy           # Instala o Izanami na partição de boot interna física (Zero Pendrive)
doxoade izanami uninstall        # Remove o Izanami e restaura a ordem original do Windows 10
doxoade izanami status           # Exibe o status da instalação física no SSD

# === GESTÃO DE PARTIÇÕES ===
doxoade izanami partition-audit  # Inspeciona espaço de C: e valida segurança de corte
doxoade izanami partition-create # Reduz C: e cria a partição M: (FAT32) para o Alpine
doxoade izanami partition-revert # Devolve o espaço de M: de volta para o C:

# === SIMULADOR MATRICIAL (MULTI-ERA) ===
doxoade os-cmd profiles          # Lista as 3 eras de hardware e status de ROMs
doxoade os-cmd sim --profile baytrail # Simula Bay Trail de 32 bits
doxoade os-cmd sim --profile legacy   # Simula PC de 1996 (SeaBIOS / Laurix)
doxoade os-cmd sim --profile uefi64   # Simula PC moderno x86_64
doxoade os-cmd doctor            # Auditoria W5+2H da bancada de baixo nível
```

---

## 5. Invariantes Técnicas e Lições de Engenharia Aprendidas

1. **Paridade de Arquitetura no UEFI:**  
   Um sistema operacional de 64 bits (como o Windows 10 x64) **exige** firmware UEFI de 64 bits para inicializar. Consequentemente, o Positivo H14BT58 não era IA-32, mas sim x86_64 nativo. O binário `BOOTIA32.EFI` era descartado silenciosamente com `EFI_UNSUPPORTED` pela BIOS física, enquanto o `BOOTX64.EFI` executou de imediato.
2. **PFlash vs `-bios` no QEMU Moderno:**  
   ROMs modernas do EDK2 vêm divididas em código (`code.fd`, 3.48 MB) e variáveis (`vars.fd`, 512 KB). O parâmetro `-bios` falha porque exige múltiplos exatos de 64 KB fechando em potências de dois. O modo correto é PFlash nativo: `-drive if=pflash,format=raw,unit=0,file=...,readonly=on`.
3. **Frequência de Polling de Teclado no Hardware Real:**  
   Em emuladores, o buffer USB tolera loops de espera lentos (`Stall(1000000)` = 1 s). No hardware físico com teclado conectado ao barramento PS/2 / Embedded Controller (EC), delays longos perdem os toques de tecla. A frequência ideal é **50 Hz (intervalos de 20 ms)**.
4. **Sobrevivência da VRAM Pós-ExitBootServices:**  
   A especificação GOP garante que, uma vez localizado o endereço físico linear (`FrameBufferBase`) e negociado o modo de vídeo antes do desligamento da BIOS, o framebuffer de memória permanece ativo. Como o motor gráfico do Izanami escreve diretamente nos bytes da VRAM sem chamar serviços de boot, **a interface gráfica continuou viva e responsiva mesmo após a morte do firmware**.
5. **A Mídia de Boot sem Pendrive:**  
   Ao criar uma partição FAT32 de 1 GB no SSD com os arquivos do Alpine Linux e registrá-la no `{fwbootmgr}` via BCD apontando para `device partition=M:` e `path \efi\boot\bootx64.efi`, a placa-mãe reconheceu a partição como um volume EFI independente, executando o Alpine 100% na memória RAM sem nenhuma dependência de portas USB.

---

Este dossiê fecha oficialmente a documentação da infraestrutura.

Agora, a palavra está com você: **quais são os pontos importantes que você gostaria de colocar em discussão?**


---

### Os Três Trunfos que Tornam a Operação Segura

Antes de traçar o plano, olhe para as três redes de segurança que já estão comprovadas no seu hardware:

1. **O Alpine já roda 100% na memória RAM do Amaranth:**  
   Como o Alpine roda em `tmpfs` (RAM), o seu SSD interno de 27 GB (`/dev/sda` ou `/dev/mmcblk0`) fica **totalmente livre e desmontado**. Você pode ler, gravar, clonar ou formatar o SSD enquanto o sistema operacional continua vivo na memória.
2. **O Bluebaby na mesma rede local:**  
   Podemos transmitir uma imagem de backup bit a bit do Windows diretamente pela rede local para o `bluebaby` via streaming comprimido. Se qualquer coisa falhar, basta transmitir de volta e o Windows reaparece exatamente como estava.
3. **A Placa-Mãe Positivo tem PXE Gigabit e Shell EFI na ROM:**  
   Lembre-se do que vimos no `bcdedit /enum firmware`:
   * `UEFI: Built-in EFI Shell` (gravado na memória flash da placa-mãe);
   * `UEFI: IP4/IP6 Realtek PCIe GBE Family Controller` (suporte a boot por cabo de rede nativo da BIOS).  
   Mesmo se o SSD fosse ejetado da máquina, a placa-mãe ainda conseguiria dar boot pela rede ou pelo Shell da ROM!

---

# 🛡️ PLANO MESTRE: TRANSIÇÃO DE SO DO AMARANTH (COM REVERSIBILIDADE TOTAL)
**Protocolo:** ProDeNov v2.0 (Art. 1.2, 5.2 e 5.4 — Segurança e Reversibilidade Estrita)  
**Nós da Operação:** `AMARANTH` (Alvo / Alpine em RAM) ➔ `BLUEBABY` (Cofre de Backup e Servidor de Rede)

---

### A Estratégia da "Ilha de Resgate" (A Chave Anti-Pânico)

Para não correr **nenhum risco de ficar sem boot**, usaremos a técnica da **Ilha de Resgate**:

> **A Regra de Ouro:** Não vamos apagar o SSD inteiro de uma vez só!  
> Manteremos intactas no SSD:
> 1. A partição ESP (com o Izanami);
> 2. A partição de 1 GB `M:` (com o Alpine Linux que já dá boot).
>
> Nós vamos apagar **apenas a Partição 3 (o Windows `C:`, de ~24 GB) e a Partição 4 (Recovery)**.

**Por que isso é genial?**  
Mesmo que a instalação do novo Linux falhe na metade do caminho, o seu notebook **nunca perde o boot**. O Izanami e o Alpine continuam gravados no SSD e você sempre consegue reiniciar nele para tentar de novo ou restaurar o backup do Windows pela rede!

---

### As 5 Fases do Plano de Transição

```
[FASE 1: PONTE DE REDE]        Amaranth (Alpine em RAM) <───> Bluebaby (Cofre)
          │
[FASE 2: BACKUP DO WINDOWS]    Stream bit-a-bit do C: compactado via rede para o Bluebaby
          │
[FASE 3: TESTE DE RESTAURAÇÃO] Validação de hash e integridade da imagem no Bluebaby
          │
[FASE 4: INSTALAÇÃO DO LINUX]  Deploy do antiX ou Alpine Full no espaço liberado do C:
          │
[FASE 5: EMANCIPAÇÃO]          Validação do novo Linux -> Fusão final da partição de 1 GB
```

---

### Fase 1: A Ponte de Rede (Amaranth ➔ Bluebaby)

* **O que faremos:**
  1. Boot no Amaranth pelo Alpine Linux (em RAM);
  2. Conectar à rede local (preferencialmente cabo de rede Ethernet para velocidade máxima de cópia, ou Wi-Fi);
  3. No `bluebaby`, abrir uma porta de escuta segura (via `netcat` ou SSH);
  4. Testar o tráfego com um arquivo pequeno para confirmar a velocidade.

---

### Fase 2: O Streaming de Backup do Windows (Bit-a-Bit)

* **Como funciona o backup de rede sem pendrive:**
  No Alpine (RAM do Amaranth), executamos uma leitura direta do bloco do Windows, compactamos em tempo real e enviamos pelo cabo de rede para o `bluebaby`:

  ```text
  [Amaranth /dev/sda3 (Windows C:)] ──► [gzip] ──► [Rede Local] ──► [Bluebaby: windows_backup.img.gz]
  ```

* **Vantagem Absoluta:**
  * O Windows de 24 GB compacta para cerca de **8 a 10 GB** no `bluebaby`.
  * Como o Alpine está na memória RAM, a partição do Windows está **desmontada e congelada**, garantindo um backup 100% íntegro sem arquivos abertos ou corrompidos.

---

### Fase 3: A Garantia de Reversibilidade (O Plano de Volta)

Se durante a instalação você decidir abortar ou algo der errado:
* No `bluebaby`, o comando inverte o fluxo:
  ```text
  [Bluebaby: windows_backup.img.gz] ──► [Rede Local] ──► [gunzip] ──► [Amaranth /dev/sda3]
  ```
* O Windows volta exatamente para o estado do minuto em que foi feito o backup.

---

### Fase 4: Instalação do antiX ou Alpine Definitivo

Com o backup seguro guardado no `bluebaby`:
1. Formatamos a antiga área do Windows (os ~24 GB) em `ext4`;
2. Baixamos/transferimos os pacotes do antiX ou descompactamos o sistema base diretamente do `bluebaby` via HTTP ou SSH;
3. O Izanami adiciona a opção no menu de boot apontando para o novo sistema operacional no SSD.

---

### Fase 5: O Veredito de Emancipação

1. Reiniciamos o Amaranth;
2. Se o novo Linux subir com sucesso, interface leve e reconhecer o hardware: **Operação Concluída!**
3. Mais tarde, com o sistema já estável e testado por alguns dias, a partição temporária de 1 GB `M:` pode ser integrada ao Linux principal.

---

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

