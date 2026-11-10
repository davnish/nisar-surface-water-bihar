# NISAR surface-water mapping & change detection (InGARSS 2026 YP Hackathon)

Reproducible workflow for mapping surface water and detecting change over the Bihar Ganga floodplain (reference bbox W 86.3946, S 25.4098, E 86.6054, N 25.5902) using **NISAR L2 GCOV** only. L-band is the production band (all dates, full footprint); S-band and L+S are compared on the reference box (S-band read from Bhoonidhi by HTTP range requests, see Limitations).

## Results at a glance
| Product | Method | Evidence |
|---|---|---|
| Water masks, 15 dates (asc 98/14, 2025-11-28 → 2026-10-18) | **C3**: Lee 7×7 → scene-relative HH + texture + multi-date features → LightGBM → MMU 0.25 ha (L07) | test-block F1 **0.832** vs same-date Sentinel-2 (5 dates); S1 agreement 0.74–0.82 in the monsoon |
| Change maps + new water outside persistent water | post-classification comparison of C3 masks (L09) | OA 0.948, gain F1 0.72 vs S2-derived change |
| Polarimetric assessment (Task H) | full-pol (desc 120/76 QPDH) vs dual-pol feature sets, same classifier/samples (L08) | see `experiments/L08_polarimetric_features/README.md` |
| L vs S vs L+S (Task C), 8 simultaneous dates, reference box | identical per-band pipeline + LightGBM; feature-level fusion (F01, F02) | S 0.810 ≈ L 0.809 test F1; L+S 0.828, ΔF1 +0.018 [0.002, 0.041], one S2 date; L+S over-maps one rough-surface monsoon date, so production stays L-only |
| S-band compact-pol (Task H) | Stokes / m-χ descriptors (S02) | total power separates water (JM 1.3); m, χ, δ do not (JM ≤ 0.04) |
| Full scene footprint, 15 dates + change (64,000 km²) | tiled production of C3 (no-HAND variant), 20 m, scene threshold = reference-box threshold − 1 dB (L10, L10b, L13) | vs frame-wide S2 (2026-01-15): **Ganga floodplain belt F1 0.81**, reference box 0.85, southern plain 0.47 (dark dry fields partly over-mapped). Belt: 3,048 km² new water outside persistent water 01-15 → 09-12 |

Reproduce everything: `uv sync` → `nisar-water fetch` (bbox windows) → run the configs in order R00, L00, L07, L08, L09, L10, L10b, S00, S02, F01, F02 (`uv run nisar-water run experiments/<id>/config.yaml`). Walkthrough notebook: [`notebooks/walkthrough.ipynb`](notebooks/walkthrough.ipynb).

- **Methodology & decision log:** [`docs/methodology.md`](docs/methodology.md)
- **Experiment status:** [`experiments/INDEX.md`](experiments/INDEX.md)

The bbox is used for scene discovery and fast method development only. Final outputs cover the full selected scene footprint.

## Setup
```bash
git clone --recurse-submodules <repo>   # or: git submodule update --init --recursive
uv sync                                 # Python 3.12 env from pyproject.toml / uv.lock
uv run pytest                           # unit tests
```
Data downloads need a NASA Earthdata login stored in `~/.netrc`:
```
machine urs.earthdata.nasa.gov login <user> password <pass>
```
(then `chmod 600 ~/.netrc`).

## Running an experiment
Every experiment is one folder under `experiments/`: a `config.yaml` (what to run) and a `README.md` (why, and what we concluded).
```bash
uv run nisar-water run experiments/L00_data_inventory/config.yaml   # run → experiments/<id>/runs/<timestamp>/
uv run nisar-water report L00_data_inventory                        # refresh README results + INDEX.md

# data: stream only the bbox window from ASF and cache it (~100s of MB/date, no 7 GB download)
uv run nisar-water fetch experiments/L00_data_inventory/runs/<ts>/tables/inventory.csv --track 98 --date 2026-01-15
# full granules (needed only for full-footprint production, L10; mind disk space)
uv run nisar-water download experiments/L00_data_inventory/runs/<ts>/tables/inventory.csv --granule <name>
```
Experiments read the cached window from `data/interim/nisar_<band>/` when it exists, and fall back to a raw granule in `data/raw/`.
Each run folder contains:

| File / folder | Contents |
|---|---|
| `config.yaml` | frozen copy of the config |
| `provenance.json` | git commit, package versions, input files |
| `metrics.json` | machine-readable results |
| `results.md` | auto-generated results summary |
| `figures/` | maps stamped with date, CRS, resolution and source |
| `outputs/` | COG rasters (git-ignored) |
| `tables/` | CSV / GeoJSON tables |
| `log.txt` | run log |

