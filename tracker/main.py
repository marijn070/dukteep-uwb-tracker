"""Entry point — builds the DearPyGui window and drives the application loop."""

from __future__ import annotations

import math
from typing import Optional

import dearpygui.dearpygui as dpg
import numpy as np

import sound
from config import apply_config, load_config, save_config
from events import EventDetector
from pitch import (
    DRAG_HIT,
    draw_dynamic,
    draw_static_pitch,
    field_to_screen,
    screen_to_field,
)
from serial_reader import SerialReader
from state import AppState, apply_default_anchor_positions
from trilateration import KalmanFilter2D, trilaterate

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

RIGHT_W = 330  # right panel pixel width
SCORE_H = 100  # score-bar pixel height (larger font)
VP_W, VP_H = 1280, 800

# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_app = AppState()
_kalman = KalmanFilter2D(process_noise=0.5, measurement_noise=3.0)
_events = EventDetector()
_serial: Optional[SerialReader] = None

# Canvas transform (updated on resize or field-dimension change)
_tr: dict = {"scale": 1.0, "ox": 32.0, "oy": 32.0}
_canvas_wh: list[float] = [0.0, 0.0]

# Anchor drag state
_drag: dict = {"id": None, "active": False}

# Gate trilateration to run only when new serial data arrives
_new_data = False

# Scoreboard font (loaded during GUI build)
_score_font = None


# ---------------------------------------------------------------------------
# Serial helpers
# ---------------------------------------------------------------------------


def _start_serial() -> None:
    global _serial
    _stop_serial()
    fs = _app.field_settings
    _serial = SerialReader(
        port=fs.serial_port,
        baud_rate=fs.baud_rate,
        out_queue=_app.serial_queue,
        sma_window=fs.sma_window,
    )
    _serial.start()
    _refresh_serial_status()


def _stop_serial() -> None:
    global _serial
    if _serial is not None:
        _serial.stop()
        _serial = None
    _refresh_serial_status()


def _refresh_serial_status() -> None:
    if not dpg.does_item_exist("serial_status"):
        return
    if _serial is None:
        dpg.configure_item("serial_status", default_value="Disconnected", color=(170, 35, 35, 255))
    elif getattr(_serial, "error", None):
        dpg.configure_item(
            "serial_status", default_value=f"Error: {_serial.error}", color=(170, 35, 35, 255)
        )
    else:
        dpg.configure_item("serial_status", default_value="Connected", color=(25, 145, 25, 255))


# ---------------------------------------------------------------------------
# Per-frame data pipeline
# ---------------------------------------------------------------------------


def _process_queue() -> None:
    """Drain the serial queue, update anchor states, set _new_data flag."""
    global _new_data
    _new_data = False
    q = _app.serial_queue
    latest: Optional[dict] = None
    while not q.empty():
        try:
            latest = q.get_nowait()
        except Exception:
            break
    if latest is None:
        return

    _new_data = True
    distances = latest["distances"]  # {anchor_id: smoothed_mm}

    # All anchors start offline; only those in this packet are online.
    for anchor in _app.anchors.values():
        anchor.online = False

    for anchor_id, dist_mm in distances.items():
        if anchor_id in _app.anchors:
            a = _app.anchors[anchor_id]
            a.online = True
            a.noisy = False
            a.last_distance_mm = dist_mm


def _update_position() -> None:
    """Run trilateration + Kalman filter when fresh data is available."""
    if not _new_data:
        return

    anchor_positions: dict[int, tuple[float, float]] = {}
    distances_m: dict[int, float] = {}
    for anchor_id, anchor in _app.anchors.items():
        if anchor.online and not anchor.disabled and anchor.last_distance_mm > 0:
            anchor_positions[anchor_id] = (anchor.x, anchor.y)
            distances_m[anchor_id] = anchor.last_distance_mm / 1000.0

    if len(anchor_positions) < 3:
        return

    raw = trilaterate(anchor_positions, distances_m)
    if raw is None:
        return

    filtered = _kalman.update(raw[0], raw[1])
    _app.ball_position = filtered

    trail_limit = _app.field_settings.trail_length
    _app.trail.append(filtered)
    if len(_app.trail) > trail_limit:
        _app.trail = _app.trail[-trail_limit:]


