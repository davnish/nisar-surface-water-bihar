# L09_change_detection

**Status:** done  <!-- planned | running | done | abandoned -->
**Decision:** adopt **post-classification comparison (PCC) of C3 masks** (mean OA 0.948, stable-water F1 0.84 vs S2-derived change; log-ratio worse at 3 and 5 dB)  <!-- adopt | reject | iterate — one line why -->
**Owner / date:** nischal, 2026-11-09

## Question / hypothesis
Which gives more credible date-to-date change maps (problem statement §6 classes): comparing two single-date water masks (PCC) or thresholding the HH log-ratio from the earlier state? PCC inherits both masks' errors; log-ratio ignores date-independent confusers but is speckle- and roughness-sensitive.

## Data
- C3 masks (L07 `lgbm_rel_full_mmu25`) for the 15 asc 98/14 dates; HH Lee 7×7 dB for the log-ratio.
- Pairs: 5 key pairs (dry-season recession; dry → monsoon peak; pre-monsoon → peak; peak → recession; dry → post-monsoon) + all consecutive pairs.
- Assessment: S2-derived change (change classes of the two S2 reference masks) on TEST blocks, for the pairs where both dates have S2 (4 pairs). Persistent water = dry-season S2 persistent water (R00).

## Method & parameters
- **pcc:** `change/classes.change_map(mask_earlier, mask_later)`.
- **logratio_{3,5}db:** r = HH_later − HH_earlier (dB). Earlier non-water with r < −t → gain; earlier water with r > +t → loss; otherwise the earlier state.
- **New water outside persistent water** (Task E) = gain pixels not in the persistent-water mask. Areas = pixel count × 100 m² (EPSG:32645, 10 m), km².

## Baseline compared against
The two methods against each other on identical masks, pairs and blocks.

## Results
Auto-filled by `uv run nisar-water report <ID>` from the latest run. Do not edit inside the markers.
<!-- RESULTS:START -->
Run: `experiments/L09_change_detection/runs/20261109-225657`

**Headline:** best method = pcc (mean gain/loss F1 vs S2 change, test blocks) = 0.3019

| metric | value |
|---|---|
| source_run | experiments/L07_supervised_rf_lgbm/runs/20261109-223929 |

**Change-class areas per pair (km², full bbox)**

