# L10b_change_full_footprint

**Status:** done  <!-- planned | running | done | abandoned -->
**Decision:** adopt: PCC change and new-water maps over the full frame from the L10 iteration-3 masks; headline areas reported for the floodplain belt, southern-plain areas indicative  <!-- adopt | reject | iterate — one line why -->
**Owner / date:** nisar_analysis team, 2026-11-10

## Question / hypothesis
Change classes (stable water, gain, loss, stable non-water) and newly detected water outside persistent water over the full asc 98/14 frame, using the L10 masks (Tasks D, E on the full footprint).

## Data
- Water masks: L10_full_footprint run 20261110-224243 (`water`, 20 m, 15 dates, iteration 3).
- Persistent water: from the same run (NISAR water on ≥ 4 of 5 dry dates ∪ JRC GSW ≥ 50 %, 2,806 km²), because the R00 S2 persistent mask covers the box only.
- No change reference over the frame (S2-derived change exists only in the box, L09).

## Method & parameters
Post-classification comparison (the L09 winner: OA 0.948 vs S2-derived change in the box), same pairs as L09 plus all consecutive pairs. Occurrence (% of valid dates water) is accumulated incrementally to bound memory. Zone areas (`tables/change_areas_by_zone.csv`) split the frame at northing 2,775 km (floodplain belt vs southern plain, see L10).

## Baseline compared against
L09 PCC in the reference box (same rules, 10 m, C3 masks).

## Results
Auto-filled by `uv run nisar-water report <ID>` from the latest run. Do not edit inside the markers.
<!-- RESULTS:START -->
Run: `experiments/L10b_change_full_footprint/runs/20261110-224723`

**Headline:** no S2-referenced pairs = nan

| metric | value |
|---|---|
| source_run | experiments/L10_full_footprint/runs/20261110-224243 |

**Change-class areas per pair (km², full bbox)**

| pair                                | method   |   Stable non-water (km²) |   Stable water (km²) |   Newly detected water (gain) (km²) |   Water loss (receded) (km²) |   New water outside persistent (km²) |
|:------------------------------------|:---------|-------------------------:|---------------------:|------------------------------------:|-----------------------------:|-------------------------------------:|
| dry-season recession (S2 both)      | pcc      |                 55138.96 |              2241.12 |                              178.90 |                       510.22 |                               151.75 |
| dry season → post-monsoon (S2 both) | pcc      |                 53980.48 |              1290.26 |                              743.38 |                       515.03 |                               644.13 |
| dry season → monsoon peak           | pcc      |                 51183.19 |              1556.43 |                             3824.68 |                       264.36 |                              3655.79 |
| pre-monsoon → monsoon peak          | pcc      |                 52345.57 |              1474.75 |                             4092.26 |                       201.92 |                              3678.07 |
| monsoon peak → recession            | pcc      |                 52146.38 |              1989.51 |                               97.03 |                      3541.13 |                                73.41 |
| consecutive 2025-11-28→2025-12-10   | pcc      |                 55177.16 |              2229.36 |                              140.13 |                       487.00 |                               114.37 |
| consecutive 2025-12-10→2025-12-22   | pcc      |                 55465.55 |              1979.94 |                              161.56 |                       372.22 |                               116.76 |
| consecutive 2025-12-22→2026-01-03   | pcc      |                 55535.98 |              1972.65 |                              309.69 |                       204.55 |                               174.11 |
| consecutive 2026-01-03→2026-01-15   | pcc      |                 55241.14 |              2125.07 |                              288.39 |                       159.78 |                               226.52 |
| consecutive 2026-01-15→2026-06-20   | pcc      |                 53780.53 |              1262.81 |                              356.48 |                       508.50 |                               326.41 |
| consecutive 2026-06-20→2026-07-02   | pcc      |                 56992.09 |              1054.27 |                              173.95 |                       639.98 |                               120.56 |
| consecutive 2026-07-02→2026-07-14   | pcc      |                 54593.85 |              1134.46 |                             1970.07 |                        61.24 |                              1522.92 |
| consecutive 2026-07-14→2026-07-26   | pcc      |                 51837.72 |              2536.78 |                             2074.79 |                       506.27 |                              1970.86 |
| consecutive 2026-07-26→2026-08-19   | pcc      |                 50955.19 |              2544.59 |                             2055.50 |                      2107.69 |                              1953.21 |
| consecutive 2026-08-19→2026-08-31   | pcc      |                 50050.39 |              3854.74 |                             3115.70 |                       751.93 |                              2976.56 |
| consecutive 2026-08-31→2026-09-12   | pcc      |                 50343.53 |              3958.93 |                             1638.41 |                      3085.66 |                              1557.63 |
| consecutive 2026-09-12→2026-09-24   | pcc      |                 52411.56 |              4124.66 |                             1254.18 |                      1488.79 |                              1189.98 |
| consecutive 2026-09-24→2026-10-06   | pcc      |                 53316.01 |              3368.90 |                              453.63 |                      1994.78 |                               410.89 |
| consecutive 2026-10-06→2026-10-18   | pcc      |                 53927.64 |              2005.08 |                               81.46 |                      1759.34 |                                58.95 |

