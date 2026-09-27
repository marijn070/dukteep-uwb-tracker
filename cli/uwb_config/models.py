"""Pydantic models for UWB device configuration and CLI app config.

These replace the older dataclass-based models.  Pydantic gives us:
- Validation on construction (catch bad values early)
- JSON Schema generation for config-file validation
- Serialisation/deserialisation with aliases for TOML friendliness
"""

from __future__ import annotations

from enum import IntEnum
from pathlib import Path
from typing import Any, Dict

import tomli_w  # type: ignore[import-untyped]  # noqa: F811
from pydantic import BaseModel, ConfigDict, Field, model_validator

# ── Enums with human-friendly labelling ──────────────────────────────────────


class Role(IntEnum):
    TAG = 0
    ANCHOR = 1  # "anchor" is the human-facing name for base-station

    # Aliases so both "TAG"/"ANCHOR" and old names work
    BASE_STATION = 1


class Channel(IntEnum):
    CH5 = 0
    CH9 = 1


class Rate(IntEnum):
    R850K = 0
    R6800K = 1


# ── Human → wire-value helpers ───────────────────────────────────────────────

ROLE_MAP: Dict[str, Role] = {
    "tag": Role.TAG,
    "anchor": Role.ANCHOR,
    "base_station": Role.ANCHOR,
    "0": Role.TAG,
    "1": Role.ANCHOR,
}

CHANNEL_MAP: Dict[str, Channel] = {
    "5": Channel.CH5,
    "9": Channel.CH9,
    "ch5": Channel.CH5,
    "ch9": Channel.CH9,
    "0": Channel.CH5,
    "1": Channel.CH9,
}

RATE_MAP: Dict[str, Rate] = {
    "850k": Rate.R850K,
    "6.8m": Rate.R6800K,
    "850": Rate.R850K,
    "6800": Rate.R6800K,
    "0": Rate.R850K,
    "1": Rate.R6800K,
}


def _parse_role(v: object) -> Role:
    if isinstance(v, Role):
        return v
    if isinstance(v, int):
        return Role(v)
    key = str(v).strip().lower().replace(" ", "_")
    if key in ROLE_MAP:
        return ROLE_MAP[key]
    raise ValueError(f"Unknown role: {v!r}.  Use tag|anchor.")


def _parse_channel(v: object) -> Channel:
    if isinstance(v, Channel):
        return v
    if isinstance(v, int):
        return Channel(v)
    key = str(v).strip().lower().replace(" ", "")
    if key in CHANNEL_MAP:
        return CHANNEL_MAP[key]
    raise ValueError(f"Unknown channel: {v!r}.  Use 5|9.")


def _parse_rate(v: object) -> Rate:
    if isinstance(v, Rate):
        return v
    if isinstance(v, int):
        return Rate(v)
    key = str(v).strip().lower().replace(" ", "")
    if key in RATE_MAP:
        return RATE_MAP[key]
    raise ValueError(f"Unknown rate: {v!r}.  Use 850k|6.8m.")


# ── Device config (AT+GETCFG / AT+SETCFG) ────────────────────────────────────


class DeviceConfig(BaseModel):
    """Mirrors the AT+SETCFG=id,role,ch,rate command."""

    model_config = ConfigDict(use_enum_values=False)

    id: int = Field(ge=0, le=255, description="Device ID")
    role: Role = Field(default=Role.ANCHOR, description="tag | anchor")
    channel: Channel = Field(default=Channel.CH5, description="5 | 9")
    rate: Rate = Field(default=Rate.R850K, description="850k | 6.8m")

    @model_validator(mode="before")
    @classmethod
    def _coerce_fields(cls, data: Any) -> Any:
        """Allow human-friendly strings in constructors and TOML files."""
        if not isinstance(data, dict):
            return data
        for field_name, parser in (
            ("role", _parse_role),
            ("channel", _parse_channel),
            ("rate", _parse_rate),
        ):
            if field_name in data:
                data[field_name] = parser(data[field_name])
        return data

    def to_at_command(self) -> str:
        return f"AT+SETCFG={self.id},{self.role.value},{self.channel.value},{self.rate.value}\r\n"

    @classmethod
    def from_at_response(cls, response: str) -> DeviceConfig | None:
        """Parse a ``GETCFG=ID:…,ROLE:…,CH:…,RATE:…`` response line."""
        try:
            for line in response.strip().splitlines():
                if line.upper().startswith("GETCFG"):
                    # line looks like: GETCFG=ID:1,ROLE:1,CH:0,RATE:0
                    body = line.split("=", 1)[1] if "=" in line else line[6:].strip()
                    parts: dict[str, str] = {}
                    for token in body.split(","):
                        k, v = token.split(":", 1)
                        parts[k.strip().lower()] = v.strip()
                    return cls(
                        id=int(parts["id"]),
                        role=Role(int(parts["role"])),
                        channel=Channel(int(parts["ch"])),
                        rate=Rate(int(parts["rate"])),
                    )
        except Exception:
            pass
        return None


