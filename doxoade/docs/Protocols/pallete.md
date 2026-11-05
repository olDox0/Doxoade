padrão de design:

1.1. Cor de destaque principal, fria:
    Esmeralda, 26bc5f.                  # RGB(38, 188, 95)
    Esmeralda Escuro, 197b3f.           # RGB(25, 123, 63)
    
1.2. Cor de destaque quente: Esta cor é util para exibição de destaques e erros
    Laranja Blaze, FF6700.              # RGB(255, 103, 0)
    Laranja Black Escuro, e05a00.       # RGB(224, 90, 0)
    Amarelo Urobilin, E8AA00            # RGB(232, 170, 0)
    Magenta Electric, C81576            # RGB(200, 21, 118)
    
1.3. Cor secundaria, fria:
    Brandeis Blue, 006CFF.              # RGB(0, 108, 255)
    
1.4. Cor de fundo claro:
    Athens gray, EDF1F5                 # RGB(237, 241, 245)
    e1ebf4.                             # RGB(225, 235, 244)
    
1.5. Cor de fundo escuro:
    Mortar,                #4C4552.     # RGB(76, 69, 82)
    Blue-Magenta:          #16101a      # RGB(22, 16, 26)
    Piano Black     
        0° claro:          #5e5c5e      # RGB(94, 92, 94)
        1° leve:           #2f2e30      # RGB(47, 46, 48)
        2° normal:         #19171a      # RGB(25, 23, 26)
        3° escuro:         #0f0d0f      # RGB(15, 13, 15)

   Letreiro1:Nordic Breeze #d2dce6      # RGB(210, 220, 230)
   Leitreiro2:#c4d0ae                   # RGB(196, 208, 174)
   
1.9 Cor de terminal
        #0a331a                         # RGB(10, 51, 26)
        
:root { 
    --bg-dark:     #0f0d0f;        /* Piano Black 3 */
    --panel:       #19171a;        /* Piano Black 2 */
    --panel-light: #2f2e30;        /* Piano Black 1 */
    --border:      #4c4552;        /* Mortar */
    
    --text-main:  #d2dce6;         /* Nordic Breeze */
    --text-muted: #5e5c5e;         /* Piano Black 0 */
    
    --accent-primary:  #26bc5f;    /* Esmeralda */
    --accent-dark:     #197b3f;    /* Esmeralda Escuro */
    --target:          #ff6700;    /* Laranja Blaze */
    --target-dark:     #e05a00;    /* Laranja Escuro */
    --secondary-hover: #006cff;    /* Brandeis Blue */
    --warning:         #e8aa00;    /* Urobilin Yellow */
    --term-bg:         #0a331a;    /* Fundo Terminal */

    --pastel-orange: #E38D53;      /* fluxo grama cor 1 */
    --pastel-pink:   #CE699E;      /* fluxo grama cor 2 */
    --pastel-blue:   #4D91E8;      /* fluxo grama cor 3 */
    --pastel-green:  #57B87C;      /* fluxo grama cor 3 */
        
    --dark-pastel-orange: #5a3821; /* fluxo grama cor 1 */
    --dark-pastel-pink:   #52293f; /* fluxo grama cor 2 */
    --dark-pastel-blue:   #1e395c; /* fluxo grama cor 3 */
    --dark-pastel-green:  #224931; /* fluxo grama cor 3 */
}
