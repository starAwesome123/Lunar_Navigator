"""Sanity-check plot: Sun and Earth elevation for one cached site.
Usage: python plot_check.py apollo11_check
"""
import sys
import pandas as pd
import matplotlib.pyplot as plt

site = sys.argv[1]
df = pd.read_csv(f"data/horizons_{site}.csv", parse_dates=["time_utc"])
fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(df.time_utc, df.sun_el, label="Sun elevation")
ax.plot(df.time_utc, df.earth_el, label="Earth elevation")
ax.axhline(0, color="k", lw=0.8)
ax.set_ylabel("Elevation above smooth horizon (deg)")
ax.set_title(f"{site}: Sun and Earth seen from the lunar surface")
ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
fig.savefig(f"check_{site}.png", dpi=130)
print("sunlit %:", round((df.sun_el > 0).mean() * 100, 1),
      "| Earth-visible %:", round((df.earth_el > 0).mean() * 100, 1))