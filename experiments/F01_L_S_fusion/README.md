# F01_L_S_fusion

**Status:** done  <!-- planned | running | done | abandoned -->
**Decision:** fusion **L+S gives a small, significant gain** on the one S2-referenced date (test F1 0.826 vs 0.807 L-only; ΔF1 +0.018 [+0.002, +0.041]) but is **less robust across dates** (over-maps 09-24 by 2×). Production stays **L-only C3**; L+S is reported as the best bbox result where both bands exist.
**Owner / date:** nischal, 2026-11-10

## Question / hypothesis
Does S-band (9.4 cm) add information to L-band (24 cm) for open-water mapping, and does S-band alone do as well as L-band? Expectation: S-band is more sensitive to surface roughness and vegetation canopy (so it sees less flooded vegetation), but as an independent speckle realisation with a different confuser set, L+S should reduce false alarms.

## Data
- 8 simultaneous L+S dates, asc 98/14: 2026-07-14, 07-26, 08-19, 08-31, 09-12, 09-24, 10-06, 10-18.
- L-band DHDH HH/HV 10 m (ASF). S-band DHNA HH/HV 10 m (Bhoonidhi, bbox windows read with HTTP range requests; same EPSG:32645 grid as L-band, no resampling).
- **Truth:** Sentinel-2 MNDWI on 2026-10-18 only. That is the single S2 date in the S-band period, because the monsoon is cloud-covered. Train/val/test are 2 km spatial blocks of that date. Sentinel-1 VV masks on all 8 dates are used as a consistency check only.
- Extent: reference bbox only (S-band full frames are 12.6 GB each at ~0.2 MB/s, so not downloadable in time).

## Method & parameters
- Each band is processed identically: Lee 7×7, dB, tiled-KI scene threshold (own ENL), texture (5, 15 px), and scene-relative HH features (HH − own threshold). The S-band features are prefixed `S_`.
- Variants:
  - `{L,S}_C1_mmu25`: tiled KI + 0.25 ha MMU;
  - `{L,S,LS}_lgbm`: LightGBM on relative + texture features;
  - `*_px`: pixel-only HH/HV/HV−HH.
- Same 300k samples, block split, and threshold selection on val blocks for all variants. Multi-date temporal features were not used here, so the dates are not mixed.
- Bootstrap: 2 km test blocks, 2000 draws, baseline `L_lgbm`.

## Baseline compared against
`L_lgbm`, the L-band-only model with the same feature recipe, samples and blocks. L07's C3 additionally uses 15-date temporal features and HAND, so its 0.832 is not comparable here.

## Results
Auto-filled by `uv run nisar-water report <ID>` from the latest run. Do not edit inside the markers.
<!-- RESULTS:START -->
Run: `experiments/F01_L_S_fusion/runs/20261110-033355`

**Headline:** selected variant = LS_lgbm (chosen on val; test F1 pooled) = 0.8260

| metric | value |
|---|---|
| best_variant | LS_lgbm |

**Test-block scores by variant (mean over dates, and pooled confusion matrix)**

| variant    |   f1_mean |   iou_mean |   precision_mean |   recall_mean |   f1_pooled |   iou_pooled |   val_f1_pooled |
|:-----------|----------:|-----------:|-----------------:|--------------:|------------:|-------------:|----------------:|
| LS_lgbm    |     0.826 |      0.704 |            0.865 |         0.791 |       0.826 |        0.704 |           0.885 |
| S_lgbm     |     0.808 |      0.679 |            0.843 |         0.777 |       0.808 |        0.679 |           0.865 |
| LS_lgbm_px |     0.778 |      0.636 |            0.834 |         0.729 |       0.778 |        0.636 |           0.851 |
| L_lgbm     |     0.807 |      0.677 |            0.809 |         0.805 |       0.807 |        0.677 |           0.849 |
| S_C1_mmu25 |     0.762 |      0.615 |            0.824 |         0.709 |       0.762 |        0.615 |           0.848 |
| S_lgbm_px  |     0.757 |      0.609 |            0.820 |         0.702 |       0.757 |        0.609 |           0.841 |
| L_lgbm_px  |     0.757 |      0.609 |            0.807 |         0.713 |       0.757 |        0.609 |           0.827 |
| L_C1_mmu25 |     0.780 |      0.639 |            0.749 |         0.813 |       0.780 |        0.639 |           0.816 |

