# Ingestion

Turns MMM papers in `data/pdfs/` into structured, citable chunks for the RAG index.

```
PDF → DocumentConverter → DoclingDocument (JSON) → HybridChunker → chunks (+ section, page)
```

All import paths below are checked against `docling==2.140.0`.

## 1. Conversion — `docling`

| Import | Why it matters |
|---|---|
| `docling.document_converter.DocumentConverter`, `PdfFormatOption` | Entry point. `converter.convert(path).document` returns a `DoclingDocument`. |
| `docling.datamodel.base_models.InputFormat` | Key for `format_options={InputFormat.PDF: PdfFormatOption(...)}`. |
| `docling.datamodel.pipeline_options.PdfPipelineOptions` | The settings that decide extraction quality (see below). |
| `docling.datamodel.pipeline_options.TableFormerMode` | `ACCURATE` vs `FAST` table recognition. |

`PdfPipelineOptions` fields to set (defaults in parentheses):

- `do_formula_enrichment = True` (False) — equations as LaTeX (adstock, Hill function, priors). **Most important for this paper.**
- `do_ocr = False` (True) — papers are born-digital; OCR is slower and adds noise.
- `do_table_structure = True`, `table_structure_options.mode = TableFormerMode.ACCURATE` (already default) — results tables.
- `generate_picture_images` (False) — leave off; figures are R plots, keep captions only.

## 2. Document model — `docling_core.types.doc`

| Import | Why it matters |
|---|---|
| `DoclingDocument` | The parsed paper. Save with `save_as_json` / reload with `load_from_json` so you don't re-run conversion. Export with `export_to_markdown()` to inspect. |
| `DocItemLabel` | Filter items by type: `SECTION_HEADER`, `TEXT`, `FORMULA`, `TABLE`, `CAPTION`, `PAGE_HEADER`/`PAGE_FOOTER` (drop), `REFERENCE` (bibliography — drop or index separately). |
| `TextItem`, `TableItem`, `PictureItem` | Item classes; each has `.prov` (page number + bbox) for citations. `TableItem.export_to_markdown()` keeps a table as one unit. |

Iterate with `doc.iterate_items()` to walk content in reading order.

## 3. Chunking — `docling.chunking` / `docling_core.transforms.chunker`

| Import | Why it matters |
|---|---|
| `docling.chunking.HybridChunker` | Splits along the heading hierarchy, then by token limit. Each chunk's `meta` carries `headings` and `doc_items` (→ pages). |
| `docling_core.transforms.chunker.tokenizer.huggingface.HuggingFaceTokenizer` | Make the chunker count tokens with **the same tokenizer as your embedding model**, and set `max_tokens` to its limit. |
| `chunker.contextualize(chunk)` | Prepends section headings to the chunk text — embed this, not the raw text. |

## 4. Cleanup — standard library

- `unicodedata.normalize("NFKC", text)` — fixes ligatures (`Eﬀects` → `Effects`) so keyword search works.

## Suggested first check

Convert pages 1–10 of the Jin et al. (2017) paper (`page_range` on `convert`) and read the markdown: confirm the adstock and Hill equations come out as clean LaTeX before building chunking.
