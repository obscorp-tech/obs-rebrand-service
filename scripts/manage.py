#!/usr/bin/env python3
"""
Rebrand Service — deployment and management script.

Usage:
    ./scripts/manage.py install    # New install: check/install all dependencies
    ./scripts/manage.py update     # Idempotent update: pull, rebuild, preserve data
    ./scripts/manage.py clean      # Clean slate: wipe config/data, fresh install
    ./scripts/manage.py status     # Show service status
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_URL = os.environ.get("REBRAND_REPO_URL", "git@github.com:obscorp/rebrand-service.git")
INSTALL_DIR = Path(os.environ.get("REBRAND_INSTALL_DIR", "/opt/rebrand-service"))
BACKUP_DIR = Path("/var/backups/deploy/rebrand-service")
LOG_DIR = Path("/var/log/deploy")
LOG_FILE = LOG_DIR / "deploy.log"
MARKER = "# --- MANAGED BY rebrand-service deploy ---"

# ---------------------------------------------------------------------------
# Logging — stdout + file
# ---------------------------------------------------------------------------


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("deploy")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    fh = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


log = setup_logging()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(cmd: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a command, log it, optionally capture output."""
    log.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
    )
    if capture and result.stdout:
        log.debug("stdout: %s", result.stdout.strip())
    return result


