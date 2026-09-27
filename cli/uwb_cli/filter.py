"""``uwb filter`` — read/write Kalman filter and calibration parameters."""

from __future__ import annotations

from typing import Annotated

import typer
from rich import print as rprint
from rich.table import Table

from uwb_config.device import open_device, send_at
from uwb_config.models import FilterConfig

app = typer.Typer(help="Read/write Kalman filter and calibration parameters.")

PORT = Annotated[
    str,
    typer.Option("-p", "--port", envvar="UWB_PORT", help="Serial port path", show_default=True),
]
BAUD = Annotated[int, typer.Option("-b", "--baudrate", help="Baud rate", show_default=True)]
DRY_RUN = Annotated[bool, typer.Option("--dry-run", help="Print AT commands without sending")]


@app.command()
def get(
    port: PORT = "/dev/ttyUSB0",
    baudrate: BAUD = 115_200,
    dry_run: DRY_RUN = False,
) -> None:
    """Read current filter/calibration parameters from chip."""
    dev = open_device(port, baudrate, dry_run=dry_run)
    try:
        resp = send_at(dev, "AT+GETDEV\r\n", wait=0.3)
        rprint(f"[dim]Raw response:[/dim] {resp.strip()}")
        cfg = FilterConfig.from_at_response(resp)
        if cfg is None:
            rprint("[red]Failed to parse filter config.[/red]")
            raise typer.Exit(1)

        table = Table(title="Filter / Calibration Config")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")

        rows = [
            ("Label capacity", str(cfg.label_capacity)),
            ("Antenna delay", str(cfg.antenna_delay)),
            ("Kalman enable", str(cfg.kalman_enable)),
            ("Kalman Q", str(cfg.kalman_q)),
            ("Kalman R", str(cfg.kalman_r)),
            ("Slope (a)", str(cfg.a)),
            ("Intercept (b)", str(cfg.b)),
            ("Position enable", str(cfg.pos_enable)),
            ("Position dims", str(cfg.pos_dim)),
        ]
        for field, value in rows:
            table.add_row(field, value)
        rprint(table)
    finally:
        dev.close()


@app.command()
def set(
    kalman_enable: Annotated[
        bool, typer.Option("--kalman/--no-kalman", help="Enable/disable Kalman filter")
    ] = True,
    kalman_q: Annotated[float, typer.Option("--kalman-q", help="Process noise Q", min=0)] = 0.01,
    kalman_r: Annotated[float, typer.Option("--kalman-r", help="Measurement noise R", min=0)] = 0.1,
    a: Annotated[float, typer.Option("--slope", "-a", help="Distance correction slope")] = 1.0,
    b: Annotated[
        float, typer.Option("--intercept", "-b", help="Distance correction intercept")
    ] = 0.0,
    antenna_delay: Annotated[
        int, typer.Option("--antenna-delay", help="Antenna delay value")
    ] = 16_400,
    label_capacity: Annotated[
        float, typer.Option("--label-capacity", help="Label capacity", min=0)
    ] = 10.0,
    pos_enable: Annotated[
        bool, typer.Option("--pos/--no-pos", help="Enable/disable positioning engine")
    ] = False,
    pos_dim: Annotated[
        int, typer.Option("--pos-dim", help="Positioning dimensions (2 or 3)", min=1, max=3)
    ] = 2,
    port: PORT = "/dev/ttyUSB0",
    baudrate: BAUD = 115_200,
    dry_run: DRY_RUN = False,
) -> None:
    """Set filter/calibration parameters on chip.

    Reads current values first so unspecified fields are preserved.
    Use ``--dry-run`` to preview the AT command.
    """
    dev = open_device(port, baudrate, dry_run=dry_run)
    try:
        # Read current values as base
        resp = send_at(dev, "AT+GETDEV\r\n", wait=0.3)
        current = FilterConfig.from_at_response(resp)

        if current is None:
            rprint("[yellow]Could not read current config — using defaults as base.[/yellow]")
            current = FilterConfig()

        # Merge CLI overrides
        merged = FilterConfig(
            label_capacity=label_capacity,
            antenna_delay=antenna_delay,
            kalman_enable=kalman_enable,
            kalman_q=kalman_q,
            kalman_r=kalman_r,
            a=a,
            b=b,
            pos_enable=pos_enable,
            pos_dim=pos_dim,
        )

        rprint("[bold]Sending filter config:[/bold]")
        rprint(f"  {merged.to_at_command().strip()}")

        send_at(dev, merged.to_at_command(), wait=0.3)
        if not dry_run:
            send_at(dev, "AT+SAVE\r\n", wait=0.3)
            rprint("[green]Filter config written and saved.[/green]")
    finally:
        dev.close()
