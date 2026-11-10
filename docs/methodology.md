# Methodology: surface-water mapping and change detection with NISAR L2 GCOV

**Living document.** It records the methodology currently in use and the decisions behind it, and is updated whenever an experiment concludes. Per-experiment detail (configs, runs, figures) is in `experiments/<id>/README.md`; status is in [`experiments/INDEX.md`](../experiments/INDEX.md). This document is the basis of the submitted technical note.

| | |
|---|---|
| Last updated | 2026-11-09 |
| Current stage | L-band L00–L09, R00 done; champion **C3** (L07). S-band obtained 2026-11-09 (§2.2): S00, S02, F01 (L vs S vs L+S), F02 done. L10/L10b full footprint done (reliable in the floodplain belt, see §5.1) |
| Central question | Does combining NISAR L- and S-band L2 GCOV improve surface-water mapping or change detection relative to single-frequency baselines, and under what conditions? |

---

## 1. Study area and processing extent

- **Region:** Ganga alluvial plain, Bihar. The reference bbox is W 86.3946, S 25.4098, E 86.6054, N 25.5902 (`configs/aoi.yaml`, `data/bbox.geojson`).
- **What the bbox is for:** scene discovery and **method development only**. Final products cover the **full selected NISAR scene footprint**, as the problem statement requires (L10).
- **Landscape:** an active, migrating river system. There are meandering channels, oxbow lakes, a broad Ganga channel with sand/char surfaces, agricultural land and settlements. Two consequences:
  1. *persistent* water must be defined from current observations, not from a long-term climatology (§4.2);
  2. dry sand is the main expected SAR false positive (§5).

## 2. Data

### 2.1 NISAR L-band L2 GCOV (ASF DAAC)
Found by L00, which searched the full archive for granules intersecting the bbox: 72 granules, 64 after de-duplication.

| Series | Role | Mode / pols | Posting | Dates |
|---|---|---|---|---|
| **Asc 98/14** | primary L-band series, water mapping + change detection | `4005 DHDH`: HH, HV (diagonal terms only) | 10 m (freq A) | 15 dates every 12 days: 2025-11-28 → 2026-01-15, then 2026-06-20 → 2026-10-18 |
| **Desc 120/76** | polarimetric assessment (Task H) and geometry check | 9× `2005 QPDH`: full 4×4 covariance (10 terms); 4× `4005 DHDH` | 20 m QPDH / 10 m DHDH | 2025-11-30 → 2026-10-20 |
| Desc 48/75–76 | not used: the bbox sits on the frame corner (~0.6 coverage) | DHDH, QPDH | 10–20 m | reported in L00 only |

Product facts confirmed from the HDF5 metadata (L00), not assumed:
- **Projection:** EPSG:32645 (UTM 45N) for every product.
- **Backscatter:** RTC applied; output is γ0 in linear power (`rtcGammaToSigmaFactor` supplied).
- **⚠ Noise correction not applied** (`noiseCorrectionApplied = False`). L01 confirmed HV over water is noise-limited: median −25.2 to −25.7 dB on every dry date, at the ≈ −25 dB NESZ requirement, with a slight drift across range.
- **Shadow masking not applied.** Terrain effects are negligible on this flat plain.
- **Polarimetric symmetrization not applied:** HV and VH are separate in QPDH. We symmetrize before building C3/T3 (L08).
- **`mask` layer:** 1…n = valid sample from sub-swath n; 0 = partially focused/invalid; 255 = outside the acquisition. 0 and 255 are set to NaN.
- **Frequency B** (5 MHz) is posted at 80 m and is not used as the main input.
- **No gaps or misalignment:** no acquisitions on any track between mid-Jan and mid-Jun 2026. Asc 98/14 also has a gap from 26 Jul to 19 Aug.

### 2.2 S-band L2 GCOV (Bhoonidhi, NRSC/ISRO)
- Bhoonidhi STAC API (`io/bhoonidhi.py`, user login; collection `NISAR_SSAR_GCOV`). 21 granules intersect the bbox (S00):
  - **asc 98/14, mode 3700 DHNA:** S-band HH/HV, 10 m, 9 dates 2026-07-14 → 10-30, **acquired simultaneously with the L-band DHDH series** (8 common dates). The bbox window lies exactly on the L-band canonical grid.
  - **desc 120/76 and 48/75–76, mode 2500 CRNA:** S-band compact-pol (RHRH, RHRV, RVRV), 20 m; 120/76 dates coincide with L-band QPDH.
  - **No dry-season S-band** (nothing before 2026-07-14); only 2026-10-18 has an S2 reference.
