"""``uwb device`` — read/write device identity and radio parameters."""

from __future__ import annotations

from typing import Annotated

import typer
from rich import print as rprint
from rich.table import Table

from uwb_config.device import open_device, send_at
from uwb_config.models import (
    Channel,
    DeviceConfig,
    Rate,
    Role,
    _parse_channel,
    _parse_rate,
    _parse_role,
)

app = typer.Typer(help="Read/write device identity and radio parameters.")

# Reusable option annotations
PORT = Annotated[
    str,
    typer.Option("-p", "--port", envvar="UWB_PORT", help="Serial port path", show_default=True),
]
BAUD = Annotated[int, typer.Option("-b", "--baudrate", help="Baud rate", show_default=True)]
DRY_RUN = Annotated[bool, typer.Option("--dry-run", help="Print AT commands without sending")]


def _label_role(r: Role) -> str:
    return "tag" if r == Role.TAG else "anchor"


def _label_channel(c: Channel) -> str:
    return "5" if c == Channel.CH5 else "9"


def _label_rate(r: Rate) -> str:
    return "850k" if r == Rate.R850K else "6.8M"


# ── get ──────────────────────────────────────────────────────────────────────


@app.command()
def get(
    port: PORT = "/dev/ttyUSB0",
    baudrate: BAUD = 115_200,
    dry_run: DRY_RUN = False,
) -> None:
    """Read current device configuration from chip."""
    dev = open_device(port, baudrate, dry_run=dry_run)
    try:
        resp = send_at(dev, "AT+GETCFG\r\n", wait=0.3)
        rprint(f"[dim]Raw response:[/dim] {resp.strip()}")
        cfg = DeviceConfig.from_at_response(resp)
        if cfg is None:
            rprint("[red]Failed to parse device config.[/red]")
            raise typer.Exit(1)

        table = Table(title="Device Config")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Wire", style="dim")
        table.add_row("ID", str(cfg.id), str(cfg.id))
        table.add_row("Role", _label_role(cfg.role), str(cfg.role.value))
        table.add_row("Channel", _label_channel(cfg.channel), str(cfg.channel.value))
        table.add_row("Rate", _label_rate(cfg.rate), str(cfg.rate.value))
        rprint(table)
    finally:
        dev.close()


# ── set ──────────────────────────────────────────────────────────────────────


@app.command()
def set(
    id: Annotated[int, typer.Option("--id", "-i", help="Device ID (0-255)")],
    role: Annotated[str, typer.Option("--role", "-r", help="tag | anchor")] = "anchor",
    channel: Annotated[str, typer.Option("--channel", "-c", help="5 | 9")] = "5",
    rate: Annotated[str, typer.Option("--rate", help="850k | 6.8m")] = "850k",
    port: PORT = "/dev/ttyUSB0",
    baudrate: BAUD = 115_200,
    dry_run: DRY_RUN = False,
) -> None:
    """Set device configuration on chip."""
    cfg = DeviceConfig(
        id=id,
        role=_parse_role(role),
        channel=_parse_channel(channel),
        rate=_parse_rate(rate),
    )

    rprint("[bold]Setting device config:[/bold]")
    rprint(f"  ID      = {cfg.id}")
    rprint(f"  Role    = {_label_role(cfg.role)}")
    rprint(f"  Channel = {_label_channel(cfg.channel)}")
    rprint(f"  Rate    = {_label_rate(cfg.rate)}")
    rprint()

    dev = open_device(port, baudrate, dry_run=dry_run)
    try:
        resp = send_at(dev, cfg.to_at_command(), wait=0.3)
        if resp.strip():
            rprint(f"[dim]Response:[/dim] {resp.strip()}")
        if not dry_run:
            send_at(dev, "AT+SAVE\r\n", wait=0.3)
            rprint("[green]Config written and saved.[/green]")
    finally:
        dev.close()


# ── list ─────────────────────────────────────────────────────────────────────


@app.command(name="list")
def list_devices() -> None:
    """Show recognised device roles and their wire values."""
    table = Table(title="Device Roles & Values")
    table.add_column("CLI value", style="cyan")
    table.add_column("Wire value", style="green")
    table.add_column("Description")

    for label, role in [("tag", Role.TAG), ("anchor", Role.ANCHOR)]:
        table.add_row(label, str(role.value), role.name)

    table.add_section()
    table.add_row("5", str(Channel.CH5.value), "Channel 5")
    table.add_row("9", str(Channel.CH9.value), "Channel 9")

    table.add_section()
    table.add_row("850k", str(Rate.R850K.value), "850 Kbps")
    table.add_row("6.8m", str(Rate.R6800K.value), "6.8 Mbps")

    rprint(table)
