# NC drinking water: non-coliform sample results (Durham, Wake, Chatham, Orange)

Data scraped from [NC Drinking Water Watch](https://www.pwss.enr.state.nc.us/NCDWW2/) (NC DEQ Public Water Supply Section).

## Scope

- **Search:** Non-Coliform Samples [By Analyte]
- **Counties:** Durham, Wake, Chatham, Orange (principal county served)
- **Water systems:** active only (`WaterSystemStatusCode=A`), all system types, all source types
- **Dates:** sample collection date 2021-10-11 to 2026-10-11 (last 5 years). The sample list was first scraped for 2010-10-11 to 2026-10-11 and then filtered.
- **Scraped:** 2026-10-11

## Data

See `data/` (added once the run completes).

- `noncoliform_results_with_concentrations` — one row per sample × analyte: water system, lab sample no., collection date, analyte, method, non-detect flag, concentration + unit, reporting level + unit, monitoring period.
- `noncoliform_by_analyte` — sample counts by county and analyte (no concentrations).

### Notes

- A **non-detect** (`Non-Detect = True`, the site's "Less than Indicator" = Y) has no concentration; the reporting level is the detection limit it was below.
- For a few radionuclides in Wake and Durham, the site's analyte list reports slightly more samples than its own per-analyte sample page returns (e.g. Wake Radium-226: 3,054 vs 3,030 over 2010–2026). The data here matches the sample pages.
- Inactive water systems are not included.

## Reproducing

The site sits behind Cloudflare, which blocks plain `curl`/`requests`; `curl_cffi` impersonates Chrome's TLS fingerprint.

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 1. analyte lists + per-analyte sample lists (~450 pages)
.venv/bin/python scripts/scrape_ncdww.py run
# 2. clean sample-by-analyte tables
.venv/bin/python scripts/parse_ncdww.py run data
# 3. per-sample result pages (concentrations); resumable, ~8 pages/s
.venv/bin/python scripts/fetch_results.py run run/concentrations_work
# 4. combine into CSV + Excel
.venv/bin/python scripts/build_results.py run/concentrations_work data
```

Counties and dates are set at the top of `scrape_ncdww.py` (`COUNTIES`, `BEGIN`, `END`) and `fetch_results.py` (`MIN_DATE`).
