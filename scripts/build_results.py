"""Combine fetched per-sample results into CSV + Excel.

Usage: python build_results.py WORK_DIR OUT_DIR
"""
import json, os, re, sys
import pandas as pd

work, out = sys.argv[1], sys.argv[2]
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


def split_unit(v):
    m = re.fullmatch(r"([-+]?[\d.]+(?:[eE][-+]?\d+)?)\s*(.*)", v or "")
    return (float(m.group(1)), m.group(2).strip()) if m else (None, v or "")


d[["Concentration Value", "Concentration Unit"]] = d["Concentration"].apply(lambda v: pd.Series(split_unit(v)))
d[["Reporting Level Value", "Reporting Level Unit"]] = d["Reporting Level"].apply(lambda v: pd.Series(split_unit(v)))
d["Non-Detect"] = d["Less Than Indicator"].eq("Y")
for c in ["Collection Date", "Monitoring Period Begin", "Monitoring Period End"]:
    d[c] = pd.to_datetime(d[c], format="%m-%d-%Y", errors="coerce")
d = d[d["Collection Date"].between("2021-10-11", "2026-10-11")]  # last 5 years

d = d[["Principal County Served", "Water System No.", "Water System Name", "Lab Sample No.", "Sample ID",
       "Collection Date", "Analyte Code", "Analyte Name", "Method Code", "Non-Detect",
       "Concentration Value", "Concentration Unit", "Reporting Level Value", "Reporting Level Unit",
       "Level Type", "Concentration", "Reporting Level", "Monitoring Period Begin", "Monitoring Period End",
       "Search County"]]
d = d.sort_values(["Principal County Served", "Analyte Name", "Water System No.", "Collection Date"])

summary = (d.groupby(["Principal County Served", "Analyte Code", "Analyte Name"])
           .agg(Results=("Sample ID", "size"),
                Detects=("Non-Detect", lambda x: int((~x).sum())),
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
print("unparsed concentrations:", int((d["Concentration"].ne("") & d["Concentration Value"].isna()).sum()))
print("non-detects with a concentration:", int((d["Non-Detect"] & d["Concentration Value"].notna()).sum()))
print("detects without a concentration:", int((~d["Non-Detect"] & d["Concentration Value"].isna()).sum()))
print(d["Concentration Unit"].value_counts().head(15))
