"""Least-squares trilateration and 2-D Kalman filter for UWB ball tracking."""

from typing import Optional

import numpy as np

MAX_RESIDUAL_M = 2.0  # metres; solutions with higher RMS error are discarded


def trilaterate(
    anchor_positions: dict[int, tuple[float, float]],
    distances_m: dict[int, float],
) -> Optional[tuple[float, float]]:
    """Estimate (x, y) position via linearised least-squares trilateration.

    Parameters
    ----------
    anchor_positions:
        Mapping of anchor_id -> (x, y) in metres.
    distances_m:
        Mapping of anchor_id -> measured distance in metres.

    Returns
    -------
    (x, y) in metres, or None if the solution is unreliable.

    Algorithm
    ---------
    For each anchor i:  (x - xi)^2 + (y - yi)^2 = di^2
    Subtracting the equation of anchor 0 eliminates the quadratic terms:
        2*(xi - x0)*x + 2*(yi - y0)*y = xi^2 - x0^2 + yi^2 - y0^2 - di^2 + d0^2
    This yields A*[x,y]^T = b, solved with numpy least squares.
    """
    # Find common anchor ids
    common = [k for k in anchor_positions if k in distances_m]
    if len(common) < 3:
        return None

    # Anchor 0 is the reference for linearisation
    ref = common[0]
    x0, y0 = anchor_positions[ref]
    d0 = distances_m[ref]

    rows_A = []
    rows_b = []
    for anchor_id in common[1:]:
        xi, yi = anchor_positions[anchor_id]
        di = distances_m[anchor_id]
        rows_A.append([2.0 * (xi - x0), 2.0 * (yi - y0)])
        rows_b.append(xi**2 - x0**2 + yi**2 - y0**2 - di**2 + d0**2)

    A = np.array(rows_A, dtype=float)
    b = np.array(rows_b, dtype=float)

    result, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    x_est, y_est = float(result[0]), float(result[1])

    # Compute RMS residual across all anchors
    residuals = []
    for anchor_id in common:
        xi, yi = anchor_positions[anchor_id]
        dist_computed = np.hypot(x_est - xi, y_est - yi)
        residuals.append((dist_computed - distances_m[anchor_id]) ** 2)

    rms = float(np.sqrt(np.mean(residuals)))
    if rms > MAX_RESIDUAL_M:
        return None

    return (x_est, y_est)


class KalmanFilter2D:
    """Simple constant-velocity 2-D Kalman filter.

    State vector: [x, y, vx, vy].
    Assumes dt = 1 (one update per call).

    Parameters
    ----------
    process_noise:
        Scalar multiplier for the process noise covariance Q.
    measurement_noise:
        Scalar multiplier for the measurement noise covariance R.
    """

    def __init__(self, process_noise: float = 0.5, measurement_noise: float = 3.0) -> None:
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise
        self.initialized = False
        self._build_matrices()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_matrices(self) -> None:
        dt = 1.0

        # State transition: x_k = F * x_{k-1}
        self.F = np.array(
            [
                [1, 0, dt, 0],
                [0, 1, 0, dt],
                [0, 0, 1, 0],
                [0, 0, 0, 1],
            ],
            dtype=float,
        )

        # Observation matrix: we only measure x and y
        self.H = np.array(
            [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
            ],
            dtype=float,
        )

        # Process noise covariance
        self.Q = np.eye(4, dtype=float) * self.process_noise

        # Measurement noise covariance
        self.R = np.eye(2, dtype=float) * self.measurement_noise

        # Initial state and covariance (reset when (re)initialised)
        self.x = np.zeros((4, 1), dtype=float)
        self.P = np.eye(4, dtype=float) * 500.0

    def reset(self) -> None:
        """Reinitialise the filter; next update will seed state from measurement."""
        self._build_matrices()
        self.initialized = False

    def update(self, x: float, y: float) -> tuple[float, float]:
        """Predict then update with a new (x, y) measurement.

        On the very first call the state is seeded directly from the measurement
        so there is no transient jump from zero.

        Returns
        -------
        Filtered (x, y) estimate.
        """
        z = np.array([[x], [y]], dtype=float)

        if not self.initialized:
            self.x[0, 0] = x
            self.x[1, 0] = y
            self.x[2, 0] = 0.0
            self.x[3, 0] = 0.0
            self.initialized = True
            return (x, y)

        # --- Predict ---
        x_pred = self.F @ self.x
        P_pred = self.F @ self.P @ self.F.T + self.Q

        # --- Update ---
        S = self.H @ P_pred @ self.H.T + self.R  # innovation covariance
        K = P_pred @ self.H.T @ np.linalg.inv(S)  # Kalman gain
        y_innov = z - self.H @ x_pred  # innovation
        self.x = x_pred + K @ y_innov
        self.P = (np.eye(4) - K @ self.H) @ P_pred

        return (float(self.x[0, 0]), float(self.x[1, 0]))
