"""DearPyGui drawing helpers for the football pitch and HUD overlay."""

from __future__ import annotations

import math

import dearpygui.dearpygui as dpg

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------

C_PITCH = (42, 120, 42, 255)
C_PITCH_STRIPE = (50, 135, 50, 255)  # subtle alternating stripe
C_LINE = (240, 240, 240, 255)
C_GOAL = (30, 80, 200, 160)
C_ANCHOR_ONLINE = (255, 200, 30, 255)
C_ANCHOR_OFFLINE = (100, 100, 100, 150)
C_ANCHOR_NOISY = (255, 100, 30, 220)
C_BALL = (255, 70, 10, 255)
C_BALL_OUTLINE = (255, 255, 255, 255)
C_TRANSPARENT = (0, 0, 0, 0)

ANCHOR_HALF = 8  # half-size of the diamond marker (pixels)
BALL_RADIUS = 8  # ball circle radius (pixels)
DRAG_HIT = 14  # pixel radius for anchor hit-testing


# ---------------------------------------------------------------------------
# Coordinate transform helpers
# ---------------------------------------------------------------------------


def compute_transform(
    canvas_w: float, canvas_h: float, field_w: float, field_h: float, padding: float = 32.0
) -> tuple[float, float, float]:
    """Return (scale, offset_x, offset_y) centring the field in the canvas."""
    avail_w = max(canvas_w - 2 * padding, 1.0)
    avail_h = max(canvas_h - 2 * padding, 1.0)
    scale = min(avail_w / field_w, avail_h / field_h)
    field_px_w = field_w * scale
    field_px_h = field_h * scale
    ox = padding + (avail_w - field_px_w) / 2.0
    oy = padding + (avail_h - field_px_h) / 2.0
    return scale, ox, oy


def field_to_screen(
    fx: float, fy: float, scale: float, ox: float, oy: float
) -> tuple[float, float]:
    return (ox + fx * scale, oy + fy * scale)


def screen_to_field(
    px: float, py: float, scale: float, ox: float, oy: float
) -> tuple[float, float]:
    if scale == 0:
        return (0.0, 0.0)
    return ((px - ox) / scale, (py - oy) / scale)


# ---------------------------------------------------------------------------
# Static pitch (redrawn whenever field dimensions or canvas size changes)
# ---------------------------------------------------------------------------