# ---------------------------------------------------------------------------
# Anchor drag
# ---------------------------------------------------------------------------


def _on_mouse_down(sender, app_data: int) -> None:
    """Left-button click: begin dragging the nearest anchor."""
    if app_data != 0:
        return
    if not dpg.does_item_exist("pitch_dl"):
        return
    if not dpg.is_item_hovered("pitch_dl"):
        return

    lx, ly = _canvas_mouse()

    if lx is None or ly is None:
        return

    scale, ox, oy = _tr["scale"], _tr["ox"], _tr["oy"]
    for anchor_id, anchor in _app.anchors.items():
        sx, sy = field_to_screen(anchor.x, anchor.y, scale, ox, oy)
        if math.hypot(lx - sx, ly - sy) <= DRAG_HIT:
            _drag["id"] = anchor_id
            _drag["active"] = True
            return


def _on_mouse_up(sender, app_data: int) -> None:
    if app_data == 0:
        _drag["id"] = None
        _drag["active"] = False


def _apply_drag() -> None:
    """Update dragged anchor position every frame."""
    if not _drag["active"] or _drag["id"] is None:
        return
    lx, ly = _canvas_mouse()
    if lx is None or ly is None:
        return

    scale, ox, oy = _tr["scale"], _tr["ox"], _tr["oy"]
    fx, fy = screen_to_field(lx, ly, scale, ox, oy)
    aid = _drag["id"]
    _app.anchors[aid].x = fx
    _app.anchors[aid].y = fy
    _sync_anchor_inputs(aid)


def _canvas_mouse() -> tuple[Optional[float], Optional[float]]:
    """Mouse position relative to the pitch drawlist top-left corner."""
    try:
        rect_min = dpg.get_item_rect_min("pitch_dl")
    except Exception:
        return None, None
    mx, my = dpg.get_mouse_pos(local=False)
    return mx - rect_min[0], my - rect_min[1]


# ---------------------------------------------------------------------------
# Anchor input callbacks
# ---------------------------------------------------------------------------


def _anchor_x_cb(sender, app_data, user_data: int) -> None:
    _app.anchors[user_data].x = float(app_data)


def _anchor_y_cb(sender, app_data, user_data: int) -> None:
    _app.anchors[user_data].y = float(app_data)


def _anchor_enabled_cb(sender, app_data, user_data: int) -> None:
    """Checkbox is True when enabled, so disabled = not checked."""
    _app.anchors[user_data].disabled = not bool(app_data)


def _sync_anchor_inputs(aid: int) -> None:
    tx, ty = f"anc_{aid}_x", f"anc_{aid}_y"
    if dpg.does_item_exist(tx):
        dpg.set_value(tx, _app.anchors[aid].x)
    if dpg.does_item_exist(ty):
        dpg.set_value(ty, _app.anchors[aid].y)


# ---------------------------------------------------------------------------
# Update right-panel anchor status every frame
# ---------------------------------------------------------------------------


def _refresh_anchor_panel() -> None:
    for i, anchor in _app.anchors.items():
        dist_tag = f"anc_{i}_dist"
        st_tag = f"anc_{i}_status"
        if not dpg.does_item_exist(st_tag):
            continue

        if anchor.disabled:
            dist_str = "—"
            st_str = "Disabled"
            col = (170, 50, 50, 220)
        elif anchor.online and not anchor.noisy:
            dist_str = f"{anchor.last_distance_mm / 1000.0:.3f} m"
            st_str = "Online "
            col = (25, 145, 25, 255)
        elif anchor.noisy:
            dist_str = "noisy"
            st_str = "Noisy  "
            col = (200, 90, 10, 255)
        else:
            dist_str = "—"
            st_str = "Offline"
            col = (110, 110, 115, 200)

        dpg.set_value(dist_tag, dist_str)
        dpg.set_value(st_tag, st_str)
        dpg.configure_item(st_tag, color=col)


# ---------------------------------------------------------------------------
# Static pitch
# ---------------------------------------------------------------------------


