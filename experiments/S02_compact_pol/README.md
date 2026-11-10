# S02_compact_pol

**Status:** done  <!-- planned | running | done | abandoned -->
**Decision:** for water, S-band compact-pol information is in the **total power** (g0 / RH / RV); normalised CP descriptors (m, χ, δ, α_s, m-χ fractions) do not separate water from land (JM ≤ 0.04). Use CP intensity, not decompositions  <!-- adopt | reject | iterate — one line why -->
**Owner / date:** nischal, 2026-11-10

## Question / hypothesis
Task H(iii): do S-band compact-polarimetric descriptors (Stokes child parameters, m-χ decomposition) separate water from land better than CP intensity?

## Data
- Bhoonidhi `NISAR_SSAR_GCOV`, desc 120/76, mode 2500 CRNA (circular transmit, H/V receive), 2026-09-14 (monsoon). Terms RHRH, RHRV, RVRV, frequency A, 20 m; bbox window streamed by HTTP range reads (28 × 4 MB). The window is an exact 2×2 aggregate of the canonical 10 m grid (shifted by one 10 m column, like L-band QPDH).
- **No optical reference** exists for this date (monsoon cloud). The Sentinel-1 VV water map of 2026-09-14 (R00) is used as a **comparison reference**: all numbers are agreement with S1, not accuracy.

## Method & parameters
`features/compact.py`: boxcar 3×3 (60 m) on the covariance terms; Stokes vector g0..g3; degree of polarisation m, ellipticity χ, relative phase δ, α_s; m-χ decomposition (Raney et al. 2012) powers and fractions (vendored nisar-polarimetric-training conventions, right-circular transmit). Reference-free tiled-KI maps per descriptor (+ MMU 0.25 ha); per-descriptor JM / best single-threshold F1 against the S1 map on train blocks.

## Baseline compared against
CP intensity (RH power, `RH_tiled`).

## Results
Auto-filled by `uv run nisar-water report <ID>` from the latest run. Do not edit inside the markers.
<!-- RESULTS:START -->
Run: `experiments/S02_compact_pol/runs/20261110-005612`

**Headline:** selected variant = g0_tiled (best; test F1 pooled) = 0.8469

| metric | value |
|---|---|
| best_variant | g0_tiled |

**Test-block scores by variant (mean over dates, and pooled confusion matrix)**

| variant            |   f1_mean |   iou_mean |   precision_mean |   recall_mean |   f1_pooled |   iou_pooled |
|:-------------------|----------:|-----------:|-----------------:|--------------:|------------:|-------------:|
| g0_tiled           |     0.847 |      0.734 |            0.969 |         0.752 |       0.847 |        0.734 |
| RH_tiled           |     0.829 |      0.708 |            0.974 |         0.722 |       0.829 |        0.708 |
| RV_tiled           |     0.819 |      0.694 |            0.978 |         0.705 |       0.819 |        0.694 |
| mchi_surface_tiled |     0.787 |      0.649 |            0.784 |         0.789 |       0.787 |        0.649 |
| mchi_double_tiled  |     0.731 |      0.576 |            0.654 |         0.828 |       0.731 |        0.576 |

**Per-feature separability on TRAIN pixels (JM, best single-threshold F1)**