def draw_static_pitch(
    layer_tag: str, canvas_w: float, canvas_h: float, field_w: float, field_h: float, goal_w: float
) -> tuple[float, float, float]:
    """Draw all static pitch elements onto *layer_tag* and return (scale, ox, oy)."""
    dpg.delete_item(layer_tag, children_only=True)

    scale, ox, oy = compute_transform(canvas_w, canvas_h, field_w, field_h)
    fw = field_w * scale
    fh = field_h * scale

    # --- Solid background ---
    dpg.draw_rectangle(
        [ox, oy], [ox + fw, oy + fh], fill=C_PITCH, color=C_TRANSPARENT, parent=layer_tag
    )

    # --- Alternating 5m horizontal stripes ---
    stripe_px = 5.0 * scale
    num_stripes = max(1, int(math.ceil(field_h / 5.0)))
    for i in range(num_stripes):
        if i % 2 == 1:
            sy = oy + i * stripe_px
            sh = min(stripe_px, oy + fh - sy)
            dpg.draw_rectangle(
                [ox, sy],
                [ox + fw, sy + sh],
                fill=C_PITCH_STRIPE,
                color=C_TRANSPARENT,
                parent=layer_tag,
            )

    # --- Pitch outline ---
    dpg.draw_rectangle(
        [ox, oy],
        [ox + fw, oy + fh],
        color=C_LINE,
        thickness=2,
        fill=C_TRANSPARENT,
        parent=layer_tag,
    )

    # --- Centre line ---
    cx = ox + fw / 2.0
    cy = oy + fh / 2.0
    dpg.draw_line([cx, oy], [cx, oy + fh], color=C_LINE, thickness=2, parent=layer_tag)

    # --- Centre circle (15% of the shorter field dimension) ---
    cr = min(field_w, field_h) * 0.15 * scale
    dpg.draw_circle([cx, cy], cr, color=C_LINE, thickness=2, fill=C_TRANSPARENT, parent=layer_tag)
    dpg.draw_circle(
        [cx, cy], max(3, 0.2 * scale), fill=C_LINE, color=C_TRANSPARENT, parent=layer_tag
    )

    # --- Goals ---
    goal_half_px = goal_w / 2.0 * scale
    goal_depth = field_w * 0.05 * scale  # 5% of field length (≈2 m on 40 m pitch)
    goal_top = cy - goal_half_px
    goal_bot = cy + goal_half_px

    dpg.draw_rectangle(
        [ox - goal_depth, goal_top],
        [ox, goal_bot],
        fill=C_GOAL,
        color=C_LINE,
        thickness=2,
        parent=layer_tag,
    )
    dpg.draw_rectangle(
        [ox + fw, goal_top],
        [ox + fw + goal_depth, goal_bot],
        fill=C_GOAL,
        color=C_LINE,
        thickness=2,
        parent=layer_tag,
    )

    # --- Penalty areas (15% of field length deep, goal_w + 7.5% of field height wide) ---
    pen_d = field_w * 0.15 * scale
    pen_half = (goal_w / 2.0 + field_h * 0.075) * scale
    pen_top = cy - pen_half
    pen_bot = cy + pen_half

    dpg.draw_rectangle(
        [ox, pen_top],
        [ox + pen_d, pen_bot],
        color=C_LINE,
        thickness=2,
        fill=C_TRANSPARENT,
        parent=layer_tag,
    )
    dpg.draw_rectangle(
        [ox + fw - pen_d, pen_top],
        [ox + fw, pen_bot],
        color=C_LINE,
        thickness=2,
        fill=C_TRANSPARENT,
        parent=layer_tag,
    )

    # Penalty spots (15% of field length from goal line)
    pen_spot_x = field_w * 0.15 * scale
    pen_spot_r = max(2, 0.2 * scale)
    dpg.draw_circle(
        [ox + pen_spot_x, cy], pen_spot_r, fill=C_LINE, color=C_TRANSPARENT, parent=layer_tag
    )
    dpg.draw_circle(
        [ox + fw - pen_spot_x, cy], pen_spot_r, fill=C_LINE, color=C_TRANSPARENT, parent=layer_tag
    )

    # --- Corner arcs (1 m radius) ---
    _draw_corner_arcs(layer_tag, scale, ox, oy, fw, fh)

    return scale, ox, oy


def _draw_corner_arcs(
    layer_tag: str, scale: float, ox: float, oy: float, fw: float, fh: float
) -> None:
    """Approximate quarter-circle arcs at each corner with line segments."""
    r = 1.0 * scale
    segs = 10
    configs = [
        (ox, oy, 0.0, math.pi / 2.0),
        (ox + fw, oy, math.pi / 2.0, math.pi),
        (ox + fw, oy + fh, math.pi, 3.0 * math.pi / 2.0),
        (ox, oy + fh, 3.0 * math.pi / 2.0, 2.0 * math.pi),
    ]
    for cx, cy, a_start, a_end in configs:
        pts = [
            [
                cx + r * math.cos(a_start + (a_end - a_start) * t / segs),
                cy + r * math.sin(a_start + (a_end - a_start) * t / segs),
            ]
            for t in range(segs + 1)
        ]
        for i in range(len(pts) - 1):
            dpg.draw_line(pts[i], pts[i + 1], color=C_LINE, thickness=2, parent=layer_tag)


# ---------------------------------------------------------------------------
# Dynamic layer (cleared and redrawn every frame)
# ---------------------------------------------------------------------------


def draw_dynamic(
    layer_tag: str, app_state, scale: float, ox: float, oy: float, canvas_w: float, canvas_h: float
) -> None:
    """Clear *layer_tag* and redraw anchors, ball, trail, and notifications."""
    dpg.delete_item(layer_tag, children_only=True)

    _draw_trail(layer_tag, app_state, scale, ox, oy)
    _draw_ball(layer_tag, app_state, scale, ox, oy)
    _draw_anchors(layer_tag, app_state, scale, ox, oy)
    _draw_notifications(layer_tag, app_state, canvas_w, canvas_h)