def _redraw_static() -> None:
    w, h = _canvas_wh
    if w < 10 or h < 10:
        return
    fs = _app.field_settings
    scale, ox, oy = draw_static_pitch(
        "static_layer",
        w,
        h,
        fs.width_m,
        fs.height_m,
        fs.goal_width_m,
    )
    _tr["scale"] = scale
    _tr["ox"] = ox
    _tr["oy"] = oy


# ---------------------------------------------------------------------------
# Field-settings callbacks
# ---------------------------------------------------------------------------


def _field_setting_cb(sender, app_data, user_data: str) -> None:
    setattr(_app.field_settings, user_data, app_data)
    if user_data in ("width_m", "height_m", "goal_width_m"):
        _redraw_static()
    elif user_data == "trail_length":
        tl = _app.field_settings.trail_length
        if len(_app.trail) > tl:
            _app.trail = _app.trail[-tl:]
    elif user_data == "position_smoothing":
        _kalman.R = np.eye(2) * max(0.5, float(app_data))
        _kalman.reset()


# ---------------------------------------------------------------------------
# Scoreboard callbacks
# ---------------------------------------------------------------------------


def _home_plus(s, a):
    _app.home_score += 1
    _refresh_score()


def _home_minus(s, a):
    _app.home_score = max(0, _app.home_score - 1)
    _refresh_score()


def _away_plus(s, a):
    _app.away_score += 1
    _refresh_score()


def _away_minus(s, a):
    _app.away_score = max(0, _app.away_score - 1)
    _refresh_score()


def _reset_score(s, a):
    _app.home_score = 0
    _app.away_score = 0
    _refresh_score()


def _on_home_name(s, a):
    _app.home_name = a


def _on_away_name(s, a):
    _app.away_name = a


def _refresh_score() -> None:
    if dpg.does_item_exist("score_display"):
        dpg.set_value("score_display", f"{_app.home_score} — {_app.away_score}")


def _refresh_score_from_event() -> None:
    """Called each frame to catch goals scored by the event detector."""
    _refresh_score()


# ---------------------------------------------------------------------------
# GUI construction
# ---------------------------------------------------------------------------


def _apply_light_theme() -> None:
    """Set DearPyGui global style colours to a light theme."""
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (240, 240, 245))
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (248, 248, 252))
            dpg.add_theme_color(dpg.mvThemeCol_Text, (30, 30, 35))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (255, 255, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Button, (215, 215, 222))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (195, 195, 205))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (175, 175, 190))
            dpg.add_theme_color(dpg.mvThemeCol_TitleBg, (225, 225, 232))
            dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, (218, 218, 226))
            dpg.add_theme_color(dpg.mvThemeCol_Border, (175, 175, 185))
            dpg.add_theme_color(dpg.mvThemeCol_Separator, (190, 190, 198))
            dpg.add_theme_color(dpg.mvThemeCol_Header, (215, 215, 225))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (200, 200, 212))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (190, 190, 205))
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg, (245, 245, 250))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, (235, 235, 240))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, (180, 180, 190))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (242, 242, 248))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (235, 235, 240))
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
    dpg.bind_theme(theme)


def _build_gui() -> None:
    # Load a larger font for the scoreboard
    global _score_font
    with dpg.font_registry():
        _score_font = dpg.add_font("/usr/share/fonts/Adwaita/AdwaitaSans-Regular.ttf", 58)

    with dpg.handler_registry():
        dpg.add_mouse_click_handler(callback=_on_mouse_down)
        dpg.add_mouse_release_handler(callback=_on_mouse_up)

    with dpg.window(tag="main_window", no_scrollbar=True, no_scroll_with_mouse=True):
        # ── Score bar at the top ──────────────────────────────────────────
        _build_score_bar()

        # ── Pitch + right panel ─────────────────────────────────────────
        with dpg.group(horizontal=True):
            _build_pitch_panel()
            _build_right_panel()


