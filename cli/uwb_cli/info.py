"""``uwb info`` — device identification and status."""

from __future__ import annotations

from typing import Annotated

import typer
from rich import print as rprint

from uwb_config.device import open_device, send_at

app = typer.Typer(help="Device identification and status.")

PORT = Annotated[
    str,
    typer.Option("-p", "--port", envvar="UWB_PORT", help="Serial port path", show_default=True),
]
BAUD = Annotated[int, typer.Option("-b", "--baudrate", help="Baud rate", show_default=True)]


@app.command()
def version(
    port: PORT = "/dev/ttyUSB0",
    baudrate: BAUD = 115_200,
) -> None:
    """Query firmware version."""
    dev = open_device(port, baudrate)
    try:
        resp = send_at(dev, "AT+VERSION?\r\n", wait=0.3)
        rprint(f"[bold]Version:[/bold] {resp.strip() or '(no response)'}")
    finally:
        dev.close()


@app.command()
def status(
    port: PORT = "/dev/ttyUSB0",
    baudrate: BAUD = 115_200,
) -> None:
    """Show combined device + filter status."""
    from uwb_config.models import DeviceConfig, FilterConfig

    dev = open_device(port, baudrate)
    try:
        # Device config
        resp = send_at(dev, "AT+GETCFG\r\n", wait=0.3)
        rprint(f"[dim]GETCFG:[/dim] {resp.strip()}")
        dcfg = DeviceConfig.from_at_response(resp)
        if dcfg:
            rprint(
                f"  ID={dcfg.id}  role={dcfg.role.name}  ch={dcfg.channel.name}  rate={dcfg.rate.name}"
            )

        # Filter config
        resp = send_at(dev, "AT+GETDEV\r\n", wait=0.3)
        rprint(f"[dim]GETDEV:[/dim] {resp.strip()}")
        fcfg = FilterConfig.from_at_response(resp)
        if fcfg:
            rprint(
                f"  Kalman={'on' if fcfg.kalman_enable else 'off'}"
                f"  Q={fcfg.kalman_q}  R={fcfg.kalman_r}"
                f"  slope={fcfg.a}  int={fcfg.b}"
            )
    finally:
        dev.close()
