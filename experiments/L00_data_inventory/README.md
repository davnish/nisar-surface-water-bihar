# L00_data_inventory

**Status:** done  <!-- planned | running | done | abandoned -->
**Decision:** adopt asc 98/14 (DHDH) as the L-band change-detection series, and desc 120/76 QPDH as the full-pol (L08) series; final date choice waits on the R00 cloud check  <!-- adopt | reject | iterate — one line why -->
**Owner / date:** nischal, 2026-10-25

## Question / hypothesis
Which NISAR L2 GCOV granules cover the reference AOI? For each one: date, direction, track/frame, mode, polarisations per frequency, footprint. Answers needed:
1. Do the problem-statement candidates (asc 98/14, desc 120/76) exist? Are other tracks available?
2. Is L-band quad-pol available, which decides L08's full-pol scope?
3. Which dates span low water (dry season), monsoon peak and recession, for change detection?

## Data
- ASF DAAC catalogue (`asf_search`, dataset NISAR, processingLevel GCOV), with the reference bbox as the intersect geometry and no date filter.
- HDF5 metadata was streamed for one granule per track/frame/mode (`profile_metadata: true` → `tables/metadata_profile.csv`).
- One bbox window was streamed via `nisar-water fetch` for a raster check: asc 98/14, 2026-01-15.

## Method & parameters
- `nisar_water.io.search.search_gcov`: one row per granule, with filename fields parsed by the vendored `nisar_utils.product.parse_filename`. Records the fraction of the bbox covered by each footprint.
- `dedupe`: one granule per (track, frame, acquisition minute, mode, pol code), preferring `PR` (production) over `UR` (urgent response), then the highest CRID. This removed 8 UR duplicates.
- The polarisation code is `<freqA><freqB>`. `DHDH` = HH/HV on both A and B. `QPDH` = quad-pol (HH/HV/VH/VV) on A, dual-pol on B. Mode `4005` = 40 MHz A + 5 MHz B; `2005` = 20 MHz A + 5 MHz B.

## Results
Auto-filled by `uv run nisar-water report <ID>` from the latest run. Do not edit inside the markers.
<!-- RESULTS:START -->
Run: `experiments/L00_data_inventory/runs/20261025-220021`

**Headline:** granules (deduplicated) = 64

| metric | value |
|---|---|
| n_granules_raw | 72 |
| n_granules_dedup | 64 |
| n_quad_pol | 27 |
| tracks_found | A 98/14, D 120/76, D 48/75, D 48/76 |
| tracks_not_in_problem_statement | D 48/75, D 48/76 |
| date_range | 2025-11-01 to 2026-10-20 |
| n_downloaded | 0 |

**Granules by track / mode**

| track_frame   | polarization_code   |   mode_code |   n | first      | last       |   median_bbox_cover |   size_gb |
|:--------------|:--------------------|------------:|----:|:-----------|:-----------|--------------------:|----------:|
| A 98/14       | DHDH                |        4005 |  15 | 2025-11-28 | 2026-10-18 |              1      |    103.58 |
| D 120/76      | DHDH                |        4005 |   4 | 2026-07-04 | 2026-10-20 |              1      |     28.59 |
| D 120/76      | QPDH                |        2005 |   9 | 2025-11-30 | 2026-09-26 |              1      |     77.38 |
| D 48/75       | DHDH                |        2005 |   5 | 2026-06-29 | 2026-10-15 |              0.578  |     10.15 |
| D 48/75       | DHDH                |        4005 |   6 | 2025-11-01 | 2026-10-15 |              0.593  |     21.19 |
| D 48/75       | QPDH                |        2005 |   9 | 2025-12-07 | 2026-10-03 |              0.614  |     54.29 |
| D 48/76       | DHDH                |        2005 |   1 | 2026-06-29 | 2026-06-29 |              0.408  |      1.9  |
| D 48/76       | DHDH                |        4005 |   6 | 2025-11-01 | 2026-10-15 |              0.5825 |     40.21 |
| D 48/76       | QPDH                |        2005 |   9 | 2025-12-07 | 2026-10-03 |              0.585  |     72.09 |

