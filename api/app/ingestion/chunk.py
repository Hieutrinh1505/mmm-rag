import re
import unicodedata
from pathlib import Path
import json

from docling.chunking import HybridChunker
from docling_core.transforms.chunker.hierarchical_chunker import DocChunk
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.types.doc import DocItemLabel, DoclingDocument

EMBED_MODEL: str = "BAAI/bge-small-en-v1.5"
CHUNKING_STRATEGY: str = "hybrid-512"
tokenizer: HuggingFaceTokenizer = HuggingFaceTokenizer.from_pretrained(EMBED_MODEL, max_tokens=512)
chunker: HybridChunker = HybridChunker(tokenizer=tokenizer, merge_peers=True, repeat_table_header=True)

SECTION_NUM: re.Pattern = re.compile(r"^(\d+(?:\.\d+)*)\s")  # "2.1 Carryover Effect" -> "2.1"
SUBFIGURE: re.Pattern = re.compile(r"^\([a-z]\)\s")  # "(a) Retention rate α": figure panel, not a section
SKIP_SECTIONS: set[str] = {"References", "Acknowledgment"}


def read_from_json(file_path: str) -> DoclingDocument:
    """Load a DoclingDocument saved by parse.py."""
    return DoclingDocument.load_from_json(file_path)


def build_heading_paths(doc: DoclingDocument) -> dict[str, list[str]]:
    """Map each section header to its full path, e.g. "2.1 ..." -> ["2 ...", "2.1 ..."].

    docling marks every header as level 1, so depth is rebuilt from the section number.
    """
    paths: dict[str, list[str]] = {}
    stack: list[tuple[int, str]] = []  # (depth, title) from top level down to current header
    for item, _ in doc.iterate_items():
        if item.label != DocItemLabel.SECTION_HEADER:
            continue
        title: str = item.text
        if SUBFIGURE.match(title):
            paths[title] = [t for _, t in stack]  # inherit the enclosing real section
            continue
        m: re.Match | None = SECTION_NUM.match(title)
        depth: int = m.group(1).count(".") + 1 if m else 1
        if title == "STAN Sampler Codes":  # unnumbered child of "Appendix" in Jin et al. 2017
            depth = 2
        stack = [(d, t) for d, t in stack if d < depth] + [(depth, title)]
        paths[title] = [t for _, t in stack]
    return paths


def should_skip(heading_path: list[str]) -> bool:
    """True for chunks under sections not worth embedding (references, acknowledgments)."""
    return bool(heading_path) and heading_path[0] in SKIP_SECTIONS


def to_record(chunk: DocChunk, heading_paths: dict[str, list[str]], doc_name: str) -> dict:
    """Flatten one docling chunk into a JSON-serializable row for the chunks table."""
    heading: str | None = chunk.meta.headings[0] if chunk.meta.headings else None
    contextualized: str = unicodedata.normalize("NFKC", chunker.contextualize(chunk))
    pages: list[int] = [item.prov[0].page_no for item in chunk.meta.doc_items]
    return {
        "document": doc_name,
        "heading_path": heading_paths.get(heading, [heading] if heading else []),
        "text": unicodedata.normalize("NFKC", chunk.text),
        "contextualized_text": contextualized,
        "element_refs": [item.self_ref for item in chunk.meta.doc_items],
        "element_types": sorted({item.label.value for item in chunk.meta.doc_items}),
        "page_start": min(pages),
        "page_end": max(pages),
        "token_count": tokenizer.count_tokens(contextualized),
        "embedding_model": EMBED_MODEL,
        "chunking_strategy": CHUNKING_STRATEGY,
    }


def process_chunk(file_path: str) -> list[dict]:
    """Chunk one parsed paper; returns records with references/acknowledgments removed."""
    doc: DoclingDocument = read_from_json(file_path)
    heading_paths: dict[str, list[str]] = build_heading_paths(doc)
    records: list[dict] = []
    for chunk in chunker.chunk(doc):
        record: dict = to_record(chunk, heading_paths, doc.name)
        if not should_skip(record["heading_path"]):
            records.append(record)
    return records

def save_chunk_to_json(records: list[dict], out_path: str) -> None:
    """Write all chunk records for one paper to a single JSON file"""
    path: Path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Successfully wrote {len(records)} chunks to {out_path}")
    


if __name__ == "__main__":
    records: list[dict] = process_chunk(
        "data/parsed/Jin_Wang_Sun_Chan_Koehler_2017_Bayesian_Methods_for_MMM.json"
    )
    print(f"{len(records)} chunks")
    for r in records[:3]:
        print(r["page_start"], " > ".join(r["heading_path"]), "|", r["text"][:80])
    save_chunk_to_json(
        records,
        "data/chunks/Jin_Wang_Sun_Chan_Koehler_2017_Bayesian_Methods_for_MMM.json",
    )