**Agreement with comparison reference (F1, all pixels; consistency, not accuracy)**

| date       |   LS_lgbm |   LS_lgbm_px |   L_C1_mmu25 |   L_lgbm |   L_lgbm_px |   S_C1_mmu25 |   S_lgbm |   S_lgbm_px |
|:-----------|----------:|-------------:|-------------:|---------:|------------:|-------------:|---------:|------------:|
| 2026-07-14 |     0.750 |        0.737 |        0.731 |    0.741 |       0.680 |        0.755 |    0.737 |       0.752 |
| 2026-07-26 |     0.833 |        0.827 |        0.795 |    0.816 |       0.783 |        0.837 |    0.817 |       0.830 |
| 2026-08-19 |     0.802 |        0.793 |        0.777 |    0.774 |       0.750 |        0.808 |    0.799 |       0.807 |
| 2026-08-31 |     0.847 |        0.788 |        0.806 |    0.795 |       0.713 |        0.858 |    0.848 |       0.849 |
| 2026-09-12 |     0.873 |        0.849 |        0.835 |    0.820 |       0.792 |        0.877 |    0.880 |       0.876 |
| 2026-09-24 |     0.634 |        0.619 |        0.748 |    0.713 |       0.544 |        0.813 |    0.762 |       0.023 |
| 2026-10-06 |     0.846 |        0.827 |        0.802 |    0.788 |       0.769 |        0.852 |    0.861 |       0.851 |
| 2026-10-18 |     0.795 |        0.794 |        0.754 |    0.771 |       0.762 |        0.810 |    0.802 |       0.804 |

**Mapped water area per date (km²)**

| date       |   LS_lgbm |   LS_lgbm_px |   L_C1_mmu25 |   L_lgbm |   L_lgbm_px |   S_C1_mmu25 |   S_lgbm |   S_lgbm_px |   comparison_reference_km2 |
|:-----------|----------:|-------------:|-------------:|---------:|------------:|-------------:|---------:|------------:|---------------------------:|
| 2026-07-14 |      30.0 |         29.0 |         35.3 |     33.4 |        26.7 |         28.6 |     31.6 |        30.2 |                       37.8 |
| 2026-07-26 |      49.0 |         47.6 |         56.2 |     54.0 |        44.9 |         44.8 |     51.5 |        47.7 |                       47.8 |
| 2026-08-19 |      90.1 |         86.8 |        102.9 |    101.7 |        82.0 |         82.4 |     93.2 |        86.0 |                       85.7 |
| 2026-08-31 |     137.4 |        104.0 |        153.6 |    159.9 |        92.5 |        122.1 |    132.9 |       114.3 |                      123.3 |
| 2026-09-12 |     167.0 |        144.9 |        184.9 |    189.6 |       134.6 |        144.8 |    161.0 |       146.7 |                      153.1 |
| 2026-09-24 |     258.0 |         74.6 |        174.8 |    202.7 |        64.6 |        123.5 |    161.2 |         1.6 |                      129.8 |
| 2026-10-06 |     143.8 |        122.7 |        172.2 |    179.7 |       115.8 |        120.6 |    134.4 |       121.9 |                      140.5 |
| 2026-10-18 |      74.1 |         74.9 |         90.1 |     82.5 |        75.6 |         74.7 |     78.5 |        74.5 |                       73.6 |

**Spatial-block bootstrap (2 km test blocks, 2000 draws): F1 and difference vs baseline, 95 % intervals**

