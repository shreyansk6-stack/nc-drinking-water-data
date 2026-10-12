# NC drinking water: non-coliform sample results (Durham, Wake, Chatham, Orange)

Data scraped from [NC Drinking Water Watch](https://www.pwss.enr.state.nc.us/NCDWW2/) (NC DEQ Public Water Supply Section).

## Download

The files are too large for GitHub to preview in the browser; these links download them directly.

- **[noncoliform_results_with_concentrations.xlsx](https://github.com/shreyansk6-stack/nc-drinking-water-data/raw/main/data/noncoliform_results_with_concentrations.xlsx)** (17 MB) — main file: every result with concentrations; Summary sheet + one sheet per county
- [noncoliform_results_with_concentrations.csv](https://github.com/shreyansk6-stack/nc-drinking-water-data/raw/main/data/noncoliform_results_with_concentrations.csv) (35 MB) — same data as one CSV
- [noncoliform_by_analyte.xlsx](https://github.com/shreyansk6-stack/nc-drinking-water-data/raw/main/data/noncoliform_by_analyte.xlsx) (11 MB) — sample counts by analyte and county
- [noncoliform_samples_all_counties.csv](https://github.com/shreyansk6-stack/nc-drinking-water-data/raw/main/data/noncoliform_samples_all_counties.csv) (20 MB) — the sample list behind those counts

## Scope

- **Search:** Non-Coliform Samples [By Analyte]
- **Counties:** Durham, Wake, Chatham, Orange (principal county served)
- **Water systems:** active only (`WaterSystemStatusCode=A`), all system types, all source types
- **Dates:** sample collection date 2021-10-11 to 2026-10-11 (last 5 years). The sample list was first scraped for 2010-10-11 to 2026-10-11 and then filtered.
- **Scraped:** 2026-10-11

## Data

All files cover 2021-10-11 to 2026-10-11.

| County | Samples | Results | Detects (with a value) |
|---|---|---|---|
| Chatham | 1,824 | 9,733 | 4,639 |
| Durham | 5,776 | 25,545 | 15,025 |
| Orange | 7,146 | 19,862 | 9,793 |
| Wake | 36,193 | 164,832 | 42,458 |

Results per county match the site's by-analyte sample listings exactly.

- `noncoliform_results_with_concentrations.csv` / `.xlsx` — one row per sample × analyte: water system, lab sample no., collection date, analyte, method, non-detect flag, concentration + unit, reporting level + unit, monitoring period.
- `noncoliform_by_analyte.xlsx` / `noncoliform_samples_all_counties.csv` — the by-analyte sample listings and counts by county and analyte (no concentrations).

### Notes

- A **non-detect** (`Non-Detect = True`, the site's "Less than Indicator" = Y) has no concentration value; the reporting level is the detection limit it was below. The site records some non-detects with a concentration of "0" (e.g. nitrate-nitrite, HAA5, TTHM) or a bare unit (PFAS); those are blanked in `Concentration Value` and kept as-is in the raw `Concentration` column.
- Each sample's results page also lists coliform analytes (Coliform TCR 3100, E. coli 3014). These are dropped, matching the site's non-coliform search. Every remaining result matches a sample-analyte pair in the site's by-analyte search (checked by the site's internal sample ID).
- Heterotrophic bacteria (HPC) results have no concentration on the site.
- Some labs reuse a lab sample number for different samples on the same day; use `Sample ID` (the site's internal ID) to identify a sample uniquely.
- For a few radionuclides in Wake and Durham, the site's analyte list reports slightly more samples than its own per-analyte sample page returns (e.g. Wake Radium-226: 3,054 vs 3,030 over 2010–2026). The data here matches the sample pages.
- Inactive water systems are not included.

## Reproducing

The site sits behind Cloudflare, which blocks plain `curl`/`requests`; `curl_cffi` impersonates Chrome's TLS fingerprint.

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 1. analyte lists + per-analyte sample lists (~450 pages)
.venv/bin/python scripts/scrape_ncdww.py run
# 2. clean sample-by-analyte tables
.venv/bin/python scripts/parse_ncdww.py run data 2021-10-11
# 3. per-sample result pages (concentrations); resumable, ~8 pages/s
.venv/bin/python scripts/fetch_results.py run run/concentrations_work
# 4. combine into CSV + Excel
.venv/bin/python scripts/build_results.py run run/concentrations_work data
```

Counties and dates are set at the top of `scrape_ncdww.py` (`COUNTIES`, `BEGIN`, `END`) and `fetch_results.py` (`MIN_DATE`).