| pair                                | method       |   Stable non-water (km²) |   Stable water (km²) |   Newly detected water (gain) (km²) |   Water loss (receded) (km²) |   New water outside persistent (km²) |
|:------------------------------------|:-------------|-------------------------:|---------------------:|------------------------------------:|-----------------------------:|-------------------------------------:|
| dry-season recession (S2 both)      | pcc          |                   371.95 |                32.50 |                                1.07 |                        20.95 |                                 0.86 |
| dry-season recession (S2 both)      | logratio_3db |                   335.02 |                37.30 |                               38.00 |                        16.15 |                                37.92 |
| dry-season recession (S2 both)      | logratio_5db |                   363.71 |                43.54 |                                9.32 |                         9.91 |                                 9.29 |
| dry season → post-monsoon (S2 both) | pcc          |                   347.12 |                31.08 |                               45.78 |                         2.50 |                                44.60 |
| dry season → post-monsoon (S2 both) | logratio_3db |                   307.00 |                27.83 |                               85.90 |                         5.75 |                                85.44 |
| dry season → post-monsoon (S2 both) | logratio_5db |                   343.42 |                31.43 |                               49.48 |                         2.14 |                                49.27 |
| dry season → monsoon peak           | pcc          |                   261.97 |                32.45 |                              130.93 |                         1.13 |                               129.59 |
| dry season → monsoon peak           | logratio_3db |                   253.41 |                22.93 |                              139.49 |                        10.65 |                               139.10 |
| dry season → monsoon peak           | logratio_5db |                   300.03 |                30.50 |                               92.87 |                         3.08 |                                92.68 |
| pre-monsoon → monsoon peak          | pcc          |                   262.24 |                24.43 |                              138.95 |                         0.87 |                               131.20 |
| pre-monsoon → monsoon peak          | logratio_3db |                   267.40 |                20.36 |                              133.78 |                         4.94 |                               127.69 |
| pre-monsoon → monsoon peak          | logratio_5db |                   313.22 |                23.82 |                               87.96 |                         1.47 |                                83.34 |
| monsoon peak → recession            | pcc          |                   259.41 |                73.16 |                                3.70 |                        90.21 |                                 3.47 |
| monsoon peak → recession            | logratio_3db |                   231.04 |                98.75 |                               32.07 |                        64.62 |                                31.87 |
| monsoon peak → recession            | logratio_5db |                   254.10 |               121.66 |                                9.00 |                        41.71 |                                 8.88 |
| consecutive 2025-11-28→2025-12-10   | pcc          |                   370.52 |                44.48 |                                2.50 |                         8.97 |                                 2.25 |
| consecutive 2025-11-28→2025-12-10   | logratio_3db |                   343.67 |                47.93 |                               29.35 |                         5.52 |                                29.25 |
| consecutive 2025-11-28→2025-12-10   | logratio_5db |                   366.29 |                50.96 |                                6.74 |                         2.49 |                                 6.70 |
| consecutive 2025-12-10→2025-12-22   | pcc          |                   378.04 |                38.33 |                                1.45 |                         8.66 |                                 1.13 |
| consecutive 2025-12-10→2025-12-22   | logratio_3db |                   367.78 |                38.80 |                               11.71 |                         8.18 |                                11.64 |
| consecutive 2025-12-10→2025-12-22   | logratio_5db |                   377.47 |                43.78 |                                2.02 |                         3.21 |                                 2.00 |
| consecutive 2025-12-22→2026-01-03   | pcc          |                   384.43 |                33.95 |                                2.27 |                         5.82 |                                 1.47 |
| consecutive 2025-12-22→2026-01-03   | logratio_3db |                   378.40 |                34.65 |                                8.30 |                         5.13 |                                 8.06 |
| consecutive 2025-12-22→2026-01-03   | logratio_5db |                   385.47 |                37.85 |                                1.23 |                         1.93 |                                 1.16 |
| consecutive 2026-01-03→2026-01-15   | pcc          |                   388.36 |                31.68 |                                1.89 |                         4.54 |                                 1.38 |
| consecutive 2026-01-03→2026-01-15   | logratio_3db |                   382.22 |                31.81 |                                8.03 |                         4.42 |                                 7.87 |
| consecutive 2026-01-03→2026-01-15   | logratio_5db |                   389.16 |                34.71 |                                1.09 |                         1.52 |                                 1.03 |
| consecutive 2026-01-15→2026-06-20   | pcc          |                   389.63 |                22.02 |                                3.27 |                        11.55 |                                 2.87 |
| consecutive 2026-01-15→2026-06-20   | logratio_3db |                   316.23 |                20.73 |                               76.67 |                        12.84 |                                76.49 |
| consecutive 2026-01-15→2026-06-20   | logratio_5db |                   366.27 |                25.31 |                               26.62 |                         8.27 |                                26.55 |
| consecutive 2026-06-20→2026-07-02   | pcc          |                   398.99 |                21.87 |                                2.19 |                         3.43 |                                 1.63 |
| consecutive 2026-06-20→2026-07-02   | logratio_3db |                   372.08 |                23.50 |                               29.10 |                         1.79 |                                28.06 |
| consecutive 2026-06-20→2026-07-02   | logratio_5db |                   395.75 |                24.71 |                                5.43 |                         0.58 |                                 5.07 |
| consecutive 2026-07-02→2026-07-14   | pcc          |                   392.64 |                23.31 |                                9.79 |                         0.75 |                                 6.61 |
| consecutive 2026-07-02→2026-07-14   | logratio_3db |                   392.61 |                22.09 |                                9.82 |                         1.97 |                                 8.26 |
| consecutive 2026-07-02→2026-07-14   | logratio_5db |                   398.70 |                23.49 |                                3.72 |                         0.56 |                                 2.89 |
| consecutive 2026-07-14→2026-07-26   | pcc          |                   371.08 |                31.49 |                               22.30 |                         1.60 |                                17.93 |
| consecutive 2026-07-14→2026-07-26   | logratio_3db |                   333.28 |                30.77 |                               60.10 |                         2.33 |                                55.92 |
| consecutive 2026-07-14→2026-07-26   | logratio_5db |                   367.56 |                32.28 |                               25.82 |                         0.82 |                                22.34 |
| consecutive 2026-07-26→2026-08-19   | pcc          |                   330.08 |                51.50 |                               42.60 |                         2.30 |                                41.15 |
| consecutive 2026-07-26→2026-08-19   | logratio_3db |                   306.26 |                49.29 |                               66.42 |                         4.50 |                                65.17 |
| consecutive 2026-07-26→2026-08-19   | logratio_5db |                   329.15 |                52.79 |                               43.53 |                         1.00 |                                42.55 |
| consecutive 2026-08-19→2026-08-31   | pcc          |                   289.36 |                88.23 |                               43.02 |                         5.87 |                                42.69 |
| consecutive 2026-08-19→2026-08-31   | logratio_3db |                   277.45 |                78.59 |                               54.93 |                        15.51 |                                54.79 |
| consecutive 2026-08-19→2026-08-31   | logratio_5db |                   302.16 |                90.35 |                               30.22 |                         3.75 |                                30.15 |
| consecutive 2026-08-31→2026-09-12   | pcc          |                   255.34 |               123.48 |                               39.89 |                         7.76 |                                39.55 |
| consecutive 2026-08-31→2026-09-12   | logratio_3db |                   242.18 |               127.31 |                               53.05 |                         3.93 |                                52.89 |
| consecutive 2026-08-31→2026-09-12   | logratio_5db |                   269.70 |               130.47 |                               25.53 |                         0.77 |                                25.47 |
| consecutive 2026-09-12→2026-09-24   | pcc          |                   244.10 |               129.68 |                               19.00 |                        33.69 |                                18.75 |
| consecutive 2026-09-12→2026-09-24   | logratio_3db |                   246.12 |               111.48 |                               16.98 |                        51.89 |                                16.91 |
| consecutive 2026-09-12→2026-09-24   | logratio_5db |                   258.42 |               137.00 |                                4.68 |                        26.37 |                                 4.64 |
| consecutive 2026-09-24→2026-10-06   | pcc          |                   253.87 |               127.52 |                               23.92 |                        21.17 |                                23.72 |
| consecutive 2026-09-24→2026-10-06   | logratio_3db |                   213.83 |               138.54 |                               63.97 |                        10.14 |                                63.82 |
| consecutive 2026-09-24→2026-10-06   | logratio_5db |                   255.13 |               145.45 |                               22.66 |                         3.24 |                                22.61 |
| consecutive 2026-10-06→2026-10-18   | pcc          |                   272.77 |                74.59 |                                2.26 |                        76.85 |                                 2.10 |
| consecutive 2026-10-06→2026-10-18   | logratio_3db |                   261.19 |               105.32 |                               13.84 |                        46.12 |                                13.72 |
| consecutive 2026-10-06→2026-10-18   | logratio_5db |                   272.52 |               124.87 |                                2.52 |                        26.57 |                                 2.43 |

