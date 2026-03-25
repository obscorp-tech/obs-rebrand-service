"""CLI for document rebranding."""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from rebrand_service.batch import BatchProcessor, write_audit_log
from rebrand_service.models import load_all_configs, load_brand_config

app = typer.Typer(
    name="rebrand",
    help="Batch document rebranding CLI for MSP multi-client environments.",
    no_args_is_help=True,
)
console = Console()

DEFAULT_CONFIGS_DIR = Path("configs/clients")

STATUS_ICONS = {
    "success": "[green]✓[/green]",
    "error": "[red]✗[/red]",
    "skipped": "[yellow]⊘[/yellow]",
}


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _resolve_config(client: str, configs_dir: Path) -> Path:
    config_path = configs_dir / f"{client}.yaml"
    if not config_path.exists():
        console.print(f"[red]Client config not found: {config_path}[/red]")
        raise typer.Exit(code=1)
    return config_path


@app.command()
def single(
    client: str = typer.Option(..., "--client", "-c", help="Client slug"),
    input_file: Path = typer.Option(..., "--input", "-i", help="Input DOCX/PPTX file"),
    output_dir: Path = typer.Option(..., "--output", "-o", help="Output directory"),
    configs_dir: Path = typer.Option(DEFAULT_CONFIGS_DIR, "--configs-dir"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Rebrand a single DOCX or PPTX file."""
    _setup_logging(verbose)

    if not input_file.exists():
        console.print(f"[red]Input file not found: {input_file}[/red]")
        raise typer.Exit(code=1)

    config_path = _resolve_config(client, configs_dir)
    brand = load_brand_config(config_path)
    processor = BatchProcessor(brand, repo_root=Path.cwd())
    result = processor.process_file(input_file, output_dir)

    if result["status"] == "success":
        console.print(f"[green]✓[/green] {result['output_file']}")
        console.print(f"  SHA-256: {result['output_sha256'][:16]}…")
    else:
        console.print(f"[red]✗ {result.get('error', 'Unknown error')}[/red]")
        raise typer.Exit(code=1)


@app.command()
def batch(
    client: str = typer.Option(..., "--client", "-c", help="Client slug"),
    input_dir: Path = typer.Option(..., "--input-dir", "-i", help="Input directory"),
    output_dir: Path = typer.Option(..., "--output-dir", "-o", help="Output directory"),
    recursive: bool = typer.Option(False, "--recursive", "-r"),
    configs_dir: Path = typer.Option(DEFAULT_CONFIGS_DIR, "--configs-dir"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Rebrand all DOCX/PPTX files in a directory."""
    _setup_logging(verbose)

    if not input_dir.exists():
        console.print(f"[red]Input directory not found: {input_dir}[/red]")
        raise typer.Exit(code=1)

    config_path = _resolve_config(client, configs_dir)
    brand = load_brand_config(config_path)
    processor = BatchProcessor(brand, repo_root=Path.cwd())
    results = processor.process_directory(input_dir, output_dir, recursive=recursive)
    audit_path = write_audit_log(results, output_dir, client)

    table = Table(title=f"Rebrand Results — {brand.client_name}")
    table.add_column("File", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("SHA-256 (output)", style="dim")

    for r in results:
        file_name = Path(r["input_file"]).name
        sha = r.get("output_sha256", "—")[:16]
        table.add_row(file_name, STATUS_ICONS.get(r["status"], "?"), sha)

    console.print(table)
    console.print(f"\nAudit log: {audit_path}")


@app.command()
def validate(
    configs_dir: Path = typer.Option(DEFAULT_CONFIGS_DIR, "--configs-dir"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Validate all client brand configs."""
    _setup_logging(verbose)
    configs = load_all_configs(configs_dir)

    if not configs:
        console.print("[yellow]No configs found.[/yellow]")
        raise typer.Exit(code=1)

    table = Table(title="Client Brand Configs")
    table.add_column("Slug", style="cyan")
    table.add_column("Name")
    table.add_column("Primary Color")
    table.add_column("Compliance", style="dim")

    for slug, cfg in sorted(configs.items()):
        frameworks = ", ".join(cfg.compliance.frameworks) if cfg.compliance.frameworks else "—"
        table.add_row(slug, cfg.client_name, f"#{cfg.colors.primary}", frameworks)

    console.print(table)
    console.print(f"\n[green]✓ {len(configs)} configs validated[/green]")


@app.command()
def clients(
    configs_dir: Path = typer.Option(DEFAULT_CONFIGS_DIR, "--configs-dir"),
) -> None:
    """List all configured clients."""
    _setup_logging(verbose=False)
    configs = load_all_configs(configs_dir)
    for slug in sorted(configs):
        console.print(f"  {slug}: {configs[slug].client_name}")


if __name__ == "__main__":
    app()
