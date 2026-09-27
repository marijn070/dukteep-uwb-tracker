"""Load and save application configuration as TOML.

Reading uses the stdlib `tomllib` (Python 3.11+).
Writing uses manual f-string serialisation — no external dependencies.
"""

import tomllib
from pathlib import Path

from state import AppState, FieldSettings

DEFAULT_CONFIG_PATH = "uwb.toml"


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def load_config(path: str = DEFAULT_CONFIG_PATH) -> dict:
    """Read a TOML config file and return its contents as a dict.

    Returns an empty dict if the file does not exist or cannot be parsed.
    """
    p = Path(path)
    if not p.exists():
        return {}
    try:
        with open(p, "rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        print(f"[config] Warning: could not parse '{path}': {exc}")
        return {}


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def apply_config(app_state: AppState, cfg: dict) -> None:
    """Write values from *cfg* into *app_state*.

    Only keys present in the config dict are applied; missing keys keep their
    existing (default) values.
    """
    fs: FieldSettings = app_state.field_settings

    field_cfg = cfg.get("field", {})
    _set_if_present(fs, "width_m", field_cfg, float)
    _set_if_present(fs, "height_m", field_cfg, float)
    _set_if_present(fs, "goal_width_m", field_cfg, float)
    _set_if_present(fs, "sma_window", field_cfg, int)
    _set_if_present(fs, "trail_length", field_cfg, int)
    _set_if_present(fs, "position_smoothing", field_cfg, int)
    _set_if_present(fs, "out_of_play_debounce", field_cfg, int)
    _set_if_present(fs, "goal_debounce", field_cfg, int)
    _set_if_present(fs, "serial_port", field_cfg, str)
    _set_if_present(fs, "baud_rate", field_cfg, int)

    teams_cfg = cfg.get("teams", {})
    if "home_name" in teams_cfg:
        app_state.home_name = str(teams_cfg["home_name"])
    if "away_name" in teams_cfg:
        app_state.away_name = str(teams_cfg["away_name"])
    if "home_score" in teams_cfg:
        app_state.home_score = int(teams_cfg["home_score"])
    if "away_score" in teams_cfg:
        app_state.away_score = int(teams_cfg["away_score"])

    anchors_cfg = cfg.get("anchors", {})
    for i in range(8):
        x_key = f"bs{i}_x"
        y_key = f"bs{i}_y"
        disabled_key = f"bs{i}_disabled"
        if x_key in anchors_cfg:
            app_state.anchors[i].x = float(anchors_cfg[x_key])
        if y_key in anchors_cfg:
            app_state.anchors[i].y = float(anchors_cfg[y_key])
        if disabled_key in anchors_cfg:
            app_state.anchors[i].disabled = bool(anchors_cfg[disabled_key])


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------


def save_config(app_state: AppState, path: str = DEFAULT_CONFIG_PATH) -> None:
    """Serialise field settings, anchor positions, and team info to *path* as TOML."""
    fs: FieldSettings = app_state.field_settings

    lines: list[str] = []

    # [field]
    lines.append("[field]")
    lines.append(f"width_m = {fs.width_m}")
    lines.append(f"height_m = {fs.height_m}")
    lines.append(f"goal_width_m = {fs.goal_width_m}")
    lines.append(f"sma_window = {fs.sma_window}")
    lines.append(f"trail_length = {fs.trail_length}")
    lines.append(f"position_smoothing = {fs.position_smoothing}")
    lines.append(f"out_of_play_debounce = {fs.out_of_play_debounce}")
    lines.append(f"goal_debounce = {fs.goal_debounce}")
    lines.append(f'serial_port = "{fs.serial_port}"')
    lines.append(f"baud_rate = {fs.baud_rate}")
    lines.append("")

    # [teams]
    lines.append("[teams]")
    lines.append(f'home_name = "{app_state.home_name}"')
    lines.append(f'away_name = "{app_state.away_name}"')
    lines.append(f"home_score = {app_state.home_score}")
    lines.append(f"away_score = {app_state.away_score}")
    lines.append("")

    # [anchors]
    lines.append("[anchors]")
    for i in range(8):
        anchor = app_state.anchors[i]
        lines.append(f"bs{i}_x = {anchor.x}")
        lines.append(f"bs{i}_y = {anchor.y}")
        lines.append(f"bs{i}_disabled = {str(anchor.disabled).lower()}")
    lines.append("")

    content = "\n".join(lines)
    Path(path).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _set_if_present(obj, attr: str, source: dict, cast) -> None:
    """Set *attr* on *obj* from *source[attr]* cast to *cast*, if the key exists."""
    if attr in source:
        setattr(obj, attr, cast(source[attr]))
