"""Step 3: download Sun and Earth azimuth/elevation seen from points on the Moon
(JPL Horizons API) and cache one CSV per site in data/.

Usage:
    python fetch_horizons.py                       # default window
    python fetch_horizons.py --start 2027-01-01 --stop 2027-04-01 --step 60m
    python fetch_horizons.py --only apollo11_check # one site only
"""
import argparse, io, time
import pandas as pd
import requests

API = "https://ssd.jpl.nasa.gov/api/horizons.api"
BODIES = {"sun": "10", "earth": "399"}      # Horizons IDs


def parse_horizons(text):
    """Turn Horizons observer-table text (CSV_FORMAT=YES) into a DataFrame."""
    if "$$SOE" not in text:
        raise RuntimeError("No ephemeris in reply. Horizons said:\n" + text[:2000])
    head, rest = text.split("$$SOE", 1)
    body = rest.split("$$EOE", 1)[0]
    header_line = [l for l in head.splitlines() if "Date" in l][-1]
    cols = [c.strip() for c in header_line.split(",")]
    rows = [[f.strip() for f in l.split(",")] for l in body.strip().splitlines()]
    df = pd.DataFrame([r[:len(cols)] for r in rows], columns=cols)
    time_col = [c for c in cols if c.startswith("Date")][0]
    az_col = [c for c in cols if c.startswith("Azi")][0]
    el_col = [c for c in cols if c.startswith("Elev")][0]
    out = pd.DataFrame({
        "time_utc": pd.to_datetime(df[time_col], format="%Y-%b-%d %H:%M"),
        "az_deg": pd.to_numeric(df[az_col]),
        "el_deg": pd.to_numeric(df[el_col]),
    })
    return out


def fetch_body(body_id, lat, lon_east, start, stop, step):
    params = {
        "format": "json",
        "COMMAND": f"'{body_id}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'coord@301'",             # topocentric point on the Moon (301)
        "COORD_TYPE": "'GEODETIC'",
        "SITE_COORD": f"'{lon_east},{lat},0'",   # east lon (deg), lat (deg), alt (km)
        "START_TIME": f"'{start}'",
        "STOP_TIME": f"'{stop}'",
        "STEP_SIZE": f"'{step}'",
        "QUANTITIES": "'4'",                 # apparent azimuth & elevation
        "ANG_FORMAT": "'DEG'",
        "CSV_FORMAT": "'YES'",
    }
    r = requests.get(API, params=params, timeout=60)
    r.raise_for_status()
    return parse_horizons(r.json()["result"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2027-01-01")
    ap.add_argument("--stop", default="2027-04-01")
    ap.add_argument("--step", default="60m")
    ap.add_argument("--only", default=None)
    a = ap.parse_args()

    sites = pd.read_csv("sites.csv")
    if a.only:
        sites = sites[sites.name == a.only]
    for _, s in sites.iterrows():
        print(f"Fetching {s['name']} ({s.lat_deg}, {s.lon_deg_east}) ...")
        parts = {}
        for body, bid in BODIES.items():
            df = fetch_body(bid, s.lat_deg, s.lon_deg_east, a.start, a.stop, a.step)
            parts[body] = df.rename(columns={"az_deg": f"{body}_az", "el_deg": f"{body}_el"})
            time.sleep(1)                    # be polite to the API
        out = parts["sun"].merge(parts["earth"], on="time_utc")
        out.to_csv(f"data/horizons_{s['name']}.csv", index=False)
        print(f"  saved data/horizons_{s['name']}.csv  ({len(out)} rows)")


if __name__ == "__main__":
    main()