- **Access constraint:** 12.6 GB granules, download endpoint limited to 2 requests/min and ~0.13–0.27 MB/s per connection (≈ 13 h per granule). Bbox windows are therefore read with **HTTP range requests** through h5py (`RangeFile`: 4 MB cached blocks, ≥ 31 s apart): 28–48 requests, 15–26 min per granule. Full-footprint S-band processing is not feasible in the time available.
- Pre-processing as L-band: Lee 7×7 with its own per-scene ENL (≈ 3.5, fewer looks than L-band ≈ 5.5); S-band HV over water ≈ −19 dB (L-band ≈ −24 dB): a higher noise floor.

### 2.3 Reference and ancillary data (Microsoft Planetary Computer)

| Dataset | Use | Notes |
|---|---|---|
| Sentinel-2 L2A (tile 45RVJ) | same-date reference water masks (truth for metrics) | optical: misses water under vegetation canopy and is unavailable under cloud |
| Sentinel-1 RTC (VV) | cross-sensor comparison only, never truth | asc S1A passes 0.5 h from desc 120/76 |
| JRC Global Surface Water v1.3 | long-term context only | 1984–2020 climatology; see §4.2 |

### 2.4 Data access
- Full granules are 7–9 GB, and local disk is limited.
- `nisar-water fetch` streams only the bbox window from ASF over HTTPS. earthaccess reads just the needed HDF5 chunks (512 × 512), about 40 MB per date.
- Windows are cached as NetCDF in `data/interim/nisar_L/`, and experiments read the cache.
- Full-footprint production (L10) downloads the 15 asc 98/14 granules in full (6.9 GB each, ~104 GB; disk was freed for this) and processes them tile by tile (§5.1).

## 3. Pre-processing

1. **Read:** chosen covariance terms on the bbox window (`io/gcov.py`, built on the vendored `nisar_utils` toolkit).
2. **Mask:** invalid pixels (mask 0/255, non-finite values) become NaN in every term.
3. **Grid:** all analysis uses the canonical grid `configs/grid_bbox.yaml`. This is the asc 98/14 bbox window: EPSG:32645, 10 m, 2006 × 2126 px.
   - Every 98/14 granule is on this exact grid, so change detection needs no resampling.
   - 120/76 QPDH 20 m pixels are exact 2 × 2 aggregates of it.
   - Reference rasters are warped onto it.
4. **Speckle filtering:** applied in linear power, before dB. **Adopted: Lee 7×7** (L01).
   - The ENL is estimated per scene from homogeneous land: 5.0–5.7.
   - Filtering raises the best single-threshold F1 from 0.69 to 0.81. Boxcar 7 over-smooths.
5. **Convert to dB:** γ0 dB = 10·log10(γ0). Work stays in γ0 (terrain-flattened); σ0 is available but not used.

## 4. Reference data (R00)

### 4.1 Sentinel-2 water masks
For each NISAR acquisition:
1. **Find candidates:** every S2 L2A scene within ±3 days, with times compared in hours. Asc 98/14 passes at ~23:38 UTC, which is 05:08 IST the next day.
2. **Cloud screening:**
   - SCL invalid classes: nodata, defective, cloud shadow, cloud medium/high, cirrus.
   - A brightness/whiteness test: cloud = B02 > 0.2 **and** B02/B04 ≥ 0.85.
   - A 200 m disk buffer, applied only to invalid clusters of at least 1 ha. Sen2Cor flags isolated bright-sand specks as cloud; buffering those punched 400 m holes in the sand bars.
   - The scene with the largest clear fraction wins; ties go to the smallest |Δt|.
