"""FastAPI service for document rebranding."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from rebrand_service.batch import BatchProcessor, write_audit_log
from rebrand_service.models import load_all_configs, load_brand_config

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Rebrand Service",
    description="Batch document rebranding API for MSP multi-client environments",
    version="0.1.0",
)

# Config directory — override with REBRAND_CONFIG_DIR env var
CONFIGS_DIR = Path(__file__).resolve().parent.parent.parent / "configs" / "clients"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class HealthResponse(BaseModel):
    status: str
    clients_loaded: int


class ClientListResponse(BaseModel):
    clients: list[str]


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Service health check with config validation."""
    try:
        configs = load_all_configs(CONFIGS_DIR)
        return HealthResponse(status="healthy", clients_loaded=len(configs))
    except Exception as e:
        logger.exception("Health check failed: %s", e)
        return HealthResponse(status="degraded", clients_loaded=0)


@app.get("/clients", response_model=ClientListResponse)
async def list_clients() -> ClientListResponse:
    """List all configured client slugs."""
    configs = load_all_configs(CONFIGS_DIR)
    return ClientListResponse(clients=sorted(configs.keys()))


@app.post("/rebrand/{client_slug}")
async def rebrand_file(
    client_slug: str,
    file: Annotated[UploadFile, File(description="DOCX or PPTX file to rebrand")],
) -> FileResponse:
    """Rebrand a single uploaded file for the specified client."""
    # Validate client
    config_path = CONFIGS_DIR / f"{client_slug}.yaml"
    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"Client '{client_slug}' not found")

    # Validate file type
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Filename required")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".docx", ".pptx"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Use .docx or .pptx",
        )

    try:
        brand = load_brand_config(config_path)
        processor = BatchProcessor(brand, repo_root=REPO_ROOT)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            input_path = tmp_path / file.filename
            output_dir = tmp_path / "output"
            output_dir.mkdir()

            # Save uploaded file
            content = await file.read()
            input_path.write_bytes(content)

            # Process
            result = processor.process_file(input_path, output_dir)

            if result["status"] == "error":
                raise HTTPException(
                    status_code=500,
                    detail=f"Rebranding failed: {result.get('error', 'Unknown error')}",
                )

            output_path = output_dir / file.filename
            if not output_path.exists():
                raise HTTPException(status_code=500, detail="Output file not generated")

            # Return the rebranded file
            media_type = (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if suffix == ".docx"
                else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )

            return FileResponse(
                path=str(output_path),
                filename=f"rebranded_{file.filename}",
                media_type=media_type,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Rebrand failed for %s/%s: %s", client_slug, file.filename, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/rebrand/{client_slug}/batch")
async def rebrand_batch(
    client_slug: str,
    files: Annotated[
        list[UploadFile],
        File(description="Multiple DOCX/PPTX files to rebrand"),
    ],
) -> JSONResponse:
    """Rebrand multiple files for the specified client. Returns audit log."""
    config_path = CONFIGS_DIR / f"{client_slug}.yaml"
    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"Client '{client_slug}' not found")

    try:
        brand = load_brand_config(config_path)
        processor = BatchProcessor(brand, repo_root=REPO_ROOT)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            input_dir = tmp_path / "input"
            output_dir = tmp_path / "output"
            input_dir.mkdir()
            output_dir.mkdir()

            # Save all uploaded files
            for f in files:
                if f.filename:
                    file_path = input_dir / f.filename
                    content = await f.read()
                    file_path.write_bytes(content)

            # Batch process
            results = processor.process_directory(input_dir, output_dir)
            audit_path = write_audit_log(results, output_dir, client_slug)
            audit_data = audit_path.read_text(encoding="utf-8")

            return JSONResponse(
                content={
                    "message": f"Processed {len(results)} files",
                    "audit": __import__("json").loads(audit_data),
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Batch rebrand failed for %s: %s", client_slug, e)
        raise HTTPException(status_code=500, detail=str(e)) from e