def _build_pitch_panel() -> None:
    with dpg.child_window(
        tag="pitch_panel",
        width=-(RIGHT_W + 4),
        height=-(SCORE_H + 4),
        no_scrollbar=True,
        border=False,
    ):
        with dpg.drawlist(tag="pitch_dl", width=100, height=100):
            with dpg.draw_layer(tag="static_layer"):
                pass
            with dpg.draw_layer(tag="dynamic_layer"):
                pass


def _build_right_panel() -> None:
    with dpg.child_window(tag="right_panel", width=RIGHT_W, height=-(SCORE_H + 4)):
        # ── Anchor Status ────────────────────────────────────────────────
        dpg.add_text("Anchor Status", color=(140, 110, 20, 255))
        dpg.add_separator()
        dpg.add_spacer(height=2)

        for i in range(8):
            anchor = _app.anchors[i]

            with dpg.group(horizontal=True):
                dpg.add_checkbox(
                    tag=f"anc_{i}_enabled",
                    default_value=not anchor.disabled,
                    callback=_anchor_enabled_cb,
                    user_data=i,
                )
                dpg.add_text(f"BS{i} ", color=(50, 50, 55, 255))
                dpg.add_text("Offline", tag=f"anc_{i}_status", color=(110, 110, 115, 200))
                dpg.add_spacer(width=6)
                dpg.add_text("—", tag=f"anc_{i}_dist", color=(90, 90, 95, 200))

            with dpg.group(horizontal=True):
                dpg.add_text("  X")
                dpg.add_input_float(
                    tag=f"anc_{i}_x",
                    default_value=anchor.x,
                    width=90,
                    step=0,
                    format="%.1f",
                    callback=_anchor_x_cb,
                    user_data=i,
                )
                dpg.add_text("Y")
                dpg.add_input_float(
                    tag=f"anc_{i}_y",
                    default_value=anchor.y,
                    width=90,
                    step=0,
                    format="%.1f",
                    callback=_anchor_y_cb,
                    user_data=i,
                )

            dpg.add_spacer(height=1)

        dpg.add_separator()
        dpg.add_spacer(height=4)

        # ── Field Settings ───────────────────────────────────────────────
        dpg.add_text("Field Settings", color=(140, 110, 20, 255))
        dpg.add_separator()
        dpg.add_spacer(height=2)

        fs = _app.field_settings
        _float_row("Width (m)", "width_m", fs.width_m)
        _float_row("Height (m)", "height_m", fs.height_m)
        _float_row("Goal W (m)", "goal_width_m", fs.goal_width_m)
        _int_row("SMA window", "sma_window", fs.sma_window, 1, 50)
        _int_row("Trail length", "trail_length", fs.trail_length, 0, 500)
        _int_row("Smoothing", "position_smoothing", fs.position_smoothing, 1, 20)
        _int_row("OOP debounce", "out_of_play_debounce", fs.out_of_play_debounce, 1, 120)
        _int_row("Goal debounce", "goal_debounce", fs.goal_debounce, 1, 120)

        dpg.add_separator()
        dpg.add_spacer(height=4)

        # ── Serial ───────────────────────────────────────────────────────
        dpg.add_text("Serial Connection", color=(140, 110, 20, 255))
        dpg.add_separator()
        dpg.add_spacer(height=2)

        with dpg.group(horizontal=True):
            dpg.add_text("Port ")
            dpg.add_input_text(
                default_value=fs.serial_port,
                width=184,
                callback=lambda s, a: setattr(_app.field_settings, "serial_port", a),
            )

        with dpg.group(horizontal=True):
            dpg.add_text("Baud ")
            dpg.add_input_int(
                default_value=fs.baud_rate,
                width=120,
                step=0,
                callback=lambda s, a: setattr(_app.field_settings, "baud_rate", a),
            )

        dpg.add_spacer(height=4)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Connect", width=100, callback=lambda s, a: _start_serial())
            dpg.add_button(label="Disconnect", width=100, callback=lambda s, a: _stop_serial())

        dpg.add_spacer(height=2)
        dpg.add_text("Disconnected", tag="serial_status", color=(180, 40, 40, 255))

        dpg.add_spacer(height=6)
        dpg.add_separator()
        dpg.add_spacer(height=4)
        dpg.add_button(label="Save settings", width=-1, callback=lambda s, a: save_config(_app))


