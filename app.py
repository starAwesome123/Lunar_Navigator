"""Lunar Landing Site Navigator - minimal MVP (Streamlit).
Run:  streamlit run app.py
"""
import os
from datetime import timedelta
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from metrics import load_site, load_gnss, site_metrics, hours_until_change

st.set_page_config(page_title=" LuGRE landing navigation site", layout="wide")
st.title("LuGRE landing navigation site")
st.caption("Compare lunar landing sites by Sun and Earth visibility, plus a GNSS-signal "
           "geometry layer (can Earth's GPS/Galileo signals reach the site?).")

sites = pd.read_csv("sites.csv")
sites = sites[sites.name.apply(lambda n: os.path.exists(f"data/horizons_{n}.csv"))]
gnss = load_gnss()

with st.sidebar:
    pick = st.multiselect("Sites", list(sites.name), default=list(sites.name)[1:3])
    mission_days = st.slider("Surface mission length (days)", 1, 10, 6)
if not pick:
    st.info("Pick at least one site.")
    st.stop()

data = {n: load_site(n) for n in pick}
t_min = min(d.time_utc.min() for d in data.values()).to_pydatetime()
t_max = max(d.time_utc.max() for d in data.values()).to_pydatetime()
start, end = st.sidebar.slider("Date range (UTC)", t_min, t_max, (t_min, t_max))
data = {n: d[(d.time_utc >= start) & (d.time_utc <= end)] for n, d in data.items()}

rows = {}
for n, d in data.items():
    if len(d) < 2:
        continue
    rows[n] = site_metrics(d, gnss, mission_days)
table = pd.DataFrame(rows).T
st.subheader("Side-by-side comparison")
st.dataframe(table.round(1))
st.caption("meets_sun_33% / meets_earth_50% reuse the screening thresholds from Gracy & Lee (2024). "
           "Values are a smooth-horizon baseline, not terrain-aware site results.")

st.subheader("Sky view: where are the Sun and Earth at a chosen time?")
st.caption("Centre = straight overhead, outer ring = horizon. Filled dot = above the horizon, hollow dot = below it. "
           "Azimuth: 0 deg = north, clockwise.")
t_sel = st.slider("Time (UTC)", start, end, value=start, step=timedelta(hours=1))
dial_cols = st.columns(min(len(data), 3))
for i, (n, d) in enumerate(data.items()):
    d = d.sort_values("time_utc").reset_index(drop=True)
    if len(d) < 2:
        continue
    step_h = (d.time_utc.iloc[1] - d.time_utc.iloc[0]).total_seconds() / 3600
    k = int((d.time_utc - pd.Timestamp(t_sel)).abs().idxmin())
    row = d.iloc[k]
    with dial_cols[i % len(dial_cols)]:
        fig = plt.figure(figsize=(3.4, 3.4))
        ax = fig.add_subplot(111, projection="polar")
        ax.set_theta_zero_location("N"); ax.set_theta_direction(-1)
        ax.plot(np.linspace(0, 2 * np.pi, 200), [90] * 200, "k-", lw=1)
        for name, az, el, color in [("Sun", row.sun_az, row.sun_el, "orange"),
                                    ("Earth", row.earth_az, row.earth_el, "tab:blue")]:
            ax.scatter(np.radians(az), min(90 - el, 100), s=150,
                       c=color if el > 0 else "white", edgecolors=color, linewidths=2,
                       zorder=3, label=f"{name} {el:.1f} deg")
        ax.set_rlim(0, 100); ax.set_yticklabels([]); ax.set_rticks([30, 60, 90])
        ax.set_title(f"{n}\n{row.time_utc:%Y-%m-%d %H:%M} UTC", fontsize=8)
        ax.legend(fontsize=6, loc="lower left", bbox_to_anchor=(-0.15, -0.2))
        st.pyplot(fig)
        for name, series in [("Sun", d.sun_el), ("Earth", d.earth_el)]:
            h, up = hours_until_change(series.to_numpy(), k, step_h)
            if h is None:
                st.write(f"{name}: stays {'up' if up else 'down'} for the rest of the data window")
            else:
                st.write(f"{name} {'sets' if up else 'rises'} in {h:.0f} h")

st.subheader("Timelines")
cols = st.columns(min(len(data), 2))
for i, (n, d) in enumerate(data.items()):
    with cols[i % len(cols)]:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.plot(d.time_utc, d.sun_el, label="Sun elevation")
        ax.plot(d.time_utc, d.earth_el, label="Earth elevation")
        if gnss is not None:
            g = d[["time_utc", "earth_el"]].merge(gnss, on="time_utc", how="left")
            usable = (g.earth_el > 0) & (g.n_total.fillna(0) >= 1)
            ax.fill_between(g.time_utc, -10, 10, where=usable, alpha=0.15, color="green",
                            label="Earth up + >=1 GNSS sat usable")
        ax.axhline(0, color="k", lw=0.7)
        ax.set_ylabel("deg above smooth horizon"); ax.set_title(n)
        ax.legend(fontsize=6); fig.autofmt_xdate(); fig.tight_layout()
        st.pyplot(fig)

pol = sites[(sites.lat_deg < -80) & sites.name.isin(pick)]
if len(pol):
    st.subheader("Where the polar sites are (schematic)")
    fig = plt.figure(figsize=(3.8, 3.8))
    ax = fig.add_subplot(111, projection="polar")
    ax.set_theta_zero_location("N"); ax.set_theta_direction(-1)
    ax.scatter(np.radians(pol.lon_deg_east), 90 + pol.lat_deg, s=50, c="tab:red", zorder=3)
    for _, s in pol.iterrows():
        ax.annotate(s["name"], (np.radians(s.lon_deg_east), 90 + s.lat_deg), fontsize=6,
                    xytext=(4, 4), textcoords="offset points")
    ax.set_rlim(0, 6); ax.set_rticks([2, 4, 6]); ax.set_yticklabels(["2 deg", "4 deg", "6 deg"], fontsize=6)
    ax.set_title("Distance from the lunar south pole; angle = east longitude", fontsize=7)
    st.pyplot(fig)

with st.expander("How to read the table"):
    st.markdown("""
Each row is one site, over the date range chosen in the sidebar. Percentages are the **share of hours** in that range.
- **sunlit_% / earth_visible_%**: share of time the Sun / Earth is above the (smooth) horizon.
- **sun_and_earth_%**: both up at once (power and direct-to-Earth link).
- **longest_dark_h / longest_earth_outage_h**: the single longest unbroken stretch without Sun / without Earth (a maximum, not an average).
- **start_times_for_Nd_mission_%**: share of possible arrival times from which Sun and Earth both stay up for the whole N-day stay (set N with the sidebar slider; only this column depends on it).
- **earth_up_and_>=1_gnss_%**: share of time Earth is up AND at least one GPS/Galileo satellite is geometrically placed to send a signal toward the Moon. **>=4** means enough satellites for a position-and-clock solution in principle. Geometry only, not signal strength.
""")

with st.expander("Method and limitations"):
    st.markdown("""
- Sun/Earth elevations: JPL Horizons, hourly, observer on the lunar surface (smooth sphere, no terrain).
- GNSS layer: geometric count of GPS+Galileo satellites inside an assumed main-lobe cone and not
  blocked by Earth; receiver at the Moon's centre; no signal strength (LuGRE saw weaker signals than predicted).
- Site coordinates: Gracy & Lee 2024 (IdeaFest); Chen et al. 2024 (ICES-2024-211); Wagner et al. 2017 (Apollo).
""")