**Water area per date (km²)**

| date       |   water_km2 |   valid_km2 |
|:-----------|------------:|------------:|
| 2025-11-28 |     2812.84 |    59688.84 |
| 2025-12-10 |     2373.62 |    58068.27 |
| 2025-12-22 |     2236.21 |    59638.05 |
| 2026-01-03 |     2311.91 |    58091.55 |
| 2026-01-15 |     2420.22 |    58073.95 |
| 2026-06-20 |     1711.46 |    59422.37 |
| 2026-07-02 |     1245.84 |    59425.26 |
| 2026-07-14 |     3105.00 |    57775.15 |
| 2026-07-26 |     4664.42 |    57774.93 |
| 2026-08-19 |     4606.74 |    57775.85 |
| 2026-08-31 |     7060.05 |    59427.05 |
| 2026-09-12 |     5622.02 |    59426.06 |
| 2026-09-24 |     5383.03 |    59425.04 |
| 2026-10-06 |     3828.42 |    59427.95 |
| 2026-10-18 |     2086.59 |    57778.19 |

Figures:
- [change_pcc_2025-11-28_2026-01-15.png](runs/20261110-224723/figures/change_pcc_2025-11-28_2026-01-15.png)
- [change_pcc_2026-01-15_2026-09-12.png](runs/20261110-224723/figures/change_pcc_2026-01-15_2026-09-12.png)
- [change_pcc_2026-01-15_2026-10-18.png](runs/20261110-224723/figures/change_pcc_2026-01-15_2026-10-18.png)
- [change_pcc_2026-06-20_2026-09-12.png](runs/20261110-224723/figures/change_pcc_2026-06-20_2026-09-12.png)
- [change_pcc_2026-09-12_2026-10-18.png](runs/20261110-224723/figures/change_pcc_2026-09-12_2026-10-18.png)
- [new_water_pcc_2025-11-28_2026-01-15.png](runs/20261110-224723/figures/new_water_pcc_2025-11-28_2026-01-15.png)
- [new_water_pcc_2026-01-15_2026-09-12.png](runs/20261110-224723/figures/new_water_pcc_2026-01-15_2026-09-12.png)
- [new_water_pcc_2026-01-15_2026-10-18.png](runs/20261110-224723/figures/new_water_pcc_2026-01-15_2026-10-18.png)
- [new_water_pcc_2026-06-20_2026-09-12.png](runs/20261110-224723/figures/new_water_pcc_2026-06-20_2026-09-12.png)
- [new_water_pcc_2026-09-12_2026-10-18.png](runs/20261110-224723/figures/new_water_pcc_2026-09-12_2026-10-18.png)
- [water_occurrence.png](runs/20261110-224723/figures/water_occurrence.png)
<!-- RESULTS:END -->

## Observations & failure modes
Change areas by zone (km², `tables/change_areas_by_zone.csv`; L10 iteration 3 masks):

| Pair | Belt stable water | Belt gain | Belt loss | Belt new outside persistent | South new outside persistent* |
|---|---:|---:|---:|---:|---:|
| 2025-11-28 → 2026-01-15 | 669 | 38 | 314 | 27 | 125 |
| 2026-01-15 → 2026-09-12 | 601 | 3,203 | 31 | 3,048 | 608 |
| 2026-09-12 → 2026-10-18 | 1,194 | 66 | 2,772 | 57 | 16 |
| 2026-01-15 → 2026-10-18 | 542 | 665 | 90 | 574 | 70 |
| 2026-06-20 → 2026-09-12 | 671 | 3,365 | 68 | 3,098 | 580 |

\*Southern plain still includes commission error (L10: precision 0.33 vs S2 on 01-15); indicative only.
- The belt gain pattern (Ganga and Kosi floodplain belts, oxbows south of the channel) matches L09 in the box; it is reported as *newly detected water*, not attributed to flooding.
- With the box-calibrated threshold (L10 iteration 3) the early-monsoon date 2026-06-20 is no longer inflated (iteration 2: +12,168 km² of gain 01-15 → 06-20 over the frame).

## Next step
Recompute after L10 is retrained for the southern plain; sample-based (Olofsson) area estimates need a frame-wide change reference.
