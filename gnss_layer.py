"""Count GPS + Galileo satellites whose signals could reach the Moon.

Geometry only (no signal strength). Receiver = Moon's centre (a lunar site is
~1700 km off-centre, a tiny angle at 384,000 km). A satellite counts if
 (1) the line satellite->Moon does not pass through Earth, and
 (2) the angle between the satellite's Earth-pointing axis and the direction to
     the Moon is <= MAX_OFF_DEG (main-lobe limit).
Usage: python gnss_layer.py data/horizons_apollo11_check.csv --max-off-deg 23.5
Output: data/gnss_count.csv (time_utc, n_gps, n_gal, n_total)

MAX_OFF_DEG default is a typical GPS L1 main-lobe value: VERIFY it against the
LuGRE paper (DOI 10.33012/navi.756) / GPS Space Service Volume documents.
TLE predictions are only good for days to a few weeks: keep the window short.
"""
import argparse
import numpy as np
import pandas as pd

R_EARTH_KM = 6371.0
URLS = {"gps": "https://celestrak.org/NORAD/elements/gp.php?GROUP=gps-ops&FORMAT=tle",
        "gal": "https://celestrak.org/NORAD/elements/gp.php?GROUP=galileo&FORMAT=tle"}


def usable_mask(sat_km, moon_km, max_off_deg, margin_km=100.0):
    """sat_km, moon_km: arrays (3, T). Returns boolean array (T,)."""
    to_moon = moon_km - sat_km
    to_earth = -sat_km
    cosang = (to_moon * to_earth).sum(0) / (
        np.linalg.norm(to_moon, axis=0) * np.linalg.norm(to_earth, axis=0))
    off = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
    # closest approach of the segment sat->Moon to Earth's centre
    t = np.clip(-(sat_km * to_moon).sum(0) / (to_moon * to_moon).sum(0), 0, 1)
    closest = np.linalg.norm(sat_km + t * to_moon, axis=0)
    return (off <= max_off_deg) & (closest > R_EARTH_KM + margin_km)


def main():
    import requests
    from skyfield.api import Loader
    ap = argparse.ArgumentParser()
    ap.add_argument("horizons_csv")
    ap.add_argument("--max-off-deg", type=float, default=23.5)
    a = ap.parse_args()

    times = pd.read_csv(a.horizons_csv, parse_dates=["time_utc"]).time_utc
    load = Loader("data")
    ts = load.timescale()
    t = ts.utc(times.dt.year.values, times.dt.month.values, times.dt.day.values,
               times.dt.hour.values, times.dt.minute.values)
    eph = load("de421.bsp")
    moon_km = eph["earth"].at(t).observe(eph["moon"]).position.km

    out = pd.DataFrame({"time_utc": times})
    for key, url in URLS.items():
        r = requests.get(url, timeout=60); r.raise_for_status()
        with open(f"data/{key}.tle", "w") as f:
            f.write(r.text)
        sats = load.tle_file(f"{key}.tle")
        count = np.zeros(len(times), dtype=int)
        used = 0
        for s in sats:
            try:
                count += usable_mask(s.at(t).position.km, moon_km, a.max_off_deg)
                used += 1
            except Exception as e:                      # skip bad/decayed elements
                print("skip", s.name, e)
        out[f"n_{key}"] = count
        print(f"{key}: {used} satellites, max simultaneously usable = {count.max()}")
    out["n_total"] = out.n_gps + out.n_gal
    out.to_csv("data/gnss_count.csv", index=False)
    print("saved data/gnss_count.csv")


if __name__ == "__main__":
    main()