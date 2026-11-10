"""L00 data inventory: catalogue search, de-duplication, per-track summary, timeline and footprint maps.

For granules already downloaded to data/raw/nisar_<band>, also records the HDF5-level
profile (frequencies, covariance terms present, EPSG, posting) and dumps the HDF5 tree.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from shapely.geometry import box

from nisar_water.config import load_aoi, load_paths
from nisar_water.io.search import dedupe, search_gcov

# reference palette (dataviz skill, validated light-mode): identity is also carried by marker/label
TRACK_COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # fixed order; >4 tracks must not cycle
POL_STYLE = {"dual-pol": ("#2a78d6", "o"), "quad-pol": ("#eb6834", "s"), "compact-pol": ("#1baf7a", "^")}
TEXT, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def run(ctx) -> None:
    aoi = load_aoi()
    bbox = aoi["bbox_wsen"]
    tables = ctx.run_dir / "tables"
    tables.mkdir(exist_ok=True)

    raw = search_gcov(bbox, start=ctx.cfg.extra.get("start"), end=ctx.cfg.extra.get("end"))
    if ctx.cfg.extra.get("min_bbox_cover", 0):
        raw = raw[raw["bbox_cover_frac"] >= ctx.cfg.extra["min_bbox_cover"]]
    inv = dedupe(raw)
    ctx.log.info("%d granules found, %d after de-duplication", len(raw), len(inv))

    raw.drop(columns="geometry").to_csv(tables / "inventory_raw.csv", index=False)
    inv.drop(columns="geometry").to_csv(tables / "inventory.csv", index=False)
    inv.to_file(tables / "footprints.geojson", driver="GeoJSON")

    inv["track_frame"] = inv["direction"].str[0] + " " + inv["track"].astype(str) + "/" + inv["frame"].astype(str)
    summary = (inv.groupby(["track_frame", "polarization_code", "mode_code"])
               .agg(n=("granule", "size"), first=("start_time", "min"), last=("start_time", "max"),
                    median_bbox_cover=("bbox_cover_frac", "median"), size_gb=("size_gb", "sum"))
               .reset_index())
    summary["first"] = summary["first"].dt.date
    summary["last"] = summary["last"].dt.date
    summary.to_csv(tables / "summary_by_track.csv", index=False)

    hdf = _hdf5_profiles(inv, load_paths()[f"raw_nisar_{ctx.cfg.data.band}"], tables, ctx)
    meta = _metadata_profiles(inv, ctx) if ctx.cfg.extra.get("profile_metadata") else None

    _timeline(inv, ctx.figures / "acquisition_timeline.png")
    _footprints(inv, bbox, ctx.figures / "footprints_vs_bbox.png")

    candidates = {f"{v['relative_orbit']}/{v['frame']}" for v in aoi["candidates"].values()}
    ctx.metrics.update({
        "headline": {"name": "granules (deduplicated)", "value": len(inv)},
        "n_granules_raw": len(raw),
        "n_granules_dedup": len(inv),
        "n_quad_pol": int((inv["pol_class"] == "quad-pol").sum()),
        "tracks_found": ", ".join(sorted(inv["track_frame"].unique())),
        "tracks_not_in_problem_statement": ", ".join(sorted(
            tf for tf in inv["track_frame"].unique() if tf.split(" ")[1] not in candidates)) or "none",
        "date_range": f"{inv['start_time'].min().date()} to {inv['start_time'].max().date()}",
        "n_downloaded": len(hdf),
        "tables": {"Granules by track / mode": summary.to_markdown(index=False)},
    })
    if hdf:
        ctx.metrics["tables"]["HDF5 profile (downloaded granules)"] = pd.DataFrame(hdf).to_markdown(index=False)
    if meta is not None:
        meta.to_csv(tables / "metadata_profile.csv", index=False)
        ctx.metrics["tables"]["Product metadata (one granule per track/frame/mode, streamed)"] = (
            meta.drop(columns=["granule"]).to_markdown(index=False))


def _metadata_profiles(inv: pd.DataFrame, ctx) -> pd.DataFrame:
    """Stream metadata (no rasters) of the latest granule per track/frame/mode/pol code."""
    from nisar_water.io.gcov import metadata_profile

    picks = inv.sort_values("start_time").groupby(["track_frame", "mode_code", "polarization_code"]).tail(1)
    rows = []
    for _, g in picks.iterrows():
        ctx.log.info("metadata: %s", g["granule"])
        for r in metadata_profile(g["url"]):
            rows.append({"track_frame": g["track_frame"], "pol_code": g["polarization_code"],
                         "date": g["start_time"].date(), "granule": g["granule"], **r})
    return pd.DataFrame(rows)


def _hdf5_profiles(inv: pd.DataFrame, raw_dir, tables, ctx) -> list[dict]:
    import h5py

    from nisar_water.io.gcov import profile

    rows = []
    for g in inv["granule"]:
        p = raw_dir / f"{g}.h5"
        if not p.exists():
            continue
        ctx.inputs.append(p)
        prof = profile(p)
        for freq in prof["frequencies"]:
            rows.append({"granule": g[:60] + "…", "frequency": freq,
                         "diagonal": ",".join(prof["diagonal_terms"].get(freq, [])),
                         "off_diagonal": ",".join(prof["off_diagonal_terms"].get(freq, [])) or "—",
                         "epsg": prof["epsg"], "x_spacing": prof["x_spacing"], "y_spacing": prof["y_spacing"]})
        with h5py.File(p, "r") as f:
            lines = []
            f.visititems(lambda n, o: lines.append(
                f"{n}  {o.shape} {o.dtype}" if isinstance(o, h5py.Dataset) else f"{n}/"))
        (tables / f"h5_tree_{g}.txt").write_text("\n".join(lines))
    return rows


def _style(ax) -> None:
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def _timeline(inv: pd.DataFrame, path) -> None:
    rows = sorted(inv["track_frame"].unique())
    fig, ax = plt.subplots(figsize=(10, 0.6 * len(rows) + 1.6))
    for pol, (colour, marker) in POL_STYLE.items():
        sub = inv[inv["pol_class"] == pol]
        if len(sub):
            ax.scatter(sub["start_time"], sub["track_frame"].map(rows.index), s=64, color=colour, marker=marker,
                       edgecolor="#fcfcfb", linewidth=1.5, label=f"{pol} (freq A)", zorder=3)
    ax.set_yticks(range(len(rows)), [f"{r}" for r in rows])
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlabel("Acquisition date (UTC)", color=MUTED, fontsize=9)
    ax.set_title("NISAR L2 GCOV acquisitions intersecting the reference bbox (by direction track/frame)",
                 color=TEXT, fontsize=10, loc="left")
    _style(ax)
    ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(0, -0.18), ncol=3)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _footprints(inv, bbox, path) -> None:
    fig, ax = plt.subplots(figsize=(7, 7))
    for i, (tf, sub) in enumerate(inv.groupby("track_frame")):
        if i >= len(TRACK_COLOURS):
            raise ValueError("more track/frames than categorical slots; facet the map instead")
        colour = TRACK_COLOURS[i]
        sub.boundary.plot(ax=ax, color=colour, linewidth=1, alpha=0.5)
        c = sub.geometry.iloc[0].centroid
        ax.annotate(tf, (c.x, c.y), color=TEXT, fontsize=8, ha="center",
                    bbox=dict(boxstyle="round,pad=0.2", fc="#fcfcfb", ec=colour, lw=1.5))
    ax.plot(*box(*bbox).exterior.xy, color=TEXT, linewidth=2)
    ax.annotate("reference bbox", (bbox[0], bbox[3]), xytext=(0, 4), textcoords="offset points",
                fontsize=8, color=TEXT)
    ax.set_xlabel("Longitude (°E)", color=MUTED, fontsize=9)
    ax.set_ylabel("Latitude (°N)", color=MUTED, fontsize=9)
    ax.set_title("GCOV frame footprints vs reference bbox", color=TEXT, fontsize=10, loc="left")
    ax.set_aspect("equal")
    _style(ax)
    ax.annotate("CRS: EPSG:4326  |  Source: ASF DAAC NISAR L2 GCOV catalogue", xy=(0, -0.1),
                xycoords="axes fraction", fontsize=7, color=MUTED, va="top")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
