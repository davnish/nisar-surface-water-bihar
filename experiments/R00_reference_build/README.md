# R00_reference_build

**Status:** done  <!-- planned | running | done | abandoned -->
**Decision:** adopt iteration 4 (run 20261026-002406): 10/28 NISAR dates have an S2 reference; persistent water from dry-season S2  <!-- adopt | reject | iterate — one line why -->
**Owner / date:** nischal, 2026-10-25

## Question / hypothesis
For each NISAR acquisition (asc 98/14 and desc 120/76), can we build an independent, near-coincident reference water mask good enough to compute F1/IoU? Which NISAR dates can actually be validated, given monsoon cloud cover?

Supporting layers built here:
- persistent water, for the "new water outside persistent water" task;
- Sentinel-1 water maps, as a cross-sensor comparison only, never as truth;
- a spatial-block train/test split.

## Data
- **NISAR acquisitions:** taken from the latest L00 `inventory.csv` (tracks 98 and 120).
- **Grid:** `configs/grid_bbox.yaml`, the asc 98/14 bbox window: EPSG:32645, 10 m, 2006 × 2126 px. Every 98/14 granule shares this grid. The 120/76 QPDH 20 m pixels are exact 2 × 2 aggregates of it.
- **Sentinel-2 L2A** (Planetary Computer, tile 45RVJ): B02/B03/B04/B08 at 10 m, B11 and SCL at 20 m.
  - Processing-baseline ≥ 04.00 DN offset (−1000) is removed.
  - Limitation: an optical water extent misses water under vegetation canopy, which L-band can see. Expect L-band "false positives" that are actually real flooded vegetation.
- **JRC Global Surface Water v1.3** (Pekel et al. 2016): occurrence 1984–2020 at 30 m, resampled nearest to 10 m.
  - Limitation: it's a climatology that ends in 2020. Rivers here migrate, so the persistent-water mask is approximate along active channels.
- **Sentinel-1 RTC** (Planetary Computer): VV γ0, 10 m. Used for comparison only.
- **Outputs:** `data/reference/` (git-ignored, reproducible from this config).
  - `s2_water_<nisar date>.tif`, `s1_water_<nisar date>.tif`, `jrc_occurrence.tif`, `jrc_persistent.tif`, `split_blocks.tif`.
  - Dates are the NISAR **UTC** start date. Asc 98/14 passes at ~23:38 UTC, i.e. 05:08 IST the next day.

## Method & parameters
The final method is iteration 4; how it got there is under *Iteration history* below. All parameters are in `config.yaml`.

**Sentinel-2 reference** (`tasks/reference.py`, `io/ancillary.py`):
1. **Candidates:** every S2 L2A scene within ±3 days of the NISAR acquisition, with times compared in hours.
2. **Clear-sky mask:**
   - SCL valid: not nodata, defective, cloud shadow, cloud medium/high or cirrus;
   - **and** not bright-white: cloud = B02 > 0.2 ∧ B02/B04 ≥ 0.85;
   - plus a 200 m disk buffer around invalid clusters ≥ 1 ha.
3. **Scene choice:** the largest clear fraction wins; ties go to the smallest |Δt|. Built if the clear fraction is ≥ 30%. Cloudy pixels are set to 255 and never scored.
4. **Water:** MNDWI > 0 (Xu 2006). MNDWI is chosen over NDWI because SWIR suppresses soil and built-up false positives.
5. **QC gate:** rejected if the MNDWI and NDWI > 0 water maps disagree (F1 < 0.5).
6. **Diagnostics recorded:** F1 against S2's own SCL water class, the MNDWI Otsu threshold, and recall of JRC persistent water.

**Persistent water:**
- water in every clear dry-season (Nov–Mar) S2 reference, with ≥ 2 clear observations per pixel;
- each S2 scene counts once (two NISAR dates can share one scene).

**JRC GSW:** occurrence ≥ 75% is kept as context only.