3. **Build condition:** clear fraction ≥ 30%. Cloudy pixels become nodata and are never scored.
4. **Water:** MNDWI = (B03 − B11)/(B03 + B11) > 0 (Xu 2006). Surface reflectance has the baseline ≥ 04.00 DN offset removed.
5. **Automatic QC:** the reference is rejected if the MNDWI and NDWI (McFeeters 1996) water maps disagree (F1 < 0.5).
6. **Diagnostics recorded:** agreement with S2's own SCL water class, the MNDWI Otsu threshold, and recall of JRC persistent water.

Filenames are keyed by the **NISAR UTC acquisition date**: `data/reference/s2_water_<date>.tif` (1 water, 0 non-water, 255 nodata).

### 4.2 Persistent water
- **Definition:** water in **every** clear dry-season (Nov–Mar) S2 reference, with ≥ 2 clear observations per pixel (`persistent_water.tif`). Each S2 scene counts once.
- **Why not JRC:** pixels with JRC occurrence ≥ 75% cover only 1.0 km² of the bbox, against 27.8 km² of current dry-season water. The rivers have migrated since the climatology was built, so JRC is reported as context only.
- **Use:** "newly detected water outside persistent water bodies" (Task E) uses this layer.

### 4.3 Sentinel-1 comparison masks
- VV γ0 dB from the nearest RTC scene within ±6 days.
- Water = VV below a **tiled bimodal threshold** (§5, step 3).
- Comparison only: different wavelength, geometry and date.

### 4.4 Spatial train/test split
- 2 km blocks; 30% go to test, stratified on whether a block contains persistent water (seed 42) (`split_blocks.tif`).
- Thresholds and models are tuned on **train** blocks. **All reported metrics use test blocks only**, so spatial autocorrelation can't inflate accuracy.

### 4.5 What can be validated
10 of 28 NISAR acquisitions have an S2 reference (R00 iteration 4):

| Period | Dates (asc 98/14 · desc 120/76) |
|---|---|
| Dry season | asc 2025-11-28, 12-10, 2026-01-03, 01-15 · desc 2025-11-30, 2026-01-05, 01-17 |
| Pre-monsoon | desc 2026-06-22 |
| Monsoon | none |
| Recession | asc 2026-10-18 (50% clear) · desc 2026-10-20 |

- **Primary single-date test:** 2026-01-15, with S2 5 h later.
- **Quantitative change pairs on 98/14:** only dry season → 2026-10-18 (recession).

### 4.6 Known limitations of the reference
- **Monsoon gap:** no S2 reference between 2026-06-22 and 2026-10-18. Monsoon-peak NISAR dates can only be assessed qualitatively and against Sentinel-1. This is stated in every result.
- **Time gap:** S2 is up to ±3 days from NISAR. Water can change in that time (recession, irrigation).
- **Flooded vegetation:** optical MNDWI misses water under crops and vegetation, while L-band (double bounce) may detect it. Some L-band "false positives" may be real; these are inspected against the S1 masks and imagery.
- **Mixed pixels:** the 20 m SWIR band is resampled to 10 m, so narrow channels have mixed edge pixels.

## 5. Water mapping: the L-band method ladder

Experiments run from simple to complex. Each one is compared with the current best on the same dates, split and extent. The method column grows as experiments conclude.

