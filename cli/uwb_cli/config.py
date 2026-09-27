"""``uwb config`` — manage uwb.toml configuration files."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import tomli_w  # type: ignore[import-untyped]
import typer
from rich import print as rprint
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax

from uwb_config.models import AppConfig

app = typer.Typer(help="Manage uwb.toml configuration files.")


@app.command()
def init(
    path: Annotated[
        str,
        typer.Option("-o", "--output", help="Output path (default: ./uwb.toml)"),
    ] = "uwb.toml",
    force: Annotated[
        bool,
        typer.Option("-f", "--force", help="Overwrite existing file"),
    ] = False,
) -> None:
    """Interactively scaffold a uwb.toml config file."""
    dest = Path(path).expanduser().resolve()

    if dest.exists() and not force:
        rprint(f"[yellow]{dest} already exists. Use --force to overwrite.[/yellow]")
        raise typer.Exit(1)

    rprint(Panel.fit("[bold]UWB Config Initialisation[/bold]", border_style="cyan"))
    rprint()

    # Device section
    rprint("[bold cyan]Device[/bold cyan]")
    dev_id = int(Prompt.ask("  Device ID", default="1"))
    dev_role = Prompt.ask("  Role (tag/anchor)", default="anchor")
    dev_channel = Prompt.ask("  Channel (5/9)", default="5")
    dev_rate = Prompt.ask("  Rate (850k/6.8m)", default="850k")

    # Filter section
    rprint()
    rprint("[bold cyan]Filter[/bold cyan]")
    kalman = Confirm.ask("  Enable Kalman filter?", default=True)
    kalman_q = float(Prompt.ask("  Kalman Q (process noise)", default="0.01"))
    kalman_r = float(Prompt.ask("  Kalman R (measurement noise)", default="0.1"))
    antenna_delay = int(Prompt.ask("  Antenna delay", default="16400"))
    label_cap = float(Prompt.ask("  Label capacity", default="10.0"))
    slope = float(Prompt.ask("  Distance slope (a)", default="1.0"))
    intercept = float(Prompt.ask("  Distance intercept (b)", default="0.0"))
    pos = Confirm.ask("  Enable positioning engine?", default=False)
    pos_dim = int(Prompt.ask("  Positioning dimensions (2/3)", default="2"))

    # Build config
    from uwb_config.models import (
        Channel,
        DeviceConfig,
        FilterConfig,
        Rate,
        Role,
    )

    cfg = AppConfig(
        device=DeviceConfig(
            id=dev_id,
            role=Role.TAG if dev_role.lower() == "tag" else Role.ANCHOR,
            channel=Channel.CH5 if dev_channel == "5" else Channel.CH9,
            rate=Rate.R850K if dev_rate.lower() in ("850k", "850") else Rate.R6800K,
        ),
        filter=FilterConfig(
            kalman_enable=kalman,
            kalman_q=kalman_q,
            kalman_r=kalman_r,
            antenna_delay=antenna_delay,
            label_capacity=label_cap,
            a=slope,
            b=intercept,
            pos_enable=pos,
            pos_dim=pos_dim,
        ),
    )

    cfg.save(dest)
    rprint(f"\n[green]Config written to {dest}[/green]")

    # Show a preview
    toml_text = dest.read_text()
    rprint()
    rprint(Syntax(toml_text, "toml", theme="monokai", line_numbers=False))


@app.command()
def show(
    path: Annotated[
        str,
        typer.Option("-c", "--config", help="Config file path (auto-detected if omitted)"),
    ] = "",
) -> None:
    """Display the current merged configuration."""
    cfg = AppConfig.load(path if path else None)

    # Use model_dump with mode="json" for clean output
    dumped = cfg.model_dump(mode="json", exclude_defaults=False)

    rprint(
        Syntax(
            tomli_w.dumps(dumped),
            "toml",
            theme="monokai",
            line_numbers=False,
        )
    )


@app.command()
def validate(
    path: Annotated[
        str,
        typer.Option("-c", "--config", help="Config file path (auto-detected if omitted)"),
    ] = "",
) -> None:
    """Validate a uwb.toml file."""
    try:
        cfg = AppConfig.load(path if path else None)
        rprint("[green]✓ Config is valid[/green]")
        rprint(f"  Device: id={cfg.device.id} role={cfg.device.role.name}")
        rprint(f"  Filter: Kalman={'on' if cfg.filter.kalman_enable else 'off'}")
        if cfg.corrections:
            rprint(f"  Corrections: {len(cfg.corrections)} anchor(s)")
    except Exception as e:
        rprint(f"[red]✗ Invalid config:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def path() -> None:
    """Show config file lookup order and which file is active."""
    candidates = [
        ("1. ./uwb.toml", Path("uwb.toml")),
        ("2. ~/.config/uwb/config.toml", Path.home() / ".config" / "uwb" / "config.toml"),
    ]
    found = False
    for label, p in candidates:
        marker = " ✔ [green](found)[/green]" if p.exists() else ""
        rprint(f"  {label}{marker}")
        if p.exists() and not found:
            found = True

    if not found:
        rprint("\n  [yellow]No config file found — using defaults.[/yellow]")
