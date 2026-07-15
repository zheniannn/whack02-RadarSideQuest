"""Trajectory-shapes gallery for the RadarSideQuest set.

Because stage 5b pulls EVERY GA flight into coverage, the gallery now
summarises the whole survey's flight population (~19k/day) rather than the
~1.1k that happened to pass near the radar in WHACK02. Trajectories are
pooled across days, clustered by shape into a handful of pattern types, and
6 exemplars per cluster are shown per day (and pooled), coloured by time,
with a green start dot and a red end square. Rows are ordered by global
prevalence.

Shape features are position- and scale-aware but translation-invariant
(computed in local ENU relative to each trajectory's own centroid), so the
relocation does not change an individual trajectory's shape -- only which
trajectories are in the population being summarised.

Usage:
    python scripts/11_trajectory_gallery.py
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.geometry import EARTH_RADIUS_M
from utils.io import get_plot_dir, get_trajectories_dir

DATES = ["2022-06-06", "2022-06-13", "2022-06-20", "2022-06-27"]
N_CLUSTERS = 5
N_EXEMPLARS = 6
DOWNSAMPLE = 60          # points kept per trajectory for plotting
SEED = 20220606

SURFACE = "#fcfcfb"; INK = "#0b0b0b"; INK2 = "#52514e"; MUTED = "#898781"; GRID = "#e1e0d9"
START_C = "#1baf7a"; END_C = "#e34948"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "text.color": INK, "font.size": 10, "axes.titlesize": 12,
})


def _local_en(lat, lon):
    """Local ENU metres relative to the trajectory's own centroid."""
    lat0 = lat.mean()
    e = EARTH_RADIUS_M * np.cos(np.radians(lat0)) * np.radians(lon - lon.mean())
    n = EARTH_RADIUS_M * np.radians(lat - lat0)
    return e, n


def _features_and_path(e, n):
    """Shape descriptor + a downsampled (e,n) path for plotting."""
    seg = np.hypot(np.diff(e), np.diff(n))
    path = seg.sum()
    net = np.hypot(e[-1] - e[0], n[-1] - n[0])
    straightness = net / path if path > 0 else 0.0
    heading = np.arctan2(np.diff(e), np.diff(n))
    dh = (np.diff(heading) + np.pi) % (2 * np.pi) - np.pi
    total_turn = np.degrees(np.abs(dh).sum())           # total absolute turning
    bbox = np.hypot(e.max() - e.min(), n.max() - n.min())
    turn_per_km = total_turn / (path / 1000 + 1e-6)
    feats = [straightness, np.log1p(path / 1000), np.log1p(total_turn),
             np.log1p(bbox / 1000), np.log1p(turn_per_km)]
    raw = (straightness, path / 1000, total_turn)   # for data-driven labelling

    if len(e) > DOWNSAMPLE:
        idx = np.linspace(0, len(e) - 1, DOWNSAMPLE).astype(int)
        e, n = e[idx], n[idx]
    return feats, np.column_stack([e, n]).astype(np.float32), raw


def load_all():
    """Per-trajectory features + downsampled paths + raw shape stats, pooled."""
    rows, paths, days, raws = [], [], [], []
    for date in DATES:
        f = os.path.join(get_trajectories_dir(),
                         f"states_{date}_conventionalGA_trajectories_10s.csv")
        df = pd.read_csv(f, usecols=["trajectory_id", "lat_interp", "lon_interp", "timestamp"])
        df = df.sort_values(["trajectory_id", "timestamp"])
        tid = df["trajectory_id"].to_numpy()
        lat = df["lat_interp"].to_numpy(); lon = df["lon_interp"].to_numpy()
        change = np.flatnonzero(tid[1:] != tid[:-1]) + 1
        starts = np.r_[0, change]; ends = np.r_[change, len(tid)]
        for s, en in zip(starts, ends):
            if en - s < 4:
                continue
            e, n = _local_en(lat[s:en], lon[s:en])
            feats, path, raw = _features_and_path(e, n)
            rows.append(feats); paths.append(path); days.append(date); raws.append(raw)
        del df
    return np.array(rows), paths, np.array(days), np.array(raws)


def describe_cluster(straightness: float, path_km: float, turn_deg: float) -> str:
    """Label ONE cluster from the median shape of the trajectories in it --
    data-driven, so the name reflects what the cluster actually contains.

    Straightness (net displacement / path length) is the primary signal: a
    transit runs roughly one way (~1.0); a circuit or airwork returns toward
    its start (low). Total turning only separates single vs many loops among
    the low-straightness ones -- it is unreliable for straight flights, which
    accumulate gentle course wiggle without ever looping.
    """
    if straightness >= 0.9:
        return "Long cross-country transit" if path_km >= 80 else "Direct transit"
    if straightness >= 0.6:
        return "Direct transit, light maneuvering"
    if straightness >= 0.35:
        return "Circuits + repositioning"
    loops = turn_deg / 360.0                         # low straightness: it loops back
    return f"Intensive airwork (~{loops:.0f} loops)" if loops >= 2.5 else "Racetrack / single circuit"


