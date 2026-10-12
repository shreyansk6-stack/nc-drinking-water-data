"""Re-parse saved NCDWW pages into a clean CSV + Excel workbook.

Usage: python parse_ncdww.py RUN_DIR OUT_DIR
"""
import io, os, re, sys
import pandas as pd

run, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)


def clean(x):
    return "" if pd.isna(x) else re.sub(r"\s+", " ", str(x)).strip()


def data_table(html, must_have):
    """Return the table whose header row contains `must_have`, with that row as header."""
    for t in pd.read_html(io.StringIO(html), converters=None):
        t = t.map(clean)
        for i in range(min(3, len(t))):
            row = t.iloc[i].tolist()
            if must_have in row:
                return t.iloc[i + 1:].set_axis(row, axis=1).reset_index(drop=True)
    raise ValueError(f"no table with {must_have}")


analytes = pd.read_csv(os.path.join(run, "analytes.csv"), dtype=str)
frames, checks = [], []
for _, a in analytes.iterrows():
    county, code = a["Search County"], a["Analyte Code"]
    html = open(os.path.join(run, "raw", county, f"{code}.html")).read()
    m = re.search(r"Total Number of Records Fetched\s*=\s*([\d,]+)", html)
    fetched = int(m.group(1).replace(",", ""))
    t = data_table(html, "Lab Sample No.")
    t = t[t["Lab Sample No."] != ""]
    t.insert(0, "Analyte Type", a["Analyte Type"])
    t.insert(0, "Analyte Name", a["Analyte Name"])
    t.insert(0, "Analyte Code", code)
    frames.append(t)
    checks.append({**a.to_dict(), "Records fetched": fetched, "Rows parsed": len(t)})

s = pd.concat(frames, ignore_index=True)
s = s[["Principal County Served", "Analyte Code", "Analyte Name", "Analyte Type",
       "Water System No.", "Water System Name", "Lab Sample No.", "Type",
       "Collection Date", "Sampling Point"]]
s = s.rename(columns={"Type": "Sample Type"})
s["Collection Date"] = pd.to_datetime(s["Collection Date"], format="%m-%d-%Y")
c = pd.DataFrame(checks)
c["Rows parsed"] = c["Rows parsed"].astype(int)
c["Samples (site count)"] = c["Samples (site count)"].astype(int)

bad = c[c["Rows parsed"] != c["Records fetched"]]
assert bad.empty, bad
print(s.shape, s.isna().sum().sum(), "nulls")

summary = (s.groupby(["Principal County Served", "Analyte Code", "Analyte Name", "Analyte Type"])
           .agg(Samples=("Lab Sample No.", "size"),
                Water_Systems=("Water System No.", "nunique"),
                First_Sample=("Collection Date", "min"),
                Last_Sample=("Collection Date", "max"))
           .reset_index().rename(columns={"Water_Systems": "Water Systems",
                                          "First_Sample": "First Sample", "Last_Sample": "Last Sample"}))
summary = summary.merge(
    c.rename(columns={"Search County": "Principal County Served"})[
        ["Principal County Served", "Analyte Code", "Samples (site count)"]],
    on=["Principal County Served", "Analyte Code"])
summary["Note"] = summary.apply(
    lambda r: "" if r["Samples"] == r["Samples (site count)"] else
    "Site's analyte list count differs from rows on its sample page", axis=1)
wide = summary.pivot_table(index=["Analyte Code", "Analyte Name", "Analyte Type"],
                           columns="Principal County Served", values="Samples",
                           fill_value=0).reset_index()
wide.columns.name = None

s.to_csv(os.path.join(out, "noncoliform_samples_all_counties.csv"), index=False)
with pd.ExcelWriter(os.path.join(out, "noncoliform_by_analyte.xlsx"), engine="openpyxl",
                    datetime_format="yyyy-mm-dd") as xw:
    wide.to_excel(xw, "Counts by county", index=False)
    summary.to_excel(xw, "Summary", index=False)
    for county, g in s.groupby("Principal County Served"):
        g.sort_values(["Analyte Name", "Collection Date"]).to_excel(xw, county.title(), index=False)
    for ws in xw.book.worksheets:
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for col in ws.columns:
            w = max(len(str(col[0].value)), *(len(str(c.value)) for c in col[1:200] if c.value is not None))
            ws.column_dimensions[col[0].column_letter].width = min(w + 2, 45)
print(summary.groupby("Principal County Served")[["Samples"]].sum())
print(summary[summary["Note"] != ""][["Principal County Served", "Analyte Name", "Samples", "Samples (site count)"]].to_string())
