"""Stage 5b (RadarSideQuest): build the relocated trajectory set.

Reads the ORIGINAL WHACK01 trajectories and the frozen scenario, then writes
a new per-day trajectory set in which every trajectory outside the radar's
instrumented range has been rigidly translated so its first point lands
within 10 km of the site (see utils/relocate.py). In-coverage trajectories
are copied unchanged. Stages 6-9 then run on this relocated set.

Run AFTER stage 5 (needs the site) and BEFORE stages 6-9.

Usage:
    python scripts/05b_relocate_trajectories.py
"""

import argparse
import json
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.io import get_scenario_path, get_source_trajectories_dir, get_trajectories_dir
from utils.relocate import RADIUS_M, relocate_day

DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")


def parse_args():
    p = argparse.ArgumentParser(description="Stage 5b: relocate out-of-coverage trajectories.")
    p.add_argument("--scenario", type=str, default=None)
    p.add_argument("--source-dir", type=str, default=None,
                   help="Original trajectory CSVs (default: active/trajectories_10s).")
    p.add_argument("--output-dir", type=str, default=None,
                   help="Relocated set (default: active/sidequest/trajectories_10s).")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    with open(args.scenario or get_scenario_path()) as f:
        sc = json.load(f)
    src_dir = args.source_dir or get_source_trajectories_dir()
    out_dir = args.output_dir or get_trajectories_dir()
    os.makedirs(out_dir, exist_ok=True)

    files = sorted(f for f in os.listdir(src_dir)
                   if f.startswith("states_") and f.endswith("_trajectories_10s.csv"))
    if not files:
        raise FileNotFoundError(f"No source trajectory CSVs in {src_dir}")

    print(f"Relocating out-of-coverage trajectories to within {RADIUS_M/1000:.0f} km of "
          f"({sc['site_lat_deg']}, {sc['site_lon_deg']})...")
    for i, name in enumerate(files):
        date = DATE_PATTERN.search(name).group(1)
        df = pd.read_csv(os.path.join(src_dir, name),
                         dtype={"icao24": str, "callsign": str})
        rng = np.random.default_rng(sc["seed"] + 5000 + i)   # reproducible, distinct stream
        out, stats = relocate_day(df, sc["site_lat_deg"], sc["site_lon_deg"],
                                  sc["range_max_m"], rng)
        out.to_csv(os.path.join(out_dir, name), index=False)
        print(f"  {date}: {stats['trajectories']} trajectories "
              f"({stats['kept_in_coverage']} kept in coverage, "
              f"{stats['relocated']} relocated) -> {name}")

    print("\n05b_relocate_trajectories completed.")


if __name__ == "__main__":
    main()
