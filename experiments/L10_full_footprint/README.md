# L10_full_footprint

**Status:** done  <!-- planned | running | done | abandoned -->
**Decision:** adopt iteration 3 (scene threshold = reference-box threshold − 1 dB, L13): floodplain belt F1 0.81 vs a frame-wide S2 mosaic, reference box 0.85; the southern plain improves from 0.29 to 0.47 but still over-maps dark dry fields, so its areas are indicative  <!-- adopt | reject | iterate — one line why -->
**Owner / date:** nisar_analysis team, 2026-11-10

## Question / hypothesis
Does the production model (C3 without HAND, L07 `lgbm_rel_nohand_mmu25`, box test F1 0.820) give credible water masks over the whole asc 98/14 frame (~64,000 km², 15 dates), as the problem statement requires? Where it fails outside the reference box, why, and can it be fixed?

## Data
- 15 NISAR L2 GCOV L-band asc 98/14 DHDH granules (HH, HV), 2025-11-28 … 2026-10-18 (`config.yaml` → `data`); full frame, output 20 m (every 2nd 10 m sample), EPSG:32645.
- Validation: (1) box S2 references (R00) on TEST blocks, 5 dates (`tables/bbox_check.csv`); (2) **frame-wide S2 for 2026-01-15** (`scripts/l10_s2_crosscheck.py`: S2 L2A mosaic ±3 days, 40 m, R00 cloud rules, MNDWI > 0; 99 % of the frame clear, MNDWI–NDWI F1 0.87; `outputs/s2_frame/`); (3) frame-wide Sentinel-1 VV at 100 m with the R00 box-validated thresholds, 5 dates (`scripts/l10_s1_crosscheck.py`; comparison, not truth).
- Zones: **floodplain belt** = northing ≥ 2,775 km (~18,000 km², includes the reference box and the Ganga/Kosi floodplain) and **southern plain**; `scripts/l10_zone_scores.py` writes the zone tables.

## Method & parameters
Tiles of 2048 px (~20 km, the scale the model was trained at) with a 32 px halo; Lee 7×7 with per-scene ENL, texture and 15-date temporal statistics as in L07; the model is applied to every second 10 m sample (20 m output) and the MMU (0.25 ha) applied after.
- **Iteration 1** (run 20261110-051412): a ~10 km far-range strip of near-zero power (−146 dB) that the GCOV mask marks valid on the 5 dry-season granules (X0500x processing), with a backscatter ramp towards it, became water; per-tile KI thresholds of ~−10 dB in low-water tiles gave speckled 20 km blocks.
- **Iteration 2** (run 20261110-144223): edge mask (10 km in the run + 8 km post-fix, `scripts/l10_edge_postfix.py`; now `buffer_m: 18000`) and per-tile thresholds regularised (> 3 dB from the date median → median of neighbours). Validation: belt F1 0.77, **southern plain F1 0.29** (precision 0.17), 06-20 belt water 16× Sentinel-1.
- **Iteration 3** (run 20261110-224243, L13): the per-tile KI threshold split land types in low-water tiles (01-15 median −14.9 dB in the south vs −16.4 dB in the belt; block precision vs t Spearman −0.65). Every tile now uses the date's reference-box threshold (the one the model was trained against) − 1 dB, selected on L13 tuning tiles (eval tiles: south F1 0.26 → 0.41, belt 0.79 → 0.79). Run as 5 shards (`extra.shard: [i, 5]`) merged with `extra.merge_shards` (identical to a single run; shard logs in `tables/shard_logs/`).
- Persistent water = NISAR water on ≥ 4 of 5 dry dates ∪ JRC GSW occurrence ≥ 50 % (2,386 km²).

## Baseline compared against
L07 C3 in the reference box (test F1 0.820 for this model) and iterations 1–2 of this experiment on the same frame and references.

## Results
Auto-filled by `uv run nisar-water report <ID>` from the latest run. Do not edit inside the markers.
<!-- RESULTS:START -->
Run: `experiments/L10_full_footprint/runs/20261110-224243`

**Headline:** full-footprint mean water area (km²) = 3431.2250

| metric | value |
|---|---|
| footprint_km2 | 62793.8488 |
| output_posting_m | 20.0000 |
| persistent_water_km2 | 2386.1896 |

**Water area per date, full footprint (km²)**

