"""Filesystem path helpers for the RadarSideQuest variant.

Same data root as the main pipeline (`data/` beside the repo, or
WHACK_DATA_ROOT), but every output is isolated under `active/sidequest/`
so nothing collides with WHACK02-Radar. Figures go to `plot/sidequest/`.

The variant reads the ORIGINAL WHACK01 trajectories, relocates the ones
outside radar coverage to within 10 km of the site (stage 5b), and runs the
radar stages on that relocated set.

    <data root>/active/
    ├── trajectories_10s/            # WHACK01 stage 4 output (source, read-only here)
    └── sidequest/
        ├── trajectories_10s/        # stage 5b relocated set (stages 6-9 input)
        └── radar/                   # scenario, beam crossings, per-stage outputs
"""

import os

# Repository root: one level above utils/.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_data_root() -> str:
    """$WHACK_DATA_ROOT if set, else `data/` beside the repository."""
    return os.environ.get("WHACK_DATA_ROOT") or os.path.join(os.path.dirname(_REPO_ROOT), "data")


def _traj_tag(dt_s: float) -> str:
    return f"{dt_s:g}".replace(".", "p") + "s"


def get_source_trajectories_dir(dt_s: float = 10.0) -> str:
    """Original WHACK01 stage-4 trajectories (read-only source for stage 5 site
    selection and for the stage-5b relocation)."""
    return os.path.join(get_data_root(), "active", f"trajectories_{_traj_tag(dt_s)}")


def get_sidequest_dir() -> str:
    """Root for everything this variant writes."""
    return os.path.join(get_data_root(), "active", "sidequest")


def get_trajectories_dir(dt_s: float = 10.0) -> str:
    """Relocated trajectory set (stage 5b output; the input to stages 6-9)."""
    return os.path.join(get_sidequest_dir(), f"trajectories_{_traj_tag(dt_s)}")


def get_radar_dir() -> str:
    """Root for everything the radar stages write (isolated from WHACK02)."""
    return os.path.join(get_sidequest_dir(), "radar")


def get_scenario_path() -> str:
    """Radar scenario JSON (stage 5 output, stage 6 input)."""
    return os.path.join(get_radar_dir(), "scenario.json")


def get_beam_crossings_dir() -> str:
    """Deterministic beam-crossing cache, shared by stages 6-9."""
    return os.path.join(get_radar_dir(), "beam_crossings")


def get_stage_dir(stage: int) -> str:
    """Per-day truth/detection CSVs for one measurement stage."""
    return os.path.join(get_radar_dir(), f"stage{stage:02d}")


def get_plot_dir() -> str:
    """Figures directory (isolated under plot/whack02-RadarSideQuest/)."""
    return os.path.join(get_data_root(), "plot", "whack02-RadarSideQuest")
