"""Tests for brand config models."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from rebrand_service.models import (
    BrandConfig,
    ColorPalette,
    Typography,
    compute_file_hash,
    load_all_configs,
    load_brand_config,
)


@pytest.fixture
def valid_config_dict() -> dict:
    return {
        "client_name": "Test Corp",
        "client_slug": "test-corp",
        "colors": {
            "primary": "#2E75B6",
            "secondary": "4A90D9",
            "accent": "F5A623",
        },
        "typography": {
            "heading_font": "Georgia",
            "body_font": "Calibri",
            "heading_size_pt": 14,
            "body_size_pt": 11,
        },
    }


@pytest.fixture
def config_file(valid_config_dict: dict, tmp_path: Path) -> Path:
    config_path = tmp_path / "test-corp.yaml"
    config_path.write_text(yaml.dump(valid_config_dict), encoding="utf-8")
    return config_path


class TestColorPalette:
    def test_strip_hash_prefix(self) -> None:
        palette = ColorPalette(primary="#2E75B6", secondary="4A90D9", accent="F5A623")
        assert palette.primary == "2E75B6"

    def test_uppercase_normalization(self) -> None:
        palette = ColorPalette(primary="2e75b6", secondary="4a90d9", accent="f5a623")
        assert palette.primary == "2E75B6"

    def test_invalid_hex_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            ColorPalette(primary="ZZZZZZ", secondary="4A90D9", accent="F5A623")

    def test_wrong_length_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex color"):
            ColorPalette(primary="2E7", secondary="4A90D9", accent="F5A623")


class TestTypography:
    def test_defaults(self) -> None:
        typo = Typography()
        assert typo.heading_font == "Calibri"
        assert typo.body_size_pt == 11

    def test_size_bounds(self) -> None:
        with pytest.raises(ValueError):
            Typography(heading_size_pt=200)

    def test_line_spacing_bounds(self) -> None:
        with pytest.raises(ValueError):
            Typography(line_spacing=0.5)


class TestBrandConfig:
    def test_valid_config(self, valid_config_dict: dict) -> None:
        config = BrandConfig(**valid_config_dict)
        assert config.client_name == "Test Corp"
        assert config.client_slug == "test-corp"
        assert config.colors.primary == "2E75B6"

    def test_invalid_slug_raises(self, valid_config_dict: dict) -> None:
        valid_config_dict["client_slug"] = "invalid slug!"
        with pytest.raises(ValueError, match="alphanumeric"):
            BrandConfig(**valid_config_dict)

    def test_default_compliance(self, valid_config_dict: dict) -> None:
        config = BrandConfig(**valid_config_dict)
        assert config.compliance.frameworks == []
        assert config.compliance.require_watermark is False


class TestLoadConfig:
    def test_load_from_yaml(self, config_file: Path) -> None:
        config = load_brand_config(config_file)
        assert config.client_slug == "test-corp"

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises((FileNotFoundError, OSError)):
            load_brand_config(tmp_path / "nonexistent.yaml")

    def test_load_all_configs(self, config_file: Path) -> None:
        configs = load_all_configs(config_file.parent)
        assert "test-corp" in configs

    def test_load_all_skips_templates(self, config_file: Path) -> None:
        template_path = config_file.parent / "_template.yaml"
        template_path.write_text(
            yaml.dump(
                {
                    "client_name": "Template",
                    "client_slug": "template",
                    "colors": {"primary": "000000", "secondary": "111111", "accent": "222222"},
                }
            ),
            encoding="utf-8",
        )
        configs = load_all_configs(config_file.parent)
        assert "template" not in configs


class TestFileHash:
    def test_deterministic_hash(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world", encoding="utf-8")
        hash1 = compute_file_hash(test_file)
        hash2 = compute_file_hash(test_file)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("content a", encoding="utf-8")
        file_b.write_text("content b", encoding="utf-8")
        assert compute_file_hash(file_a) != compute_file_hash(file_b)
