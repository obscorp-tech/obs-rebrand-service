"""Batch rebranding processor with audit trail."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from rebrand_service.docx_rebrander import DocxRebrander
from rebrand_service.models import BrandConfig
from rebrand_service.pptx_rebrander import PptxRebrander

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".docx", ".pptx"}


class BatchProcessor:
    """Process multiple files for a single client brand."""

    def __init__(
        self,
        brand: BrandConfig,
        repo_root: Path | None = None,
    ) -> None:
        self.brand = brand
        self.repo_root = repo_root or Path.cwd()
        self.docx_rebrander = DocxRebrander(brand, repo_root=self.repo_root)
        self.pptx_rebrander = PptxRebrander(brand, repo_root=self.repo_root)

    def process_file(self, input_path: Path, output_dir: Path) -> dict[str, str]:
        """Rebrand a single file based on extension."""
        output_path = output_dir / input_path.name
        ext = input_path.suffix.lower()

        if ext == ".docx":
            return self.docx_rebrander.rebrand(input_path, output_path)
        elif ext == ".pptx":
            return self.pptx_rebrander.rebrand(input_path, output_path)
        else:
            logger.warning("Unsupported file type: %s", input_path.name)
            return {
                "input_file": str(input_path),
                "client": self.brand.client_slug,
                "status": "skipped",
                "reason": f"Unsupported extension: {ext}",
            }

    def process_directory(
        self,
        input_dir: Path,
        output_dir: Path,
        recursive: bool = False,
    ) -> list[dict[str, str]]:
        """
        Rebrand all supported files in a directory.

        Returns list of audit records for each file processed.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        if recursive:
            files = [
                f
                for f in input_dir.rglob("*")
                if f.suffix.lower() in SUPPORTED_EXTENSIONS and not f.name.startswith("~")
            ]
        else:
            files = [
                f
                for f in input_dir.iterdir()
                if f.suffix.lower() in SUPPORTED_EXTENSIONS and not f.name.startswith("~")
            ]

        if not files:
            logger.warning("No supported files found in %s", input_dir)
            return []

        logger.info(
            "Processing %d files for client '%s'",
            len(files),
            self.brand.client_name,
        )

        results: list[dict[str, str]] = []
        for file_path in sorted(files):
            # Preserve subdirectory structure for recursive mode
            if recursive:
                relative = file_path.relative_to(input_dir)
                file_output_dir = output_dir / relative.parent
            else:
                file_output_dir = output_dir

            result = self.process_file(file_path, file_output_dir)
            results.append(result)

        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = sum(1 for r in results if r["status"] == "error")
        skip_count = sum(1 for r in results if r["status"] == "skipped")

        logger.info(
            "Batch complete: %d success, %d errors, %d skipped",
            success_count,
            error_count,
            skip_count,
        )

        return results


def write_audit_log(
    results: list[dict[str, str]],
    output_dir: Path,
    client_slug: str,
) -> Path:
    """Write batch results to a JSON audit log."""
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    log_path = output_dir / f"audit_{client_slug}_{timestamp}.json"

    audit_record = {
        "timestamp": timestamp,
        "client": client_slug,
        "total_files": len(results),
        "success": sum(1 for r in results if r["status"] == "success"),
        "errors": sum(1 for r in results if r["status"] == "error"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "files": results,
    }

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(audit_record, indent=2), encoding="utf-8")
    logger.info("Audit log written: %s", log_path)
    return log_path
