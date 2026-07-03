import time
from pathlib import Path
from doxoade.tools.hermes_systems.hermes_format import parse_header
data = Path('.doxoade/hermes/build/doxoade.cli.hermes').read_bytes()
t0 = time.perf_counter()
for _ in range(1000):
    parse_header(data)
t1 = time.perf_counter()
print(f'Parse HBC3: {(t1-t0)/1000*1000:.3f}ms por arquivo')