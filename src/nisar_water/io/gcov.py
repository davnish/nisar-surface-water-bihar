"""Read NISAR L2 GCOV backscatter terms into a georeferenced xarray Dataset.

GCOV diagonal terms (HHHH, HVHV, ...) are RTC-normalised gamma0 in linear power.
Off-diagonal terms (HHHV, ...) are complex and are read only on request. Low-level
HDF5 access uses the vendored nisar_utils functions.

A source is a local .h5 path or an ASF HTTPS URL. URLs are streamed with
earthaccess (Earthdata creds in ~/.netrc), so only the HDF5 chunks covering the
requested window are transferred. Bbox windows are cached once as NetCDF in
data/interim (`fetch_window`) and experiments read that cache (`load_window`).
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

import h5py
import numpy as np
import xarray as xr
from pyproj import Transformer
from rasterio.transform import from_origin

from nisar_water._npt import gcov, product, spatial

# GCOV `mask` layer (per the product's own attribute description, checked in L00): 1..n = valid
# sample from sub-swath n; 0 = partially focused / invalid; 255 = outside the acquisition extent.
MASK_INVALID_VALUES = (0, 255)


def profile(path: str | Path) -> dict:
    """Filename + HDF5 product profile (frequencies, covariance terms, EPSG, spacing). Local files only."""
    return product.identify_nisar_product(str(path)).to_dict()


@lru_cache(maxsize=1)
def _https_fs():
    import earthaccess

    earthaccess.login(strategy="netrc")
    return earthaccess.get_fsspec_https_session()


@contextmanager
def open_source(source: str | Path, block_size_mb: int = 8):
    """h5py.File for a local path or an HTTPS URL (streamed, block-cached)."""
    if str(source).startswith("http"):
        with _https_fs().open(str(source), mode="rb", block_size=block_size_mb * 2**20,
                              cache_type="blockcache") as fobj, h5py.File(fobj, "r") as f:
            yield f
    else:
        with h5py.File(source, "r") as f:
            yield f


def grid_path(f: h5py.File, frequency: str = "frequencyA") -> str:
    for family in ("LSAR", "SSAR"):
        gp = f"/science/{family}/GCOV/grids/{frequency}"
        if gp in f:
            return gp
    raise KeyError(f"No GCOV grid for {frequency} in {f.filename}")


def bbox_to_window(x: np.ndarray, y: np.ndarray, epsg: int, bbox_wsen: list[float]) -> tuple[int, int, int, int]:
    """Row/col window (r0, r1, c0, c1) covering a lon/lat bbox in the grid's projected CRS."""
    t = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    w, s, e, n = bbox_wsen
    xs, ys = t.transform([w, e, e, w], [s, s, n, n])
    return spatial.coordinate_to_index(x, y, min(xs), max(xs), min(ys), max(ys))


def read_gcov(source: str | Path, frequency: str = "frequencyA", terms: list[str] | None = None,
              bbox_wsen: list[float] | None = None, aux: bool = True) -> xr.Dataset:
    """Read `terms` (default: all diagonal terms) on the bbox window, or the full grid if bbox is None.

    Invalid pixels (mask in MASK_INVALID_VALUES, or non-finite) are NaN in every term.
    The returned Dataset carries x/y coords, `epsg`, `transform` and source metadata in attrs.
    """
    name = Path(str(source)).name
    with open_source(source) as f:
        gp = grid_path(f, frequency)
        x, y = gcov.get_grid_coordinates(f, gp)
        epsg = int(f[f"{gp}/projection"].attrs["epsg_code"])
        available = [n for n in f[gp] if len(n) == 4 and n.isupper()]
        terms = terms or [t for t in available if t[:2] == t[2:]]
        missing = [t for t in terms if t not in available]
        if missing:
            raise KeyError(f"{missing} not in {name}/{frequency}; available: {available}")

        r0, r1, c0, c1 = (0, len(y), 0, len(x)) if bbox_wsen is None else bbox_to_window(x, y, epsg, bbox_wsen)
        if r1 <= r0 or c1 <= c0:
            raise ValueError(f"bbox does not overlap {name}")
        mask = f[f"{gp}/mask"][r0:r1, c0:c1]
        invalid = np.isin(mask, MASK_INVALID_VALUES)

        data = {}
        for t in terms:
            arr = gcov.read_window(f, f"{gp}/{t}", r0, r1, c0, c1)
            arr = arr.astype(np.complex64) if np.iscomplexobj(arr) else arr.astype(np.float32)
            arr[invalid | ~np.isfinite(arr)] = np.nan
            data[t] = (("y", "x"), arr)
        data["mask"] = (("y", "x"), mask)
        if aux and f"{gp}/rtcGammaToSigmaFactor" in f:
            data["rtcGammaToSigmaFactor"] = (("y", "x"), gcov.read_window(
                f, f"{gp}/rtcGammaToSigmaFactor", r0, r1, c0, c1).astype(np.float32))

    xs, ys = x[c0:c1], y[r0:r1]
    dx, dy = float(xs[1] - xs[0]), float(ys[0] - ys[1])
    ds = xr.Dataset(data, coords={"x": xs, "y": ys})
    ds.attrs.update({
        "source": name,
        "frequency": frequency,
        "available_terms": ",".join(available),
        "epsg": epsg,
        "spacing_m": (abs(dx), abs(dy)),
        # coordinates are pixel centres
        "transform": tuple(from_origin(xs[0] - dx / 2, ys[0] + dy / 2, abs(dx), abs(dy)))[:6],
        "window_rows_cols": (r0, r1, c0, c1),
    })
    return ds


