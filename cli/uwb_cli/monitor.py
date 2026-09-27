"""``uwb monitor`` — live distance monitoring with SMA filter."""

from __future__ import annotations

import struct
from collections import deque
from typing import Annotated

import serial
import typer
from rich.live import Live
from rich.table import Table

app = typer.Typer(help="Live UWB distance monitoring.")

MARKER = b"CmdM:4["
NUM_ANCHORS = 8
PACKET_SIZE = 8 + 2 + (NUM_ANCHORS * 4)  # ts(8) + seq(2) + distances(32)

PORT = Annotated[
    str,
    typer.Option("-p", "--port", envvar="UWB_PORT", help="Serial port path", show_default=True),
]
BAUD = Annotated[int, typer.Option("-b", "--baudrate", help="Baud rate", show_default=True)]


def _make_table(
    seq: int,
    raw: list[int],
    smoothed: list[float | None],
    total_dropped: int,
    window: int,
    corrections: dict[int, tuple[float, float]] | None = None,
) -> Table:
    """Build a Rich table for live display."""
    table = Table()
    table.add_column("Anchor", style="cyan", justify="center")
    table.add_column("Raw mm", justify="right")
    table.add_column(f"SMA-{window} mm", justify="right", style="green")
    table.add_column("Corrected mm", justify="right", style="magenta")
    table.add_column("Status", justify="center")

    for i in range(NUM_ANCHORS):
        r = raw[i]
        s = smoothed[i]

        # Apply per-anchor correction if available
        corrected: float | None = None
        if corrections and i in corrections and s is not None:
            ca, cb = corrections[i]
            corrected = ca * s + cb

        if r == 0 and s is None:
            table.add_row(f"BS{i}", "----", "----", "----", "[dim]offline[/dim]")
        elif r > 10_000:
            table.add_row(
                f"BS{i}",
                str(r),
                f"{s:.0f}" if s else "----",
                f"{corrected:.0f}" if corrected else "----",
                "[red]noisy[/red]",
            )
        else:
            s_str = f"{s:.0f}" if s is not None else "----"
            c_str = f"{corrected:.0f}" if corrected is not None else "----"
            table.add_row(
                f"BS{i}",
                str(r),
                f"[green]{s_str}[/green]",
                f"[magenta]{c_str}[/magenta]" if corrected is not None else "----",
                "[green]ok[/green]",
            )

    table.caption = f"Seq: {seq}  |  Dropped: {total_dropped}"
    return table


@app.command()
def live(
    port: PORT = "/dev/ttyACM0",
    baudrate: BAUD = 115_200,
    window: Annotated[
        int,
        typer.Option(
            "-w",
            "--window",
            help="Moving average window size (1 = no filter)",
            min=1,
            show_default=True,
        ),
    ] = 20,
    config: Annotated[
        str,
        typer.Option("-c", "--config", help="uwb.toml path for anchor corrections"),
    ] = "",
) -> None:
    """Monitor UWB distance data with simple moving average (SMA) filter.

    Window size controls smoothing:
      -w 1   →  raw values only
      -w 10  →  ~1 second of averaging at 10 Hz
      -w 20  →  ~2 seconds (default, good for calibration)
      -w 50  →  heavy smoothing
    """
    # Load corrections from config if available
    corrections: dict[int, tuple[float, float]] = {}
    if config:
        from uwb_config.models import AppConfig

        cfg = AppConfig.load(config)
        for anchor_id, corr in cfg.corrections.items():
            corrections[int(anchor_id)] = (corr.a, corr.b)

    ser = serial.Serial(port, baudrate, timeout=1)
    buf = bytes()
    last_seq: int | None = None
    total_dropped = 0
    seq = 0
    raw = [0] * NUM_ANCHORS
    smoothed: list[float | None] = [None] * NUM_ANCHORS
    history: list[deque[int]] = [deque(maxlen=window) for _ in range(NUM_ANCHORS)]

    with Live(
        _make_table(0, raw, smoothed, 0, window, corrections),
        refresh_per_second=20,
    ) as live:
        while True:
            buf += ser.read(ser.in_waiting or 1)

            while MARKER in buf:
                idx = buf.index(MARKER) + len(MARKER)
                if len(buf) < idx + PACKET_SIZE:
                    break

                _ts = struct.unpack_from("<Q", buf, idx)[0]
                seq = struct.unpack_from("<H", buf, idx + 8)[0]
                raw = [
                    struct.unpack_from("<I", buf, idx + 10 + i * 4)[0] for i in range(NUM_ANCHORS)
                ]

                # Simple moving average per anchor
                for i in range(NUM_ANCHORS):
                    if 0 < raw[i] <= 100_000:
                        history[i].append(raw[i])
                        smoothed[i] = sum(history[i]) / len(history[i])

                if last_seq is not None:
                    gap = (seq - last_seq) % 65536
                    total_dropped += gap - 1

                last_seq = seq
                buf = buf[idx + PACKET_SIZE :]
                live.update(_make_table(seq, raw, smoothed, total_dropped, window, corrections))
