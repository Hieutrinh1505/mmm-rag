---- DOCUMENTS: one row per source paper ----
CREATE TABLE documents (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name           TEXT NOT NULL UNIQUE,                 -- = doc.name / chunk "document" field
    title          TEXT NOT NULL,
    authors        TEXT[] NOT NULL DEFAULT '{}',
    year           INTEGER,
    source_path    TEXT NOT NULL,                        -- data/pdfs/...
    sha256         TEXT NOT NULL UNIQUE,                 -- skip re-ingesting the same PDF
    parser         TEXT NOT NULL DEFAULT 'docling',
    parser_version TEXT NOT NULL,                        -- e.g. '2.140.0'
    parsed_at      TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

---- CHUNKS: retrieval units from chunk.py ----
CREATE TABLE chunks (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id         BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ord                 INTEGER NOT NULL,                -- chunk order within the paper
    heading_path        TEXT[] NOT NULL DEFAULT '{}',    -- ["2 Model Specification", "2.1 Carryover Effect"]
    text                TEXT NOT NULL,
    contextualized_text TEXT NOT NULL,                   -- what gets embedded
    element_refs        TEXT[] NOT NULL DEFAULT '{}',    -- docling self_refs, e.g. '#/texts/12'
    element_types       TEXT[] NOT NULL DEFAULT '{}',    -- e.g. {formula, text}
    page_start          INTEGER NOT NULL,
    page_end            INTEGER NOT NULL,
    token_count         INTEGER NOT NULL,
    chunking_strategy   TEXT NOT NULL,                   -- e.g. 'hybrid-512'
    chunker_version     TEXT,                            -- docling version that chunked it
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunking_strategy, ord)         -- re-running chunk load can't duplicate
);

-- Keyword search alongside vectors
CREATE INDEX chunks_fts_idx ON chunks USING gin (to_tsvector('english', contextualized_text));

---- EMBEDDINGS: one vector per (chunk, model) ----
CREATE TABLE embeddings (
    chunk_id        BIGINT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    embedding_model TEXT NOT NULL,                       -- e.g. 'BAAI/bge-small-en-v1.5'
    embedding       vector(384) NOT NULL,                -- 384 = bge-small-en-v1.5 dimension
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (chunk_id, embedding_model)
);

-- Approximate nearest-neighbor search with cosine distance (<=>)
CREATE INDEX embeddings_hnsw_idx ON embeddings USING hnsw (embedding vector_cosine_ops);
