# Plan: chunking & storage

Input: `data/parsed/*.json` (DoclingDocument). Output: rows in Postgres (`docker compose up -d`, port 5433).

```
DoclingDocument JSON ──► documents
                     ├─► sections   (rebuilt heading tree)
                     ├─► elements   (paragraph / equation / table / caption / code, + offsets)
                     ├─► chunks ◄── chunk_elements ──► elements
                     │      └─► embeddings (per model)
                     ├─► notation   (later, LLM-extracted)
                     └─► bibliography
```

## Tables & keys

| Table | Primary key | Key columns | Notes |
|---|---|---|---|
| `documents` | `id` | `title, authors[], year, source_path, sha256, parser, parser_version, parsed_at, canonical_text` | `sha256` UNIQUE → skip re-ingest. `canonical_text` = NFKC-normalized text all offsets point into. |
| `sections` | `id` | `document_id` FK, `parent_id` FK (self), `number` ('2.1'), `title`, `level`, `heading_path` text[], `ord` | Tree rebuilt from numbering (see gotchas). |
| `elements` | `id` | `document_id`, `section_id` FKs, `docling_ref` ('#/texts/12'), `type`, `text`, `latex`, `char_start`, `char_end`, `page`, `bbox` jsonb, `ord` | `type` ∈ paragraph, list_item, equation, table, caption, code, footnote. UNIQUE(`document_id`, `docling_ref`). |
| `chunks` | `id` | `document_id` FK, `section_id` FK, `text`, `contextualized_text`, `token_count`, `chunking_strategy`, `chunker_version`, `char_start`, `char_end`, `page_start`, `page_end` | `chunking_strategy` e.g. `hybrid-512`; lets two strategies coexist. |
| `chunk_elements` | (`chunk_id`, `element_id`) | `ord` | Many-to-many: cite the exact paragraph/equation. |
| `embeddings` | (`chunk_id`, `embedding_model`) | `embedding vector(N)` | One table per dimension if you compare models. HNSW + `vector_cosine_ops`. |
| `notation` | `id` | `document_id` FK, `symbol` ('α_m'), `latex`, `meaning`, `defined_in_element_id` FK | Phase 2. |
| `bibliography` | `id` | `document_id` FK, `ord`, `raw_text`, `authors`, `year`, `title` | From `REFERENCE` items; parse fields later. |

Also: a GIN full-text index on `chunks.contextualized_text` for keyword (BM25-style) search alongside vectors.

## Docling for chunking

- **Load, don't re-parse:** `DoclingDocument.load_from_json(path)`.
- **Walk elements:** `doc.iterate_items()` → `item.label`, `item.text`, `item.self_ref` (→ `docling_ref`), `item.prov[0].page_no` / `.bbox`. Tables: `TableItem.export_to_markdown(doc)`; captions: `table.caption_text(doc)`.
- **Chunk:** `docling.chunking.HybridChunker(tokenizer=..., merge_peers=True, repeat_table_header=True)`.
  - Tokenizer = the embedding model's: `HuggingFaceTokenizer.from_pretrained(model_name, max_tokens=...)` (or the OpenAI tokenizer if using OpenAI embeddings).
  - Per chunk: `chunk.text`, `chunk.meta.headings`, `chunk.meta.captions`, `chunk.meta.doc_items` (→ `self_ref` → `chunk_elements`).
  - `chunker.contextualize(chunk)` → `contextualized_text` (this is what gets embedded).
- **Embeddings:** `sentence-transformers` (local, free) or an API model. Pin the exact version with `uv add`.
- **DB driver:** `psycopg[binary]` + `pgvector` (Python package, registers the `vector` type).

## Gotchas found in our parse

1. **Flat headings:** docling gives every `SECTION_HEADER` level 1. Rebuild the tree from the numbering regex `^(\d+(?:\.\d+)*)\s+` ('2.1' → parent '2'); unnumbered ('Abstract', 'Appendix') → level 1.
2. **Character offsets aren't in docling:** compute them yourself while assembling `canonical_text` (append each element, record start/end).
3. **Stan code split across pp. 28–30** into 3 `CODE` items → merge consecutive CODE items first.
4. **Drop** `PAGE_HEADER`, `PAGE_FOOTER`; route `REFERENCE` → `bibliography`, not chunks. Keep figure **captions**, skip `PICTURE`.
5. **Equations:** keep each FORMULA in the same chunk as the sentence before it ("ROAS is calculated as" + formula + "where …"). Check this in the output.
6. NFKC-normalize text (ligatures); 2 `U+FFFD` chars on p.9 are a known loss.

## Tomorrow, in order

1. Decide embedding model (sets tokenizer + `vector(N)` + `max_tokens`).
2. Write `db/init/02_schema.sql` for the tables above. Recreate the volume (`docker compose down -v && up -d`) since init scripts run only on first start.
3. `ingestion/structure.py`: JSON → documents / sections / elements (+ offsets). Verify the section tree prints correctly.
4. `ingestion/chunk.py`: HybridChunker → chunks + chunk_elements. Inspect 10 chunks by hand: equations, tables, headings.
5. `ingestion/embed.py`: embeddings + HNSW index. Run 5 test queries ("What is delayed adstock?", "How is mROAS defined?").