**Sentinel-1 comparison:** nearest RTC scene within ±6 days. Water = VV dB below a tiled bimodal threshold (`classify/threshold.py::tiled`: 256 px tiles, Ashman D ≥ 2, the 10 most bimodal tiles pooled).

**Split:**
- 2 km blocks, 30% test, stratified on persistent-water presence (seed 42);
- every later experiment tunes on train blocks and reports test blocks only.

## Results
Auto-filled by `uv run nisar-water report <ID>` from the latest run. Do not edit inside the markers.
<!-- RESULTS:START -->
Run: `experiments/R00_reference_build/runs/20261026-002406`

**Headline:** NISAR dates with S2 reference = 10/28

| metric | value |
|---|---|
| n_nisar_acquisitions | 28 |
| n_s2_reference | 10 |
| n_s2_rejected_qc | 0 |
| n_s1_comparison | 28 |
| persistent_water_km2 | 27.8333 |
| persistent_water_dates | 2025-11-28, 2025-11-30, 2025-12-10, 2026-01-03, 2026-01-15 |
| jrc_persistent_water_km2 | 1.0390 |
| test_block_fraction | 0.2945 |

**Reference availability per NISAR acquisition**

| nisar_date   | nisar_time_utc   |   track | pol   | s2_scene                                               |   s2_clear_frac |   s2_dt_hours | s2_built   | s2_status   |   f1_vs_ndwi |   s2_water_frac |   mndwi_otsu |   f1_vs_scl_water |   recall_of_jrc_persistent | s1_scene                                                           |   s1_dt_hours |   s1_vv_threshold_db |   s1_tiles_used | s1_built   |
|:-------------|:-----------------|--------:|:------|:-------------------------------------------------------|----------------:|--------------:|:-----------|:------------|-------------:|----------------:|-------------:|------------------:|---------------------------:|:-------------------------------------------------------------------|--------------:|---------------------:|----------------:|:-----------|
| 2025-11-28   | 23:38            |      98 | DHDH  | S2B_MSIL2A_20251127T045029_R076_T45RVJ_20251127T065028 |           0.998 |        42.800 | True       | built       |        0.880 |           0.116 |        0.149 |             0.517 |                      0.886 | S1A_IW_GRDH_1SDV_20251130T122135_20251130T122200_062107_07C58F_rtc |        36.700 |              -14.850 |              10 | True       |
| 2025-11-30   | 12:51            |     120 | QPDH  | S2C_MSIL2A_20251202T045151_R076_T45RVJ_20251202T082114 |           0.995 |        40.000 | True       | built       |        0.881 |           0.110 |        0.114 |             0.483 |                      0.891 | S1A_IW_GRDH_1SDV_20251130T122135_20251130T122200_062107_07C58F_rtc |         0.500 |              -14.850 |              10 | True       |
| 2025-12-10   | 23:38            |      98 | DHDH  | S2C_MSIL2A_20251212T045221_R076_T45RVJ_20251212T081316 |           0.968 |        29.200 | True       | built       |        0.753 |           0.119 |        0.132 |             0.426 |                      0.898 | S1A_IW_GRDH_1SDV_20251212T122134_20251212T122159_062282_07CC69_rtc |        36.700 |              -15.030 |              10 | True       |
| 2025-12-22   | 23:38            |      98 | DHDH  | S2C_MSIL2A_20251222T045221_R076_T45RVJ_20251222T082510 |           0.000 |        18.800 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1A_IW_GRDH_1SDV_20251224T122132_20251224T122157_062457_07D32E_rtc |        36.700 |              -13.940 |              10 | True       |
| 2025-12-24   | 12:51            |     120 | QPDH  | S2A_MSIL2A_20251224T045241_R076_T45RVJ_20251224T080610 |           0.000 |         8.000 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1A_IW_GRDH_1SDV_20251224T122132_20251224T122157_062457_07D32E_rtc |         0.500 |              -13.940 |              10 | True       |
| 2026-01-03   | 23:38            |      98 | DHDH  | S2B_MSIL2A_20260106T045109_R076_T45RVJ_20260106T083404 |           0.958 |        53.200 | True       | built       |        0.825 |           0.056 |        0.041 |             0.254 |                      0.863 | S1A_IW_GRDH_1SDV_20260108T001209_20260108T001234_062668_07DB61_rtc |        96.600 |              -11.740 |              10 | True       |
| 2026-01-05   | 12:51            |     120 | QPDH  | S2B_MSIL2A_20260106T045109_R076_T45RVJ_20260106T083404 |           0.958 |        16.000 | True       | built       |        0.825 |           0.056 |        0.041 |             0.254 |                      0.863 | S1A_IW_GRDH_1SDV_20260108T001209_20260108T001234_062668_07DB61_rtc |        59.400 |              -11.740 |              10 | True       |
| 2026-01-15   | 23:38            |      98 | DHDH  | S2B_MSIL2A_20260116T045039_R076_T45RVJ_20260116T074038 |           0.997 |         5.200 | True       | built       |        0.922 |           0.065 |        0.127 |             0.316 |                      0.813 | S1A_IW_GRDH_1SDV_20260117T122130_20260117T122155_062807_07E0AD_rtc |        36.700 |              -14.570 |              10 | True       |
| 2026-01-17   | 12:51            |     120 | QPDH  | S2B_MSIL2A_20260116T045039_R076_T45RVJ_20260116T074038 |           0.997 |        32.000 | True       | built       |        0.922 |           0.065 |        0.127 |             0.316 |                      0.813 | S1A_IW_GRDH_1SDV_20260117T122130_20260117T122155_062807_07E0AD_rtc |         0.500 |              -14.570 |              10 | True       |
| 2026-06-20   | 23:38            |      98 | DHDH  | S2C_MSIL2A_20260620T044701_R076_T45RVJ_20260620T095614 |           0.003 |        18.900 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1A_IW_GRDH_1SDV_20260622T122128_20260622T122153_065082_083408_rtc |        36.700 |              -14.080 |              10 | True       |
| 2026-06-22   | 12:51            |     120 | QPDH  | S2B_MSIL2A_20260625T044659_R076_T45RVJ_20260625T083525 |           0.884 |        63.900 | True       | built       |        0.776 |           0.022 |       -0.343 |             0.239 |                      0.795 | S1A_IW_GRDH_1SDV_20260622T122128_20260622T122153_065082_083408_rtc |         0.500 |              -14.080 |              10 | True       |
| 2026-07-02   | 23:38            |      98 | DHDH  | S2A_MSIL2A_20260702T045241_R076_T45RVJ_20260702T095512 |           0.082 |        18.800 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1D_IW_GRDH_1SDV_20260702T001124_20260702T001149_003487_0062AB_rtc |        23.400 |              -11.670 |              10 | True       |
| 2026-07-04   | 12:50            |     120 | DHDH  | S2A_MSIL2A_20260702T045241_R076_T45RVJ_20260702T095512 |           0.082 |        56.000 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1D_IW_GRDH_1SDV_20260702T001124_20260702T001149_003487_0062AB_rtc |        60.700 |              -11.670 |              10 | True       |
| 2026-07-14   | 23:38            |      98 | DHDH  | S2B_MSIL2A_20260715T044659_R076_T45RVJ_20260715T083355 |           0.025 |         5.100 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1D_IW_GRDH_1SDV_20260714T001125_20260714T001150_003662_00689F_rtc |        23.400 |              -11.770 |              10 | True       |
| 2026-07-16   | 12:50            |     120 | DHDH  | S2B_MSIL2A_20260715T044659_R076_T45RVJ_20260715T083355 |           0.025 |        32.100 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1D_IW_GRDH_1SDV_20260714T001125_20260714T001150_003662_00689F_rtc |        60.700 |              -11.770 |              10 | True       |
| 2026-07-26   | 23:38            |      98 | DHDH  | S2B_MSIL2A_20260725T044659_R076_T45RVJ_20260725T083358 |           0.026 |        42.900 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1D_IW_GRDH_1SDV_20260726T001126_20260726T001151_003837_006EA0_rtc |        23.400 |              -13.480 |              10 | True       |
| 2026-08-19   | 23:38            |      98 | DHDH  | S2C_MSIL2A_20260819T044701_R076_T45RVJ_20260819T095714 |           0.040 |        18.900 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1D_IW_GRDH_1SDV_20260819T001126_20260819T001151_004187_007ABD_rtc |        23.400 |              -11.700 |              10 | True       |
| 2026-08-21   | 12:51            |     120 | QPDH  | S2B_MSIL2A_20260824T044659_R076_T45RVJ_20260824T082928 |           0.081 |        63.900 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1D_IW_GRDH_1SDV_20260819T001126_20260819T001151_004187_007ABD_rtc |        60.700 |              -11.700 |              10 | True       |
| 2026-08-31   | 23:38            |      98 | DHDH  | S2B_MSIL2A_20260903T044659_R076_T45RVJ_20260903T084603 |           0.017 |        53.100 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1D_IW_GRDH_1SDV_20260831T001127_20260831T001152_004362_0080EC_rtc |        23.400 |              -11.900 |              10 | True       |
| 2026-09-02   | 12:50            |     120 | QPDH  | S2B_MSIL2A_20260903T044659_R076_T45RVJ_20260903T084603 |           0.017 |        15.900 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1D_IW_GRDH_1SDV_20260831T001127_20260831T001152_004362_0080EC_rtc |        60.700 |              -11.900 |              10 | True       |
| 2026-09-12   | 23:38            |      98 | DHDH  | S2B_MSIL2A_20260913T044659_R076_T45RVJ_20260913T084712 |           0.136 |         5.100 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1D_IW_GRDH_1SDV_20260912T001128_20260912T001153_004537_008704_rtc |        23.400 |              -12.110 |              10 | True       |
| 2026-09-14   | 12:50            |     120 | QPDH  | S2B_MSIL2A_20260913T044659_R076_T45RVJ_20260913T084712 |           0.136 |        32.100 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1D_IW_GRDH_1SDV_20260912T001128_20260912T001153_004537_008704_rtc |        60.700 |              -12.110 |              10 | True       |
| 2026-09-24   | 23:38            |      98 | DHDH  | S2B_MSIL2A_20260923T044659_R076_T45RVJ_20260923T084252 |           0.008 |        42.900 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1D_IW_GRDH_1SDV_20260924T001128_20260924T001153_004712_008D08_rtc |        23.400 |              -10.540 |              10 | True       |
| 2026-09-26   | 12:50            |     120 | QPDH  | S2C_MSIL2A_20260928T044701_R076_T45RVJ_20260928T075011 |           0.173 |        39.900 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1D_IW_GRDH_1SDV_20260924T001128_20260924T001153_004712_008D08_rtc |        60.700 |              -10.540 |              10 | True       |
| 2026-10-06   | 23:38            |      98 | DHDH  | S2C_MSIL2A_20261008T044701_R076_T45RVJ_20261008T074850 |           0.000 |        29.100 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1D_IW_GRDH_1SDV_20261006T001128_20261006T001153_004887_009321_rtc |        23.400 |              -12.110 |              10 | True       |
| 2026-10-08   | 12:50            |     120 | DHDH  | S2C_MSIL2A_20261008T044701_R076_T45RVJ_20261008T074850 |           0.000 |         8.100 | False      | too_cloudy  |      nan     |         nan     |      nan     |           nan     |                    nan     | S1D_IW_GRDH_1SDV_20261006T001128_20261006T001153_004887_009321_rtc |        60.700 |              -12.110 |              10 | True       |
| 2026-10-18   | 23:38            |      98 | DHDH  | S2C_MSIL2A_20261018T044811_R076_T45RVJ_20261018T074216 |           0.503 |        18.800 | True       | built       |        0.874 |           0.193 |        0.096 |             0.678 |                      0.916 | S1D_IW_GRDH_1SDV_20261018T001128_20261018T001153_005062_009936_rtc |        23.400 |              -13.420 |              10 | True       |
| 2026-10-20   | 12:50            |     120 | DHDH  | S2B_MSIL2A_20261023T044839_R076_T45RVJ_20261023T083740 |           1.000 |        64.000 | True       | built       |        0.858 |           0.161 |        0.140 |             0.625 |                      0.895 | S1D_IW_GRDH_1SDV_20261018T001128_20261018T001153_005062_009936_rtc |        60.700 |              -13.420 |              10 | True       |

