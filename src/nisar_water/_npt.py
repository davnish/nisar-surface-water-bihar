"""Shim for the vendored nisar-polarimetric-training toolkit (Apache-2.0).

The upstream repo is not pip-installable (flat layout, no package config), so it is
pinned as a git submodule under third_party/ and put on sys.path here. Import its
modules through this shim, e.g. ``from nisar_water._npt import product``.

Only the pure functions are used. Its session/config helpers write into the
submodule's own config/ folder and are deliberately avoided.
"""
import sys

from nisar_water import REPO_ROOT

NPT_ROOT = REPO_ROOT / "third_party" / "nisar-polarimetric-training"
NPT_COMMIT = "f2c96ff9d9d427711ae56dd756aba2051c37f4ec"

if not (NPT_ROOT / "nisar_utils").is_dir():
    raise ImportError(
        f"nisar_utils not found at {NPT_ROOT}. Run: git submodule update --init --recursive"
    )
if str(NPT_ROOT) not in sys.path:
    sys.path.insert(0, str(NPT_ROOT))

from nisar_utils import gcov, polarimetry, product, spatial  # noqa: E402

__all__ = ["gcov", "polarimetry", "product", "spatial", "NPT_COMMIT"]