# ── Filter / calibration config (AT+GETDEV / AT+SETDEV) ─────────────────────


class FilterConfig(BaseModel):
    """Mirrors the AT+SETDEV command parameters (Kalman + calibration)."""

    label_capacity: float = Field(default=10.0, ge=0, description="Label capacity")
    antenna_delay: int = Field(default=16400, description="Antenna delay")
    kalman_enable: bool = Field(default=True, description="Kalman filter on/off")
    kalman_q: float = Field(default=0.01, ge=0, description="Process noise Q")
    kalman_r: float = Field(default=0.1, ge=0, description="Measurement noise R")
    a: float = Field(default=1.0, description="Distance correction slope")
    b: float = Field(default=0.0, description="Distance correction intercept")
    pos_enable: bool = Field(default=False, description="Positioning engine on/off")
    pos_dim: int = Field(default=2, ge=1, le=3, description="Positioning dimensions (2 or 3)")

    def to_at_command(self) -> str:
        return (
            f"AT+SETDEV={self.label_capacity},{self.antenna_delay},"
            f"{int(self.kalman_enable)},{self.kalman_q},{self.kalman_r},"
            f"{self.a},{self.b},{int(self.pos_enable)},{self.pos_dim}\r\n"
        )

    @classmethod
    def from_at_response(cls, response: str) -> FilterConfig | None:
        """Parse a ``GETDEV=CAP:…,ANNDELAY:…,…`` response line."""
        try:
            for line in response.strip().splitlines():
                if line.split(":")[0].upper().startswith("GETDEV"):
                    # Handle both `GETDEV:` and `GETDEV=CAP:...` formats
                    if "=" in line:
                        body = line.split("=", 1)[1]
                    else:
                        body = line.split(":", 1)[1] if ":" in line else line[6:].strip()
                    parts: dict[str, str] = {}
                    for token in body.split(","):
                        token = token.strip()
                        if not token:
                            continue
                        k, v = token.split(":", 1)
                        parts[k.strip().lower()] = v.strip()
                    return cls(
                        label_capacity=float(parts["cap"]),
                        antenna_delay=int(parts["anndelay"]),
                        kalman_enable=bool(int(parts["kalman_enable"])),
                        kalman_q=float(parts["kalman_q"]),
                        kalman_r=float(parts["kalman_r"]),
                        a=float(parts["para_a"]),
                        b=float(parts["para_b"]),
                        pos_enable=bool(int(parts["pos_enable"])),
                        pos_dim=int(parts["pos_dimen"]),
                    )
        except Exception:
            pass
        return None


# ── Per-anchor distance correction ───────────────────────────────────────────


class AnchorCorrection(BaseModel):
    """Optional per-anchor slope/intercept tweak (applied on top of device calibration)."""

    a: float = 1.0
    b: float = 0.0


# ── CLI application config (uwb.toml) ────────────────────────────────────────


class AppConfig(BaseModel):
    """Top-level config read from ``uwb.toml``.

    Resolution order:  defaults  <  config-file  <  env  <  CLI-flags.
    """

    model_config = ConfigDict(extra="forbid")

    device: DeviceConfig = Field(default_factory=DeviceConfig)
    filter: FilterConfig = Field(default_factory=FilterConfig)
    corrections: Dict[str, AnchorCorrection] = Field(
        default_factory=dict,
        description='Per-anchor corrections keyed by anchor ID, e.g. corrections = {"0" = {a = 1.01, b = -5}}',
    )

    @classmethod
    def load(cls, path: str | Path | None = None) -> AppConfig:
        """Load config from a TOML file.

        If *path* is ``None`` the default lookup order is used:
        1. ``./uwb.toml``
        2. ``~/.config/uwb/config.toml``
        """
        import tomllib

        if path is not None:
            p = Path(path).expanduser().resolve()
            if not p.exists():
                raise FileNotFoundError(f"Config file not found: {p}")
            raw = tomllib.loads(p.read_text())
            return cls.model_validate(raw)

        # Default lookup
        candidates = [
            Path("uwb.toml"),
            Path.home() / ".config" / "uwb" / "config.toml",
        ]
        for c in candidates:
            if c.exists():
                raw = tomllib.loads(c.read_text())
                return cls.model_validate(raw)

        # No config file found → return defaults
        return cls()

    def save(self, path: str | Path) -> None:
        """Write config as TOML."""
        p = Path(path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        # model_dump with mode="json" gives us plain ints for enums
        data = self.model_dump(mode="json", exclude_defaults=False)
        p.write_text(tomli_w.dumps(data))
