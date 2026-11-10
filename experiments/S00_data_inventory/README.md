# S00_data_inventory

**Status:** done
**Decision:** use asc 98/14 S-band DH (8 dates simultaneous with L-band) for F01/F02 and desc 120/76 CP (2026-09-14) for S02
**Owner / date:** nischal, 2026-11-10

## Question / hypothesis
Which NISAR S-band L2 GCOV granules cover the AOI, in which modes and polarisations, and which coincide with the L-band series (Task A, S-band half)?

## Data
- Source: Bhoonidhi (NRSC/ISRO) STAC API, collection `NISAR_SSAR_GCOV`, searched with the reference bbox on 2026-11-09 (`src/nisar_water/io/bhoonidhi.py`). The `NISAR_SSAR-Beta_GCOV` collection returned no search results.
- Access: user login (token API). Granules are 12.6 GB and the download endpoint is limited to 2 requests/min and ~0.13–0.27 MB/s per connection, so a full granule takes ~13 h. Instead, **only the bbox window is read with HTTP range requests** (h5py over a cached, rate-limited range reader, `RangeFile`): ~41 × 4 MB requests, ~21 min per granule.

## Results
21 S-band GCOV granules intersect the bbox (all online):

| date       | time_utc   | direction   |   track |   frame |   mode | pol_code   | polarization   | processing   |   incidence_deg | coverage   |   bbox_cover_frac | L_band_same_acquisition   |
|:-----------|:-----------|:------------|--------:|--------:|-------:|:-----------|:---------------|:-------------|----------------:|:-----------|------------------:|:--------------------------|
| 2026-08-28 | 12:58:45   | Descending  |      48 |      75 |   2500 | CRNA       | CP             | PR           |            41.2 | F          |             0.846 | 2005 QPDH                 |
| 2026-09-09 | 12:59:06   | Descending  |      48 |      75 |   2500 | CRNA       | CP             | PR           |            41.2 | P          |             0.991 | 2005 DHDH                 |
| 2026-09-21 | 12:58:45   | Descending  |      48 |      75 |   2500 | CRNA       | CP             | PR           |            41.2 | F          |             0.833 | 2005 QPDH                 |
| 2026-10-03 | 12:59:06   | Descending  |      48 |      75 |   2500 | CRNA       | CP             | PR           |            41.2 | P          |             0.975 | 2005 DHDH                 |
| 2026-08-28 | 12:59:18   | Descending  |      48 |      76 |   2500 | CRNA       | CP             | PR           |            41.2 | F          |             0.814 | 2005 QPDH                 |
| 2026-09-09 | 12:59:18   | Descending  |      48 |      76 |   2500 | CRNA       | CP             | PR           |            41.2 | F          |             0.825 | 2005 QPDH                 |
| 2026-09-21 | 12:59:18   | Descending  |      48 |      76 |   2500 | CRNA       | CP             | PR           |            41.2 | F          |             0.823 | 2005 QPDH                 |
| 2026-10-03 | 12:59:18   | Descending  |      48 |      76 |   2500 | CRNA       | CP             | PR           |            41.2 | F          |             0.814 | 2005 QPDH                 |
| 2026-07-14 | 23:38:11   | Ascending   |      98 |      14 |   3700 | DHNA       | DH             | PR           |            41.2 | F          |             1     | 4005 DHDH                 |
| 2026-07-26 | 23:38:11   | Ascending   |      98 |      14 |   3700 | DHNA       | DH             | PR           |            41.2 | F          |             1     | 4005 DHDH                 |
| 2026-08-19 | 23:38:10   | Ascending   |      98 |      14 |   3700 | DHNA       | DH             | PR           |            41.2 | F          |             1     | 4005 DHDH                 |
| 2026-08-31 | 23:38:10   | Ascending   |      98 |      14 |   3700 | DHNA       | DH             | UR           |            41.2 | F          |             1     | 4005 DHDH                 |
| 2026-09-12 | 23:38:09   | Ascending   |      98 |      14 |   3700 | DHNA       | DH             | UR           |            41.2 | F          |             1     | 4005 DHDH                 |
| 2026-09-24 | 23:38:10   | Ascending   |      98 |      14 |   3700 | DHNA       | DH             | UR           |            41.2 | F          |             1     | 4005 DHDH                 |
| 2026-10-06 | 23:38:10   | Ascending   |      98 |      14 |   3700 | DHNA       | DH             | PR           |            41.2 | F          |             1     | 4005 DHDH                 |
| 2026-10-18 | 23:38:10   | Ascending   |      98 |      14 |   3700 | DHNA       | DH             | PR           |            41.2 | F          |             1     | 4005 DHDH                 |
| 2026-10-30 | 23:38:11   | Ascending   |      98 |      14 |   3700 | DHNA       | DH             | UR           |            41.2 | F          |             1     | —                         |
| 2026-08-21 | 12:50:59   | Descending  |     120 |      76 |   2500 | CRNA       | CP             | PR           |            41.2 | F          |             1     | 2005 QPDH                 |
| 2026-09-02 | 12:50:59   | Descending  |     120 |      76 |   2500 | CRNA       | CP             | PR           |            41.2 | F          |             1     | 2005 QPDH                 |
| 2026-09-14 | 12:50:59   | Descending  |     120 |      76 |   2500 | CRNA       | CP             | PR           |            41.2 | F          |             1     | 2005 QPDH                 |
| 2026-09-26 | 12:50:59   | Descending  |     120 |      76 |   2500 | CRNA       | CP             | PR           |            41.2 | F          |             1     | 2005 QPDH                 |

`L_band_same_acquisition` = polarisation code of the L-band GCOV with the same track, frame and date (NISAR acquires L and S simultaneously in these modes; start times are identical to the second).

## Observations
- **Asc 98/14, mode 3700 DHNA:** S-band HH/HV dual-pol, frequency A, 10 m, EPSG:32645. Terms HHHH, HHHV, HVHV; no frequency B. The bbox window falls **exactly on the L-band canonical grid** (same transform), so L and S pixels coincide with no resampling. 9 dates 2026-07-14 → 10-30; 8 coincide with L-band DHDH acquisitions (10-30 has no L-band GCOV in our inventory). **No dry-season S-band** (none before 2026-07-14).
- **Desc 120/76 and 48/75–76, mode 2500 CRNA:** S-band compact-pol (circular transmit, H/V receive). 120/76 dates coincide with L-band QPDH (08-21, 09-02, 09-14, 09-26).
- S-band speckle ENL ≈ 3.5 (L-band ≈ 5.5); S-band HV over water ≈ −18.8 dB vs L-band ≈ −23.9 dB on 2026-10-18 (higher noise floor).
- Only one S-band date has a same-date S2 reference: asc 2026-10-18 (S2 50 % clear).

## Decision
F01 (L vs S vs L+S water mapping) and F02 (change) on the 8 simultaneous asc dates; S02 (compact-pol, Task H iii) on desc 2026-09-14. Full-footprint S-band processing is not feasible with this download rate (13 h per granule) and is stated as a limitation.