def label_clusters(cluster_of: np.ndarray, raws: np.ndarray) -> dict:
    """Median shape stats per cluster -> a descriptive label each."""
    names = {}
    for c in range(N_CLUSTERS):
        m = raws[cluster_of == c]
        s, p, t = np.median(m, axis=0)
        names[c] = describe_cluster(float(s), float(p), float(t))
    return names


def draw_panel(ax, path):
    e, n = path[:, 0], path[:, 1]
    t = np.linspace(0, 1, len(e))
    ax.scatter(e, n, c=t, cmap="viridis", s=3, lw=0)
    ax.plot(e[0], n[0], marker="o", color=START_C, ms=6)
    ax.plot(e[-1], n[-1], marker="s", color=END_C, ms=6)
    r = max(np.ptp(e), np.ptp(n), 1.0) * 0.6
    cx, cy = (e.max() + e.min()) / 2, (n.max() + n.min()) / 2
    ax.set_xlim(cx - r, cx + r); ax.set_ylim(cy - r, cy + r)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_edgecolor(GRID)


def render(paths, labels, cluster_of, members, title, out_path, rng):
    order = sorted(range(N_CLUSTERS), key=lambda c: -members[c].size)   # prevalence
    total = sum(members[c].size for c in range(N_CLUSTERS))
    fig, axes = plt.subplots(N_CLUSTERS, N_EXEMPLARS,
                             figsize=(N_EXEMPLARS * 2.1, N_CLUSTERS * 2.1))
    for row, c in enumerate(order):
        idx = members[c]
        pick = rng.choice(idx, size=min(N_EXEMPLARS, idx.size), replace=False)
        for col in range(N_EXEMPLARS):
            ax = axes[row, col]
            if col < len(pick):
                draw_panel(ax, paths[pick[col]])
            else:
                ax.axis("off")
        axes[row, 0].set_ylabel(f"{labels[c]}\n{idx.size} ({100*idx.size/total:.0f}%)",
                                rotation=0, ha="right", va="center", fontsize=10, color=INK2,
                                labelpad=60)
    fig.suptitle(title, color=INK, y=0.99)
    fig.tight_layout(rect=(0.13, 0, 1, 0.97))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150); plt.close(fig)


def main():
    print("Loading trajectories + shape features (pooled across 4 days)...")
    X, paths, days, raws = load_all()
    print(f"  {len(X)} trajectories")
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
    km = KMeans(N_CLUSTERS, random_state=SEED, n_init=10).fit(Xs)
    cluster_of = km.labels_
    labels = label_clusters(cluster_of, raws)
    print("  cluster labels (data-driven):")
    for c in range(N_CLUSTERS):
        s, p, t = np.median(raws[cluster_of == c], axis=0)
        print(f"    {labels[c]:36s} n={int((cluster_of==c).sum()):6d}  "
              f"straight={s:.2f} path={p:.0f}km turn={t:.0f}deg")
    rng = np.random.default_rng(SEED)
    pdir = get_plot_dir()

    # Pooled gallery.
    members = {c: np.flatnonzero(cluster_of == c) for c in range(N_CLUSTERS)}
    render(paths, labels, cluster_of, members,
           f"GA trajectory patterns — all four days pooled ({len(X):,} relocated flights)\n"
           "clustered by shape · rows in global-prevalence order · colour = time",
           os.path.join(pdir, "2_trajectory_shapes_gallery.png"), rng)
    print(f"  pooled -> {pdir}/2_trajectory_shapes_gallery.png")

    # Per-day galleries (same clusters).
    for date in DATES:
        day_mask = days == date
        members_d = {c: np.flatnonzero((cluster_of == c) & day_mask) for c in range(N_CLUSTERS)}
        render(paths, labels, cluster_of, members_d,
               f"GA trajectory patterns — {date} ({int(day_mask.sum()):,} in-coverage flights)\n"
               "same clusters as the pooled gallery · rows in global-prevalence order · colour = time",
               os.path.join(pdir, f"2_trajectory_shapes_gallery_{date}.png"), rng)
        print(f"  {date} -> gallery")

    print("\n11_trajectory_gallery completed.")


if __name__ == "__main__":
    main()
