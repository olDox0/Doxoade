# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_compress.py
import os
import marshal
import zlib
#import lzma
import types
from pathlib import Path
from .hermes_format import build_header, MAGIC_HBC3
from .hermes_format_hbc4 import build_header_hbc4, MAGIC_HBC4
from .hermes_dict.hermes_builder import HermesDictionaryBuilder

class HermesCompressor:
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.hermes_output_dir = self.root / '.doxoade' / 'hermes' / 'build'
        self.hermes_output_dir.mkdir(parents=True, exist_ok=True)

    def compress_file(self, py_file_path: Path, optimized_content: str = None,
                      use_dynamic_scan: bool = False, use_hbc4: bool = False):
        """
        Comprime arquivo Python para formato .hermes.
        
        Args:
            py_file_path: Caminho do arquivo .py
            optimized_content: Conteúdo otimizado (se None, lê do arquivo)
            use_dynamic_scan: Usa scanner dinâmico local
            use_hbc4: Usa formato HBC4 (sem LZMA, mais rápido)
        
        Returns:
            Tuple (original_size, final_size, hermes_file, dynamic_count)
        """
        # 1. Obtém código fonte
        source = optimized_content if optimized_content is not None \
                 else py_file_path.read_text(encoding='utf-8')
        original_size = len(source.encode('utf-8'))

        # 2. Compila para bytecode com Otimização Máxima
        code_obj = compile(source, str(py_file_path), 'exec', optimize=2)

        # 3. Se dynamic scan ativo, tokeniza os co_consts do bytecode
        dynamic_encoder = {}
        if use_dynamic_scan:
            dynamic_encoder = self._build_and_apply_dynamic(
                py_file_path, source
            )
            if dynamic_encoder:
                code_obj = self._tokenize_code_consts(code_obj, dynamic_encoder)

        # 4. Serializa
        marshalled_data = marshal.dumps(code_obj)

        # 5. Comprime (ou não, se HBC4)
        if use_hbc4:
            # HBC4: Sem compressão LZMA (mais rápido)
            final_size = len(marshalled_data)
        else:
            # HBC3: Com compressão zlib (menor). NOTA: se trocar o algoritmo aqui,
            # atualize também hermes_loader.py._decompress_data (branch HBC3) —
            # o loader precisa usar o MESMO algoritmo de descompressão.
            compressed_data = zlib.compress(marshalled_data, level=6)
            final_size = len(compressed_data)

        # 6. Define caminho de saída
        py_file_abs = py_file_path.resolve()
        relative_path = py_file_abs.relative_to(self.root)
        module_name = str(relative_path.with_suffix('')).replace(os.sep, '.')
        hermes_file = self.hermes_output_dir / f"{module_name}.hermes"

        # 7. Salva com formato apropriado
        if use_hbc4 and dynamic_encoder:
            # HBC4 com tokens dinâmicos
            payload = build_header_hbc4(dynamic_encoder, marshalled_data)
            hermes_file.write_bytes(payload)
        elif use_hbc4:
            # HBC4 sem tokens (apenas marshalled)
            hermes_file.write_bytes(MAGIC_HBC4 + marshalled_data)
        elif dynamic_encoder:
            # HBC3 com tokens dinâmicos
            self._write_hbc3(hermes_file, compressed_data, dynamic_encoder)
        else:
            # HBC1 legacy (apenas LZMA)
            hermes_file.write_bytes(b"HBC1" + compressed_data)

        return original_size, final_size, hermes_file, len(dynamic_encoder)

    # ─────────────────────────────────────────────────────────────────────
    # Pipeline de scan dinâmico
    # ─────────────────────────────────────────────────────────────────────
    def _build_and_apply_dynamic(self, py_file_path: Path, source: str) -> dict:
        """Constrói dicionário local para o arquivo."""
        from .hermes_dynamic_scanner import build_dynamic_dictionary

        # Carrega encoder global para não duplicar tokens
        builder = HermesDictionaryBuilder(str(self.root))
        global_dict = builder.load_dictionary()
        existing_encoder = {}
        if global_dict and 'encoder' in global_dict:
            existing_encoder = {
                k: int(v) if isinstance(v, str) and v.isdigit() else v
                for k, v in global_dict['encoder'].items()
            }

        return build_dynamic_dictionary(
            py_file_path,
            existing_encoder,
            max_new_tokens=200,
            min_freq=2
        )

    def _tokenize_code_consts(self, code_obj, encoder: dict):
        """Percorre recursivamente o code object e substitui strings em co_consts."""
        new_consts = []
        for const in code_obj.co_consts:
            if isinstance(const, str):
                # Substitui padrões na string (ordena por tamanho para evitar sobreposição)
                sorted_patterns = sorted(encoder.items(),
                                        key=lambda x: len(x[0]), reverse=True)
                result = const
                for pattern, token_int in sorted_patterns:
                    if pattern in result:
                        result = result.replace(pattern, chr(token_int))
                new_consts.append(result)
            elif isinstance(const, types.CodeType):
                # Recursão para code objects aninhados (funções, lambdas)
                new_consts.append(self._tokenize_code_consts(const, encoder))
            else:
                new_consts.append(const)

        return code_obj.replace(co_consts=tuple(new_consts))

    def _write_hbc3(self, hermes_file: Path, compressed_data: bytes,
                    dynamic_encoder: dict):
        """Escreve arquivo no formato HBC3 (binário nativo + bitmap)."""
        header = build_header(dynamic_encoder)
        payload = header + compressed_data
        hermes_file.write_bytes(payload)