| feature                 |    jm |   best_f1_train |   threshold | water_is   |   water_p50 |   land_p50 |
|:------------------------|------:|----------------:|------------:|:-----------|------------:|-----------:|
| mchi_volume             | 1.379 |           0.912 |     -13.296 | <          |     -19.401 |     -9.649 |
| RV                      | 1.304 |           0.912 |     -15.202 | <          |     -21.473 |    -11.746 |
| g0                      | 1.304 |           0.911 |     -11.444 | <          |     -18.099 |     -7.964 |
| HH                      | 1.261 |           0.906 |     -14.028 | <          |     -20.876 |    -10.429 |
| mchi_surface            | 0.675 |           0.840 |     -20.075 | <          |     -27.235 |    -16.253 |
| mchi_double_bounce      | 0.474 |           0.798 |     -22.170 | <          |     -27.878 |    -17.611 |
| RV-RH                   | 0.013 |           0.670 |      -5.514 | >          |      -1.142 |     -1.306 |
| m                       | 0.039 |           0.669 |       0.659 | <          |       0.271 |      0.321 |
| mchi_volume_frac        | 0.039 |           0.669 |       0.342 | >          |       0.729 |      0.680 |
| mchi_double_bounce_frac | 0.023 |           0.668 |       0.494 | <          |       0.117 |      0.121 |
| mchi_surface_frac       | 0.024 |           0.666 |       0.564 | <          |       0.124 |      0.157 |
| alpha_s_deg             | 0.004 |           0.666 |       3.427 | >          |      45.061 |     42.478 |
| chi_deg                 | 0.004 |           0.666 |      41.620 | <          |      -0.097 |      2.534 |
| delta_deg               | 0.002 |           0.666 |    -178.361 | >          |       0.518 |    -29.776 |

**Per date**

| variant            | date       |   threshold_db |    f1 |   iou |   precision |   recall |   water_km2 |
|:-------------------|:-----------|---------------:|------:|------:|------------:|---------:|------------:|
| RH_tiled           | 2026-09-14 |        -18.167 | 0.829 | 0.708 |       0.974 |    0.722 |     115.634 |
| RV_tiled           | 2026-09-14 |        -18.878 | 0.819 | 0.694 |       0.978 |    0.705 |     112.471 |
| g0_tiled           | 2026-09-14 |        -14.720 | 0.847 | 0.734 |       0.969 |    0.752 |     121.340 |
| mchi_surface_tiled | 2026-09-14 |        -22.350 | 0.787 | 0.649 |       0.784 |    0.789 |     151.927 |
| mchi_double_tiled  | 2026-09-14 |        -21.207 | 0.731 | 0.576 |       0.654 |    0.828 |     193.804 |

Figures:
- [f1_by_date.png](runs/20261110-005612/figures/f1_by_date.png)
- [water_RH_tiled_2026-09-14.png](runs/20261110-005612/figures/water_RH_tiled_2026-09-14.png)
- [water_RV_tiled_2026-09-14.png](runs/20261110-005612/figures/water_RV_tiled_2026-09-14.png)
- [water_g0_tiled_2026-09-14.png](runs/20261110-005612/figures/water_g0_tiled_2026-09-14.png)
- [water_mchi_double_tiled_2026-09-14.png](runs/20261110-005612/figures/water_mchi_double_tiled_2026-09-14.png)
- [water_mchi_surface_tiled_2026-09-14.png](runs/20261110-005612/figures/water_mchi_surface_tiled_2026-09-14.png)
<!-- RESULTS:END -->

## Observations and failure modes
- Power-type descriptors separate water well: m-χ volume power (JM 1.38), RV and g0 (1.30), RH (1.26). Their tiled maps agree with S1 at F1 0.82–0.85 (precision ≈ 0.97: whatever the threshold maps is also S1 water; recall 0.71–0.75).
- **Normalised descriptors do not separate water:** m (water 0.27 vs land 0.32), χ, δ, α_s and all m-χ fractions have JM ≤ 0.04. Over open water the S-band return is close to the noise floor (S-band HV over water ≈ −19 dB vs land −14 dB on 10-18), so the received wave is depolarised noise: low m, no meaningful χ. m-χ volume power ranks first only because it is g0·(1 − m), i.e. mostly total power.
- m-χ surface / double-bounce powers map worse than total power (F1 0.79 / 0.73): splitting power into scattering mechanisms adds noise without adding contrast.
- Limitations: one date, monsoon, S1 comparison only (no accuracy), 20 m posting.

## Decision
Report as the Task H(iii) result. S-band CP data can map water through total power; CP decompositions do not improve water/land discrimination at the current noise level.