def _float_row(label: str, attr: str, default: float) -> None:
    with dpg.group(horizontal=True):
        dpg.add_text(f"{label:<15}")
        dpg.add_input_float(
            default_value=default,
            width=106,
            step=0,
            format="%.2f",
            callback=_field_setting_cb,
            user_data=attr,
        )


def _int_row(label: str, attr: str, default: int, lo: int = 0, hi: int = 9999) -> None:
    with dpg.group(horizontal=True):
        dpg.add_text(f"{label:<15}")
        dpg.add_input_int(
            default_value=default,
            width=90,
            step=0,
            min_value=lo,
            max_value=hi,
            min_clamped=True,
            max_clamped=True,
            callback=_field_setting_cb,
            user_data=attr,
        )


def _build_score_bar() -> None:
    with dpg.child_window(tag="score_bar", height=SCORE_H, no_scrollbar=True, border=False):
        dpg.add_spacer(height=4)
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=12)

            # Home
            dpg.add_input_text(
                default_value=_app.home_name,
                width=110,
                callback=_on_home_name,
            )
            dpg.add_button(label="-##hm", width=30, callback=_home_minus)
            dpg.add_button(label="+##hp", width=30, callback=_home_plus)

            # Elastic spacer → pushes score to center
            dpg.add_spacer(width=0)

            # Score
            dpg.add_text(
                f"{_app.home_score} — {_app.away_score}",
                tag="score_display",
                color=(180, 130, 20, 255),
            )
            if _score_font is not None:
                dpg.bind_item_font("score_display", _score_font)

            # Elastic spacer → pushes away controls to the right
            dpg.add_spacer(width=0)

            # Away
            dpg.add_button(label="-##am", width=30, callback=_away_minus)
            dpg.add_button(label="+##ap", width=30, callback=_away_plus)
            dpg.add_spacer(width=4)
            dpg.add_input_text(
                default_value=_app.away_name,
                width=110,
                callback=_on_away_name,
            )

            dpg.add_spacer(width=16)
            dpg.add_button(label="Reset", callback=_reset_score)
            dpg.add_spacer(width=12)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    global _canvas_wh

    # Load persisted config
    apply_default_anchor_positions(_app)
    cfg = load_config()
    apply_config(_app, cfg)

    # Sync Kalman noise from loaded setting
    _kalman.R = np.eye(2) * max(0.5, float(_app.field_settings.position_smoothing))

    # Pre-generate sound effects
    sound.init_sounds()

    dpg.create_context()
    _apply_light_theme()
    _build_gui()

    dpg.create_viewport(
        title="UWB Ball Tracker", width=VP_W, height=VP_H, min_width=800, min_height=500
    )
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("main_window", True)

    # Auto-connect on startup
    _start_serial()

    # ── Main render loop ─────────────────────────────────────────────────
    while dpg.is_dearpygui_running():
        # Resize drawlist to match the pitch panel
        try:
            new_w, new_h = dpg.get_item_rect_size("pitch_panel")
        except Exception:
            new_w, new_h = 0.0, 0.0

        if new_w > 10 and new_h > 10:
            if [new_w, new_h] != _canvas_wh:
                _canvas_wh = [new_w, new_h]
                dpg.configure_item("pitch_dl", width=int(new_w), height=int(new_h))
                _redraw_static()

        # Data pipeline
        _process_queue()
        _update_position()

        # Events (goal / out-of-play)
        _events.update(_app, _app.ball_position)

        # Anchor drag
        _apply_drag()

        # Refresh UI
        _refresh_anchor_panel()
        _refresh_score_from_event()

        # Redraw dynamic layer (every frame)
        if _canvas_wh[0] > 10 and _canvas_wh[1] > 10:
            draw_dynamic(
                "dynamic_layer",
                _app,
                _tr["scale"],
                _tr["ox"],
                _tr["oy"],
                float(_canvas_wh[0]),
                float(_canvas_wh[1]),
            )

        dpg.render_dearpygui_frame()

    # Persist settings on exit
    save_config(_app)
    _stop_serial()
    dpg.destroy_context()


if __name__ == "__main__":
    main()