Figures:
- [jrc_occurrence.png](runs/20261026-002406/figures/jrc_occurrence.png)
- [jrc_persistent.png](runs/20261026-002406/figures/jrc_persistent.png)
- [persistent_water.png](runs/20261026-002406/figures/persistent_water.png)
- [s1_water_2025-11-28.png](runs/20261026-002406/figures/s1_water_2025-11-28.png)
- [s1_water_2025-11-30.png](runs/20261026-002406/figures/s1_water_2025-11-30.png)
- [s1_water_2025-12-10.png](runs/20261026-002406/figures/s1_water_2025-12-10.png)
- [s1_water_2026-01-03.png](runs/20261026-002406/figures/s1_water_2026-01-03.png)
- [s1_water_2026-01-05.png](runs/20261026-002406/figures/s1_water_2026-01-05.png)
- [s1_water_2026-01-15.png](runs/20261026-002406/figures/s1_water_2026-01-15.png)
- [s1_water_2026-01-17.png](runs/20261026-002406/figures/s1_water_2026-01-17.png)
- [s1_water_2026-06-22.png](runs/20261026-002406/figures/s1_water_2026-06-22.png)
- [s1_water_2026-10-18.png](runs/20261026-002406/figures/s1_water_2026-10-18.png)
- [s1_water_2026-10-20.png](runs/20261026-002406/figures/s1_water_2026-10-20.png)
- [s2_availability.png](runs/20261026-002406/figures/s2_availability.png)
- [s2_rgb_2025-11-28.png](runs/20261026-002406/figures/s2_rgb_2025-11-28.png)
- [s2_rgb_2025-11-30.png](runs/20261026-002406/figures/s2_rgb_2025-11-30.png)
- [s2_rgb_2025-12-10.png](runs/20261026-002406/figures/s2_rgb_2025-12-10.png)
- [s2_rgb_2026-01-03.png](runs/20261026-002406/figures/s2_rgb_2026-01-03.png)
- [s2_rgb_2026-01-05.png](runs/20261026-002406/figures/s2_rgb_2026-01-05.png)
- [s2_rgb_2026-01-15.png](runs/20261026-002406/figures/s2_rgb_2026-01-15.png)
- [s2_rgb_2026-01-17.png](runs/20261026-002406/figures/s2_rgb_2026-01-17.png)
- [s2_rgb_2026-06-22.png](runs/20261026-002406/figures/s2_rgb_2026-06-22.png)
- [s2_rgb_2026-10-18.png](runs/20261026-002406/figures/s2_rgb_2026-10-18.png)
- [s2_rgb_2026-10-20.png](runs/20261026-002406/figures/s2_rgb_2026-10-20.png)
- [s2_water_2025-11-28.png](runs/20261026-002406/figures/s2_water_2025-11-28.png)
- [s2_water_2025-11-30.png](runs/20261026-002406/figures/s2_water_2025-11-30.png)
- [s2_water_2025-12-10.png](runs/20261026-002406/figures/s2_water_2025-12-10.png)
- [s2_water_2026-01-03.png](runs/20261026-002406/figures/s2_water_2026-01-03.png)
- [s2_water_2026-01-05.png](runs/20261026-002406/figures/s2_water_2026-01-05.png)
- [s2_water_2026-01-15.png](runs/20261026-002406/figures/s2_water_2026-01-15.png)
- [s2_water_2026-01-17.png](runs/20261026-002406/figures/s2_water_2026-01-17.png)
- [s2_water_2026-06-22.png](runs/20261026-002406/figures/s2_water_2026-06-22.png)
- [s2_water_2026-10-18.png](runs/20261026-002406/figures/s2_water_2026-10-18.png)
- [s2_water_2026-10-20.png](runs/20261026-002406/figures/s2_water_2026-10-20.png)
- [split_blocks.png](runs/20261026-002406/figures/split_blocks.png)
<!-- RESULTS:END -->

