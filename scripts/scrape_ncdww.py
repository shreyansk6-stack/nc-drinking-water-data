"""Scrape NC Drinking Water Watch: Non-Coliform Samples [By Analyte] for several counties.

Usage: python scrape_ncdww.py OUT_DIR
Writes OUT_DIR/raw/<county>/*.html, OUT_DIR/samples.csv, OUT_DIR/analytes.csv
"""
import io, os, re, sys, time
import pandas as pd
from curl_cffi import requests

COUNTIES = ["DURHAM", "WAKE", "CHATHAM", "ORANGE"]
BEGIN, END = "10/11/2010", "10/11/2026"
BASE = "https://www.pwss.enr.state.nc.us/NCDWW2/JSP/"
DELAY = 0.7

out = sys.argv[1]


def get(s, url):
    for attempt in range(5):
        try:
            r = s.get(url, timeout=180)
            if r.status_code == 200 and "Drinking Water" in r.text:
                return r.text
            print(f"  HTTP {r.status_code}, retrying", flush=True)
        except Exception as e:
            print(f"  error {e}, retrying", flush=True)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"failed: {url}")


def clean(x):
    return re.sub(r"\s+", " ", str(x)).strip()


all_samples, all_analytes = [], []
for county in COUNTIES:
    raw = os.path.join(out, "raw", county)
    os.makedirs(raw, exist_ok=True)
    s = requests.Session(impersonate="chrome")
    search = (BASE + "SearchDispatch?number=&name=&companyname=&WaterSystemStatusCode=A"
              f"&county={county.replace(' ', '+')}&WaterSystemType=All&SourceWaterType=All"
              "&PointOfContactType=None&SampleType=NonTCRAnalyte&stateclassificationcode=All"
              f"&begin_date={BEGIN.replace('/', '%2F')}&end_date={END.replace('/', '%2F')}"
              "&action1=Search+For+Samples")
    html = get(s, search)
    open(os.path.join(raw, "_analyte_list.html"), "w").write(html)

    # analyte code -> link (the county filter lives in the session, not the link)
    links = {m.group(2).strip(): m.group(1).replace("&amp;", "&")
             for m in re.finditer(r'href="(NonTcrSamplesGlobal[^"]*)"[^>]*>\s*(?:<[^>]*>\s*)*([^<\s]+)', html)}
    t = max(pd.read_html(io.StringIO(html)), key=len)
    t = t.map(clean)
    hdr = t.iloc[0].tolist()
    t = t.iloc[1:].set_axis(hdr, axis=1)
    # pandas drops leading zeros (0999 -> 999); restore the code as written in the link text
    bare = {k.lstrip("0"): k for k in links}
    t["Analyte Code"] = t["Analyte Code"].map(lambda c: bare.get(c.lstrip("0"), c))
    missing = set(links) - set(t["Analyte Code"])
    if missing:
        print(f"  WARNING analytes not matched in table: {missing}", flush=True)
    t = t[t["Analyte Code"].isin(links)]
    print(f"{county}: {len(t)} analytes", flush=True)

    for _, a in t.iterrows():
        code, name = a["Analyte Code"], a["Analyte Name"]
        expected = int(str(a["Number of Sample(s)"]).replace(",", ""))
        time.sleep(DELAY)
        page = get(s, BASE + links[code])
        open(os.path.join(raw, f"{code}.html"), "w").write(page)
        m = re.search(r"Total Number of Records Fetched\s*=\s*([\d,]+)", page)
        fetched = int(m.group(1).replace(",", "")) if m else None
        st = max(pd.read_html(io.StringIO(page)), key=len).map(clean)
        st = st.iloc[1:].set_axis([clean(h) for h in st.iloc[0]], axis=1)
        st.insert(0, "Analyte Name", name)
        st.insert(0, "Analyte Code", code)
        st.insert(0, "Search County", county)
        all_samples.append(st)
        all_analytes.append({"Search County": county, "Analyte Code": code, "Analyte Name": name,
                             "Analyte Type": a.get("Type"), "Samples (site count)": expected,
                             "Records fetched": fetched, "Rows parsed": len(st)})
        flag = "" if len(st) == fetched else "  <-- MISMATCH"
        print(f"  {code} {name}: {len(st)} rows (site says {fetched}){flag}", flush=True)

pd.concat(all_samples).to_csv(os.path.join(out, "samples.csv"), index=False)
pd.DataFrame(all_analytes).to_csv(os.path.join(out, "analytes.csv"), index=False)
print("done", flush=True)
