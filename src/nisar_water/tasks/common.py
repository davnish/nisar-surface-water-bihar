"""Helpers shared by experiment tasks: scene loading, dates, references and the train/test split."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import xarray as xr

from nisar_water import REPO_ROOT
from nisar_water.config import load_aoi, load_paths
from nisar_water.grid import load_grid
from nisar_water.io.gcov import load_window, read_gcov, window_path
from nisar_water.io.raster import read
from nisar_water.validate.sampling import TEST, TRAIN


def acq_date(granule: str) -> str:
    """UTC start date from a NISAR filename: NISAR_L2_PR_GCOV_..._<YYYYmmddTHHMMSS>_<end>_..."""
    stamp = next(tok for tok in Path(granule).name.split("_") if len(tok) == 15 and tok[8] == "T")
    return datetime.strptime(stamp, "%Y%m%dT%H%M%S").strftime("%Y-%m-%d")


def load_scene(cfg, granule: str, ctx=None) -> xr.Dataset:
    """Cached window from `nisar-water fetch` if present, else the local raw granule.

    For the bbox extent, the window must sit exactly on the canonical grid (configs/grid_bbox.yaml),
    so every layer (references, split, other dates) aligns pixel for pixel.
    """
    d = cfg.data
    path = window_path(load_paths()["interim"] / f"nisar_{d.band}", granule, d.frequency, d.extent)
    if path.exists():
        ds = load_window(path)[d.terms]
    else:
        path = load_paths()[f"raw_nisar_{d.band}"] / (granule if granule.endswith(".h5") else f"{granule}.h5")
        ds = read_gcov(path, d.frequency, d.terms, load_aoi()["bbox_wsen"] if d.extent == "bbox" else None)
    if ctx is not None:
        ctx.inputs.append(path)
    if d.extent == "bbox":
        g = load_grid("bbox")
        same = (tuple(ds.sizes[k] for k in ("y", "x")) == g.shape
                and np.allclose(ds.attrs["transform"][:6], g.transform[:6]))
        k = round(ds.attrs["transform"][0] / g.transform[0])
        t = ds.attrs["transform"]
        co, ro = (t[2] - g.transform[2]) / g.transform[0], (t[5] - g.transform[5]) / g.transform[4]
        on_lattice = np.isclose(co, round(co)) and np.isclose(ro, round(ro))
        coarse = (not same and k >= 1 and np.isclose(t[0], g.transform[0] * k) and np.isclose(t[4], g.transform[4] * k))
        if coarse and not on_lattice:
            # same posting family but a sub-pixel offset (e.g. a different frame grid): nearest placement,
            # shift <= half a 10 m pixel, recorded in the attributes
            ds.attrs["regrid_shift_m"] = (float((round(co) - co) * g.transform[0]), float((round(ro) - ro) * g.transform[0]))
        if coarse:
            # exact k x k aggregate of the canonical grid, possibly shifted by whole 10 m pixels (QP 20 m windows
            # start 10 m east of the bbox grid): features are computed at the native posting and replicated
            # onto the 10 m grid by `to_canonical` (no interpolation)
            ds.attrs["upsample"] = (k, int(round(ro)), int(round(co)))
        elif not same:
            raise ValueError(f"{granule} window is not on the canonical bbox grid "
                             f"({ds.attrs['transform']}, {dict(ds.sizes)}); resampling not implemented yet")
    ds.attrs["date"] = acq_date(granule)
    return ds


def apply_split(ref: np.ndarray, split: str) -> np.ndarray:
    """Restrict reference pixels to the train or test blocks from R00 (others become nodata 255)."""
    if split == "all":
        return ref
    blocks, _ = read(load_paths()["reference"] / "split_blocks.tif")
    keep = TEST if split == "test" else TRAIN
    return np.where(blocks == keep, ref, 255).astype(np.uint8)


def load_reference(pattern: str, date: str, split: str = "all") -> np.ndarray | None:
    """Reference raster for `date` (pattern like 'data/reference/s2_water_{date}.tif'), split applied; None if absent."""
    p = REPO_ROOT / pattern.format(date=date)
    if not p.exists():
        return None
    ref, _ = read(p)
    return apply_split(ref, split)


def to_canonical(feats: dict[str, np.ndarray], attrs: dict) -> tuple[dict[str, np.ndarray], dict]:
    """Replicate features of a k x k coarser aligned window onto the canonical bbox grid (nearest, exact)."""
    if "upsample" not in attrs:
        return feats, attrs
    k, ro, co = attrs["upsample"]
    g = load_grid("bbox")
    ir = (np.arange(g.shape[0]) - ro) // k
    ic = (np.arange(g.shape[1]) - co) // k
    out = {}
    for n, v in feats.items():
        okr, okc = (ir >= 0) & (ir < v.shape[0]), (ic >= 0) & (ic < v.shape[1])
        a = np.full(g.shape, np.nan, np.float32)
        a[np.ix_(okr, okc)] = v[np.ix_(ir[okr], ic[okc])]
        out[n] = a
    attrs = {**attrs, "transform": tuple(g.transform[:6]), "spacing_m": (g.transform[0], -g.transform[4]),
             "native_spacing_m": attrs["spacing_m"]}
    return out, attrs