| date       |   water_km2 |   valid_km2 |
|:-----------|------------:|------------:|
| 2025-11-28 |      2812.8 |     59688.8 |
| 2025-12-10 |      2373.6 |     58068.3 |
| 2025-12-22 |      2236.2 |     59638.0 |
| 2026-01-03 |      2311.9 |     58091.6 |
| 2026-01-15 |      2420.2 |     58073.9 |
| 2026-06-20 |      1711.5 |     59422.4 |
| 2026-07-02 |      1245.8 |     59425.3 |
| 2026-07-14 |      3105.0 |     57775.2 |
| 2026-07-26 |      4664.4 |     57774.9 |
| 2026-08-19 |      4606.7 |     57775.8 |
| 2026-08-31 |      7060.1 |     59427.0 |
| 2026-09-12 |      5622.0 |     59426.1 |
| 2026-09-24 |      5383.0 |     59425.0 |
| 2026-10-06 |      3828.4 |     59427.9 |
| 2026-10-18 |      2086.6 |     57778.2 |

**bbox consistency vs S2 (TEST blocks, sampled pixels)**

| date       |    f1 |   iou |   precision |   recall |
|:-----------|------:|------:|------------:|---------:|
| 2025-11-28 | 0.834 | 0.716 |       0.861 |    0.809 |
| 2025-12-10 | 0.764 | 0.619 |       0.944 |    0.642 |
| 2026-01-03 | 0.800 | 0.667 |       0.807 |    0.794 |
| 2026-01-15 | 0.830 | 0.710 |       0.817 |    0.844 |
| 2026-10-18 | 0.761 | 0.614 |       0.882 |    0.669 |

Figures:
- [water_full_2025-11-28.png](runs/20261110-224243/figures/water_full_2025-11-28.png)
- [water_full_2025-12-10.png](runs/20261110-224243/figures/water_full_2025-12-10.png)
- [water_full_2025-12-22.png](runs/20261110-224243/figures/water_full_2025-12-22.png)
- [water_full_2026-01-03.png](runs/20261110-224243/figures/water_full_2026-01-03.png)
- [water_full_2026-01-15.png](runs/20261110-224243/figures/water_full_2026-01-15.png)
- [water_full_2026-06-20.png](runs/20261110-224243/figures/water_full_2026-06-20.png)
- [water_full_2026-07-02.png](runs/20261110-224243/figures/water_full_2026-07-02.png)
- [water_full_2026-07-14.png](runs/20261110-224243/figures/water_full_2026-07-14.png)
- [water_full_2026-07-26.png](runs/20261110-224243/figures/water_full_2026-07-26.png)
- [water_full_2026-08-19.png](runs/20261110-224243/figures/water_full_2026-08-19.png)
- [water_full_2026-08-31.png](runs/20261110-224243/figures/water_full_2026-08-31.png)
- [water_full_2026-09-12.png](runs/20261110-224243/figures/water_full_2026-09-12.png)
- [water_full_2026-09-24.png](runs/20261110-224243/figures/water_full_2026-09-24.png)
- [water_full_2026-10-06.png](runs/20261110-224243/figures/water_full_2026-10-06.png)
- [water_full_2026-10-18.png](runs/20261110-224243/figures/water_full_2026-10-18.png)
<!-- RESULTS:END -->

## Observations & failure modes
- **Frame-wide S2, 2026-01-15** (`tables/s2_zone_scores.csv`): floodplain belt **F1 0.81** (precision 0.78, recall 0.83; 603 vs 570 km²), southern plain F1 0.47 (precision 0.33, recall 0.83; 1,338 vs 524 km²), inside the box 0.85. Iteration 2: 0.77 / 0.29 / 0.85.
- **Box test blocks** (5 S2 dates, `tables/bbox_check.csv`): F1 0.76–0.83 (iteration 2: 0.77–0.83).
- **Sentinel-1 ratios** (mean NISAR / S1 water fraction of 20 km blocks, `tables/s1_zone_ratios.csv`): 01-15: belt 1.4×, south 2.9×; 06-20: belt 1.4×, south 3.7×; 07-02: belt 0.6×, south 1.0×; 09-12: belt 1.3×, south 2.9×; 10-18: belt 1.2×, south 1.9×. Iteration 2: 06-20 belt 15.6×, south 37.6×.
- Belt water (`tables/water_area_by_zone.csv`): 694–1,030 km² in the dry season, 4,037 km² at 2026-09-12, 1,260 km² on 10-18.
- The remaining southern commission error is landscape-specific: dark, dry fallow fields; the temporal feature `HH_tfrac_dark` uses an absolute −16 dB threshold. Monsoon accuracy is not measured anywhere (no clear S2 Jun–mid Oct).

## Next step
Retrain with labelled samples from the southern plain (the frame-wide S2 mosaic provides them for 01-15) and a scene-relative version of `HH_tfrac_dark`; then rerun.