**Water area per date (km²)**

| date       |   water_km2 |   valid_km2 |
|:-----------|------------:|------------:|
| 2025-11-28 |       53.45 |      426.48 |
| 2025-12-10 |       46.98 |      426.48 |
| 2025-12-22 |       39.78 |      426.48 |
| 2026-01-03 |       36.22 |      426.48 |
| 2026-01-15 |       33.58 |      426.48 |
| 2026-06-20 |       25.29 |      426.48 |
| 2026-07-02 |       24.06 |      426.48 |
| 2026-07-14 |       33.09 |      426.48 |
| 2026-07-26 |       53.80 |      426.48 |
| 2026-08-19 |       94.10 |      426.48 |
| 2026-08-31 |      131.24 |      426.48 |
| 2026-09-12 |      163.37 |      426.48 |
| 2026-09-24 |      148.68 |      426.48 |
| 2026-10-06 |      151.44 |      426.48 |
| 2026-10-18 |       76.86 |      426.48 |

**Assessment vs S2-derived change (TEST blocks; S2 pairs only)**

| pair                                | method       |       n |    oa |   gain_f1 |   gain_precision |   gain_recall |   loss_f1 |   loss_precision |   loss_recall |   stable_water_f1 |   stable_water_precision |   stable_water_recall |   ref_gain_km2 |   ref_loss_km2 |   map_gain_km2_test |   map_loss_km2_test |
|:------------------------------------|:-------------|--------:|------:|----------:|-----------------:|--------------:|----------:|-----------------:|--------------:|------------------:|-------------------------:|----------------------:|---------------:|---------------:|--------------------:|--------------------:|
| dry-season recession (S2 both)      | pcc          | 1248794 | 0.956 |     0.061 |            0.045 |         0.097 |     0.617 |            0.634 |         0.600 |             0.853 |                    0.803 |                 0.909 |          0.130 |          5.906 |               0.281 |               5.588 |
| dry-season recession (S2 both)      | logratio_3db | 1248794 | 0.878 |     0.002 |            0.001 |         0.061 |     0.576 |            0.668 |         0.506 |             0.780 |                    0.692 |                 0.894 |          0.130 |          5.906 |               9.412 |               4.469 |
| dry-season recession (S2 both)      | logratio_5db | 1248794 | 0.931 |     0.003 |            0.002 |         0.029 |     0.480 |            0.747 |         0.353 |             0.742 |                    0.613 |                 0.939 |          0.130 |          5.906 |               2.132 |               2.793 |
| dry season → post-monsoon (S2 both) | pcc          |  684471 | 0.921 |     0.722 |            0.781 |         0.672 |     0.347 |            0.442 |         0.286 |             0.817 |                    0.735 |                 0.920 |          8.749 |          0.664 |               7.521 |               0.430 |
| dry season → post-monsoon (S2 both) | logratio_3db |  684471 | 0.813 |     0.527 |            0.415 |         0.724 |     0.346 |            0.280 |         0.451 |             0.742 |                    0.718 |                 0.767 |          8.749 |          0.664 |              15.277 |               1.068 |
| dry season → post-monsoon (S2 both) | logratio_5db |  684471 | 0.856 |     0.509 |            0.504 |         0.514 |     0.327 |            0.445 |         0.259 |             0.792 |                    0.710 |                 0.896 |          8.749 |          0.664 |               8.918 |               0.386 |
| consecutive 2025-11-28→2025-12-10   | pcc          | 1220481 | 0.941 |     0.095 |            0.307 |         0.056 |     0.189 |            0.129 |         0.355 |             0.855 |                    0.889 |                 0.823 |          3.408 |          0.805 |               0.622 |               2.214 |
| consecutive 2025-11-28→2025-12-10   | logratio_3db | 1220481 | 0.882 |     0.029 |            0.021 |         0.046 |     0.184 |            0.142 |         0.261 |             0.816 |                    0.818 |                 0.815 |          3.408 |          0.805 |               7.437 |               1.482 |
| consecutive 2025-11-28→2025-12-10   | logratio_5db | 1220481 | 0.930 |     0.012 |            0.019 |         0.009 |     0.177 |            0.193 |         0.164 |             0.829 |                    0.800 |                 0.859 |          3.408 |          0.805 |               1.562 |               0.683 |
| consecutive 2026-01-03→2026-01-15   | pcc          | 1223916 | 0.974 |     0.030 |            0.019 |         0.067 |     0.354 |            0.335 |         0.377 |             0.835 |                    0.781 |                 0.898 |          0.112 |          1.139 |               0.389 |               1.281 |
| consecutive 2026-01-03→2026-01-15   | logratio_3db | 1223916 | 0.956 |     0.003 |            0.002 |         0.029 |     0.324 |            0.331 |         0.316 |             0.781 |                    0.720 |                 0.853 |          0.112 |          1.139 |               2.187 |               1.089 |
| consecutive 2026-01-03→2026-01-15   | logratio_5db | 1223916 | 0.972 |     0.001 |            0.001 |         0.003 |     0.268 |            0.490 |         0.184 |             0.793 |                    0.702 |                 0.912 |          0.112 |          1.139 |               0.296 |               0.428 |

