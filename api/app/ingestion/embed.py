import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

CONN_STRING: str = "postgresql://mmm:mmm@localhost:5433/mmm_rag"
DOCLING_VERSION: str = version("docling")
EMBED_MODEL: str = "BAAI/bge-small-en-v1.5"  # must match chunk.py (tokenizer) and vector(384) in the schema
BATCH_SIZE: int = 32  # texts per forward pass; affects speed/memory only, not the vectors
MODEL: SentenceTransformer = SentenceTransformer(EMBED_MODEL)

# Paper metadata not available in the chunk files; keyed by file stem (= doc.name).
PAPERS: dict[str, dict] = {
    "Jin_Wang_Sun_Chan_Koehler_2017_Bayesian_Methods_for_MMM": {
        "title": "Bayesian Methods for Media Mix Modeling with Carryover and Shape Effects",
        "authors": ["Yuxue Jin", "Yueqing Wang", "Yunting Sun", "David Chan", "Jim Koehler"],
        "year": 2017,
    },
}


def get_sha256(file_path: Path) -> str:
    """Hash file contents in 1 MB blocks."""
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# INSERT docs
def insert_doc(conn: psycopg.Connection, pdf_path: Path) -> int:
    """Insert the paper once (keyed by content hash); return its documents.id either way."""
    name: str = pdf_path.stem
    meta: dict = PAPERS[name]
    sha: str = get_sha256(pdf_path)
    row: tuple | None = conn.execute(
        """
        INSERT INTO documents (name, title, authors, year, source_path, sha256, parser_version)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sha256) DO NOTHING
        RETURNING id
        """,
        (name, meta["title"], meta["authors"], meta["year"], str(pdf_path), sha, DOCLING_VERSION),
    ).fetchone()
    if row is None:  # already inserted → look up the existing id
        row = conn.execute("SELECT id FROM documents WHERE sha256 = %s", (sha,)).fetchone()
    return row[0]

def load_chunks(chunk_path: Path) -> list[dict]:
    """Read the chunk records saved by chunk.py."""
    return json.loads(chunk_path.read_text(encoding="utf-8"))


# INSERT chunks
def insert_chunks(conn: psycopg.Connection, document_id: int, records: list[dict]) -> int:
    """Replace this paper's chunks for the records' strategy; return number inserted.

    Delete-then-insert keeps the table identical to the file on re-runs;
    old embeddings are removed by ON DELETE CASCADE.
    """
    strategy: str = records[0]["chunking_strategy"]
    conn.execute(
        "DELETE FROM chunks WHERE document_id = %s AND chunking_strategy = %s",
        (document_id, strategy),
    )
    for ord_, record in enumerate(records):
        conn.execute(
            """
            INSERT INTO chunks (document_id, ord, heading_path, text, contextualized_text,
                                element_refs, element_types, page_start, page_end,
                                token_count, chunking_strategy, chunker_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                document_id, ord_, record["heading_path"], record["text"],
                record["contextualized_text"], record["element_refs"], record["element_types"],
                record["page_start"], record["page_end"], record["token_count"],
                record["chunking_strategy"], DOCLING_VERSION,
            ),
        )
    return len(records)

# Embed chunks
def embed_chunks(conn: psycopg.Connection) -> int:
    """Embed every chunk that has no vector for EMBED_MODEL yet; return number embedded.

    Safe to re-run: already-embedded chunks are skipped, so a crash can just be resumed.
    """
    register_vector(conn)  # lets psycopg send numpy arrays as pgvector `vector`
    rows: list[tuple] = conn.execute(
        """
        SELECT c.id, c.contextualized_text
        FROM chunks c
        LEFT JOIN embeddings e ON e.chunk_id = c.id AND e.embedding_model = %s
        WHERE e.chunk_id IS NULL
        ORDER BY c.id
        """,
        (EMBED_MODEL,),
    ).fetchall()
    if not rows:
        return 0

    ids: list[int] = [r[0] for r in rows]
    texts: list[str] = [r[1] for r in rows]
    vectors = MODEL.encode(texts, batch_size=BATCH_SIZE, normalize_embeddings=True)  # (n, 384)

    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO embeddings (chunk_id, embedding_model, embedding) VALUES (%s, %s, %s)",
            [(cid, EMBED_MODEL, vec) for cid, vec in zip(ids, vectors)],
        )
    return len(ids)


if __name__ == "__main__":
    pdf: Path = Path("data/pdfs/Jin_Wang_Sun_Chan_Koehler_2017_Bayesian_Methods_for_MMM.pdf")
    chunk_file: Path = Path("data/chunks") / f"{pdf.stem}.json"
    records: list[dict] = load_chunks(chunk_file)
    with psycopg.connect(CONN_STRING) as conn:  # one transaction: doc + chunks commit together
        document_id: int = insert_doc(conn, pdf)
        n: int = insert_chunks(conn, document_id, records)
    print(f"document_id = {document_id}, chunks inserted = {n}")

    with psycopg.connect(CONN_STRING) as conn:  # separate transaction: chunks stay saved if embedding fails
        embedded: int = embed_chunks(conn)
    print(f"chunks embedded = {embedded}")