| variant    |   f1_median |   f1_lo |   f1_hi |   dF1_vs_L_lgbm |   dF1_lo |   dF1_hi |   p_better |
|:-----------|------------:|--------:|--------:|----------------:|---------:|---------:|-----------:|
| L_C1_mmu25 |       0.781 |   0.708 |   0.835 |          -0.028 |   -0.041 |   -0.016 |      0.000 |
| S_C1_mmu25 |       0.765 |   0.696 |   0.834 |          -0.042 |   -0.095 |    0.005 |      0.049 |
| L_lgbm     |       0.809 |   0.742 |   0.857 |           0.000 |    0.000 |    0.000 |      0.000 |
| S_lgbm     |       0.810 |   0.753 |   0.861 |           0.002 |   -0.031 |    0.040 |      0.539 |
| LS_lgbm    |       0.828 |   0.775 |   0.867 |           0.018 |    0.002 |    0.041 |      0.987 |
| L_lgbm_px  |       0.759 |   0.699 |   0.812 |          -0.049 |   -0.070 |   -0.027 |      0.000 |
| S_lgbm_px  |       0.760 |   0.692 |   0.827 |          -0.047 |   -0.101 |   -0.001 |      0.022 |
| LS_lgbm_px |       0.780 |   0.719 |   0.841 |          -0.027 |   -0.064 |    0.007 |      0.085 |

**Feature importance (gain share)**

|                |   L_lgbm |   S_lgbm |   LS_lgbm |   L_lgbm_px |   S_lgbm_px |   LS_lgbm_px |
|:---------------|---------:|---------:|----------:|------------:|------------:|-------------:|
| HH_m5_rel      |    0.685 |  nan     |     0.546 |     nan     |     nan     |      nan     |
| HH_min15_rel   |    0.066 |  nan     |     0.035 |     nan     |     nan     |      nan     |
| HH_rel         |    0.057 |  nan     |     0.064 |     nan     |     nan     |      nan     |
| HH_m15_rel     |    0.056 |  nan     |     0.026 |     nan     |     nan     |      nan     |
| HH_s15         |    0.043 |  nan     |     0.028 |     nan     |     nan     |      nan     |
| HV_m15         |    0.040 |  nan     |     0.027 |     nan     |     nan     |      nan     |
| HH_s5          |    0.033 |  nan     |     0.011 |     nan     |     nan     |      nan     |
| HV             |    0.012 |  nan     |     0.005 |       0.733 |     nan     |        0.041 |
| HV-HH          |    0.009 |  nan     |     0.005 |       0.151 |     nan     |        0.030 |
| S_HH_m5_rel    |  nan     |    0.658 |     0.088 |     nan     |     nan     |      nan     |
| S_HH_min15_rel |  nan     |    0.096 |     0.050 |     nan     |     nan     |      nan     |
| S_HH_s15       |  nan     |    0.064 |     0.041 |     nan     |     nan     |      nan     |
| S_HH_rel       |  nan     |    0.054 |     0.004 |     nan     |     nan     |      nan     |
| S_HV_m15       |  nan     |    0.047 |     0.019 |     nan     |     nan     |      nan     |
| S_HH_m15_rel   |  nan     |    0.039 |     0.026 |     nan     |     nan     |      nan     |
| S_HH_s5        |  nan     |    0.023 |     0.018 |     nan     |     nan     |      nan     |
| S_HV           |  nan     |    0.013 |     0.005 |     nan     |       0.710 |        0.040 |
| S_HV-HH        |  nan     |    0.006 |     0.002 |     nan     |       0.184 |        0.020 |
| HH             |  nan     |  nan     |   nan     |       0.116 |     nan     |        0.613 |
| S_HH           |  nan     |  nan     |   nan     |     nan     |       0.106 |        0.257 |

**Per date**