PROCESSING_FLAGS = ("isFullCovariance", "noiseCorrectionApplied", "radiometricTerrainCorrectionApplied",
                    "shadowMaskingApplied", "faradayRotationApplied", "polarimetricSymmetrizationApplied",
                    "postProcessingFilteringApplied", "rfiMitigationApplied")


def _scalar(v):
    v = v[()]
    if isinstance(v, bytes):
        return v.decode()
    return v.tolist() if hasattr(v, "tolist") else v


def metadata_profile(source: str | Path) -> list[dict]:
    """Per-frequency metadata (terms, posting, shape, processing flags) without reading any raster."""
    rows = []
    with open_source(source) as f:
        family = "LSAR" if "/science/LSAR" in f else "SSAR"
        pm = f"/science/{family}/GCOV/metadata/processingInformation/parameters"
        flags = {k: _scalar(f[f"{pm}/{k}"]) for k in PROCESSING_FLAGS if f"{pm}/{k}" in f}
        for freq in sorted(f[f"/science/{family}/GCOV/grids"]):
            gp = grid_path(f, freq)
            terms = [t.decode() if isinstance(t, bytes) else t for t in f[f"{gp}/listOfCovarianceTerms"][()]]
            rows.append({"frequency": freq, "terms": ",".join(terms),
                         "posting_m": _scalar(f[f"{gp}/xCoordinateSpacing"]),
                         "shape": "x".join(map(str, f[f"{gp}/{terms[0]}"].shape)),
                         "epsg": int(f[f"{gp}/projection"].attrs["epsg_code"]), **flags})
    return rows


def window_path(interim_dir: Path, granule: str, frequency: str, extent: str = "bbox") -> Path:
    return interim_dir / f"{granule.removesuffix('.h5')}_{frequency}_{extent}.nc"


def fetch_window(source: str | Path, out: Path, frequency: str = "frequencyA", terms: list[str] | None = None,
                 bbox_wsen: list[float] | None = None, aux: bool = True) -> Path:
    """Read a window (streamed if `source` is a URL) and cache it as NetCDF. Skips if `out` exists."""
    if out.exists():
        return out
    ds = read_gcov(source, frequency, terms, bbox_wsen, aux=aux)
    out.parent.mkdir(parents=True, exist_ok=True)
    complex_terms = any(np.iscomplexobj(ds[v].values) for v in ds.data_vars)
    # complex off-diagonal terms are valid HDF5 but not valid netCDF4
    ds.to_netcdf(out, engine="h5netcdf", invalid_netcdf=complex_terms,
                 encoding={v: {"zlib": True, "complevel": 4} for v in ds.data_vars})
    return out


def load_window(path: Path) -> xr.Dataset:
    ds = xr.load_dataset(path, engine="h5netcdf")
    ds.attrs["spacing_m"] = tuple(np.atleast_1d(ds.attrs["spacing_m"]).tolist())
    ds.attrs["transform"] = tuple(np.atleast_1d(ds.attrs["transform"]).tolist())
    return ds
