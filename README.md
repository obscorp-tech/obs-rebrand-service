# rebrand-service

Batch rebranding engine for `.docx` and `.pptx` files. Per-client brand configs versioned in Git. Exposes a FastAPI service and CLI for idempotent batch processing.

## Architecture

```
configs/clients/         # Per-client brand YAML (versioned in Git)
templates/logos/         # Client logos (Git LFS recommended)
templates/docx/          # Master DOCX templates
templates/pptx/          # Master PPTX templates
src/rebrand_service/     # Core library
  models.py              # Pydantic brand config schema
  docx_rebrander.py      # DOCX rebranding logic
  pptx_rebrander.py      # PPTX rebranding logic
  batch.py               # Batch processor
  api.py                 # FastAPI service
  cli.py                 # CLI entrypoint
.github/workflows/       # CI/CD pipelines
```

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Rebrand a single file
rebrand single --client acme-corp --input docs/report.docx --output out/

# Batch rebrand a directory
rebrand batch --client acme-corp --input-dir docs/ --output-dir out/

# Run API server
uvicorn rebrand_service.api:app --host 0.0.0.0 --port 8000
```

## Adding a New Client

1. Copy `configs/clients/_template.yaml` to `configs/clients/<client-slug>.yaml`
2. Fill in brand values (colors, fonts, logo path)
3. Add logo to `templates/logos/<client-slug>/`
4. Commit and push — CI validates the config

## Compliance

All rebranding operations are idempotent and logged with SHA-256 checksums of input/output for SOC/SOX audit trails.

## Development

```bash
pytest tests/ -v
ruff check src/ tests/
ruff format src/ tests/
```
