#!/usr/bin/env python3
import argparse, csv, sys, time, re
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlencode, urljoin
from urllib import robotparser
import requests
from bs4 import BeautifulSoup

UA = "LegalPublicRecordsBot/1.0 (+contact: requester)"
TIMEOUT = 20
SLEEP_SEC = 3.0

def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def robots_allows(base_url: str, path: str) -> bool:
    rp = robotparser.RobotFileParser()
    robots_url = urljoin(base_url, "/robots.txt")
    try:
        r = requests.get(robots_url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        if r.status_code >= 400:
            return False
        rp.parse(r.text.splitlines())
        return rp.can_fetch(UA, urljoin(base_url, path))
    except Exception:
        return False

def http_get(url: str, params: Optional[Dict]=None) -> requests.Response:
    time.sleep(SLEEP_SEC)
    r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=TIMEOUT)
    r.raise_for_status()
    return r

@dataclass
class Record:
    source: str
    full_name: str
    first_name: str
    last_name: str
    middle_name: str
    dob: str
    jurisdiction: str
    doc_number: str
    status: str
    detail_url: str

def nc_doc_search(first: str, last: str) -> List[Record]:
    base = "https://webapps.doc.state.nc.us"
    path = "/opi/offendersearch.do"
    if not robots_allows(base, path):
        return []
    params = {"method": "view", "searchLastName": last, "searchFirstName": first}
    resp = http_get(urljoin(base, path), params=params)
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.select("table tr")
    out: List[Record] = []
    for tr in rows:
        tds = [clean_text(td.get_text(" ", strip=True)) for td in tr.select("td")]
        if len(tds) < 2:
            continue
        name = tds[0]
        docnum = tds[1] if re.search(r"\d", tds[1]) else ""
        a = tr.select_one("a[href*='method=view']")
        detail_href = a["href"] if a and a.has_attr("href") else ""
        detail_url = urljoin(base, detail_href) if detail_href else ""
        first_name, last_name, middle = first, last, ""
        if "," in name:
            last_name = clean_text(name.split(",")[0])
            rest = clean_text("".join(name.split(",")[1:]))
            parts = rest.split()
            if parts:
                first_name = parts[0]
                middle = " ".join(parts[1:]) if len(parts) > 1 else ""
        full_name = clean_text(name)
        out.append(Record("NC DOC", full_name, first_name, last_name, middle, "", "NC", docnum, "", detail_url))
    # detail fetch
    if robots_allows(base, path):
        for i, rec in enumerate(out):
            if not rec.detail_url:
                continue
            try:
                d = http_get(rec.detail_url)
                dsoup = BeautifulSoup(d.text, "html.parser")
                text = clean_text(dsoup.get_text(" "))
                m_dob = re.search(r"\bDOB[:\s]+([0-9]{2}/[0-9]{2}/[0-9]{4})\b", text)
                if m_dob: out[i].dob = m_dob.group(1)
                m_stat = re.search(r"\b(Custody Status|Status)[:\s]+([A-Za-z ]{3,})\b", text)
                if m_stat: out[i].status = clean_text(m_stat.group(2))
            except Exception:
                continue
    return out

def dedupe(recs: List[Record]) -> List[Record]:
    seen, out = set(), []
    for r in recs:
        key = (r.source, r.full_name, r.doc_number, r.detail_url)
        if key in seen: continue
        seen.add(key); out.append(r)
    return out

def write_csv(path: str, recs: List[Record]) -> None:
    cols = ["source","full_name","first_name","last_name","middle_name","dob","jurisdiction","doc_number","status","detail_url"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in recs:
            w.writerow(r.__dict__)

def write_manual_checklist(path: str, first: str, last: str) -> None:
    lines = [
        "# Manual checks (automation disabled to honor ToS)",
        f"- BOP Inmate Locator: https://www.bop.gov/inmateloc/?{urlencode({'inmate_first': first, 'inmate_last': last})}",
        "- VINELink: https://www.vinelink.com/",
        "- NamUs: https://www.namus.gov/",
        "- FOIA: https://www.foia.gov/",
        ""
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def run(first: str, last: str) -> List[Record]:
    return dedupe(nc_doc_search(first, last))

def main():
    ap = argparse.ArgumentParser(description="Lawful public-records locator (robots-aware).")
    ap.add_argument("--first", required=True)
    ap.add_argument("--last", required=True)
    ap.add_argument("--out", default="results.csv")
    ap.add_argument("--manual", default="manual_checklist.md")
    args = ap.parse_args()
    recs = run(args.first.strip(), args.last.strip())
    write_csv(args.out, recs)
    write_manual_checklist(args.manual, args.first.strip(), args.last.strip())
    print(f"[ok] wrote {args.out} with {len(recs)} rows")
    print(f"[ok] wrote {args.manual} with next steps")

if __name__ == "__main__":
    main()
