# test260630.py
import time
from pathlib import Path
from doxoade.tools.hermes_systems.hermes_loader import HermesLoader

loader = HermesLoader('.')
hermes_path = Path('.doxoade/hermes/build/doxoade.cli.hermes')

# Etapa 1: Leitura
t0 = time.perf_counter()
data = hermes_path.read_bytes()
t1 = time.perf_counter()
print(f"Read: {(t1-t0)*1000:.2f}ms")

# Etapa 2: Parse header
t0 = time.perf_counter()
if data.startswith(b"HBC2"):
    rest = data[4:]
    metadata_len = int.from_bytes(rest[:4], 'little')
    metadata_compressed = rest[4:4 + metadata_len]
    compressed_data = rest[4 + metadata_len:]
    import json, lzma
    metadata = json.loads(lzma.decompress(metadata_compressed))
t1 = time.perf_counter()
print(f"Parse header: {(t1-t0)*1000:.2f}ms")

# Etapa 3: LZMA decompress
t0 = time.perf_counter()
marshalled_data = lzma.decompress(compressed_data)
t1 = time.perf_counter()
print(f"LZMA decompress: {(t1-t0)*1000:.2f}ms")

# Etapa 4: Marshal loads
import marshal
t0 = time.perf_counter()
code_obj = marshal.loads(marshalled_data)
t1 = time.perf_counter()
print(f"Marshal loads: {(t1-t0)*1000:.2f}ms")

# Etapa 5: Reverse tokens (se HBC2)
if data.startswith(b"HBC2"):
    dynamic_decoder = {int(k): v for k, v in metadata['dynamic_encoder'].items()}
    t0 = time.perf_counter()
    code_obj = loader._reverse_dynamic_tokens(code_obj, dynamic_decoder)
    t1 = time.perf_counter()
    print(f"Reverse tokens: {(t1-t0)*1000:.2f}ms")