**Product metadata (one granule per track/frame/mode, streamed)**

| track_frame   | pol_code   | date       | frequency   | terms                                             |   posting_m | shape       |   epsg | isFullCovariance   | noiseCorrectionApplied   | radiometricTerrainCorrectionApplied   | shadowMaskingApplied   | faradayRotationApplied   | polarimetricSymmetrizationApplied   | postProcessingFilteringApplied   | rfiMitigationApplied   |
|:--------------|:-----------|:-----------|:------------|:--------------------------------------------------|------------:|:------------|-------:|:-------------------|:-------------------------|:--------------------------------------|:-----------------------|:-------------------------|:------------------------------------|:---------------------------------|:-----------------------|
| D 48/76       | DHDH       | 2026-06-29 | frequencyA  | HHHH,HVHV                                         |          20 | 17064x17352 |  32645 | False              | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| D 48/76       | DHDH       | 2026-06-29 | frequencyB  | HHHH,HVHV                                         |          80 | 4266x4338   |  32645 | False              | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| D 120/76      | QPDH       | 2026-09-26 | frequencyA  | HHHH,HHHV,HHVH,HHVV,HVHV,HVVH,HVVV,VHVH,VHVV,VVVV |          20 | 16920x17244 |  32645 | True               | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| D 120/76      | QPDH       | 2026-09-26 | frequencyB  | HHHH,HHHV,HVHV                                    |          80 | 4230x4311   |  32645 | True               | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| D 48/75       | QPDH       | 2026-10-03 | frequencyA  | HHHH,HHHV,HHVH,HHVV,HVHV,HVVH,HVVV,VHVH,VHVV,VVVV |          20 | 17100x17388 |  32645 | True               | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| D 48/75       | QPDH       | 2026-10-03 | frequencyB  | HHHH,HHHV,HVHV                                    |          80 | 4275x4347   |  32645 | True               | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| D 48/76       | QPDH       | 2026-10-03 | frequencyA  | HHHH,HHHV,HHVH,HHVV,HVHV,HVVH,HVVV,VHVH,VHVV,VVVV |          20 | 17064x17352 |  32645 | True               | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| D 48/76       | QPDH       | 2026-10-03 | frequencyB  | HHHH,HHHV,HVHV                                    |          80 | 4266x4338   |  32645 | True               | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| D 48/75       | DHDH       | 2026-10-15 | frequencyA  | HHHH,HVHV                                         |          20 | 17100x17388 |  32645 | False              | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| D 48/75       | DHDH       | 2026-10-15 | frequencyB  | HHHH,HVHV                                         |          80 | 4275x4347   |  32645 | False              | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| D 48/75       | DHDH       | 2026-10-15 | frequencyA  | HHHH,HVHV                                         |          10 | 34200x34776 |  32645 | False              | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| D 48/75       | DHDH       | 2026-10-15 | frequencyB  | HHHH,HVHV                                         |          80 | 4275x4347   |  32645 | False              | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| D 48/76       | DHDH       | 2026-10-15 | frequencyA  | HHHH,HVHV                                         |          10 | 34128x34704 |  32645 | False              | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| D 48/76       | DHDH       | 2026-10-15 | frequencyB  | HHHH,HVHV                                         |          80 | 4266x4338   |  32645 | False              | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| A 98/14       | DHDH       | 2026-10-18 | frequencyA  | HHHH,HVHV                                         |          10 | 33696x34344 |  32645 | False              | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| A 98/14       | DHDH       | 2026-10-18 | frequencyB  | HHHH,HVHV                                         |          80 | 4212x4293   |  32645 | False              | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| D 120/76      | DHDH       | 2026-10-20 | frequencyA  | HHHH,HVHV                                         |          10 | 33840x34488 |  32645 | False              | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |
| D 120/76      | DHDH       | 2026-10-20 | frequencyB  | HHHH,HVHV                                         |          80 | 4230x4311   |  32645 | False              | False                    | True                                  | False                  | False                    | False                               | False                            | False                  |

Figures:
- [acquisition_timeline.png](runs/20261025-220021/figures/acquisition_timeline.png)
- [footprints_vs_bbox.png](runs/20261025-220021/figures/footprints_vs_bbox.png)
<!-- RESULTS:END -->

