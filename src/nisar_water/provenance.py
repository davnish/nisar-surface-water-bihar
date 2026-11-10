"""Provenance stamped into every run: code version, environment and input files."""
from __future__ import annotations

import platform
import subprocess
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from nisar_water import REPO_ROOT

TRACKED_PACKAGES = ("numpy", "scipy", "h5py", "rasterio", "xarray", "scikit-learn", "scikit-image", "lightgbm")


def _git(*args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _pkg_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def collect(inputs: list[Path] | None = None) -> dict:
    from nisar_water._npt import NPT_COMMIT

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "nisar_polarimetric_training_commit": NPT_COMMIT,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {p: _pkg_version(p) for p in TRACKED_PACKAGES},
        # size + mtime instead of a checksum: GCOV granules are several GB each
        "inputs": [
            {"path": str(p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p),
             "bytes": p.stat().st_size, "mtime": p.stat().st_mtime}
            for p in (inputs or []) if p.exists()
        ],
    }
