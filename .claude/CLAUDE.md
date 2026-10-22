# mmm-rag

RAG system over Media Mix Modeling (MMM) research papers. Source PDFs are parsed with docling, chunked, and indexed so questions about MMM methods can be answered with citations back to the paper/page.

## Layout
- `data/pdfs/` — source papers (e.g. Jin, Wang, Sun, Chan, Koehler 2017, "Bayesian Methods for Media Mix Modeling with Carryover and Shape Effects", Google).
- `api/app/` — application code. `api/app/ingestion/parse.py` is the PDF → structured-document step (docling).
- `pyproject.toml`, `uv.lock`, `.python-version`, `.venv/` — at the repo root (one uv project for the whole repo).

## Environment
- Python 3.12 via uv. Always run from the repo root: `uv run python ...` (or `source .venv/bin/activate`).
- Dependencies are pinned exactly in `pyproject.toml` (e.g. `docling==2.140.0`) and locked in `uv.lock`. Add/upgrade with `uv add pkg==X.Y.Z`; never `pip install` into the venv.
- Commit `pyproject.toml`, `uv.lock`, `.python-version` together. `.venv/` is gitignored.
- If the project moves directories, delete `.venv` and `uv sync` — the activate script hardcodes its absolute path.

## Database
- `docker compose up -d` → Postgres 17 + pgvector 0.8.0 (`pgvector/pgvector:0.8.0-pg17`) on host port **5433** (5432 is taken by another local project). Default creds `mmm`/`mmm`, db `mmm_rag`; override via `.env`. `db/init/*.sql` runs only on first start with an empty volume.

## Git
- Never add a `Co-Authored-By: Claude` (or any Claude/AI attribution) line to commit messages or PR descriptions. Commits are authored solely by the user.
- Commit messages: short imperative subject + body listing what changed and why.

## Conventions
- The user wants suggestions before code on design questions; don't implement until asked.
- Papers are born-digital LaTeX PDFs: prefer no OCR; equations, tables, and section structure matter more than images.
- Keep page numbers / section headings with every chunk so answers can cite sources.
