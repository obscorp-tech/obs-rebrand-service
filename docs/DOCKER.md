# Docker Guide

## Quick Start

```bash
docker-compose up -d
# API at http://localhost:8000
# Health check at http://localhost:8000/health
```

## Configuration

Environment variables (set in `.env` or shell):

| Variable | Default | Description |
|----------|---------|-------------|
| `REBRAND_PORT` | `8000` | Host port for API |
| `LOG_LEVEL` | `info` | Logging verbosity |

## Volumes

| Volume | Mount | Purpose |
|--------|-------|---------|
| `configs/` | `/app/configs` (read-only) | Client brand YAML configs |
| `templates/` | `/app/templates` (read-only) | Logos and master templates |
| `rebrand-output` | `/app/output` | Batch output (persisted across restarts) |

## Operations

### Build

```bash
docker-compose build
```

### Start/Restart

```bash
docker-compose up -d           # Start
docker-compose restart         # Restart
```

### Stop

```bash
docker-compose down            # Stop containers (preserves volumes)
docker-compose down -v         # Stop + remove volumes (DATA LOSS)
```

### Logs

```bash
docker-compose logs -f         # Follow all logs
docker-compose logs rebrand-api --tail 100  # Last 100 lines
```

### Update (Idempotent)

```bash
git pull
docker-compose build
docker-compose up -d --remove-orphans
```

This preserves all data in named volumes. Only the container image is rebuilt.

### Clean Slate

**Warning**: This removes all output data. Configs are preserved in Git.

```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

Or use the management script (backs up volumes first):

```bash
sudo python3 scripts/manage.py clean
```

## Health Checks

The container runs a health check every 30s hitting `/health`. View status:

```bash
docker inspect --format='{{.State.Health.Status}}' rebrand-api
```

## Resource Limits

Default limits (adjustable in `docker-compose.yaml`):
- Memory: 512MB
- CPU: 1.0 core
- Log rotation: 10MB × 5 files

## Security

- Container runs as non-root user (`rebrand`, UID 1000)
- Config and template mounts are read-only
- No secrets stored in image or environment
- API does not persist uploaded files (temp directory only)