**Mean over S2 pairs**

| method       |    oa |   gain_f1 |   loss_f1 |
|:-------------|------:|----------:|----------:|
| logratio_3db | 0.882 |     0.140 |     0.357 |
| logratio_5db | 0.922 |     0.132 |     0.313 |
| pcc          | 0.948 |     0.227 |     0.377 |

Figures:
- [change_logratio_3db_2025-11-28_2026-01-15.png](runs/20261109-225657/figures/change_logratio_3db_2025-11-28_2026-01-15.png)
- [change_logratio_3db_2026-01-15_2026-09-12.png](runs/20261109-225657/figures/change_logratio_3db_2026-01-15_2026-09-12.png)
- [change_logratio_3db_2026-01-15_2026-10-18.png](runs/20261109-225657/figures/change_logratio_3db_2026-01-15_2026-10-18.png)
- [change_logratio_3db_2026-06-20_2026-09-12.png](runs/20261109-225657/figures/change_logratio_3db_2026-06-20_2026-09-12.png)
- [change_logratio_3db_2026-09-12_2026-10-18.png](runs/20261109-225657/figures/change_logratio_3db_2026-09-12_2026-10-18.png)
- [change_logratio_5db_2025-11-28_2026-01-15.png](runs/20261109-225657/figures/change_logratio_5db_2025-11-28_2026-01-15.png)
- [change_logratio_5db_2026-01-15_2026-09-12.png](runs/20261109-225657/figures/change_logratio_5db_2026-01-15_2026-09-12.png)
- [change_logratio_5db_2026-01-15_2026-10-18.png](runs/20261109-225657/figures/change_logratio_5db_2026-01-15_2026-10-18.png)
- [change_logratio_5db_2026-06-20_2026-09-12.png](runs/20261109-225657/figures/change_logratio_5db_2026-06-20_2026-09-12.png)
- [change_logratio_5db_2026-09-12_2026-10-18.png](runs/20261109-225657/figures/change_logratio_5db_2026-09-12_2026-10-18.png)
- [change_pcc_2025-11-28_2026-01-15.png](runs/20261109-225657/figures/change_pcc_2025-11-28_2026-01-15.png)
- [change_pcc_2026-01-15_2026-09-12.png](runs/20261109-225657/figures/change_pcc_2026-01-15_2026-09-12.png)
- [change_pcc_2026-01-15_2026-10-18.png](runs/20261109-225657/figures/change_pcc_2026-01-15_2026-10-18.png)
- [change_pcc_2026-06-20_2026-09-12.png](runs/20261109-225657/figures/change_pcc_2026-06-20_2026-09-12.png)
- [change_pcc_2026-09-12_2026-10-18.png](runs/20261109-225657/figures/change_pcc_2026-09-12_2026-10-18.png)
- [new_water_logratio_3db_2025-11-28_2026-01-15.png](runs/20261109-225657/figures/new_water_logratio_3db_2025-11-28_2026-01-15.png)
- [new_water_logratio_3db_2026-01-15_2026-09-12.png](runs/20261109-225657/figures/new_water_logratio_3db_2026-01-15_2026-09-12.png)
- [new_water_logratio_3db_2026-01-15_2026-10-18.png](runs/20261109-225657/figures/new_water_logratio_3db_2026-01-15_2026-10-18.png)
- [new_water_logratio_3db_2026-06-20_2026-09-12.png](runs/20261109-225657/figures/new_water_logratio_3db_2026-06-20_2026-09-12.png)
- [new_water_logratio_3db_2026-09-12_2026-10-18.png](runs/20261109-225657/figures/new_water_logratio_3db_2026-09-12_2026-10-18.png)
- [new_water_logratio_5db_2025-11-28_2026-01-15.png](runs/20261109-225657/figures/new_water_logratio_5db_2025-11-28_2026-01-15.png)
- [new_water_logratio_5db_2026-01-15_2026-09-12.png](runs/20261109-225657/figures/new_water_logratio_5db_2026-01-15_2026-09-12.png)
- [new_water_logratio_5db_2026-01-15_2026-10-18.png](runs/20261109-225657/figures/new_water_logratio_5db_2026-01-15_2026-10-18.png)
- [new_water_logratio_5db_2026-06-20_2026-09-12.png](runs/20261109-225657/figures/new_water_logratio_5db_2026-06-20_2026-09-12.png)
- [new_water_logratio_5db_2026-09-12_2026-10-18.png](runs/20261109-225657/figures/new_water_logratio_5db_2026-09-12_2026-10-18.png)
- [new_water_pcc_2025-11-28_2026-01-15.png](runs/20261109-225657/figures/new_water_pcc_2025-11-28_2026-01-15.png)
- [new_water_pcc_2026-01-15_2026-09-12.png](runs/20261109-225657/figures/new_water_pcc_2026-01-15_2026-09-12.png)
- [new_water_pcc_2026-01-15_2026-10-18.png](runs/20261109-225657/figures/new_water_pcc_2026-01-15_2026-10-18.png)
- [new_water_pcc_2026-06-20_2026-09-12.png](runs/20261109-225657/figures/new_water_pcc_2026-06-20_2026-09-12.png)
- [new_water_pcc_2026-09-12_2026-10-18.png](runs/20261109-225657/figures/new_water_pcc_2026-09-12_2026-10-18.png)
- [water_occurrence.png](runs/20261109-225657/figures/water_occurrence.png)
<!-- RESULTS:END -->

## Observations and failure modes
- PCC is best on every summary metric. On the one S2 pair with substantial real change (2026-01-15 → 2026-10-18: 8.75 km² S2 gain in test blocks), PCC gain F1 = 0.72 (precision/recall balanced, 7.5 vs 8.75 km²).
- Log-ratio over-detects gain at 3 dB (speckle and crop/soil-moisture changes darken fields) and still trails PCC at 5 dB.
- Gain F1 on the dry-season pairs is near zero but meaningless: S2 shows almost no gain there (0.1 km²), so any false gain dominates.
- Dry season → monsoon peak (01-15 → 09-12): 131 km² gain, 130 km² of it outside persistent water. This is **newly detected water**; it is consistent with seasonal inundation of the floodplain, but the maps alone do not establish the cause (rainfall, river overflow, irrigation, or classification error in rough/vegetated water).
- Peak → recession (09-12 → 10-18): 90 km² water loss, 3.7 km² gain.
- Change accuracy in the monsoon cannot be measured (no S2); it inherits the C3 monsoon uncertainty (S1 agreement 0.74–0.82).

## Decision
PCC on the champion masks is the change method for L10 and the submission.
