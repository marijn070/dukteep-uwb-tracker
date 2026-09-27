"""Goal and out-of-play event detection. Pure logic — no DearPyGui imports."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import sound

if TYPE_CHECKING:
    from state import AppState

# How many frames (at ~60 fps) to keep each notification visible.
NOTIFICATION_DISPLAY_FRAMES = 180  # 3 seconds


class EventDetector:
    """Detects goals and out-of-play events by inspecting the ball position each frame.

    All persistent state lives in *AppState*; this class is stateless so it can
    be recreated freely without losing information.

    Scoring convention
    ------------------
    * 'left'  — ball crossed the left  goal line → away  team scores
    * 'right' — ball crossed the right goal line → home team scores
    """

    def __init__(self) -> None:
        pass  # no per-instance state required

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, app_state: "AppState", ball_pos: Optional[tuple]) -> None:
        """Called once per rendered frame with the latest ball position (or None)."""
        # Tick timers first so notifications set this frame aren't immediately
        # decremented — they stay at NOTIFICATION_DISPLAY_FRAMES until next frame.
        self._tick_notification_timers(app_state)

        if ball_pos is None:
            # Can't evaluate events without a position — reset all frame counters.
            app_state.out_of_play_frames = 0
            app_state.goal_left_frames = 0
            app_state.goal_right_frames = 0
            return

        fs = app_state.field_settings
        x, y = ball_pos

        self._check_out_of_play(app_state, x, y, fs)
        self._check_goal_left(app_state, x, y, fs)
        self._check_goal_right(app_state, x, y, fs)

    # ------------------------------------------------------------------
    # Private checks
    # ------------------------------------------------------------------

    def _check_out_of_play(self, app_state: "AppState", x: float, y: float, fs) -> None:
        out = x < 0.0 or x > fs.width_m or y < 0.0 or y > fs.height_m
        if out:
            app_state.out_of_play_frames += 1
            if app_state.out_of_play_frames == fs.out_of_play_debounce:
                app_state.show_out_notification = True
                app_state.out_notification_timer = NOTIFICATION_DISPLAY_FRAMES
                sound.play_whistle()
        else:
            app_state.out_of_play_frames = 0

    def _check_goal_left(self, app_state: "AppState", x: float, y: float, fs) -> None:
        in_left_goal = x < 0.0 and abs(y - fs.height_m / 2.0) < fs.goal_width_m / 2.0
        if in_left_goal:
            app_state.goal_left_frames += 1
            if app_state.goal_left_frames == fs.goal_debounce:
                self._score_goal(app_state, "left")
        else:
            app_state.goal_left_frames = 0

    def _check_goal_right(self, app_state: "AppState", x: float, y: float, fs) -> None:
        in_right_goal = x > fs.width_m and abs(y - fs.height_m / 2.0) < fs.goal_width_m / 2.0
        if in_right_goal:
            app_state.goal_right_frames += 1
            if app_state.goal_right_frames == fs.goal_debounce:
                self._score_goal(app_state, "right")
        else:
            app_state.goal_right_frames = 0

    def _score_goal(self, app_state: "AppState", side: str) -> None:
        """Increment the appropriate score and trigger the goal notification.

        A goal notification already on screen acts as an additional debounce
        guard so rapid re-entries of the goal zone don't multi-score.
        """
        if app_state.show_goal_notification:
            return

        if side == "left":
            # Ball entered the left goal (home team's end) → away scores.
            app_state.away_score += 1
        else:
            # Ball entered the right goal (away team's end) → home scores.
            app_state.home_score += 1

        app_state.show_goal_notification = True
        app_state.goal_notification_timer = NOTIFICATION_DISPLAY_FRAMES
        app_state.goal_scored_side = side

        sound.play_cheer()

        # Reset both counters so the ball has to fully re-enter a goal zone
        # before another goal can be counted.
        app_state.goal_left_frames = 0
        app_state.goal_right_frames = 0

    # ------------------------------------------------------------------
    # Notification timer management
    # ------------------------------------------------------------------

    def _tick_notification_timers(self, app_state: "AppState") -> None:
        """Count down active notification timers and clear them when they expire."""
        if app_state.goal_notification_timer > 0:
            app_state.goal_notification_timer -= 1
            if app_state.goal_notification_timer == 0:
                app_state.show_goal_notification = False
                app_state.goal_scored_side = None

        if app_state.out_notification_timer > 0:
            app_state.out_notification_timer -= 1
            if app_state.out_notification_timer == 0:
                app_state.show_out_notification = False