## Observations & failure modes
**What can be validated** (`figures/s2_availability.png`, `tables/reference_availability.csv`):

| Period | NISAR dates with S2 reference |
|---|---|
| Dry season | asc 98/14: 2025-11-28, 2025-12-10, 2026-01-03, 2026-01-15. desc 120/76: 2025-11-30, 2026-01-05, 2026-01-17 |
| Pre-monsoon | 2026-06-22 (desc, 88% clear) |
| Monsoon (2026-06-20 → 2026-10-08) | **none.** Every date has < 18% clear sky |
| Recession | 2026-10-18 (asc, 50% clear, partial) and 2026-10-20 (desc) |

- The only 98/14 dry → wet pairs that can be scored are the **dry season vs 2026-10-18 (recession)**. Monsoon-peak change maps will be assessed qualitatively and against S1.
- Reference quality on built dates:
  - MNDWI–NDWI F1 is 0.75–0.92;
  - the MNDWI Otsu threshold is 0.04–0.15, close to the fixed 0, except 06-22 (−0.34, a nearly unimodal histogram with very little water);
  - recall of JRC persistent water is 0.80–0.92.
  - SCL's own water class agrees poorly (F1 0.25–0.69). SCL is conservative on narrow channels, so it's diagnostic only.
- **Water extent:** 5.6–6.5% of the bbox in January, 11–12% in Nov–Dec, 19% on 10-18 (recession). The north-western oxbow complex is extensively wet on 10-18 (`figures/s2_water_2026-10-18.png`).
- **Δt:** S2 is 5–67 h from NISAR. 01-15 (5 h) is the best-matched pair; use it as the primary single-date test.
- **Persistent water:** 27.8 km² (S2 dry season) vs 1.0 km² (JRC ≥ 75%). The Ganga channel has migrated since the JRC record.
- **S1 tiled-threshold masks agree with S2:** F1 0.69–0.78 on clear dates. The exception is 06-22 (F1 0.40, S1 over-detects); S1 is 64 h earlier, so pre-monsoon rain or field flooding is possible.

