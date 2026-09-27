"""Shared application state — no DearPyGui dependencies."""

import queue
from dataclasses import dataclass, field
from typing import Optional

MAX_ANCHORS = 8
DISTANCE_NOISY_THRESHOLD_MM = 10_000


@dataclass
class AnchorState:
    id: int
    x: float = 0.0  # field coordinates, meters
    y: float = 0.0
    last_distance_mm: int = 0
    online: bool = False
    noisy: bool = False
    disabled: bool = False  # manually excluded from trilateration


@dataclass
class FieldSettings:
    width_m: float = 40.0
    height_m: float = 20.0
    goal_width_m: float = 3.0
    sma_window: int = 5
    trail_length: int = 50
    position_smoothing: int = 3  # Kalman R scale (lower = more responsive, higher = smoother)
    out_of_play_debounce: int = 10
    goal_debounce: int = 15
    serial_port: str = "/dev/ttyACM0"
    baud_rate: int = 115200


@dataclass
class AppState:
    anchors: dict = field(
        default_factory=lambda: {i: AnchorState(id=i) for i in range(MAX_ANCHORS)}
    )
    ball_position: Optional[tuple] = None  # (x, y) meters
    trail: list = field(default_factory=list)  # list of (x, y), newest last
    home_score: int = 0
    away_score: int = 0
    home_name: str = "Home"
    away_name: str = "Away"
    field_settings: FieldSettings = field(default_factory=FieldSettings)
    serial_queue: queue.Queue = field(default_factory=queue.Queue)
    # Event state
    out_of_play_frames: int = 0
    goal_left_frames: int = 0
    goal_right_frames: int = 0
    show_goal_notification: bool = False
    goal_notification_timer: int = 0
    goal_scored_side: Optional[str] = None  # 'left' or 'right'
    show_out_notification: bool = False
    out_notification_timer: int = 0


def default_anchor_positions() -> dict:
    """Return a dict mapping anchor id to (x, y) default perimeter positions (meters)."""
    return {
        0: (0.0, 0.0),
        1: (20.0, 0.0),
        2: (40.0, 0.0),
        3: (40.0, 10.0),
        4: (40.0, 20.0),
        5: (20.0, 20.0),
        6: (0.0, 20.0),
        7: (0.0, 10.0),
    }


def apply_default_anchor_positions(app_state: AppState) -> None:
    """Set each anchor's (x, y) to the default perimeter positions."""
    for anchor_id, (x, y) in default_anchor_positions().items():
        app_state.anchors[anchor_id].x = x
        app_state.anchors[anchor_id].y = y
