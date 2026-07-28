#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hermes HBC6 Doctor — Diagnóstico Completo do Pipeline HBC6
==========================================================
Testa cada etapa do pipeline isoladamente:
  1. Bridge C disponível?
  2. Arquivo HBC6 válido?
  3. Header parseável?
  4. Payload deserializável?
  5. Motor C carrega?
  6. Execução funciona?

Uso:
  python -m doxoade.tools.hermes_systems.hermes_hbc6_doctor [arquivo.hbc6]
  python -m doxoade.tools.hermes_systems.hermes_hbc6_doctor --all
"""
import sys
import struct
import marshal
import hashlib
import traceback
from pathlib import Path
from typing import Optional, Tuple

from doxoade.tools.aegis.aegis_utils import restricted_safe_exec
from doxoade.commands.vulcan_systems.vulcan_cmd import doctor

# ─── Cores ────────────────────────────────────────────────────────────
G = "\033[32m"  # verde
R = "\033[31m"  # vermelho
Y = "\033[33m"  # amarelo
C = "\033[36m"  # ciano
B = "\033[1m"   # bold
D = "\033[2m"   # dim
X = "\033[0m"   # reset

def ok(msg):   print(f"  {G}✔{X} {msg}")
def fail(msg): print(f"  {R}✘{X} {msg}")
def warn(msg): print(f"  {Y}⚠{X} {msg}")
def info(msg): print(f"  {C}ℹ{X} {msg}")
def head(msg): print(f"\n{B}{C}{'═'*60}\n  {msg}\n{'═'*60}{X}")


class HBC6Doctor:
    """Diagnóstico etapa por etapa do pipeline HBC6."""

    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.build_dir = self.root / '.doxoade' / 'hermes' / 'build'
        self.gd_path = self.root / '.doxoade' / 'hermes' / 'master.bin'
        self.results = {}

    # ─── Etapa 1: Bridge C ────────────────────────────────────────────
    def check_bridge(self) -> bool:
        head("ETAPA 1: Motor C (hermes_bridge)")
        try:
            from doxoade.tools.hermes_systems.native import hermes_bridge
            ok(f"Bridge importado: {hermes_bridge.__file__}")
            if hasattr(hermes_bridge, 'load_module'):
                ok("load_module disponível")
            else:
                fail("load_module NÃO encontrado no bridge")
                return False
            self.results['bridge'] = hermes_bridge
            return True
        except ImportError as e:
            fail(f"Bridge não importável: {e}")
            info("Rode: doxoade hermes native")
            return False
        except Exception as e:
            fail(f"Erro inesperado: {e}")
            traceback.print_exc()
            return False

    # ─── Etapa 2: Arquivo HBC6 ────────────────────────────────────────
    def check_file(self, hbc6_path: Path) -> Optional[bytes]:
        head(f"ETAPA 2: Arquivo HBC6 — {hbc6_path.name}")
        if not hbc6_path.exists():
            fail(f"Arquivo não existe: {hbc6_path}")
            return None
        data = hbc6_path.read_bytes()
        ok(f"Tamanho: {len(data)} bytes")

        if data[:4] != b'HBC6':
            fail(f"Magic inválido: {data[:4]} (esperado b'HBC6')")
            return None
        ok("Magic: HBC6")

        version = data[4]
        flags = data[5]
        info(f"Version: {version}")
        info(f"Flags: 0x{flags:02X}", )

        flag_names = []
        if flags & 0x01: flag_names.append("TOKENIZED_CONSTS")
        if flags & 0x02: flag_names.append("BYTECODE_PATCHED")
        if flags & 0x10: flag_names.append("CUSTOM_PAYLOAD")
        if flags & 0x20: flag_names.append("LZ4_PAYLOAD")
        if flag_names:
            info(f"Flags ativas: {', '.join(flag_names)}")

        if flags & 0x10:
            fail("FLAG_CUSTOM_PAYLOAD (0x10) ativa — causa SegFault!")
            info("Recompile sem hermes_payload.py")
            return None

        self.results['flags'] = flags
        return data

    # ─── Etapa 3: Parse do Header ─────────────────────────────────────
    def check_header(self, data: bytes) -> Optional[dict]:
        head("ETAPA 3: Parse do Header")
        try:
            offset = 6
            hrt_size = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            info(f"HRT size: {hrt_size} bytes")
            hrt_data = data[offset:offset + hrt_size]
            offset += hrt_size

            macro_dict_size = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            info(f"Macro dict size: {macro_dict_size} bytes")
            macro_dict_data = data[offset:offset + macro_dict_size]
            offset += macro_dict_size

            payload_size = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            info(f"Payload size (header): {payload_size} bytes")

            actual_payload = len(data) - offset
            info(f"Payload real: {actual_payload} bytes")

            if payload_size != actual_payload:
                fail(f"MISMATCH: header={payload_size} real={actual_payload}")
                warn("O compressor pode estar escrevendo o tamanho errado")
            else:
                ok("Payload size consistente")

            header_info = {
                'hrt_size': hrt_size,
                'hrt_data': hrt_data,
                'macro_dict_size': macro_dict_size,
                'macro_dict_data': macro_dict_data,
                'payload_size': payload_size,
                'payload_offset': offset,
                'payload': data[offset:offset + payload_size],
            }

            # Parse HRT se presente
            if hrt_size > 0:
                patch_count = struct.unpack_from('<I', hrt_data, 0)[0]
                info(f"HRT patches: {patch_count}")

            # Parse macro dict se presente
            if macro_dict_size > 0:
                dict_count = macro_dict_data[0] if macro_dict_data else 0
                info(f"Macro dict entries: {dict_count}")

            self.results['header'] = header_info
            return header_info

        except Exception as e:
            fail(f"Erro no parse: {e}")
            traceback.print_exc()
            return None

    # ─── Etapa 4: Deserialização do Payload ───────────────────────────
    def check_payload(self, header: dict) -> Optional[object]:
        head("ETAPA 4: Deserialização do Payload")
        payload = header['payload']
        flags = self.results.get('flags', 0)

        # LZ4?
        if flags & 0x20:
            info("Payload comprimido com LZ4 — descomprimindo...")
            try:
                import lz4.block
                payload = lz4.block.decompress(payload)
                ok(f"LZ4 descomprimido: {len(payload)} bytes")
            except ImportError:
                fail("lz4 não instalado — pip install lz4")
                return None
            except Exception as e:
                fail(f"LZ4 decompress falhou: {e}")
                return None

        try:
            code_obj = marshal.loads(payload)
            ok(f"marshal.loads OK: {type(code_obj).__name__}")
            info(f"co_code: {len(code_obj.co_code)} bytes")
            info(f"co_consts: {len(code_obj.co_consts)} itens")
            info(f"co_names: {code_obj.co_names}")

            # Verifica code objects filhos
            child_count = sum(
                1 for c in code_obj.co_consts
                if isinstance(c, type(code_obj))
            )
            if child_count:
                info(f"Code objects filhos: {child_count}")

            # Valida bytecode com dis
            import dis
            try:
                list(dis.get_instructions(code_obj))
                ok("Bytecode válido (dis.get_instructions passou)")
            except Exception as e:
                fail(f"Bytecode INVÁLIDO: {e}")
                return None

            self.results['code_obj'] = code_obj
            return code_obj

        except Exception as e:
            fail(f"marshal.loads falhou: {e}")
            traceback.print_exc()
            return None

    # ─── Etapa 5: Motor C ─────────────────────────────────────────────
    def check_c_engine(self, hbc6_path: Path) -> Optional[object]:
        head("ETAPA 5: Motor C (hermes_bridge.load_module)")
        bridge = self.results.get('bridge')
        if not bridge:
            warn("Bridge não disponível — pulando")
            return None

        gd_str = str(self.gd_path) if self.gd_path.exists() else ""
        info(f"hbc6_path: {hbc6_path}")
        info(f"gd_path: {repr(gd_str)}")

        try:
            code_obj = bridge.load_module(str(hbc6_path), gd_str)
            if code_obj is None:
                fail("Motor C retornou NULL")
                warn("Possíveis causas:")
                warn("  - Header HBC6 incompatível com o parser C")
                warn("  - Macro dict com formato inesperado")
                warn("  - Payload corrompido")
                return None
            ok(f"Motor C retornou: {type(code_obj).__name__}")
            info(f"co_code: {len(code_obj.co_code)} bytes")
            self.results['c_code_obj'] = code_obj
            return code_obj
        except Exception as e:
            fail(f"Motor C lançou exceção: {type(e).__name__}: {e}")
            traceback.print_exc()
            return None

    # ─── Etapa 6: Execução ────────────────────────────────────────────
    def check_exec(self, code_obj, label: str = "Python") -> bool:
        head(f"ETAPA 6: Execução ({label})")
        try:
            ns = {'__name__': '__hbc6_doctor__', '__builtins__': __builtins__}
            restricted_safe_exec(code_obj, ns)
            ok(f"Execução {label} OK")
            # Mostra variáveis definidas
            user_vars = {
                k: v for k, v in ns.items()
                if not k.startswith('__')
            }
            if user_vars:
                info(f"Variáveis: {list(user_vars.keys())}")
            return True
        except Exception as e:
            fail(f"Execução {label} falhou: {e}")
            traceback.print_exc()
            return False

    # ─── Comparação Python vs C ───────────────────────────────────────
    def compare(self, py_code, c_code) -> bool:
        head("COMPARAÇÃO: Python vs Motor C")
        if c_code is None:
            warn("Sem code object do C para comparar")
            return False

        py_bc = py_code.co_code
        c_bc = c_code.co_code

        if py_bc == c_bc:
            ok(f"Bytecode idêntico ({len(py_bc)} bytes)")
        else:
            warn(f"Bytecode DIFERENTE: Python={len(py_bc)}B C={len(c_bc)}B")
            # Mostra primeira diferença
            for i in range(min(len(py_bc), len(c_bc))):
                if py_bc[i] != c_bc[i]:
                    info(f"Primeira diferença no offset {i}: "
                         f"Python=0x{py_bc[i]:02X} C=0x{c_bc[i]:02X}")
                    break

        py_names = set(py_code.co_names)
        c_names = set(c_code.co_names)
        if py_names == c_names:
            ok(f"co_names idênticos: {sorted(py_names)}")
        else:
            warn(f"co_names diferentes: "
                 f"Python={sorted(py_names)} C={sorted(c_names)}")

        return py_bc == c_bc

    # ─── Relatório Final ──────────────────────────────────────────────
    def report(self, hbc6_path: Path):
        head("RELATÓRIO FINAL")
        checks = [
            ("Bridge C",       'bridge' in self.results),
            ("Arquivo HBC6",   'flags' in self.results),
            ("Header parse",   'header' in self.results),
            ("Payload marshal",'code_obj' in self.results),
            ("Motor C load",   'c_code_obj' in self.results),
        ]
        all_ok = True
        for name, passed in checks:
            if passed:
                ok(name)
            else:
                fail(name)
                all_ok = False

        if all_ok:
            print(f"\n  {G}{B}✅ PIPELINE HBC6 100% FUNCIONAL{X}")
        else:
            print(f"\n  {R}{B}❌ PIPELINE HBC6 COM FALHAS{X}")
            # Identifica onde quebrou
            for name, passed in checks:
                if not passed:
                    print(f"  {R}→ Primeira falha: {name}{X}")
                    break

    # ─── Orquestrador ─────────────────────────────────────────────────
    def diagnose(self, hbc6_path: Path) -> bool:
        """Executa diagnóstico completo. Retorna True se tudo OK."""
        print(f"\n{B}🔬 HERMES HBC6 DOCTOR{X}")
        print(f"  {D}Projeto: {self.root}{X}")
        print(f"  {D}Alvo: {hbc6_path.name}{X}")

        # Etapa 1
        bridge_ok = self.check_bridge()

        # Etapa 2
        data = self.check_file(hbc6_path)
        if data is None:
            self.report(hbc6_path)
            return False

        # Etapa 3
        header = self.check_header(data)
        if header is None:
            self.report(hbc6_path)
            return False

        # Etapa 4
        py_code = self.check_payload(header)
        if py_code is None:
            self.report(hbc6_path)
            return False

        # Etapa 5
        c_code = None
        if bridge_ok:
            c_code = self.check_c_engine(hbc6_path)

        # Etapa 6
        if py_code:
            self.check_exec(py_code, "Python (marshal direto)")
        if c_code:
            self.check_exec(c_code, "Motor C")

        # Comparação
        if py_code and c_code:
            self.compare(py_code, c_code)

        # Relatório
        self.report(hbc6_path)
        return 'c_code_obj' in self.results


def diagnose_all(project_root: str):
    """Diagnostica todos os .hbc6 no build dir."""
    root = Path(project_root).resolve()
    build_dir = root / '.doxoade' / 'hermes' / 'build'
    hbc6_files = sorted(build_dir.glob('*.hbc6'))

    if not hbc6_files:
        print(f"{Y}Nenhum .hbc6 encontrado em {build_dir}{X}")
        return

    print(f"{B}🔬 Diagnosticando {len(hbc6_files)} arquivos HBC6...{X}\n")

    results = {'ok': [], 'fail': []}
    for hbc6 in hbc6_files:
        doctor = HBC6Doctor(project_root)
        try:
            passed = doctor.diagnose(hbc6)
            if passed:
                results['ok'].append(hbc6.name)
            else:
                results['fail'].append(hbc6.name)
        except Exception as e:
            results['fail'].append(hbc6.name)
            print(f"  {R}✘ {hbc6.name}: {e}{X}")

    head("RESUMO GERAL")
    print(f"  {G}✔ OK: {len(results['ok'])}{X}")
    print(f"  {R}✘ Falha: {len(results['fail'])}{X}")
    if results['fail']:
        print(f"\n  {R}Arquivos com problema:{X}")
        for name in results['fail']:
            print(f"    {R}• {name}{X}")


if __name__ == '__main__':
    import click

    @click.command()
    @click.argument('file', required=False, type=click.Path(exists=True))
    @click.option('--all', '-a', 'diagnose_all_flag', is_flag=True,
                  help='Diagnostica todos os .hbc6')
    def main(file, diagnose_all_flag):
        project_root = str(Path.cwd().resolve())

        if diagnose_all_flag:
            diagnose_all(project_root)
        elif file:
            doctor = HBC6Doctor(project_root)
            doctor.diagnose(Path(file).resolve())
        else:
            # Diagnóstica o dummy se existir
            build = Path(project_root) / '.doxoade' / 'hermes' / 'build'
            dummies = list(build.glob('dummy_hbc6_module_*.hbc6'))
            if dummies:
                doctor = HBC6Doctor(project_root)
                doctor.diagnose(dummies[0])
            else:
                print("Uso: python -m doxoade.tools.hermes_systems.hermes_hbc6_doctor [arquivo.hbc6]")
                print("     python -m doxoade.tools.hermes_systems.hermes_hbc6_doctor --all")

    main()
