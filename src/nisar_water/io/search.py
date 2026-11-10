"""NISAR L2 GCOV scene discovery (ASF) and download (earthaccess, Earthdata login via ~/.netrc)."""
from __future__ import annotations

from pathlib import Path

import asf_search as asf
import geopandas as gpd
import pandas as pd
from shapely.geometry import box, shape

from nisar_water._npt import product


def bbox_wkt(bbox_wsen: list[float]) -> str:
    return box(*bbox_wsen).wkt


def search_gcov(bbox_wsen: list[float], start: str | None = None, end: str | None = None,
                max_results: int = 2000) -> gpd.GeoDataFrame:
    """All GCOV granules intersecting the bbox, one row per granule with parsed filename fields."""
    results = asf.search(dataset=asf.DATASET.NISAR, processingLevel="GCOV",
                         intersectsWith=bbox_wkt(bbox_wsen), start=start, end=end,
                         maxResults=max_results)
    aoi = box(*bbox_wsen)
    rows = []
    for r in results:
        p = r.properties
        name = p["sceneName"]
        fields = product.parse_filename(name + ".h5")
        geom = shape(r.geometry)
        h5_name = f"{name}.h5"
        rows.append({
            "granule": name,
            "start_time": pd.Timestamp(p["startTime"]),
            "direction": p["flightDirection"],
            "track": int(p["pathNumber"]),
            "frame": int(p["frameNumber"]),
            "cycle": fields.get("cycle"),
            "processing_type": fields.get("processing_type"),  # PR production, UR urgent response
            "mode_code": fields.get("mode_code"),  # e.g. 4005 = 40 MHz (freq A) + 5 MHz (freq B)
            "polarization_code": fields.get("polarization_code"),  # e.g. DHDH, QPDH (A then B)
            "freqA_pols": "/".join(fields.get("primary_channels") or []),
            "freqB_pols": "/".join(fields.get("secondary_channels") or []),
            "pol_class": fields.get("polarization_class"),
            "crid": fields.get("crid"),
            "coverage": fields.get("coverage"),  # F full / P partial frame
            "size_gb": round(p.get("bytes", {}).get(h5_name, {}).get("bytes", 0) / 1e9, 2),
            "bbox_cover_frac": round(geom.intersection(aoi).area / aoi.area, 3),
            "url": p["url"],
            "geometry": geom,
        })
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    return gdf.sort_values(["track", "frame", "start_time"]).reset_index(drop=True)


def dedupe(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """One granule per (track, frame, acquisition, mode): prefer PR over UR, then the highest CRID."""
    g = gdf.copy()
    g["_pr"] = (g["processing_type"] == "PR").astype(int)
    g["_acq"] = g["start_time"].dt.floor("min")
    g = g.sort_values(["_pr", "crid"], ascending=False)
    g = g.drop_duplicates(["track", "frame", "_acq", "mode_code", "polarization_code"])
    return g.drop(columns=["_pr", "_acq"]).sort_values(["track", "frame", "start_time"]).reset_index(drop=True)


def download(urls: list[str], out_dir: Path, threads: int = 4) -> list[Path]:
    """Download granules with earthaccess (skips files already present). Needs Earthdata creds in ~/.netrc."""
    import earthaccess

    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [u for u in urls if not (out_dir / Path(u).name).exists()]
    if todo:
        earthaccess.login(strategy="netrc")
        earthaccess.download(todo, local_path=str(out_dir), threads=threads)
    return [out_dir / Path(u).name for u in urls]
