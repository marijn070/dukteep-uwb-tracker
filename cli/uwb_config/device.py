"""Serial communication with UWB device — with dry-run support."""

from __future__ import annotations

import time
from typing import Protocol

import serial


class DeviceIO(Protocol):
    """Protocol for device I/O so DryRunIO can substitute transparently."""

    def send(self, data: bytes) -> None: ...
    def receive(self, timeout: float = 1.0) -> str: ...
    def close(self) -> None: ...


class SerialIO:
    """Real serial-port I/O."""

    def __init__(self, port: str, baudrate: int = 115_200) -> None:
        self._ser = serial.Serial(port, baudrate, timeout=1)

    def send(self, data: bytes) -> None:
        self._ser.write(data)
        self._ser.flush()

    def receive(self, timeout: float = 1.0) -> str:
        time.sleep(timeout)
        return self._ser.read_all().decode(errors="ignore")

    def close(self) -> None:
        self._ser.close()


class DryRunIO:
    """Prints AT commands instead of sending them."""

    def send(self, data: bytes) -> None:
        print(f"  [dry-run] → {data.decode().rstrip()}")

    def receive(self, timeout: float = 1.0) -> str:
        print("  [dry-run] ← (no device)")
        return ""

    def close(self) -> None:
        pass


def open_device(port: str, baudrate: int = 115_200, *, dry_run: bool = False) -> DeviceIO:
    """Factory: return real or dry-run I/O depending on *dry_run*."""
    if dry_run:
        return DryRunIO()
    return SerialIO(port, baudrate)


def send_at(dev: DeviceIO, cmd: str, wait: float = 0.3) -> str:
    """Send an AT command and return the response."""
    dev.send(cmd.encode() if isinstance(cmd, str) else cmd)
    return dev.receive(timeout=wait)