## Observations & failure modes
- **Both problem-statement candidates exist, with full bbox coverage.** Asc 98/14 is DHDH every 12 days: 5 dates Nov 2025 – Jan 2026, then 10 dates Jun – Oct 2026. Desc 120/76 has 13 granules: 9 are QPDH, so **L-band full-pol is available**.
- **There is an extra track, desc 48 (frames 75/76), also with QPDH.** But the bbox sits on the corner of both frames (~0.6 coverage each), so it is not a primary candidate. Note it in the technical note only.
- **Gaps:** nothing from mid-Jan to mid-Jun 2026 on any track. Asc 98/14 also has a gap from 26 Jul to 19 Aug.
- **Asc/desc pairs within 2 days**, useful for geometry-sensitivity checks: 01-15/01-17, 08-19/08-21, 09-12/09-14, 09-24/09-26.
- **Mode differs between series.** 98/14 is always 4005, while the 120/76 QPDH dates are 2005 (20 MHz). Resolution differs, so asc-vs-desc comparisons must be resampled to a common grid.
- **Size:** ~7 GB per DHDH granule and ~8.5–9 GB per QPDH. The full asc series is ~104 GB.

**Confirmed from the product itself:**

| Item | Finding | Consequence |
|---|---|---|
| CRS | EPSG:32645 (UTM 45N) for every product | common grid, no reprojection |
| Posting, freq A | 10 m for mode 4005 (DHDH); 20 m for mode 2005 (QPDH, some DHDH) | asc 98/14 at 10 m; quad-pol at 20 m |
| Posting, freq B | 80 m, always | too coarse to be the main L-band input |
| DHDH terms | `HHHH, HVHV` only (`isFullCovariance = False`) | intensity features only; **no dual-pol H/α at freq A** |
| QPDH terms, freq A | full 4×4: 10 terms incl. `VHVH`, `HHVV`, `HVVH`… (`isFullCovariance = True`) | **L08 full-pol is feasible**. HV/VH are not symmetrised (`polarimetricSymmetrizationApplied = False`), so we symmetrise before building C3/T3. |
| QPDH terms, freq B | `HHHH, HHHV, HVHV` | dual-pol H/α possible only at 80 m |
| Backscatter | RTC applied, output γ0 in linear power (`rtcGammaToSigmaFactor` provided) | work in γ0 dB |
| ⚠ Noise correction | `noiseCorrectionApplied = False` on every product | HV over water (~−26 to −28 dB) is probably at the noise floor, so L01 must test this before trusting HV thresholds |
| Shadow masking | not applied | negligible on this flat plain; state it in the technical note |
| `mask` layer | 1…n = sub-swath of a valid sample, 0 = partially focused/invalid, 255 = outside extent (from the dataset's own description) | reader NaNs 0 and 255; bbox window on 2026-01-15 is 100% valid |
| Full frame size | ~33,700 × 34,300 px (≈340 km) at 10 m | full-footprint L10 needs tiling or chunked processing |

**Raster sanity check (2026-01-15, HH, bbox):**
- Rivers, meanders and oxbow lakes are clearly dark.
- HH percentiles: 1% = −22.0, 5% = −18.6, median = −10.9 dB. HV: 1% = −28.4, median = −20.5 dB.
- A large mid-grey sand/char surface along the Ganga in the south of the window is the expected false-positive risk; see L06.

**Candidate dates (asc 98/14), to be confirmed by R00 cloud-free S2 availability:**

| Role | Dates |
|---|---|
| Low water / dry season | 2025-12-22, 2026-01-03, 2026-01-15 |
| Early monsoon | 2026-06-20, 2026-07-02 |
| Monsoon high water | 2026-08-19, 2026-08-31, 2026-09-12 |
| Recession | 2026-10-06, 2026-10-18 |

Figures: `acquisition_timeline.png`, `footprints_vs_bbox.png`. Tables: `tables/inventory.csv`, `tables/summary_by_track.csv`, `tables/footprints.geojson`.

## Next step
1. R00: check S2 cloud-free availability for the candidate dates, then freeze the date set.
