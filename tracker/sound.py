"""Sound effects — plays WAV files from the sound/ directory asynchronously.

Looks for ``sound/goal_*.wav`` and ``sound/whistle_*.wav`` and picks a random
file each time a sound is triggered.
"""

from __future__ import annotations

import random
import subprocess
from pathlib import Path
from threading import Thread

# Directory containing the WAV files, relative to the project root.
_SOUND_DIR = Path(__file__).resolve().parent / "sound"

_goals: list[str] = []
_whistles: list[str] = []


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


def init_sounds() -> None:
    """Scan the sound/ directory for goal and whistle WAV files."""
    global _goals, _whistles
    if not _SOUND_DIR.exists():
        return

    _goals = sorted(str(p) for p in _SOUND_DIR.glob("goal_*.wav"))
    _whistles = sorted(str(p) for p in _SOUND_DIR.glob("whistle_*.wav"))


# ---------------------------------------------------------------------------
# Playback
# ---------------------------------------------------------------------------


def _play_file(path: str) -> None:
    """Play a WAV file, best-effort (tries aplay then paplay)."""
    for player in ("aplay", "paplay"):
        try:
            subprocess.Popen(
                [player, path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except FileNotFoundError:
            continue


def _play_async(path: str) -> None:
    """Fire-and-forget playback in a daemon thread."""
    t = Thread(target=_play_file, args=(path,), daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def play_whistle() -> None:
    """Play a random whistle WAV from sound/whistle_*.wav."""
    if _whistles:
        _play_async(random.choice(_whistles))


def play_cheer() -> None:
    """Play a random goal celebration WAV from sound/goal_*.wav."""
    if _goals:
        _play_async(random.choice(_goals))
