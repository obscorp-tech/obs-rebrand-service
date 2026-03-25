# Architecture

## Overview

The Rebrand Service is a Python-based document rebranding engine designed for MSPs managing 50+ clients with varying brand guidelines and compliance requirements.

## Components

### Core Library (`src/rebrand_service/`)

| Module | Responsibility |
|--------|---------------|
| `models.py` | Pydantic schemas for brand config, validation, file hashing |
| `docx_rebrander.py` | DOCX rebranding — fonts, colors, logos, compliance footers |
| `pptx_rebrander.py` | PPTX rebranding — fonts, colors, logos, compliance footers |
| `batch.py` | Batch processor with audit trail generation |
| `api.py` | FastAPI HTTP service for single/batch rebranding |
| `cli.py` | Typer CLI for local usage and CI/CD |

### Configuration (`configs/clients/`)

Each client has a YAML file defining their complete brand: colors, typography, logo placement, and compliance metadata. Configs are validated by Pydantic on load — invalid configs fail fast.

### Templates (`templates/`)

Master DOCX/PPTX templates and logos, organized by client slug. Logos should use Git LFS for binary file management.

### CI/CD (`.github/workflows/`)

- **ci.yaml** — Lint, test, validate configs on every push/PR
- **rebrand.yaml** — Auto-rebrand queued files when configs or templates change

## Data Flow

```
Input Files (docx/pptx)
    │
    ▼
BatchProcessor
    ├── DocxRebrander (fonts, colors, logo, footer)
    └── PptxRebrander (fonts, colors, logo, footer)
    │
    ▼
Output Files + Audit Log (JSON with SHA-256 hashes)
```

## Idempotency

Every operation checks state before acting:
- Logo insertion checks if a picture already exists on the slide/header
- Compliance footers check for existing matching text
- Font/color application overwrites consistently (same input → same output)
- Running rebrand twice on the same file produces functionally equivalent output

## Audit Trail

Each batch run generates a JSON audit log containing:
- Timestamp (UTC)
- Client slug
- Per-file input/output SHA-256 hashes
- Success/error/skipped status
- Error details when applicable

Audit logs are stored as GitHub Actions artifacts with 90-day retention.

## Security

- No cleartext passwords — SSH keys for GitHub auth
- Docker runs as non-root (`rebrand` user, UID 1000)
- Config files contain no secrets (colors, fonts, paths only)
- API does not persist uploaded files (temp directory, cleaned on request completion)
- File hashes provide tamper detection for compliance audits
