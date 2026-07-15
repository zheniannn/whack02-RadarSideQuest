"""Stage 5b rules: relocate trajectories into the radar's neighbourhood.

WHACK01 produces GA trajectories all over the survey region. This variant
rigidly translates EVERY trajectory so its FIRST point lands at a uniformly
random location within RADIUS_M of the radar, giving a dense scenario in
which every flight originates near the site and fans outward.

The translation is done in metric ENU using each trajectory's OWN reference
latitude for the forward conversion and the SITE latitude for the inverse,
so the aircraft's true motion (speeds, turns, shape) is preserved exactly --
only its geographic placement changes. Motion/derived columns are therefore
still valid and are carried through untouched.
"""

import numpy as np
import pandas as pd

from .geometry import EARTH_RADIUS_M

RADIUS_M = 10_000.0        # relocated origins fall uniformly within this of the site

# Position columns to translate (WHACK01 stage-4 schema). Everything else --
# altitude, motion channels, metadata -- is translation-invariant.
LAT_COLS = ["lat_interp", "lat_smooth"]
LON_COLS = ["lon_interp", "lon_smooth"]


def relocate_day(df: pd.DataFrame, site_lat: float, site_lon: float,
                 range_max_m: float, rng: np.random.Generator) -> dict:
    """Return (relocated_df, stats). Relocates EVERY trajectory so its first
    point lands within RADIUS_M of the site. df is one day's trajectories."""
    df = df.copy()
    lat = df["lat_interp"].to_numpy()
    lon = df["lon_interp"].to_numpy()

    tids = df["trajectory_id"].unique()
    n_traj = len(tids)

    g = df.groupby("trajectory_id")
    first_lat = g["lat_interp"].transform("first").to_numpy()
    first_lon = g["lon_interp"].transform("first").to_numpy()
    ref_lat = g["lat_interp"].transform("mean").to_numpy()

    # Trajectory shape in metres, relative to its own first point.
    e_self = EARTH_RADIUS_M * np.cos(np.radians(ref_lat)) * np.radians(lon - first_lon)
    n_self = EARTH_RADIUS_M * np.radians(lat - first_lat)

    # One random target origin per trajectory (uniform in the RADIUS_M disc).
    r = RADIUS_M * np.sqrt(rng.uniform(size=n_traj))
    th = rng.uniform(0, 2 * np.pi, size=n_traj)
    target = {tid: (float(r[i] * np.sin(th[i])), float(r[i] * np.cos(th[i])))
              for i, tid in enumerate(tids)}
    tid_arr = df["trajectory_id"].to_numpy()
    et = np.array([target[t][0] for t in tid_arr])
    nt = np.array([target[t][1] for t in tid_arr])

    # New ENU relative to the site, then back to lat/lon using the SITE latitude.
    new_lat = site_lat + np.degrees((nt + n_self) / EARTH_RADIUS_M)
    new_lon = site_lon + np.degrees((et + e_self) / (EARTH_RADIUS_M * np.cos(np.radians(site_lat))))

    for c in LAT_COLS:
        if c in df.columns:
            df[c] = new_lat
    for c in LON_COLS:
        if c in df.columns:
            df[c] = new_lon

    return df, {"trajectories": int(n_traj), "relocated": int(n_traj)}
