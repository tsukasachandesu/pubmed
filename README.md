# PubMed CLI

PubMed CLI is a project template for searching PubMed, storing metadata, and downloading PDFs.
It follows a clean/hexagonal architecture with async-first adapters and a Typer-based CLI.

The stack is designed around lossless storage: raw Entrez responses are stored alongside parsed
paper metadata, download attempts are recorded with HTTP headers and status codes, and PDF
artifacts are persisted atomically under a configurable data directory.

## Getting started

1. Install dependencies (preferably via `uv`):
   ```bash
   uv sync
   uv run pubmed --help
   ```
   or with pip:
   ```bash
   pip install -e .[dev]
   pubmed --help
   ```

   The `[tool.uv]` section of `pyproject.toml` declares the test/lint toolchain as
   development dependencies, so `uv sync` also prepares the local environment for
   running checks:
   ```bash
   uv run pytest
   uv run ruff check
   uv run mypy
   ```

2. Configure environment variables (see `src/pubmed/config/settings.py` for supported keys).
   At minimum, set your contact email for NCBI:
   ```bash
   export PUBMED_EMAIL="you@example.com"
   ```
   A starter `.env.example` is included; copy it to `.env` and adjust values as needed.

## Project layout

- `src/pubmed/config/` — settings, logging, and observability bootstrapping.
- `src/pubmed/presentation/cli/` — Typer application and command groups (`search`, `download`, `config`, `doctor`).
- `src/pubmed/usecases/` — placeholders for application use cases.
- `src/pubmed/adapters/` — HTTP/Botasaurus adapter placeholders.
- `src/pubmed/domain/` — domain entities will live here.
- `tests/` — Pytest-based test suite with a basic CLI smoke test.

### Data directories

- `data/papers/` — default base directory for PDFs and the SQLite database
  (`pubmed.sqlite`).
- `data/papers/pdfs/<pmid>.pdf` — persisted downloads (or placeholders when a PDF
  could not be fetched).
- `data/papers/exports/` — location for future export artifacts.

## CLI preview

The CLI is already wired with placeholder commands so you can iterate quickly:

```bash
pubmed search "cancer genomics" --retmax 50 --save-db
pubmed download --sources pmc,unpaywall --max-workers 4
pubmed config show
pubmed doctor
```

These commands currently echo input parameters and will be implemented in later milestones.

### Configuration flags

- `PUBMED_ENABLE_SCIHUB` toggles whether Sci-Hub downloads are allowed. The CLI also exposes
  `pubmed config set-scihub --enable/--disable` to manage this flag in your `.env` file.
- Botasaurus-specific options can be configured via environment variables (`BOTASAURUS_PROFILE`,
  `BOTASAURUS_MAX_BROWSERS`, `BOTASAURUS_PROXY`) or the `pubmed config set-botasaurus` command.
- Observability can be enabled per-run with `--enable-tracing` / `--enable-metrics` flags.

### Download sources

The download workflow will enqueue pending records for the following sources:

- **PMC** — direct HTTP download.
- **Unpaywall** — uses Unpaywall metadata to resolve an open-access URL.
- **Sci-Hub** — optional, gated by the Sci-Hub opt-in flag.

All download attempts record raw HTTP metadata (`raw_http_headers`, `raw_http_meta`) and a
timestamp on the `downloads` table while persisting PDFs atomically to disk.