**Iteration history** (runs kept in `runs/`; per-date maps of superseded runs are not committed):

| Iter | Run | Change | Why |
|---|---|---|---|
| 1 | 20261025-223016 | SCL only, ≥ 80% clear, JRC persistent water, global-Otsu S1 | baseline |
| 2 | 20261025-225253 | + brightness test (B02 > 0.2), 200 m buffer, ≥ 30% clear, MNDWI–NDWI QC, dry-season S2 persistent water, tiled S1 threshold | SCL called the 2026-01-01 cumulus scene 99.5% clear (`20261025-223016/figures/s2_rgb_2026-01-03.png`). JRC gave 1 km² of persistent water. Global Otsu on S1 split land classes (6/22: 29.5% water vs 2.4% in S2) |
| 3 | 20261025-232354 | brightness test → B02 > 0.2 **and** B02/B04 ≥ 0.85 | the brightness-only test plus buffer removed ~14% of clear scenes, mostly bright sand (SCL class 5; B02/B04 0.71–0.81 vs cloud 0.90–1.01) |
| 4 | **20261026-002406** | buffer only clusters ≥ 1 ha, disk kernel | SCL labels bright-sand specks on the Ganga as class 8 cloud; the square buffer punched 400 m holes into persistent water along the sand bars |

**Known limitations:**
- no monsoon reference;
- optical MNDWI misses water under vegetation;
- S2 B11 is 20 m, so edges of narrow channels are mixed;
- 10-18 is a partial (50%) reference, biased toward cloud-free areas.

## Next step
L01: channel separability (HH, HV, HV/HH, speckle filters, HV noise floor) on train blocks, using the 2026-01-15 (Δt 5 h) and 2026-10-18 references.
