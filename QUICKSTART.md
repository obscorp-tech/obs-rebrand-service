# Quick Start Guide

## Prerequisites

- Ubuntu 22.04+ LTS
- Python 3.12+ with `python3-venv` (`sudo apt install python3-venv`)
- Docker & Docker Compose
- Git with SSH key configured

## 1. Clone and Install

```bash
git clone git@github.com:obscorp/rebrand-service.git
cd rebrand-service
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Or use the management script (handles everything including venv):

```bash
sudo python3 scripts/manage.py install
```

## 2. Configure a Client

```bash
cp configs/clients/_template.yaml configs/clients/my-client.yaml
```

Edit `my-client.yaml` with the client's brand colors, fonts, logo path, and compliance requirements.

## 3. Add Logo

```bash
mkdir -p templates/logos/my-client/
cp /path/to/logo.png templates/logos/my-client/logo.png
```

## 4. Rebrand Files

### CLI — Single File

```bash
rebrand single \
  --client my-client \
  --input docs/report.docx \
  --output out/
```

### CLI — Batch Directory

```bash
rebrand batch \
  --client my-client \
  --input-dir docs/ \
  --output-dir out/ \
  --recursive
```

### API

```bash
# Start server
uvicorn rebrand_service.api:app --host 0.0.0.0 --port 8000

# Upload and rebrand
curl -X POST http://localhost:8000/rebrand/my-client \
  -F "file=@report.docx" \
  -o rebranded_report.docx
```

## 5. Docker

```bash
docker-compose up -d
# API available at http://localhost:8000
# Health check: http://localhost:8000/health
```

## 6. Validate All Configs

```bash
rebrand validate
```

## Management Commands

```bash
sudo python3 scripts/manage.py install   # Fresh install
sudo python3 scripts/manage.py update    # Pull + rebuild (preserves data)
sudo python3 scripts/manage.py clean     # Wipe + reinstall (backups preserved)
sudo python3 scripts/manage.py status    # Show service status
```
