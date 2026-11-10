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
- [jrc_occurrence.png](figures/jrc_occurrence.png)
- [jrc_persistent.png](figures/jrc_persistent.png)
- [persistent_water.png](figures/persistent_water.png)
- [s1_water_2025-11-28.png](figures/s1_water_2025-11-28.png)
- [s1_water_2025-11-30.png](figures/s1_water_2025-11-30.png)
- [s1_water_2025-12-10.png](figures/s1_water_2025-12-10.png)
- [s1_water_2026-01-03.png](figures/s1_water_2026-01-03.png)
- [s1_water_2026-01-05.png](figures/s1_water_2026-01-05.png)
- [s1_water_2026-01-15.png](figures/s1_water_2026-01-15.png)
- [s1_water_2026-01-17.png](figures/s1_water_2026-01-17.png)
- [s1_water_2026-06-22.png](figures/s1_water_2026-06-22.png)
- [s1_water_2026-10-18.png](figures/s1_water_2026-10-18.png)
- [s1_water_2026-10-20.png](figures/s1_water_2026-10-20.png)
- [s2_availability.png](figures/s2_availability.png)
- [s2_rgb_2025-11-28.png](figures/s2_rgb_2025-11-28.png)
- [s2_rgb_2025-11-30.png](figures/s2_rgb_2025-11-30.png)
- [s2_rgb_2025-12-10.png](figures/s2_rgb_2025-12-10.png)
- [s2_rgb_2026-01-03.png](figures/s2_rgb_2026-01-03.png)
- [s2_rgb_2026-01-05.png](figures/s2_rgb_2026-01-05.png)
- [s2_rgb_2026-01-15.png](figures/s2_rgb_2026-01-15.png)
- [s2_rgb_2026-01-17.png](figures/s2_rgb_2026-01-17.png)
- [s2_rgb_2026-06-22.png](figures/s2_rgb_2026-06-22.png)
- [s2_rgb_2026-10-18.png](figures/s2_rgb_2026-10-18.png)
- [s2_rgb_2026-10-20.png](figures/s2_rgb_2026-10-20.png)
- [s2_water_2025-11-28.png](figures/s2_water_2025-11-28.png)
- [s2_water_2025-11-30.png](figures/s2_water_2025-11-30.png)
- [s2_water_2025-12-10.png](figures/s2_water_2025-12-10.png)
- [s2_water_2026-01-03.png](figures/s2_water_2026-01-03.png)
- [s2_water_2026-01-05.png](figures/s2_water_2026-01-05.png)
- [s2_water_2026-01-15.png](figures/s2_water_2026-01-15.png)
- [s2_water_2026-01-17.png](figures/s2_water_2026-01-17.png)
- [s2_water_2026-06-22.png](figures/s2_water_2026-06-22.png)
- [s2_water_2026-10-18.png](figures/s2_water_2026-10-18.png)
- [s2_water_2026-10-20.png](figures/s2_water_2026-10-20.png)
- [split_blocks.png](figures/split_blocks.png)
