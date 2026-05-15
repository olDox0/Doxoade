# -*- coding: utf-8 -*-
# doxoade\tools\vulcan\soteria_engine.py
# Analista Forense - Python

import os, sys, re, json, datetime

class SoteriaForensic:
    """Cérebro Investigativo do Doxoade para falhas nativas."""
    def __init__(self):
        self.reset = "\033[0m"
        self.red = "\033[1;31m"
        self.ylw = "\033[1;33m"
        self.cyan = "\033[1;36m"

    def process_pipe(self, text):
        """Analisa o fluxo de saída em busca de assinaturas Sotéria."""
        match = re.search(r"@SOTERIA_BEGIN@(.*?)@SOTERIA_END@", text, re.DOTALL)
        if not match:
            return False
            
        nx = match.group(1)
        def get_tag(t): return (re.findall(rf"TAG_{t}:\s*(.*)", nx, re.IGNORECASE) or ["N/A"])[0].strip()

        print(f"{self.red}" + "!" * 65 + f"\n SOTÉRIA: RESGATE DE EXECUÇÃO ATIVO\n" + "!" * 65 + self.reset)
        
        # 1. Rastro de Símbolos (A Pilha)
        frames = re.findall(r"TAG_FRAME:\s*(.*)", nx)
        if frames:
            print(f"{self.cyan}■ CADEIA DE CHAMADAS (QUEBRA-CABEÇA):{self.reset}")
            for f in frames:
                color = "\033[1;32m" if "doxoade" in f.lower() else "\033[90m"
                print(f"   {color}↳ {f.strip()}{self.reset}")

        # 2. Marco de Sucesso
        print(f"\n{self.cyan}■ ÚLTIMO MARCO CONHECIDO (RASTRO):{self.reset}")
        print(f"  {self.ylw}{get_tag('RASTRO_MSG')}{self.reset} em {get_tag('RASTRO_LOC')}")

        # 3. Diagnóstico Final
        print(f"\n{self.cyan}■ CAUSA DA FALHA:{self.reset} {get_tag('MOTIVO')} | {get_tag('SUBSIS')}")
        print(f"  {self.cyan}DETALHE:{self.reset} {get_tag('DETAIL')}")
        print(f"  {self.cyan}LOCAL:{self.reset}   {get_tag('LOCAL')}")
        print(f"\n{self.red}" + "─" * 65 + self.reset + "\n")
        return True