def _draw_trail(layer_tag: str, app_state, scale: float, ox: float, oy: float) -> None:
    trail = app_state.trail
    n = len(trail)
    if n == 0:
        return
    for i, (tx, ty) in enumerate(trail):
        frac = (i + 1) / (n + 1)
        alpha = int(190 * frac)
        radius = max(2, int(BALL_RADIUS * 0.5 * frac))
        sx, sy = field_to_screen(tx, ty, scale, ox, oy)
        dpg.draw_circle(
            [sx, sy], radius, fill=(255, 160, 50, alpha), color=C_TRANSPARENT, parent=layer_tag
        )


def _draw_ball(layer_tag: str, app_state, scale: float, ox: float, oy: float) -> None:
    if app_state.ball_position is None:
        return
    bx, by = app_state.ball_position
    sx, sy = field_to_screen(bx, by, scale, ox, oy)

    # Drop shadow
    dpg.draw_circle(
        [sx + 2, sy + 3], BALL_RADIUS, fill=(0, 0, 0, 70), color=C_TRANSPARENT, parent=layer_tag
    )
    # Ball body
    dpg.draw_circle(
        [sx, sy], BALL_RADIUS, fill=C_BALL, color=C_BALL_OUTLINE, thickness=2, parent=layer_tag
    )
    # Highlight dot
    dpg.draw_circle(
        [sx - 2, sy - 2], 2, fill=(255, 255, 255, 180), color=C_TRANSPARENT, parent=layer_tag
    )


def _draw_anchors(layer_tag: str, app_state, scale: float, ox: float, oy: float) -> None:
    for i, anchor in app_state.anchors.items():
        if anchor.disabled:
            continue
        sx, sy = field_to_screen(anchor.x, anchor.y, scale, ox, oy)

        if not anchor.online:
            colour = C_ANCHOR_OFFLINE
            half = ANCHOR_HALF - 3
            lbl_c = (130, 130, 130, 180)
        elif anchor.noisy:
            colour = C_ANCHOR_NOISY
            half = ANCHOR_HALF
            lbl_c = (255, 140, 60, 220)
        else:
            colour = C_ANCHOR_ONLINE
            half = ANCHOR_HALF
            lbl_c = (255, 255, 255, 255)

        # Diamond
        dpg.draw_polygon(
            [[sx, sy - half], [sx + half, sy], [sx, sy + half], [sx - half, sy]],
            fill=colour,
            color=(255, 255, 255, 120),
            thickness=1,
            parent=layer_tag,
        )

        # Label: "BS{n}"
        dpg.draw_text([sx + half + 3, sy - 8], f"BS{i}", color=lbl_c, size=12, parent=layer_tag)

        # Distance readout (online anchors only)
        if anchor.online and anchor.last_distance_mm > 0:
            dist_str = f"{anchor.last_distance_mm / 1000.0:.2f}m"
            dpg.draw_text(
                [sx + half + 3, sy + 4],
                dist_str,
                color=(200, 200, 200, 180),
                size=11,
                parent=layer_tag,
            )


def _draw_notifications(layer_tag: str, app_state, canvas_w: float, canvas_h: float) -> None:
    """Render semi-transparent overlay banners for goal / out-of-play events."""
    if app_state.show_goal_notification:
        t = app_state.goal_notification_timer
        # Fade in quickly, hold, then fade out in the last 60 frames
        a = min(255, int(255 * min(t, 30) / 30)) if t > 0 else 0
        bw, bh = 340, 76
        bx = (canvas_w - bw) / 2
        by = (canvas_h - bh) / 2 - 30

        dpg.draw_rectangle(
            [bx, by],
            [bx + bw, by + bh],
            fill=(10, 10, 20, min(210, a)),
            color=(255, 215, 0, a),
            thickness=2,
            rounding=10,
            parent=layer_tag,
        )
        dpg.draw_text(
            [bx + 40, by + 16], "GOAL!", size=44, color=(255, 215, 0, a), parent=layer_tag
        )

    if app_state.show_out_notification:
        t = app_state.out_notification_timer
        a = min(255, int(255 * min(t, 20) / 20)) if t > 0 else 0
        bw, bh = 310, 54
        bx = (canvas_w - bw) / 2
        by = 18

        dpg.draw_rectangle(
            [bx, by],
            [bx + bw, by + bh],
            fill=(20, 10, 10, min(200, a)),
            color=(255, 100, 30, a),
            thickness=2,
            rounding=8,
            parent=layer_tag,
        )
        dpg.draw_text(
            [bx + 30, by + 12], "OUT OF PLAY", size=28, color=(255, 130, 40, a), parent=layer_tag
        )
