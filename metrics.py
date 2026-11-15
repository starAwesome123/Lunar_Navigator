"""Site metrics from the cached Horizons CSVs (+ optional GNSS count).

NOTE: Horizons gives elevation above a SMOOTH lunar sphere. Real polar sunlight
and Earth visibility are dominated by terrain, so treat results as a baseline.
"""
import os
import numpy as np
import pandas as pd

# Screening thresholds used in Gracy & Lee (2024) for Artemis III candidate sites
MIN_SUN_PCT, MIN_EARTH_PCT = 33.0, 50.0


def load_site(name, data_dir="data"):
    return pd.read_csv(os.path.join(data_dir, f"horizons_{name}.csv"),
                       parse_dates=["time_utc"])


def load_gnss(data_dir="data"):
    path = os.path.join(data_dir, "gnss_count.csv")
    if not os.path.exists(path):
        return None
    return pd.read_csv(path, parse_dates=["time_utc"])


def longest_run_hours(mask, step_h):
    best = cur = 0
    for v in np.asarray(mask, dtype=bool):
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best * step_h


def count_full_windows(mask, hours_needed, step_h):
    """(#start times with an unbroken run of `hours_needed`, #possible start times)."""
    n = max(int(round(hours_needed / step_h)), 1)
    m = pd.Series(np.asarray(mask, dtype=int))
    if len(m) < n:
        return 0, 0
    ok = int((m.rolling(n).sum() == n).sum())
    return ok, len(m) - n + 1


def site_metrics(df, gnss=None, mission_days=6):
    df = df.sort_values("time_utc").reset_index(drop=True)
    step_h = (df.time_utc.iloc[1] - df.time_utc.iloc[0]).total_seconds() / 3600
    sun = (df.sun_el > 0).to_numpy()
    earth = (df.earth_el > 0).to_numpy()
    both = sun & earth
    ok, total = count_full_windows(both, mission_days * 24, step_h)
    out = {
        "sunlit_%": 100 * sun.mean(),
        "earth_visible_%": 100 * earth.mean(),
        "sun_and_earth_%": 100 * both.mean(),
        "longest_dark_h": longest_run_hours(~sun, step_h),
        "longest_earth_outage_h": longest_run_hours(~earth, step_h),
        "longest_sun+earth_h": longest_run_hours(both, step_h),
        f"start_times_for_{mission_days}d_mission_%": 100 * ok / total if total else np.nan,
        "meets_sun_33%": bool(100 * sun.mean() >= MIN_SUN_PCT),
        "meets_earth_50%": bool(100 * earth.mean() >= MIN_EARTH_PCT),
    }
    if gnss is not None:
        g = df[["time_utc"]].merge(gnss, on="time_utc", how="left")
        n = g["n_total"].fillna(0).to_numpy()
        out["earth_up_and_>=1_gnss_%"] = 100 * (earth & (n >= 1)).mean()
        out["earth_up_and_>=4_gnss_%"] = 100 * (earth & (n >= 4)).mean()
    return out


def hours_until_change(el, k, step_h):
    """From index k: (hours until the body crosses the horizon, currently_up).
    hours is None if no crossing happens in the data."""
    el = np.asarray(el)
    up = bool(el[k] > 0)
    for j in range(k + 1, len(el)):
        if (el[j] > 0) != up:
            return (j - k) * step_h, up
    return None, up