def is_installed(cmd: str) -> bool:
    """Check if a command is available on PATH."""
    return shutil.which(cmd) is not None


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def backup_path(name: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR / f"{name}_{timestamp()}"


def file_hash(path: Path) -> str:
    """SHA-256 of a file."""
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def backup_file(path: Path) -> Path | None:
    """Backup a file with timestamp. Returns backup path or None."""
    if not path.exists():
        return None
    dest = backup_path(path.name)
    shutil.copy2(path, dest)
    log.info("Backed up %s -> %s", path, dest)
    return dest

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------

REQUIRED_CMDS = ["python3", "pip", "git", "docker", "docker-compose"]


def check_dependencies() -> list[str]:
    """Return list of missing required commands."""
    missing = [cmd for cmd in REQUIRED_CMDS if not is_installed(cmd)]
    return missing


def install_dependencies() -> None:
    """Install missing system dependencies via apt."""
    missing = check_dependencies()
    if not missing:
        log.info("All dependencies present: %s", ", ".join(REQUIRED_CMDS))
        return

    log.info("Missing dependencies: %s", ", ".join(missing))

    # Only install what's missing
    apt_packages: list[str] = []
    if "docker" in missing or "docker-compose" in missing:
        apt_packages.extend(["docker.io", "docker-compose"])
    if "git" in missing:
        apt_packages.append("git")

    if apt_packages:
        log.info("Installing: %s", ", ".join(apt_packages))
        run(["sudo", "apt-get", "update", "-qq"])
        run(["sudo", "apt-get", "install", "-y", "-qq", *apt_packages])

    # Verify
    still_missing = check_dependencies()
    if still_missing:
        log.error("Failed to install: %s", ", ".join(still_missing))
        sys.exit(1)

    log.info("All dependencies installed successfully")

# ---------------------------------------------------------------------------
# Git operations
# ---------------------------------------------------------------------------


def clone_or_pull() -> None:
    """Clone repo if not present, pull if it exists. Idempotent."""
    if INSTALL_DIR.exists() and (INSTALL_DIR / ".git").exists():
        log.info("Repo exists at %s — pulling latest", INSTALL_DIR)
        run(["git", "-C", str(INSTALL_DIR), "fetch", "--all"])
        run(["git", "-C", str(INSTALL_DIR), "pull", "--ff-only"])
    elif INSTALL_DIR.exists():
        log.warning("%s exists but is not a git repo", INSTALL_DIR)
        sys.exit(1)
    else:
        log.info("Cloning %s -> %s", REPO_URL, INSTALL_DIR)
        INSTALL_DIR.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", REPO_URL, str(INSTALL_DIR)])


def setup_git_ssh_key() -> None:
    """Ensure SSH key exists for GitHub. Prefer keys over passwords."""
    ssh_dir = Path.home() / ".ssh"
    key_path = ssh_dir / "id_ed25519"

    if key_path.exists():
        log.info("SSH key exists: %s", key_path)
        return

    log.info("Generating SSH key for GitHub")
    ssh_dir.mkdir(mode=0o700, exist_ok=True)
    run([
        "ssh-keygen",
        "-t", "ed25519",
        "-C", f"rebrand-deploy@{os.uname().nodename}",
        "-f", str(key_path),
        "-N", "",  # No passphrase (key-based, not password)
    ])
    key_path.chmod(0o600)

    pub = key_path.with_suffix(".pub").read_text().strip()
    log.info("Public key (add to GitHub deploy keys):\n%s", pub)
    log.info(
        "Add this key at: https://github.com/obscorp/rebrand-service/settings/keys"
    )

# ---------------------------------------------------------------------------
# Docker operations
# ---------------------------------------------------------------------------


def docker_build() -> None:
    """Build Docker image. Idempotent — uses layer cache."""
    log.info("Building Docker image")
    run(["docker-compose", "-f", str(INSTALL_DIR / "docker-compose.yaml"), "build"])


def docker_up() -> None:
    """Start services. Idempotent — recreates only if config changed."""
    log.info("Starting services")
    run([
        "docker-compose",
        "-f", str(INSTALL_DIR / "docker-compose.yaml"),
        "up", "-d", "--remove-orphans",
    ])


def docker_down() -> None:
    """Stop services gracefully."""
    log.info("Stopping services")
    compose_file = INSTALL_DIR / "docker-compose.yaml"
    if compose_file.exists():
        run(["docker-compose", "-f", str(compose_file), "down"], check=False)


def docker_status() -> None:
    """Show running containers."""
    compose_file = INSTALL_DIR / "docker-compose.yaml"
    if compose_file.exists():
        run(["docker-compose", "-f", str(compose_file), "ps"])
    else:
        log.warning("docker-compose.yaml not found at %s", compose_file)

# ---------------------------------------------------------------------------
# Config backup/restore
# ---------------------------------------------------------------------------


def backup_configs() -> Path | None:
    """Backup configs and persistent data before destructive operations."""
    configs_dir = INSTALL_DIR / "configs"
    if not configs_dir.exists():
        return None

    dest = backup_path("configs")
    shutil.copytree(configs_dir, dest)
    log.info("Configs backed up to %s", dest)
    return dest


def backup_docker_volumes() -> None:
    """Backup named Docker volumes."""
    result = run(
        ["docker", "volume", "ls", "--format", "{{.Name}}"],
        capture=True,
        check=False,
    )
    if result.returncode != 0:
        return

    for vol_name in result.stdout.strip().splitlines():
        if "rebrand" in vol_name:
            dest = backup_path(f"volume_{vol_name}")
            dest.mkdir(parents=True, exist_ok=True)
            run([
                "docker", "run", "--rm",
                "-v", f"{vol_name}:/source:ro",
                "-v", f"{dest}:/backup",
                "alpine",
                "cp", "-a", "/source/.", "/backup/",
            ], check=False)
            log.info("Volume %s backed up to %s", vol_name, dest)

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_install() -> None:
    """New install: check/install deps, clone, build, deploy."""
    log.info("=== NEW INSTALL ===")
    install_dependencies()
    setup_git_ssh_key()
    clone_or_pull()

    # Install Python package in dev mode
    run(["pip", "install", "-e", f"{INSTALL_DIR}[dev]", "--break-system-packages"])

    docker_build()
    docker_up()

    # Validate configs
    run(["rebrand", "validate", "--configs-dir", str(INSTALL_DIR / "configs" / "clients")], check=False)

    log.info("=== INSTALL COMPLETE ===")
    docker_status()


def cmd_update() -> None:
    """Idempotent update: pull, rebuild, preserve data."""
    log.info("=== UPDATE ===")

    # Pre-flight
    missing = check_dependencies()
    if missing:
        log.error("Missing deps: %s — run 'install' first", ", ".join(missing))
        sys.exit(1)

    if not (INSTALL_DIR / ".git").exists():
        log.error("Not installed at %s — run 'install' first", INSTALL_DIR)
        sys.exit(1)

    # Backup before update
    backup_configs()
    backup_docker_volumes()

    # Pull latest
    clone_or_pull()

    # Rebuild and restart (preserves volumes)
    run(["pip", "install", "-e", f"{INSTALL_DIR}[dev]", "--break-system-packages"])
    docker_build()
    docker_up()

    # Validate
    run(["rebrand", "validate", "--configs-dir", str(INSTALL_DIR / "configs" / "clients")], check=False)

    log.info("=== UPDATE COMPLETE ===")
    docker_status()


def cmd_clean() -> None:
    """Clean slate: backup everything, wipe, fresh install."""
    log.info("=== CLEAN SLATE ===")

    # Backup everything first
    backup_configs()
    backup_docker_volumes()

    # Stop and remove containers
    docker_down()

    # Remove Docker volumes
    result = run(
        ["docker", "volume", "ls", "--format", "{{.Name}}"],
        capture=True,
        check=False,
    )
    if result.returncode == 0:
        for vol_name in result.stdout.strip().splitlines():
            if "rebrand" in vol_name:
                run(["docker", "volume", "rm", vol_name], check=False)
                log.info("Removed volume: %s", vol_name)

    # Remove install directory
    if INSTALL_DIR.exists():
        shutil.rmtree(INSTALL_DIR)
        log.info("Removed %s", INSTALL_DIR)

    # Fresh install
    cmd_install()

    log.info("=== CLEAN SLATE COMPLETE ===")
    log.info("Backups preserved at: %s", BACKUP_DIR)


def cmd_status() -> None:
    """Show current status."""
    log.info("=== STATUS ===")

    # Git status
    if (INSTALL_DIR / ".git").exists():
        result = run(
            ["git", "-C", str(INSTALL_DIR), "log", "--oneline", "-1"],
            capture=True,
            check=False,
        )
        if result.returncode == 0:
            log.info("Git HEAD: %s", result.stdout.strip())
    else:
        log.warning("Not installed at %s", INSTALL_DIR)

    # Docker status
    docker_status()

    # Backups
    if BACKUP_DIR.exists():
        backups = sorted(BACKUP_DIR.iterdir())
        log.info("Backups: %d in %s", len(backups), BACKUP_DIR)
        for b in backups[-5:]:
            log.info("  %s", b.name)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

COMMANDS = {
    "install": cmd_install,
    "update": cmd_update,
    "clean": cmd_clean,
    "status": cmd_status,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: {sys.argv[0]} {{{','.join(COMMANDS.keys())}}}")
        print()
        print("Commands:")
        print("  install  — New install: check/install deps, clone, build, deploy")
        print("  update   — Idempotent update: pull, rebuild, preserve data")
        print("  clean    — Clean slate: backup all, wipe, fresh install")
        print("  status   — Show service status")
        sys.exit(1)

    cmd = sys.argv[1]
    COMMANDS[cmd]()


if __name__ == "__main__":
    main()
