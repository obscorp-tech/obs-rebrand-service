"""Brand configuration schema with Pydantic validation."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


class ColorPalette(BaseModel):
    """Hex color values without '#' prefix."""

    primary: str = Field(description="Primary brand color (hex, no #)")
    secondary: str = Field(description="Secondary brand color (hex, no #)")
    accent: str = Field(description="Accent color for highlights (hex, no #)")
    heading_text: str = Field(default="000000", description="Heading text color")
    body_text: str = Field(default="333333", description="Body text color")
    background: str = Field(default="FFFFFF", description="Background color")

    @field_validator("*", mode="before")
    @classmethod
    def strip_hash(cls, v: str) -> str:
        if isinstance(v, str):
            return v.lstrip("#").upper()
        return v

    @field_validator("*")
    @classmethod
    def validate_hex(cls, v: str) -> str:
        if not all(c in "0123456789ABCDEF" for c in v) or len(v) != 6:
            raise ValueError(f"Invalid hex color: {v}")
        return v


class Typography(BaseModel):
    """Font configuration for documents."""

    heading_font: str = Field(default="Calibri", description="Font for headings")
    body_font: str = Field(default="Calibri", description="Font for body text")
    heading_size_pt: int = Field(default=14, ge=8, le=72)
    body_size_pt: int = Field(default=11, ge=8, le=36)
    line_spacing: float = Field(default=1.15, ge=1.0, le=3.0)


class LogoConfig(BaseModel):
    """Logo placement configuration."""

    path: Path = Field(description="Relative path to logo file from repo root")
    width_inches: float = Field(default=1.5, ge=0.25, le=4.0)
    position: Annotated[str, Field(pattern=r"^(header|footer|title-slide)$")] = "header"

    @field_validator("path")
    @classmethod
    def validate_logo_exists(cls, v: Path) -> Path:
        # Validation deferred to runtime — path is relative to repo root
        return v


class ComplianceConfig(BaseModel):
    """Compliance-related metadata injected into documents."""

    frameworks: list[str] = Field(default_factory=list, description="e.g. SOC2, HIPAA, SOX")
    confidentiality_label: str = Field(default="", description="e.g. CONFIDENTIAL, INTERNAL")
    footer_text: str = Field(default="", description="Required footer text for compliance")
    require_watermark: bool = Field(default=False)


class BrandConfig(BaseModel):
    """Complete brand configuration for a single client."""

    client_name: str = Field(description="Display name of the client")
    client_slug: str = Field(description="URL-safe identifier, matches filename")
    colors: ColorPalette
    typography: Typography = Field(default_factory=Typography)
    logo: LogoConfig | None = None
    compliance: ComplianceConfig = Field(default_factory=ComplianceConfig)
    pptx_template: Path | None = Field(default=None, description="Path to master PPTX template")
    docx_template: Path | None = Field(default=None, description="Path to master DOCX template")

    @model_validator(mode="after")
    def slug_matches_conventions(self) -> BrandConfig:
        if not self.client_slug.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                f"client_slug must be alphanumeric with hyphens/underscores: {self.client_slug}"
            )
        return self


def load_brand_config(config_path: Path) -> BrandConfig:
    """Load and validate a brand config from YAML."""
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config = BrandConfig(**raw)
        logger.info(
            "Loaded brand config for '%s' from %s",
            config.client_name,
            config_path,
        )
        return config
    except yaml.YAMLError as e:
        logger.error("Failed to parse YAML %s: %s", config_path, e)
        raise
    except Exception as e:
        logger.error("Invalid brand config %s: %s", config_path, e)
        raise


def load_all_configs(configs_dir: Path) -> dict[str, BrandConfig]:
    """Load all client configs from a directory."""
    configs: dict[str, BrandConfig] = {}
    yaml_files = sorted(configs_dir.glob("*.yaml"))

    if not yaml_files:
        logger.warning("No client configs found in %s", configs_dir)
        return configs

    for yaml_path in yaml_files:
        if yaml_path.name.startswith("_"):
            continue  # Skip templates
        try:
            config = load_brand_config(yaml_path)
            configs[config.client_slug] = config
        except Exception as e:
            logger.error("Skipping invalid config %s: %s", yaml_path.name, e)

    logger.info("Loaded %d client brand configs", len(configs))
    return configs


def compute_file_hash(file_path: Path) -> str:
    """SHA-256 hash of a file for audit trail."""
    sha = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()
