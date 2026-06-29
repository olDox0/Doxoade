# Architectural Decision Records (ADR)

## ADR-001: Flat Binary Search over Database Indexing
- **Status:** Accepted
- **Context:** Database B-Trees for full-text search are heavy on RAM/IO for Celeron.
- **Decision:** Use a custom `vocab.bin` (sorted fixed-width terms) and `postings.bin` (varint-compressed IDs).
- **Consequence:** Search will be O(log N) with minimal RAM overhead.

## ADR-002: Zstd Compression Level 9
- **Status:** Accepted
- **Context:** N2808 has slow eMMC/HDD; CPU cycles for decompression are cheaper than IO.
- **Decision:** Compress all prose/code snippets at high level.