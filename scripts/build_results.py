"""Combine fetched per-sample results into CSV + Excel.

Usage: python build_results.py RUN_DIR WORK_DIR OUT_DIR
(RUN_DIR holds the by-analyte pages from scrape_ncdww.py; WORK_DIR the output of fetch_results.py)
"""
import json, os, re, sys
import pandas as pd

run, work, out = sys.argv[1], sys.argv[2], sys.argv[3]
COLIFORM = {"3100", "3013", "3014"}  # coliform analytes; the site's non-coliform searches exclude these

# (sample id, analyte code) pairs shown by the site's Non-Coliform [By Analyte] search
listed = set()
for county in ["CHATHAM", "DURHAM", "ORANGE", "WAKE"]:
    folder = os.path.join(run, "raw", county)
    for f in os.listdir(folder):
        if f[0].isdigit():
            for m in re.finditer(r"tsasampl_is_number=(\d+)", open(os.path.join(folder, f)).read()):
                listed.add((m.group(1), f[:-5]))
recs = []
for county in ["CHATHAM", "DURHAM", "ORANGE", "WAKE"]:
    p = os.path.join(work, f"{county}.jsonl")
    if not os.path.exists(p):
        continue
    for line in open(p):
        r = json.loads(line)
        h = r["head"]
        for row in r["rows"]:
            recs.append({"Search County": county, "Sample ID": r["sample_id"], **h, **row})

d = pd.DataFrame(recs)
d = d.drop_duplicates()
d = d[~d["Analyte Code"].isin(COLIFORM)]
d["In By-Analyte Search"] = [(s, a) in listed for s, a in zip(d["Sample ID"], d["Analyte Code"])]
d["Reporting Level"] = d["Reporting Level"].replace("null null", "")


def split_unit(v):
    m = re.fullmatch(r"([-+]?[\d.]+(?:[eE][-+]?\d+)?)\s*(.*)", v or "")
    return (float(m.group(1)), m.group(2).strip()) if m else (None, v or "")


d[["Concentration Value", "Concentration Unit"]] = d["Concentration"].apply(lambda v: pd.Series(split_unit(v)))
d[["Reporting Level Value", "Reporting Level Unit"]] = d["Reporting Level"].apply(lambda v: pd.Series(split_unit(v)))
d["Non-Detect"] = d["Less Than Indicator"].eq("Y")
# the site records some non-detects as "0" or as a bare unit; they are not measurements
d.loc[d["Non-Detect"], "Concentration Value"] = None
d.loc[d["Concentration Unit"].eq(""), "Concentration Unit"] = d["Reporting Level Unit"]
for c in ["Collection Date", "Monitoring Period Begin", "Monitoring Period End"]:
    d[c] = pd.to_datetime(d[c], format="%m-%d-%Y", errors="coerce")
d = d[d["Collection Date"].between("2021-10-11", "2026-10-11")]  # last 5 years

d = d[["Principal County Served", "Water System No.", "Water System Name", "Lab Sample No.", "Sample ID",
       "Collection Date", "Analyte Code", "Analyte Name", "In By-Analyte Search", "Method Code", "Non-Detect",
       "Concentration Value", "Concentration Unit", "Reporting Level Value", "Reporting Level Unit",
       "Level Type", "Concentration", "Reporting Level", "Monitoring Period Begin", "Monitoring Period End",
       "Search County"]]
d = d.sort_values(["Principal County Served", "Analyte Name", "Water System No.", "Collection Date"])

summary = (d.groupby(["Principal County Served", "Analyte Code", "Analyte Name"])
           .agg(Results=("Sample ID", "size"),
                Detects=("Concentration Value", "count"),
                Water_Systems=("Water System No.", "nunique"),
                Unit=("Concentration Unit", lambda x: ", ".join(sorted(set(u for u in x if u)))),
                Min_Detected=("Concentration Value", "min"),
                Median_Detected=("Concentration Value", "median"),
                Max_Detected=("Concentration Value", "max"),
                First=("Collection Date", "min"), Last=("Collection Date", "max"))
           .reset_index())
summary.columns = [c.replace("_", " ") for c in summary.columns]

os.makedirs(out, exist_ok=True)
d.to_csv(os.path.join(out, "noncoliform_results_with_concentrations.csv"), index=False)
with pd.ExcelWriter(os.path.join(out, "noncoliform_results_with_concentrations.xlsx"), engine="openpyxl",
                    datetime_format="yyyy-mm-dd") as xw:
    summary.to_excel(xw, sheet_name="Summary", index=False)
    for county, g in d.groupby("Principal County Served"):
        g = g.drop(columns=["Search County", "Concentration", "Reporting Level"])
        if len(g) > 1_048_000:  # Excel row limit
            half = len(g) // 2 + 1
            g.iloc[:half].to_excel(xw, sheet_name=f"{county.title()} 1", index=False)
            g.iloc[half:].to_excel(xw, sheet_name=f"{county.title()} 2", index=False)
        else:
            g.to_excel(xw, sheet_name=county.title(), index=False)
    for ws in xw.book.worksheets:
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for col in ws.columns:
            w = max(len(str(c.value)) for c in col[:200] if c.value is not None)
            ws.column_dimensions[col[0].column_letter].width = min(w + 2, 40)

print(d.shape)
print(d.groupby("Principal County Served").agg(results=("Sample ID", "size"), samples=("Sample ID", "nunique"),
                                               detects=("Non-Detect", lambda x: int((~x).sum()))))
print("county mismatch rows:", int((d["Principal County Served"] != d["Search County"]).sum()))
print("unparsed detect concentrations:", int((~d["Non-Detect"] & d["Concentration"].ne("") & d["Concentration Value"].isna()).sum()))
print("not in by-analyte search:", int((~d["In By-Analyte Search"]).sum()))
print("detects without a concentration:",
      d[~d["Non-Detect"] & d["Concentration Value"].isna()]["Analyte Name"].value_counts().to_dict())
print(d["Concentration Unit"].value_counts().head(15))