| variant    | date       |   threshold_db |    f1 |   iou |   precision |   recall |   water_km2 |
|:-----------|:-----------|---------------:|------:|------:|------------:|---------:|------------:|
| L_C1_mmu25 | 2026-10-18 |        -14.531 | 0.780 | 0.639 |       0.749 |    0.813 |      90.059 |
| S_C1_mmu25 | 2026-10-18 |        -13.531 | 0.762 | 0.615 |       0.824 |    0.709 |      74.699 |
| L_lgbm     | 2026-10-18 |        nan     | 0.807 | 0.677 |       0.809 |    0.805 |      82.470 |
| S_lgbm     | 2026-10-18 |        nan     | 0.808 | 0.679 |       0.843 |    0.777 |      78.492 |
| LS_lgbm    | 2026-10-18 |        nan     | 0.826 | 0.704 |       0.865 |    0.791 |      74.056 |
| L_lgbm_px  | 2026-10-18 |        nan     | 0.757 | 0.609 |       0.807 |    0.713 |      75.580 |
| S_lgbm_px  | 2026-10-18 |        nan     | 0.757 | 0.609 |       0.820 |    0.702 |      74.480 |
| LS_lgbm_px | 2026-10-18 |        nan     | 0.778 | 0.636 |       0.834 |    0.729 |      74.944 |

Figures:
- [f1_by_date.png](runs/20261110-033355/figures/f1_by_date.png)
- [water_LS_lgbm_2026-10-18.png](runs/20261110-033355/figures/water_LS_lgbm_2026-10-18.png)
- [water_LS_lgbm_px_2026-10-18.png](runs/20261110-033355/figures/water_LS_lgbm_px_2026-10-18.png)
- [water_L_C1_mmu25_2026-10-18.png](runs/20261110-033355/figures/water_L_C1_mmu25_2026-10-18.png)
- [water_L_lgbm_2026-10-18.png](runs/20261110-033355/figures/water_L_lgbm_2026-10-18.png)
- [water_L_lgbm_px_2026-10-18.png](runs/20261110-033355/figures/water_L_lgbm_px_2026-10-18.png)
- [water_S_C1_mmu25_2026-10-18.png](runs/20261110-033355/figures/water_S_C1_mmu25_2026-10-18.png)
- [water_S_lgbm_2026-10-18.png](runs/20261110-033355/figures/water_S_lgbm_2026-10-18.png)
- [water_S_lgbm_px_2026-10-18.png](runs/20261110-033355/figures/water_S_lgbm_px_2026-10-18.png)
<!-- RESULTS:END -->

## Observations & failure modes
- **S-band alone ≈ L-band alone** for open water: S_lgbm 0.810 vs L_lgbm 0.809 (ΔF1 +0.002 [−0.031, +0.040]). S is more precise (0.84 vs 0.81) and L has more recall (0.81 vs 0.78). This is consistent with L-band mapping more of the partially vegetated and flooded fringes.
- **L+S fusion** is the best variant on 10-18: F1 0.826, precision 0.865. The gain is mostly fewer false alarms. In LS_lgbm, the L-band relative HH carries 55% of the gain and the S-band relative HH and texture about 25%. The ΔF1 of +0.018 is just outside the ±0.01 tie band and its 95% interval excludes 0 (p_better 0.99), **but it is measured on one date**.
- **Robustness failure on 2026-09-24.** Both bands are 1.5–1.8 dB brighter than on neighbouring dates (scene thresholds: L −11.0 vs −12.8 dB, S −12.1 vs −13.6 dB). That points to monsoon-peak wind or rain roughening or wet soil. The models were trained on the October date alone:
  - LS_lgbm maps 258 km² (S1: 130);
  - S_lgbm_px collapses to 1.6 km²;
  - the per-band models with scene-relative features (S_lgbm 161, L_lgbm 203) and the tiled thresholds (S_C1 124) degrade much less.

  This is the same lesson as L07: **scene-relative features are what transfers across dates**, and combining two bands' feature sets gives the model more ways to latch onto absolute levels.
- Agreement with S1 (C-band, consistency only) is higher for S-band than L-band on most dates (e.g. 08-31: S 0.85 vs L 0.80). This is expected, since C and S see vegetation similarly. It is not evidence that S is more accurate.
- Pixel-only variants are about 0.05 below the texture variants for both bands, so spatial context is worth more than the second frequency.

## Next step
L+S stays a bbox-level result. With full S-band frames and S2 references on more dates, retrain LS with scene-relative features only and multi-date training. Production (L10) uses L-only C3.