To start a new experiment, copy `experiments/_template/`. Set `id` to the folder name, then fill in the README's question before running. After the run, fill in Observations, Decision and Next step. **Promotion rule:** the champion is the best F1/IoU on held-out reference blocks. If two methods are within ~0.01 F1, prefer the simpler one.

## Viewing results in QGIS
```bash
uv run nisar-water qgis          # exports layers to data/processed/qgis/ and builds qgis/nisar_water.qgz
open qgis/nisar_water.qgz        # QGIS ≥ 3.34
```
- **What's in it:** layer groups for AOI, water masks (B0 / L02, C1 / L04, C2 / L06 and champion C3 / L07, shown by default), L09 change and new-water maps and water occurrence, R00 references (persistent water, JRC, train/test blocks, S2 and S1 water), HH/HV γ0 dB (Lee 7×7), Sentinel-2 true colour, and the Esri World Imagery and OpenStreetMap basemaps.
- **Stepping through dates:** every dated layer has a temporal range of [acquisition, next acquisition). Open *View → Panels → Temporal Controller* and step in 12-day increments.
- **How it's built:** `tools/build_qgis_project.py` (PyQGIS) runs under QGIS's own Python, which the CLI calls. `--no-s2` skips downloading new Sentinel-2 true-colour images. Re-run after new experiments to pick up their outputs.

## Layout
```
configs/            AOI (bbox, candidate track/frames), canonical grid, data paths
docs/               methodology.md: living methodology + decision log
qgis/               nisar_water.qgz (built by `nisar-water qgis`; layers in data/processed/qgis/)
tools/              build_qgis_project.py (PyQGIS)
data/               raw/ (GCOV, ancillary; git-ignored), interim/, processed/, reference/
src/nisar_water/    io/ preprocess/ features/ classify/ change/ validate/ viz/ tasks/ + cli, run, report
experiments/        INDEX.md, _template/, one folder per experiment (L = L-band, S = S-band, F = fusion, R = reference)
notebooks/          read-only viewers of run outputs
reports/            technical note, slides, final figures
third_party/        nisar-polarimetric-training (pinned submodule)
tests/              unit tests
```

## Third-party code
- [`nisar-polarimetric-training`](https://github.com/dharmendraisro/nisar-polarimetric-training) by D. K. Pandey (Apache-2.0), pinned at `f2c96ff`. Used for GCOV product identification, windowed HDF5 access, and polarimetric decompositions; imported via `nisar_water._npt`. It isn't pip-installable, which is why it is a submodule. It is an unofficial training toolkit, and its decompositions are cross-checked in our tests before use.

## Data sources
- L-band L2 GCOV: NASA ASF DAAC, https://search.asf.alaska.edu/#/?dataset=NISAR&sciProducts=GCOV
- S-band L2 GCOV: Bhoonidhi, NRSC/ISRO, https://bhoonidhi.nrsc.gov.in/NISAR/

## Assumptions and limitations
- **S-band extent:** S-band granules (12.6 GB) come only from Bhoonidhi at ~0.2 MB/s, so only the reference-box window of each was read (HTTP range requests, `io/bhoonidhi.py`; credentials in a git-ignored `bhoonidhi.env`). S-only and L+S results cover the box and the 8 Jul–Oct 2026 dates with S-band; their accuracy rests on one S2 date (2026-10-18).
- **Reference:** Sentinel-2 MNDWI water within ±3 days (R00). It exists for 5 of the 15 asc dates and **for no monsoon date** (cloud); monsoon results are checked only against Sentinel-1 (comparison, not truth). S2 itself has errors (wet sand, shadows, water under vegetation).
- **Noise floor:** GCOV has no noise correction; HV and VV over open water sit near the noise-equivalent sigma-zero (≈ −25 dB), which limits cross-pol and polarimetric descriptors over water.
- **Full-footprint transfer:** the classifier is trained in the reference box. A first full-frame run with per-tile KI thresholds over-mapped the southern plain (F1 0.29 vs a frame-wide S2 mosaic) and 2026-06-20; per-tile thresholds split land types in low-water tiles (L13). With the box threshold − 1 dB the floodplain belt (northing ≥ 2,775 km) reaches F1 0.81 and the southern plain 0.47 (precision 0.33): southern areas are indicative only. Zone tables: `experiments/L10_full_footprint/runs/20261110-224243/tables/`, `experiments/L10b_change_full_footprint/runs/20261110-224723/tables/change_areas_by_zone.csv`.
- **Polarimetric assessment** (L08, S02) uses the descending 120/76 full-pol and compact-pol data in the reference box only (S-band download limits; full-pol is a different track from the production series).
- **Full footprint** is produced at 20 m (every second 10 m sample) to fit laptop compute; the bbox analyses are at 10 m.
- **Interpretation:** mapped water gain is *newly detected water*; it is not attributed to flooding, rainfall or irrigation without independent evidence.
- Areas are pixel counts × pixel area on the projected UTM 45N grid (EPSG:32645).