| Step | Experiment | Method | Status / result |
|---|---|---|---|
| 0 | L01 | Channel separability: JM distance and oracle single-threshold F1 for HH, HV, HV−HH and span under each speckle filter; HV noise check; error anatomy | **done**. HH after Lee 7 (oracle F1 0.81; span 0.81, HV 0.69, ratio 0.36). HV over water is noise-limited (≈ −25.5 dB). Errors: 49% of FP are large clusters on Ganga sand/char, 27% specks, 25% edges |
| 1 | L02 | **Baseline B0**: one global dB threshold on HH (Lee 7), tuned on train blocks | **done**. B0 = HH < −15.9 dB: test F1 **0.744** (pooled), IoU 0.59. Span ties (0.745); HV 0.58; fixed −18 dB 0.56 (precision 0.90, recall 0.43). B0 over-maps area (34 vs ≈ 28 km² on 01-15) |
| 2 | L03 | Automatic per-scene global thresholds: Otsu (1979), Kittler–Illingworth (1986) | **done, rejected**. Otsu splits land classes (≈ −11 dB, F1 0.36); KI degenerates to 'all water' on 3/5 dates (pooled F1 0.25). Water is too rare in the global histogram |
| 3 | L04 | **Tiled bimodal thresholding** (Martinis et al. 2009; Chini et al. 2017): Ashman D ≥ 2 tiles, the 10 most bimodal pooled; Otsu or KI; hysteresis growing | **done → champion C1 = tiled KI, bounded between class means**. Test F1 **0.748** (B0 0.744), reference-free. On monsoon dates F1 vs S1 is 0.74–0.83 vs B0's 0.46–0.72 (B0 misses about half the monsoon water). Tiled Otsu 0.61; hysteresis hurts |
| 4 | L05 | Dual-pol combinations: span, HH ∧ HV (tiled KI each), 2-D GMM (3/4 components) | **done, C1 kept**. Span 0.749 / HH ∧ HV 0.747 / C1 0.748 tie; GMM 0.71–0.73. HV never binds in the dry season (noise floor); in the monsoon HH ∧ HV trims area by 12–17% toward S1 (unverified) |
| 5 | L06 | Contextual refinement: MMU, morphology, HAND (Copernicus GLO-30, pysheds); selected on train blocks | **done → champion C2 = C1 + MMU 0.25 ha**. Test F1 **0.759**. Open+close 3×3 is within the tie margin (better area bias, loses narrow channels) and is flagged for review. HAND useless on this flat plain |
| 6 | L07 | Supervised LightGBM / random forest on dB channels, local texture (5×5, 15×15 mean/std/min), multi-temporal statistics over the 15 dates, HAND; **scene-relative HH features** (HH minus the scene's tiled-KI threshold). Labels: S2 on train blocks; probability threshold and model chosen on held-out VAL blocks (25% of train blocks) | **done → champion C3 = `lgbm_rel_full_mmu25`**. Test F1 **0.832** (C2 0.759), precision 0.84, recall 0.84. Iteration 1 (absolute dB features, F1 0.828) under-mapped the monsoon (S1 agreement 0.48 on 09-24, 56 vs 130 km²) because monsoon water is 3–5 dB brighter; relative features restored it (0.74 on 09-24). Texture dominates importance; HV < 1% |
| 7 | L08 | Full-pol L-band (desc QPDH): HH/HV/VV, ratios, co-pol coherence/phase, H/A/ᾱ, Pauli, Freeman–Durden from symmetrised, co-pol-phase-calibrated C3/T3; same LightGBM/samples/blocks as dual-pol subsets | **done**. Full-pol 0.814 vs dual-pol 0.795 (+texture), 0.767 vs 0.712 (pixel). Gain comes from **VV** (co-pol set 0.761; Pauli surface JM 1.07, VV 1.06 vs HH 0.85). H/ᾱ/FD weak (JM ≤ 0.35): water is noise-dominated. The delivered HHVV has a scene-wide co-pol phase offset (−155° to −160°, dry season) removed before decomposition |
| 7b | S02 | S-band compact-pol (desc CRNA, 09-14): Stokes, m, χ, δ, m-χ | **done** (vs S1 only). Total power separates water (JM 1.26–1.38; g0 map agrees with S1 at F1 0.85); m, χ, δ, m-χ fractions JM ≤ 0.04 |
| 8 | L11 | (optional) U-Net, kept only if it beats L07 on held-out blocks | optional |

**Promotion rule:** the champion is the best test-block F1/IoU. If two methods are within ~0.01 F1, keep the simpler one. The problem statement scores a simple, well-validated method above a complex one with weak evidence.

**Adopted method (champion C3, L07):**
1. Lee 7×7 (per-scene ENL) → HH, HV γ0 dB.
2. Per-scene tiled Kittler–Illingworth threshold t on HH (C1; 256 px bimodal tiles, bounded KI): −15.1 to −16.9 dB in the dry season, −11 to −14 dB in the monsoon.
3. Features: HH − t, local mean (5×5, 15×15) − t, local minimum (15×15) − t, local std of HH, HV, HV − HH, local mean HV; temporal statistics of HH/HV over all 15 dates; HAND.
4. LightGBM (400 trees) → water probability > threshold chosen on VAL blocks → remove water objects < 0.25 ha.
- Test F1 **0.832**, IoU 0.71 on the 5 referenced dates; S1 agreement on monsoon dates 0.74–0.82, equal to C2.
- The classifier learns *which dark surfaces are not water* (sand/char, smooth fields) from texture and the multi-date context; the scene-relative features carry C1's per-scene adaptation to brighter monsoon water.
- Previous champion C2 (C1 + MMU, test F1 0.759) remains the reference-free fallback.

### 5.1 Full-footprint production (L10)
- Frame asc 98/14: 33 696 × 34 344 px at 10 m (337 × 343 km). Processed in 2048 px tiles (≈ 20 km, the bbox scale the model was trained at) with a 32 px halo; the scene threshold t is computed **per tile** (fallback: the date's bbox threshold where a tile has < 3 bimodal sub-tiles).
- Model `lgbm_rel_nohand_mmu25` (test F1 0.820 on the bbox; HAND omitted to avoid a 340 km HAND build; HAND importance 5%).
- Output posting 20 m: each cell takes the label of the 10 m sample at its upper-left corner (≤ 5 m offset). MMU scaled to 6 cells (0.24 ha).
- Consistency check: the production path cropped to the bbox (smoke test, 2026-01-15) gives test F1 0.802 vs 0.823 for the same model at 10 m in L07.
- Persistent water on the full frame: NISAR water on ≥ 4 of the 5 dry-season dates OR JRC GSW occurrence ≥ 50% (2,806 km²).
- **Product artefact handled:** on the 5 dry-season granules (X0500x processing) the GCOV `mask` layer marks a far-range strip of near-zero power (−146 dB) as valid; backscatter ramps down over ~15 km towards it. Pixels within 18 km of power < −60 dB are dropped (10 km in the run + 8 km post-fix, `scripts/l10_edge_postfix.py`).
- **Tile thresholds regularised:** KI split land (~−10 dB) in low-water tiles; thresholds > 3 dB from the date median and fallback tiles take the median of kept tiles within 2 tiles.
- **Validation outside the box (iteration 2, per-tile thresholds):** frame-wide S2 mosaic for 2026-01-15 at 40 m (`scripts/l10_s2_crosscheck.py`): floodplain belt (northing ≥ 2,775 km) F1 0.77, southern plain F1 0.29 (precision 0.17), box 0.85; frame-wide S1 at 100 m (`scripts/l10_s1_crosscheck.py`): 06-20 16× in the belt.
- **Iteration 3 (L13):** per-tile KI thresholds split land types in low-water tiles (01-15 median −14.9 dB south vs −16.4 dB belt; block precision vs t Spearman −0.65). Every tile now uses the date's reference-box threshold − 1 dB (selected on 15 test tiles; eval halves: south 0.26 → 0.41, belt 0.79 → 0.79). Frame result vs S2: belt F1 0.81, south 0.47 (precision 0.33), box 0.85; belt NISAR/S1 1.4× (06-20), 1.3× (09-12), 1.2× (10-18). Run in 5 shards (`extra.shard`, merged with `extra.merge_shards`). `scripts/l10_zone_scores.py` writes the zone tables.

## 6. Change detection (L09)

**Classes** (problem statement §6). Water masks are compared between an earlier date t1 and a later date t2:

| Class | Rule |
|---|---|
| Stable water | water at t1 and t2 |
| Newly detected water (gain) | non-water at t1, water at t2 |
| Water loss (receded) | water at t1, non-water at t2 |
| Stable non-water | non-water at t1 and t2 |
| Potential temporary inundation | gain **outside persistent water** (§4.2) |

**Methods compared (L09):**
- (a) **post-classification comparison (PCC)** of two champion masks — **adopted**;
- (b) log-ratio r = HH(t2) − HH(t1) in dB from the t1 mask: gain where r < −T over t1 non-water, loss where r > +T over t1 water (T = 3 and 5 dB).

**Result (C3 masks, S2-derived change on test blocks, 4 S2 pairs):** PCC mean overall accuracy 0.948 vs 0.882/0.922 for log-ratio 3/5 dB; stable-water F1 0.84 vs 0.78/0.79; on the only pair with substantial real change (2026-01-15 → 10-18; 8.75 km² S2 gain), PCC gain F1 **0.72**. Log-ratio over-detects gain from crop/soil-moisture darkening.

**Date pairs:** dry season (2026-01-15) → monsoon peak (09-12): 131 km² gain in the bbox, 130 km² of it outside persistent water; pre-monsoon (06-20) → peak; peak → recession (10-18): 90 km² loss; dry → post-monsoon (10-18); all consecutive 12-day pairs. All on asc 98/14 (identical geometry and grid). Also a water-occurrence map (% of the 15 dates).

**Interpretation rule:** a mapped change is never attributed to flooding, rainfall or irrigation without independent evidence.

## 7. Validation and uncertainty

- **Water masks:** confusion matrix, precision, recall, F1, IoU, overall accuracy and kappa on test blocks against same-date S2 references (`validate/metrics.py`). Nodata, cloud and train pixels are excluded.
- **Change maps:** assessed against S2-reference change wherever both dates have a reference. Otherwise, a qualitative check plus comparison with S1.
- **Area:** pixel count × 100 m² (10 m grid, projected UTM). For the final products, sample-based area estimates with 95% confidence intervals (Olofsson et al. 2014).
- **Error analysis:** by land cover, incidence angle and distance to the river channel. Known error sources: sand/char surfaces, flooded vegetation, wind-roughened water, mixed pixels, the HV noise floor, the date gap with S2.
- **Without a reference:** state the limitation, give a qualitative assessment, and never invent accuracy figures.

## 8. Comparative assessment (L vs S vs L+S)

F01 / F02 (results in their READMEs): the 8 asc 98/14 dates with simultaneous L- and S-band acquisitions (2026-07-14 → 10-18), identical grid, time and geometry, so only the frequency differs. Same pipeline per band (Lee 7×7 own ENL, dB, texture, own scene threshold), same samples, blocks and LightGBM; fusion = feature-level stacking. Labels and test scores from the only S2-referenced date (10-18, 50 % clear); S1 agreement on all 8 dates; change consistency vs S1-derived change (F02).

**Result (F01, test blocks of 2026-10-18).** S LightGBM 0.808 ≈ L LightGBM 0.807 (ΔF1 +0.002 [−0.031, +0.040]); S is more precise (0.84 vs 0.81), L has more recall (0.81 vs 0.78), consistent with L-band seeing more vegetated water. L+S 0.826, ΔF1 +0.018 [+0.002, +0.041], mainly from fewer false alarms. On 2026-09-24 both bands are 1.5–1.8 dB brighter (scene thresholds L −11.0, S −12.1 dB vs about −12.8 / −13.6 on neighbouring dates); the fused model, trained on 10-18 only, maps 258 km² vs 130 km² in S1, while per-band scene-relative models stay at 161–203 km². **F02:** S and L+S change agrees better with S1-derived change (early monsoon → peak OA 0.88 / 0.87, gain F1 0.83 / 0.82) than L (0.82, 0.76); L reports more gain (158 vs 131 km²). C-band S1 shares S-band's vegetation response, so this is consistency, not accuracy. **Decision:** production stays L-only (S-band only in the box, truth on one date, fusion less robust across dates); L+S reported as the best box-level result.

Earlier plan text (kept for the record): The fusion design that the pipeline supports is feature-level: L and S features (same 10 m grid after k×k replication, as done for QPDH in L08) stacked into the same LightGBM with the same samples/blocks, compared against L-only and S-only models trained identically — so the effect of the frequency is isolated from classifier, samples and split. Matching dates (|Δt| ≤ 1 day) and geometry would have to be checked first.

## 9. Reproducibility

- **Environment:** `uv` (Python 3.12, `uv.lock`). The upstream toolkit is pinned as a git submodule (`third_party/`, commit `f2c96ff`).
- **Running:** one YAML config per experiment, run with `uv run nisar-water run <config>`.
- **Each run folder records:** a frozen config, provenance (git commit, package versions, inputs), metrics, auto-generated results, and maps. Every map is stamped with date(s), CRS, resolution and source.
- **Rebuilding data:** reference rasters in `data/reference/` are git-ignored; rebuild them from the R00 config.

## 10. Decision log

| Date | Decision | Why | Evidence |
|---|---|---|---|
| 2026-10-25 | Use asc 98/14 (DHDH, 10 m) as the main L-band series; desc 120/76 QPDH for polarimetry | Both fully cover the bbox. 98/14 has a regular 12-day series on one fixed grid; 120/76 has full-pol | L00 |
| 2026-10-25 | Drop track 48 | bbox at the frame corner, ~0.6 coverage | L00 |
| 2026-10-25 | Stream bbox windows instead of downloading granules | 7–9 GB per granule, ~24 GB free disk | L00, `io/gcov.py` |
| 2026-10-25 | Canonical 10 m grid = asc 98/14 bbox window | all 98/14 granules share it exactly; QPDH 20 m nests 2 × 2 | R00 |
| 2026-10-25 | MNDWI > 0 for S2 reference, with MNDWI–NDWI QC | SWIR suppresses soil/built-up false positives; QC catches residual cloud | R00 |
| 2026-10-25 | Cloud test = SCL + (B02 > 0.2 ∧ B02/B04 ≥ 0.85) + 200 m buffer | SCL called a ~90% cumulus scene "clear" (iter 1). A brightness-only test removed ~14% of clear scenes by masking bright sand (iter 2). Cloud B02/B04 is 0.90–1.01, sand 0.71–0.81 | R00 iterations 1–3 |
| 2026-11-10 | Scene threshold for the full frame = reference-box threshold − 1 dB (L10 iteration 3) | L13: per-tile KI split land types in low-water tiles; eval tiles south F1 0.26 → 0.41, belt 0.79 → 0.79, 06-20 7.2× → 1.0× S1 | L13 |
| 2026-11-10 | L10 iteration 3: scene threshold = reference-box threshold − 1 dB for every tile | per-tile KI split land types in low-water tiles; L13 eval tiles south F1 0.26 → 0.41, belt unchanged; frame: belt 0.81, south 0.47 | L13, L10 |
| 2026-11-10 | (superseded by iteration 3) Full-frame results reported for the floodplain belt; southern plain and 06-20/07-02 flagged | frame-wide S2 (01-15): belt F1 0.77, south F1 0.29 (commission); S1: 06-20 16×, 07-02 4× over-mapping; no time to retrain before the deadline | L10, L10b |
| 2026-11-10 | L10 iteration 2: edge mask (18 km from near-zero power) + regularised tile thresholds | iteration 1 mapped a far-range zero-power strip and −10 dB tile splits as water (dry season > post-monsoon) | L10 |
| 2026-11-10 | Keep C3; probability smoothing not adopted | 3×3 mean of probability +0.004 [0.003, 0.005] test F1: consistent but inside the ±0.01 tie band; hysteresis −0.004 to −0.025 (over-grows into dark fields) | L12 |
| 2026-11-10 | Production stays L-only; L+S reported for the box | S ≈ L (0.810 vs 0.809); L+S +0.018 [0.002, 0.041] on one date but over-maps 09-24 (258 vs 130 km² S1); S-band available only as box windows | F01, F02 |
| 2026-11-09 | Change method = PCC of C3 masks | OA 0.948, stable-water F1 0.84, gain F1 0.72 on the real-change pair; log-ratio over-detects gain | L09 |
| 2026-11-09 | Champion C3 = LightGBM, scene-relative + texture + temporal + HAND (+ MMU) | test F1 0.832 vs 0.759 (C2); fixes C2's sand/char over-mapping; scene-relative features required to keep monsoon water (absolute-dB model lost half of it) | L07 iterations 1–2 |
| 2026-11-09 | Full footprint: download granules, tile at 2048 px, 20 m output, no-HAND model | the problem statement requires full-footprint outputs; disk freed; compute budget ≈ hours on a laptop | L10 |
| 2026-10-26 | Champion C2 = C1 + MMU 0.25 ha; HAND rejected | +0.011 test F1. Open+close led on train by 0.008 (tie) but erodes narrow channels; flagged for review because it has less area bias. HAND: flat plain (95% < 5.6 m), DSM artefacts | L06 |
| 2026-10-26 | Keep HH-only C1; dual-pol adds no measurable value | span / HH ∧ HV tie C1 on test F1 (0.747–0.749); HV is at the noise floor over water; the GMMs over-map | L05 |
| 2026-10-26 | Champion C1 = bounded tiled KI on HH | ties B0 on test F1 (0.748 vs 0.744). Reference-free. On monsoon dates it agrees with S1 at F1 0.74–0.83 vs 0.46–0.72 for B0's fixed dry-season threshold | L04 |
| 2026-10-26 | Reject per-scene global Otsu/KI | water is 6–12% of pixels: Otsu splits land, KI degenerates (pooled F1 0.22–0.36 vs B0 0.744) | L03 |
| 2026-10-26 | Baseline B0 = HH < −15.9 dB (train-tuned) | test F1 0.744. Span is within 0.01, so the simpler HH is kept (promotion rule) | L02 |
| 2026-10-26 | Lee 7×7 speckle filter (per-scene ENL) and HH as the primary channel | oracle F1 0.69 → 0.81 with filtering. HH ≈ span ≫ HV ≫ HV−HH. HV is at the noise floor over water | L01 |
| 2026-10-26 | Buffer only cloud clusters ≥ 1 ha, with a disk kernel | SCL labels bright-sand specks on the Ganga as class 8 cloud (0.2–0.5% of the channel area). A 200 m square buffer turned each into a 400 m hole in persistent water (iter 3) | R00 iteration 4 |
| 2026-10-25 | Build S2 references from ≥ 30% clear (was 80%) | partial references score only clear pixels; otherwise no high-water date at all | R00 iteration 2 |
| 2026-10-25 | Persistent water from dry-season S2, not JRC | JRC ≥ 75% occurrence gives 1.0 km² vs 27.8 km² current dry-season water (river migration) | R00 iterations 2–4 |
| 2026-10-25 | Tiled bimodal threshold for S1 comparison masks | global Otsu split land classes (−12 dB) and over-mapped water up to 12×. Tiled thresholds raised S1–S2 F1 from 0.40–0.59 to 0.69–0.78 | R00 iterations 1–2 |
| 2026-10-25 | Metrics on test blocks only (2 km blocks, 30%) | avoids spatial-autocorrelation leakage | R00 |

## References

- Chini, M. et al. (2017). A hierarchical split-based approach for parametric thresholding of SAR images: flood inundation as a test case. *IEEE TGRS*, 55(12).
- Cloude, S. R., & Pottier, E. (1997). An entropy based classification scheme for land applications of polarimetric SAR. *IEEE TGRS*, 35(1).
- Freeman, A., & Durden, S. L. (1998). A three-component scattering model for polarimetric SAR data. *IEEE TGRS*, 36(3).
- Kittler, J., & Illingworth, J. (1986). Minimum error thresholding. *Pattern Recognition*, 19(1).
- Lee, J.-S. (1980). Digital image enhancement and noise filtering by use of local statistics. *IEEE TPAMI*, 2(2).
- Martinis, S., Twele, A., & Voigt, S. (2009). Towards operational near real-time flood detection using a split-based automatic thresholding procedure on high resolution TerraSAR-X data. *NHESS*, 9.
- McFeeters, S. K. (1996). The use of the Normalized Difference Water Index (NDWI) in the delineation of open water features. *IJRS*, 17(7).
- Olofsson, P. et al. (2014). Good practices for estimating area and assessing accuracy of land change. *Remote Sensing of Environment*, 148.
- Otsu, N. (1979). A threshold selection method from gray-level histograms. *IEEE TSMC*, 9(1).
- Pekel, J.-F. et al. (2016). High-resolution mapping of global surface water and its long-term changes. *Nature*, 540.
- Xu, H. (2006). Modification of normalised difference water index (NDWI) to enhance open water features in remotely sensed imagery. *IJRS*, 27(14).
- Yamaguchi, Y. et al. (2005). Four-component scattering model for polarimetric SAR image decomposition. *IEEE TGRS*, 43(8).
- Pandey, D. K. *nisar-polarimetric-training* (v1.1.0, Apache-2.0). https://github.com/dharmendraisro/nisar-polarimetric-training
