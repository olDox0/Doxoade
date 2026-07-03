from pathlib import Path
from doxoade.tools.hermes_systems.hermes_format import parse_header, get_bitmap
import lzma

data = Path('.doxoade/hermes/build/doxoade.cli.hermes').read_bytes()
print(f'Total: {len(data)} bytes')

decoder, compressed, offset = parse_header(data)
print(f'Header size: {offset} bytes')
print(f'Tokens: {len(decoder) if decoder else 0}')
print(f'Compressed size: {len(compressed) if compressed else 0} bytes')

if compressed:
    print(f'Primeiros 10 bytes do compressed: {compressed[:10]}')
    try:
        marshalled = lzma.decompress(compressed)
        print(f'✔ LZMA OK: {len(marshalled)} bytes')
    except Exception as e:
        print(f'✘ LZMA FAILED: {e}')