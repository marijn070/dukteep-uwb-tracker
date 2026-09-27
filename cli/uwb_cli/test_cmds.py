"""``uwb test`` — run device self-tests."""

from __future__ import annotations

from typing import Annotated

import typer
from rich import print as rprint

from uwb_config.device import open_device, send_at

app = typer.Typer(help="Run device self-tests (LED, screen, distance, all).")

PORT = Annotated[
    str,
    typer.Option("-p", "--port", envvar="UWB_PORT", help="Serial port path", show_default=True),
]
BAUD = Annotated[int, typer.Option("-b", "--baudrate", help="Baud rate", show_default=True)]
DRY_RUN = Annotated[bool, typer.Option("--dry-run", help="Print AT commands without sending")]


@app.command()
def led(
    port: PORT = "/dev/ttyUSB0",
    baudrate: BAUD = 115_200,
    dry_run: DRY_RUN = False,
) -> None:
    """Blink the device LED (test = 1)."""
    dev = open_device(port, baudrate, dry_run=dry_run)
    try:
        rprint("[yellow]Starting LED test...[/yellow]")
        send_at(dev, "AT+TEST=1\r\n", wait=0.3)
        rprint("[green]LED test running (device may not respond).[/green]")
        rprint("Press Ctrl+C or send AT+TEST=0 to stop.")
        try:
            import time

            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            send_at(dev, "AT+TEST=0\r\n", wait=0.3)
            rprint("[green]LED test stopped.[/green]")
    finally:
        dev.close()


@app.command()
def screen(
    port: PORT = "/dev/ttyUSB0",
    baudrate: BAUD = 115_200,
    dry_run: DRY_RUN = False,
) -> None:
    """Run screen test (test = 2)."""
    dev = open_device(port, baudrate, dry_run=dry_run)
    try:
        rprint("[yellow]Starting screen test...[/yellow]")
        send_at(dev, "AT+TEST=2\r\n", wait=0.3)
        rprint("[green]Screen test running.[/green]")
        rprint("Press Ctrl+C or send AT+TEST=0 to stop.")
        try:
            import time

            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            send_at(dev, "AT+TEST=0\r\n", wait=0.3)
            rprint("[green]Screen test stopped.[/green]")
    finally:
        dev.close()


@app.command()
def distance(
    port: PORT = "/dev/ttyUSB0",
    baudrate: BAUD = 115_200,
    dry_run: DRY_RUN = False,
) -> None:
    """Run distance test (test = 3)."""
    dev = open_device(port, baudrate, dry_run=dry_run)
    try:
        rprint("[yellow]Starting distance test...[/yellow]")
        send_at(dev, "AT+TEST=3\r\n", wait=0.3)
        rprint("[green]Distance test running.[/green]")
        rprint("Press Ctrl+C or send AT+TEST=0 to stop.")
        try:
            import time

            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            send_at(dev, "AT+TEST=0\r\n", wait=0.3)
            rprint("[green]Distance test stopped.[/green]")
    finally:
        dev.close()


@app.command()
def all(
    port: PORT = "/dev/ttyUSB0",
    baudrate: BAUD = 115_200,
    dry_run: DRY_RUN = False,
) -> None:
    """Run all tests (test = 4)."""
    dev = open_device(port, baudrate, dry_run=dry_run)
    try:
        rprint("[yellow]Starting all tests...[/yellow]")
        send_at(dev, "AT+TEST=4\r\n", wait=0.3)
        rprint("[green]All tests running.[/green]")
        rprint("Press Ctrl+C or send AT+TEST=0 to stop.")
        try:
            import time

            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            send_at(dev, "AT+TEST=0\r\n", wait=0.3)
            rprint("[green]Tests stopped.[/green]")
    finally:
        dev.close()
