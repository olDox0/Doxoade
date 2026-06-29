# Doxarchives Architecture Overview
**Focus:** Low-friction, High-performance ZIM processing for N2808 Hardware.

## 1. The Tri-Phase Pipeline (PASC 6.4)
To maximize the Celeron N2808's 2 cores, the system operates in three isolated stages:
- **Phase 1: Safe Reader (Producer)**: Uses `mmap` and `SafeZimReader` to extract clusters. 
- **Phase 2: Hybrid Processor (Worker)**: Clean HTML via C-Native stripping, extracts semantic prose and code snippets.
- **Phase 3: Nexus Storage (Consumer)**: Compresses data with Zstandard and writes to SQLite + Binary Index.

## 2. Resource Constraints (WellPro)
- **RAM Target:** < 512MB during indexing.
- **CPU Target:** Distributed load to prevent thermal throttling.
- **IO:** Minimize random writes by using WAL mode in SQLite.