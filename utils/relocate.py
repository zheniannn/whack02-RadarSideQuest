"""Stage 5b rules: relocate out-of-coverage trajectories into the radar's
neighbourhood.

WHACK01 produces GA trajectories all over the survey region; only a small
fraction pass within the radar's coverage. This variant salvages the rest:
every trajectory whose closest approach to the site exceeds the instrumented
range is rigidly translated so its FIRST point lands at a uniformly random
location within RADIUS_M of the radar. Trajectories already in coverage are
kept unchanged.

The translation is done in metric ENU using each trajectory's OWN reference
latitude for the forward conversion and the SITE latitude for the inverse,
so the aircraft's true motion (speeds, turns, shape) is preserved exactly --
only its geographic placement changes. Motion/derived columns are therefore
still valid and are carried through untouched.
"""

import numpy as np
import pandas as pd

EARTH_RADIUS_M = 6_371_000.0
RADIUS_M = 10_000.0        # relocated origins fall uniformly within this of the site

# Position columns to translate (WHACK01 stage-4 schema). Everything else --
# altitude, motion channels, metadata -- is translation-invariant.
LAT_COLS = ["lat_interp", "lat_smooth"]
LON_COLS = ["lon_interp", "lon_smooth"]


def ground_range_m(lat, lon, site_lat, site_lon):
    """Flat-earth ground range from the site (matches the radar's ENU model)."""
    e = EARTH_RADIUS_M * np.cos(np.radians(site_lat)) * np.radians(lon - site_lon)
    n = EARTH_RADIUS_M * np.radians(lat - site_lat)
    return np.hypot(e, n)


def relocate_day(df: pd.DataFrame, site_lat: float, site_lon: float,
                 range_max_m: float, rng: np.random.Generator) -> dict:
    """Return (relocated_df, stats). df is one day's trajectories."""
    df = df.copy()
    lat = df["lat_interp"].to_numpy()
    lon = df["lon_interp"].to_numpy()

    # In/out-of-coverage decision: a trajectory is out iff its closest point
    # to the site exceeds the instrumented range.
    df["_grange"] = ground_range_m(lat, lon, site_lat, site_lon)
    min_range = df.groupby("trajectory_id")["_grange"].transform("min")
    out = (min_range > range_max_m).to_numpy()

    n_traj = df["trajectory_id"].nunique()
    out_tids = df.loc[out, "trajectory_id"].unique()

    if len(out_tids):
        g = df.groupby("trajectory_id")
        first_lat = g["lat_interp"].transform("first").to_numpy()
        first_lon = g["lon_interp"].transform("first").to_numpy()
        ref_lat = g["lat_interp"].transform("mean").to_numpy()

        # Trajectory shape in metres, relative to its own first point.
        e_self = EARTH_RADIUS_M * np.cos(np.radians(ref_lat)) * np.radians(lon - first_lon)
        n_self = EARTH_RADIUS_M * np.radians(lat - first_lat)

        # One random target origin per out-of-coverage trajectory (uniform in disc).
        r = RADIUS_M * np.sqrt(rng.uniform(size=len(out_tids)))
        th = rng.uniform(0, 2 * np.pi, size=len(out_tids))
        target = {tid: (float(r[i] * np.sin(th[i])), float(r[i] * np.cos(th[i])))
                  for i, tid in enumerate(out_tids)}
        tid_arr = df["trajectory_id"].to_numpy()
        et = np.array([target[t][0] if o else 0.0 for t, o in zip(tid_arr, out)])
        nt = np.array([target[t][1] if o else 0.0 for t, o in zip(tid_arr, out)])

        # New ENU relative to the site, then back to lat/lon using the SITE latitude.
        e_new = et + e_self
        n_new = nt + n_self
        new_lat = site_lat + np.degrees(n_new / EARTH_RADIUS_M)
        new_lon = site_lon + np.degrees(e_new / (EARTH_RADIUS_M * np.cos(np.radians(site_lat))))

        for c in LAT_COLS:
            if c in df.columns:
                v = df[c].to_numpy().copy(); v[out] = new_lat[out]; df[c] = v
        for c in LON_COLS:
            if c in df.columns:
                v = df[c].to_numpy().copy(); v[out] = new_lon[out]; df[c] = v

    df = df.drop(columns="_grange")
    return df, {
        "trajectories": int(n_traj),
        "relocated": int(len(out_tids)),
        "kept_in_coverage": int(n_traj - len(out_tids)),
    }
