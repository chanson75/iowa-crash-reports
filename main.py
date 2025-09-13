import re
import sys
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs
import os

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import create_client, Client

# ----------------------
# Load environment
# ----------------------
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL or SUPABASE_KEY not set in environment")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BASE = "https://accidentreports.iowa.gov/"
RESULTS_URL = "https://accidentreports.iowa.gov/?dist=scraper"

# ----------------------
# Helpers
# ----------------------
def get_clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]{2,}", "  ", text)
    return text.strip()

def extract_label(text: str, label: str) -> str | None:
    el = re.escape(label)
    pattern = rf"{el}:\s*(?P<val>.*?)(?=(?:\s{{2,}}[A-Za-z0-9 &()\/-]+?:)|(?:\n[A-Za-z0-9 &()\/-]+?:)|$)"
    m = re.search(pattern, text, re.S | re.I)
    if m:
        return re.sub(r"\s{2,}", " ", m.group("val").strip())
    m2 = re.search(rf"{el}:\s*(?P<val>[^\n\r]+)", text, re.I)
    if m2:
        return m2.group("val").strip()
    return None

def parse_crash_date(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    for fmt in ("%m%d%Y", "%Y%m%d", "%m%d%y", "%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except:
            continue
    return s

def parse_time(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    m = re.search(r"(\d{3,4})", s)
    if m:
        t = m.group(1).zfill(4)
        return f"{t[:2]}:{t[2:]}"
    try:
        dt = datetime.strptime(s, "%H:%M")
        return dt.time().isoformat(timespec="minutes")
    except:
        pass
    return s

# ----------------------
# Parser
# ----------------------
def parse_minimal_report(html: str, url: str = None) -> dict:
    text = get_clean_text(html)
    report = {
        "case_number": None,
        "report_type": None,
        "county": None,
        "crash_date": None,
        "crash_time": None,
        "location": None,
        "officer_name": None,
        "post": None,
        "assisted_by": None,
        "summary": None,
    }

    for lab, key in [
        ("Case Number", "case_number"),
        ("Type", "report_type"),
        ("County", "county"),
        ("Crash Date", "crash_date"),
        ("Time", "crash_time"),
        ("Location", "location"),
        ("Officer Name", "officer_name"),
        ("Post", "post"),
        ("Assisted By", "assisted_by"),
        ("Summary", "summary"),
    ]:
        val = extract_label(text, lab)
        if val:
            if key == "crash_date":
                report[key] = parse_crash_date(val)
            elif key == "crash_time":
                report[key] = parse_time(val)
            else:
                report[key] = val

    if not report["case_number"] and url:
        try:
            qs = parse_qs(urlparse(url).query)
            if "caseno" in qs:
                report["case_number"] = qs["caseno"][0]
        except:
            pass

    # VEHICLES
    vehicles = []
    veh_block_re = re.compile(
        r"(Vehicle\s*(\d+)\b.*?)(?=(?:\n\s*Vehicle\s*\d+\b)|(?:\n\s*Injury\s*\d+\b)|(?:\n\s*Motor Carrier Info)|(?:\n\s*Summary:)|$)",
        re.S | re.I
    )
    for m in veh_block_re.finditer(text):
        block = m.group(1)
        vn = m.group(2)
        v = {"vehicle_number": int(vn)}
        for vlab, vkey in [
            ("Year", "year"),
            ("Make", "make"),
            ("Type", "type"),
            ("Towed By", "towed_by"),
            ("Driver Name", "driver_name"),
            ("Age", "age"),
            ("City & State of Residence", "city_state"),
            ("City & State", "city_state"),
        ]:
            vv = extract_label(block, vlab)
            if vv is not None:
                v[vkey] = vv
        vehicles.append(v)

    # INJURIES
    injuries = []
    inj_block_re = re.compile(
        r"(Injury\s*(\d+)\b.*?)(?=(?:\n\s*Injury\s*\d+\b)|(?:\n\s*Motor Carrier Info)|(?:\n\s*Summary:)|(?:\n\s*Officer Name:)|$)",
        re.S | re.I
    )
    for m in inj_block_re.finditer(text):
        block = m.group(1)
        inj_num = int(m.group(2))
        inj = {"injury_index": inj_num}
        for ilab, ikey in [
            ("Injury %d Type" % inj_num, "type"),
            ("Type", "type"),
            ("Name", "name"),
            ("Age", "age"),
            ("City & State of Residence", "city_state"),
            ("Seatbelt Use", "seatbelt_use"),
            ("Life saved by Seatbelt", "life_saved_by_seatbelt"),
            ("Transported To", "transported_to"),
            ("Transported By", "transported_by"),
        ]:
            val = extract_label(block, ilab) if "%d" in ilab else extract_label(block, ilab)
            if not val:
                val = extract_label(block, ikey.replace("_", " ").title())
            if val:
                inj[ikey] = val
        injuries.append(inj)

    # MOTOR CARRIER
    # MOTOR CARRIER
    motor_carrier = []
    if "Motor Carrier Info" in text:
        mc_block_re = re.compile(r"Motor Carrier Info(.*?)(?=(?:\n\s*Summary:)|$)", re.S | re.I)
        mm = mc_block_re.search(text)
        if mm:
            mb = mm.group(1)
            mc_entry = {}
            for lab in ("Name of Carrier", "DOT or MCC #", "City & State of Carrier", "Hazmat Involved?"):
                v = extract_label(mb, lab)
                if v:
                    key = lab.lower().replace(" ", "_")
                    mc_entry[key] = v
            
            # Only append if not already in the list
            if mc_entry and mc_entry not in motor_carrier:
                motor_carrier.append(mc_entry)


    return {
        "report": report,
        "vehicles": vehicles,
        "injuries": injuries,
        "motor_carrier": motor_carrier,
        "raw_text_sample": text.splitlines()[:8]
    }

# ----------------------
# Supabase inserts
# ----------------------
def insert_report_supabase(rep):
    """Insert or update a report row in Supabase."""
    if not rep.get("case_number"):
        return
    data = {
        "case_number": rep.get("case_number"),
        "report_type": rep.get("report_type"),
        "county": rep.get("county"),
        "crash_date": rep.get("crash_date"),
        "crash_time": rep.get("crash_time"),
        "location": rep.get("location"),
        "officer_name": rep.get("officer_name"),
        "post": rep.get("post"),
        "assisted_by": rep.get("assisted_by"),
        "summary": rep.get("summary"),
    }
    supabase.table("reports").upsert(data, on_conflict="case_number").execute()


def insert_vehicles_supabase(case_number, vehicles):
    """Insert vehicles for a report in Supabase."""
    to_insert = []
    for v in vehicles:
        if v.get("year") in ["Make:"]:
            continue
        to_insert.append({
            "case_number": case_number,
            "vehicle_number": v.get("vehicle_number"),
            "year": v.get("year"),
            "make": v.get("make"),
            "type": v.get("type"),
            "towed_by": v.get("towed_by"),
            "driver_name": v.get("driver_name"),
            "age": v.get("age"),
            "city_state": v.get("city_state"),
        })
    if to_insert:
        # Use unique constraint (case_number + vehicle_number) to avoid duplicates
        supabase.table("vehicles").upsert(to_insert, on_conflict="case_number,vehicle_number").execute()


def insert_injuries_supabase(case_number, injuries):
    to_insert = []
    for inj in injuries:
        if inj.get("type") not in ["Injured", "Fatality"]:
            continue
        to_insert.append({
            "case_number": case_number,
            "injury_index": inj.get("injury_index"),
            "type": inj.get("type"),
            "name": inj.get("name"),
            "age": inj.get("age"),
            "city_state": inj.get("city_state"),
            "seatbelt_use": inj.get("seatbelt_use"),
            "life_saved_by_seatbelt": inj.get("life_saved_by_seatbelt"),
            "transported_to": inj.get("transported_to"),
            "transported_by": inj.get("transported_by"),
        })
    if to_insert:
        # Use unique constraint (case_number + injury_index)
        supabase.table("injuries").upsert(to_insert, on_conflict=["case_number", "injury_index"]).execute()


def insert_motor_carriers_supabase(case_number, carriers):
    to_insert = []
    for c in carriers:
        carrier_name = c.get("name_of_carrier")
        usdot = c.get("dot_or_mcc_#")
        if not carrier_name or carrier_name.strip() in ["DOT or MCC #:", ""]:
            continue
        if not usdot or usdot.strip() in ["DOT or MCC #:", ""]:
            continue
        to_insert.append({
            "case_number": case_number,
            "carrier_name": carrier_name,
            "usdot_or_mcc": usdot,
            "city_state": c.get("city_state_of_carrier"),
            "hazmat_involved": c.get("hazmat_involved?"),
        })
    if to_insert:
        # Use unique constraint (case_number + usdot_or_mcc)
        supabase.table("motor_carriers").upsert(to_insert, on_conflict=["case_number", "usdot_or_mcc"]).execute()


# ----------------------
# Fetch listings
# ----------------------
def search_crashes_in_range(start_date: datetime, end_date: datetime):
    r = requests.get(RESULTS_URL, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    matches = []
    for a in soup.find_all("a"):
        text = " ".join(a.get_text(strip=True, separator=" ").split())
        m = re.search(r"on ([A-Za-z]+ \d{1,2}, \d{4})$", text)
        if m:
            try:
                d = datetime.strptime(m.group(1), "%B %d, %Y").date()
            except:
                continue
            if start_date.date() <= d <= end_date.date():
                href = a.get("href")
                if href:
                    matches.append({"title": text, "url": urljoin(BASE, href)})
    return matches

# ----------------------
# CLI main
# ----------------------
def parse_input_date(s: str) -> datetime:
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s, fmt)
        except:
            pass
    m = re.match(r"^(\d{8})$", s)
    if m:
        try:
            return datetime.strptime(m.group(1), "%m%d%Y")
        except:
            pass
    raise ValueError("Could not parse date: " + s)

def main(argv):
    if len(argv) < 3:
        print("Usage: python main.py <start_date> <end_date>")
        return
    start = parse_input_date(argv[1])
    end = parse_input_date(argv[2])

    print(f"Searching results page for crashes from {start.date()} to {end.date()} ...")
    matches = search_crashes_in_range(start, end)
    if not matches:
        print("No crash listings found in the Results list for that date range.")
        return

    sess = requests.Session()

    for idx, m in enumerate(matches, 1):
        print(f"\n[{idx}/{len(matches)}] Fetching {m['url']} ...")
        resp = sess.get(m['url'], timeout=30)
        resp.raise_for_status()
        parsed = parse_minimal_report(resp.text, url=m['url'])
        rep = parsed['report']

        if not rep.get("case_number"):
            qs = parse_qs(urlparse(m['url']).query)
            if 'caseno' in qs:
                rep['case_number'] = qs['caseno'][0]

        if rep.get("case_number"):
            insert_report_supabase(rep)
            insert_vehicles_supabase(rep['case_number'], parsed['vehicles'])
            insert_injuries_supabase(rep['case_number'], parsed['injuries'])
            insert_motor_carriers_supabase(rep['case_number'], parsed['motor_carrier'])
            print(f"  -> inserted case: {rep['case_number']}")
        else:
            print("  -> missing case_number, skipped.")

    print("\nDone. Data inserted into Supabase.")

if __name__ == "__main__":
    main(sys.argv)
