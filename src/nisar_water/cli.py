"""Command-line entry point: `uv run nisar-water --help`."""
from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(add_completion=False, help="NISAR GCOV surface-water experiments")


@app.command()
def run(config: Path) -> None:
    """Run the experiment described by CONFIG (experiments/<id>/config.yaml)."""
    from nisar_water.report import update_index, update_readme
    from nisar_water.run import run_experiment

    run_dir = run_experiment(config)
    exp_id = run_dir.parent.parent.name
    update_readme(exp_id)
    update_index()
    typer.echo(f"Results: {run_dir / 'results.md'}")


@app.command()
def report(exp_id: str) -> None:
    """Refresh an experiment's README results block (latest run) and experiments/INDEX.md."""
    from nisar_water.report import update_index, update_readme

    typer.echo(update_readme(exp_id))
    typer.echo(update_index())


@app.command()
def download(inventory_csv: Path, granule: list[str] = typer.Option(None, help="granule name(s); default all rows"),
             band: str = "L") -> None:
    """Download granules listed in an L00 inventory CSV (Earthdata creds from ~/.netrc)."""
    import pandas as pd

    from nisar_water.config import load_paths
    from nisar_water.io.search import download as dl

    inv = pd.read_csv(inventory_csv)
    if granule:
        inv = inv[inv["granule"].isin(granule)]
    total = inv["size_gb"].sum()
    typer.confirm(f"Download {len(inv)} granule(s), ~{total:.1f} GB?", abort=True)
    for p in dl(inv["url"].tolist(), load_paths()[f"raw_nisar_{band}"]):
        typer.echo(p)


@app.command()
def fetch(inventory_csv: Path, granule: list[str] = typer.Option(None, help="granule name(s)"),
          date: list[str] = typer.Option(None, help="acquisition date(s) YYYY-MM-DD"),
          track: int = typer.Option(None), frequency: str = "frequencyA",
          terms: str = typer.Option("", help="comma-separated, e.g. HHHH,HVHV; default all diagonal"),
          band: str = "L") -> None:
    """Stream bbox windows of granules from ASF and cache them in data/interim/nisar_<band>/ (no full download)."""
    import pandas as pd

    from nisar_water.config import load_aoi, load_paths
    from nisar_water.io.gcov import fetch_window, window_path

    inv = pd.read_csv(inventory_csv, parse_dates=["start_time"])
    if granule:
        inv = inv[inv["granule"].isin(granule)]
    if date:
        inv = inv[inv["start_time"].dt.strftime("%Y-%m-%d").isin(date)]
    if track is not None:
        inv = inv[inv["track"] == track]
    if inv.empty:
        raise typer.BadParameter("no granules match the filters")
    out_dir = load_paths()["interim"] / f"nisar_{band}"
    bbox = load_aoi()["bbox_wsen"]
    for _, row in inv.iterrows():
        out = window_path(out_dir, row["granule"], frequency)
        typer.echo(f"{row['start_time'].date()} {row['granule']} -> {out.name}")
        fetch_window(row["url"], out, frequency, terms.split(",") if terms else None, bbox)


@app.command()
def qgis(out: Path = Path("qgis/nisar_water.qgz"), s2: bool = True,
         qgis_python: Path = Path("/Applications/QGIS.app/Contents/MacOS/python3.12")) -> None:
    """Export layers (HH/HV dB, S2 true colour) and build a styled, time-enabled QGIS project."""
    import os
    import subprocess

    from nisar_water import REPO_ROOT
    from nisar_water.qgis_export import export

    manifest = export(s2=s2, log=typer.echo)
    if not qgis_python.exists():
        raise typer.BadParameter(f"QGIS Python not found at {qgis_python}; pass --qgis-python")
    # QGIS.app (macOS, 3.44) ships python3.12 whose stdlib + PyQGIS live in Contents/Resources/python3.11;
    # point PYTHONPATH there and keep the uv venv out of QGIS's interpreter
    res = qgis_python.parents[1] / "Resources" / "python3.11"
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": os.pathsep.join(str(res / d) for d in ("", "lib-dynload", "site-packages"))}
    env.pop("VIRTUAL_ENV", None)
    subprocess.run([str(qgis_python), str(REPO_ROOT / "tools" / "build_qgis_project.py"), str(manifest),
                    str((REPO_ROOT / out).resolve())], check=True, env=env)


if __name__ == "__main__":
    app()
