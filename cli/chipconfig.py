#!/usr/bin/env python3
"""UWB chip configuration tool."""

import time
from typing import Annotated

import serial
import typer

from uwb_config.models import (
    Channel,
    DeviceConfig as Config,
    FilterConfig as Calibration,
    Rate,
    Role,
)

app = typer.Typer()

# Shared config object reused across commands
PORT_OPTION = Annotated[
    str, typer.Option("-p", "--port", help="Serial port path", show_default=True)
]
BAUD_OPTION = Annotated[int, typer.Option("-b", "--baudrate", help="Baud rate", show_default=True)]


@app.command()
def tune(
    port: PORT_OPTION = "/dev/ttyUSB0",
    baudrate: BAUD_OPTION = 115_200,
) -> None:
    """Read current calibration from chip, edit, and write back."""
    ser = serial.Serial(port, baudrate, timeout=1)

    ser.write(b"AT+GETDEV\r\n")
    time.sleep(0.2)
    response = ser.read_all().decode(errors="ignore")
    print(f"AT response: {response}")
    cal = Calibration.from_at_response(response)

    if cal is None:
        print("Failed to read current config. Exiting.")
        raise typer.Exit(1)

    print(f"Current config: {cal}")

    cal.a = float(typer.prompt("Distance correction slope (a)", default=str(cal.a)))
    cal.b = float(typer.prompt("Distance correction intercept (b)", default=str(cal.b)))

    print(f"\nNew config: {cal}")

    if typer.confirm("Write calibration to chip?"):
        ser.write(cal.to_at_command().encode())
        time.sleep(0.2)
        print("Calibration written. Saving...")
        ser.write(b"AT+SAVE\r\n")
        time.sleep(0.2)
        resp = ser.read_all().decode(errors="ignore")
        if resp:
            print(f"Response: {resp}")
        print("Done.")

    ser.close()


@app.command()
def configure(
    port: PORT_OPTION = "/dev/ttyUSB0",
    baudrate: BAUD_OPTION = 115_200,
) -> None:
    """Read current device config from chip, edit, and write back."""
    ser = serial.Serial(port, baudrate, timeout=1)

    ser.write(b"AT+GETCFG\r\n")
    time.sleep(0.2)
    response = ser.read_all().decode(errors="ignore")
    print(f"AT response: {response}")
    cfg = Config.from_at_response(response)

    if cfg is None:
        print("Failed to read current config. Exiting.")
        raise typer.Exit(1)

    print(f"Current config: {cfg}")

    id_str = typer.prompt("ID", default=str(cfg.id))
    role_str = typer.prompt("Role (0=TAG, 1=BASE_STATION)", default=str(cfg.role.value))
    channel_str = typer.prompt("Channel (0=CH5, 1=CH9)", default=str(cfg.channel.value))
    rate_str = typer.prompt("Rate (0=R850K, 1=R6800K)", default=str(cfg.rate.value))

    new_cfg = Config(
        id=int(id_str),
        role=Role(int(role_str)),
        channel=Channel(int(channel_str)),
        rate=Rate(int(rate_str)),
    )

    print(f"\nNew config: {new_cfg}")

    if typer.confirm("Write config to chip?"):
        ser.write(new_cfg.to_at_command().encode())
        time.sleep(0.2)
        print("Config written. Saving...")
        ser.write(b"AT+SAVE\r\n")
        time.sleep(0.2)
        resp = ser.read_all().decode(errors="ignore")
        if resp:
            print(f"Response: {resp}")
        print("Done.")
    else:
        print("Aborted.")

    ser.close()


if __name__ == "__main__":
    app()
