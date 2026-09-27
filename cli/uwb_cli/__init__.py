"""``uwb`` — UWB device management CLI.

Usage::

    uwb device get                  # read device config
    uwb device set --id 1 --role anchor --channel 5
    uwb filter get                  # read Kalman/calibration params
    uwb filter set --slope 1.02 --intercept -12
    uwb info version                # query firmware version
    uwb info status                 # combined device + filter overview
    uwb test led                    # blink LED
    uwb test all                    # run all self-tests
    uwb config init                 # interactively scaffold uwb.toml
    uwb config show                 # display merged config
    uwb config validate             # validate uwb.toml
    uwb monitor live                # live distance table (SMA)

All write commands accept ``--dry-run`` to preview AT commands.
All serial commands accept ``--port`` / ``-p`` (env: ``UWB_PORT``).
"""

from __future__ import annotations

import typer

from uwb_cli import config, device, filter, info, monitor, test_cmds

app = typer.Typer(
    name="uwb",
    help="UWB device management CLI.",
    no_args_is_help=True,
)

app.add_typer(device.app, name="device")
app.add_typer(filter.app, name="filter")
app.add_typer(info.app, name="info")
app.add_typer(test_cmds.app, name="test")
app.add_typer(config.app, name="config")
app.add_typer(monitor.app, name="monitor")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
