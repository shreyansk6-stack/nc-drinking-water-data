"""Fetch per-sample result pages (concentrations) for every sample found by scrape_ncdww.py.

Usage: python fetch_results.py RUN_DIR WORK_DIR
Resumable: appends parsed rows to WORK_DIR/<county>.jsonl and skips sample ids already done.
"""
import datetime as dt, json, os, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from lxml import html as lh
from curl_cffi import requests

run, work = sys.argv[1], sys.argv[2]
COUNTIES = ["CHATHAM", "DURHAM", "ORANGE", "WAKE"]
BASE = "https://www.pwss.enr.state.nc.us/NCDWW2/JSP/"
WORKERS, DELAY = 3, 0.3
MIN_DATE = dt.date(2021, 10, 11)  # last 5 years (collection date)
COLS = ["Analyte Code", "Analyte Name", "Method Code", "Less Than Indicator", "Level Type",
        "Reporting Level", "Concentration", "Monitoring Period Begin", "Monitoring Period End"]
os.makedirs(os.path.join(work, "bad"), exist_ok=True)
tls = threading.local()
lock = threading.Lock()
pause_until = [0.0]


def norm(t):
    return re.sub(r"\s+", " ", t.replace("\xa0", " ")).strip()


def parse(page):
    doc = lh.fromstring(page)
    text = norm(doc.text_content())
    head = {}
    for key, label in [("Water System No.", "Water System No"), ("Water System Name", "Water System Name"),
                       ("Principal County Served", "Principal Cnty Served"),
                       ("Lab Sample No.", "Lab Sample No"), ("Collection Date", "Collection Date")]:
        m = re.search(re.escape(label) + r"\.? : (.*?) (?:Federal Type|Water System|Principal|Lab Sample|Collection Date|Analyte Code)", text)
        head[key] = m.group(1).strip() if m else None
    rows = []
    for tr in doc.iter("tr"):
        cells = [norm(td.text_content()) for td in tr.findall("td")]
        if len(cells) == 9 and re.fullmatch(r"\d{4}", cells[0]):
            rows.append(dict(zip(COLS, cells)))
    m = re.search(r"Total Number of Records Fetched\s*=\s*([\d,]+)", text)
    total = int(m.group(1).replace(",", "")) if m else None
    return head, rows, total


def fetch(sid, link):
    if not hasattr(tls, "s"):
        tls.s = requests.Session(impersonate="chrome")
    url = BASE + link.replace("&amp;", "&").replace(" ", "%20")
    for attempt in range(8):
        wait = pause_until[0] - time.time()
        if wait > 0:
            time.sleep(wait)
        try:
            r = tls.s.get(url, timeout=90)
            if r.status_code == 200 and "Non-Coliform Sample" in r.text:
                time.sleep(DELAY)
                return r.text
            code = r.status_code
        except Exception as e:
            code = repr(e)[:80]
        backoff = min(600, 15 * 2 ** attempt)
        with lock:
            pause_until[0] = max(pause_until[0], time.time() + backoff)
            print(f"  sample {sid}: {code}; all workers pausing {backoff}s", flush=True)
    return None


for county in COUNTIES:
    links = {}
    folder = os.path.join(run, "raw", county)
    for f in sorted(os.listdir(folder)):
        if f[0].isdigit():
            for m in re.finditer(r'href="(NonTcrSampleResultsGlobal[^"]*tsasampl_is_number=(\d+)[^"]*)"',
                                 open(os.path.join(folder, f)).read()):
                d = re.search(r"collection_date=\s*(\d\d)-(\d\d)-(\d{4})", m.group(1))
                if dt.date(int(d.group(3)), int(d.group(1)), int(d.group(2))) >= MIN_DATE:
                    links.setdefault(m.group(2), m.group(1))
    out_path = os.path.join(work, f"{county}.jsonl")
    done = set()
    if os.path.exists(out_path):
        for line in open(out_path):
            done.add(json.loads(line)["sample_id"])
    todo = [(k, v) for k, v in links.items() if k not in done]
    print(f"{county}: {len(links)} samples, {len(done)} already done, {len(todo)} to fetch", flush=True)
    out = open(out_path, "a")
    n, t0 = 0, time.time()

    def job(item):
        sid, link = item
        page = fetch(sid, link)
        if page is None:
            return sid, None
        head, rows, total = parse(page)
        if total is None or total != len(rows):
            open(os.path.join(work, "bad", f"{county}_{sid}.html"), "w").write(page)
        return sid, {"sample_id": sid, "county": county, "head": head, "rows": rows,
                     "site_total": total, "parsed": len(rows)}

    with ThreadPoolExecutor(WORKERS) as ex:
        for sid, rec in ex.map(job, todo):
            if rec is None:
                print(f"  GAVE UP on sample {sid}", flush=True)
                continue
            out.write(json.dumps(rec) + "\n")
            n += 1
            if n % 500 == 0:
                out.flush()
                rate = n / (time.time() - t0)
                print(f"  {county}: {n}/{len(todo)}  {rate:.1f}/s  ~{(len(todo) - n) / rate / 60:.0f} min left",
                      flush=True)
    out.close()
    print(f"{county}: finished", flush=True)
print("ALL DONE", flush=True)
