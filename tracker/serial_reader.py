"""Background thread: reads the UWB binary stream and pushes parsed packets to a queue."""

import queue
import struct
import threading
from collections import deque
from typing import Optional

import serial
import serial.serialutil

# Packet framing
MARKER = b"CmdM:4["
MARKER_LEN = len(MARKER)  # 7 bytes
PAYLOAD_LEN = 42  # 8 (ts) + 2 (seq) + 32 (8 × uint32 distances)

DISTANCE_NOISY_THRESHOLD_MM = 10_000


class SerialReader(threading.Thread):
    """Reads the UWB serial stream in a background daemon thread.

    Parsed packets are placed on *out_queue* as dicts:
        {'ts': int, 'seq': int, 'distances': {anchor_id: smoothed_mm}}

    Only anchors with a valid (non-zero, non-noisy) distance are included in
    the 'distances' dict.
    """

    def __init__(
        self,
        port: str,
        baud_rate: int,
        out_queue: "queue.Queue[dict]",
        sma_window: int = 5,
    ) -> None:
        super().__init__(name="SerialReader", daemon=True)
        self.port = port
        self.baud_rate = baud_rate
        self.out_queue = out_queue
        self.sma_window = sma_window

        self._stop_event = threading.Event()
        self._sma_buffers: dict[int, deque] = {}
        self.error: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Signal the run loop to exit on the next iteration."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Thread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        try:
            ser = serial.Serial(self.port, self.baud_rate, timeout=0.1)
        except serial.serialutil.SerialException as exc:
            self.error = str(exc)
            print(f"[SerialReader] Cannot open {self.port}: {exc}")
            return

        buf = b""
        try:
            while not self._stop_event.is_set():
                chunk = ser.read(256)
                if chunk:
                    buf += chunk

                # Process every complete packet that is in the buffer.
                buf = self._drain(buf)
        finally:
            ser.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _drain(self, buf: bytes) -> bytes:
        """Parse and emit all complete packets from *buf*, return leftover bytes."""
        while True:
            idx = buf.find(MARKER)

            if idx == -1:
                # No marker found — keep the tail in case the marker is split
                # across two reads (at most MARKER_LEN-1 bytes can be a prefix).
                return buf[-(MARKER_LEN - 1) :] if len(buf) >= MARKER_LEN else buf

            # Discard bytes before the marker (they're not part of a packet).
            buf = buf[idx:]

            # Check whether a full payload follows the marker.
            if len(buf) < MARKER_LEN + PAYLOAD_LEN:
                # Incomplete — wait for more data.
                return buf

            payload = buf[MARKER_LEN : MARKER_LEN + PAYLOAD_LEN]
            packet = self._parse_packet(payload)
            if packet is not None:
                self.out_queue.put(packet)

            # Advance past this packet and look for the next one.
            buf = buf[MARKER_LEN + PAYLOAD_LEN :]

    def _parse_packet(self, payload: bytes) -> Optional[dict]:
        """Unpack a 42-byte payload into a packet dict, or None on parse error."""
        if len(payload) < PAYLOAD_LEN:
            return None

        ts, seq = struct.unpack_from("<QH", payload, 0)
        raw_distances = struct.unpack_from("<8I", payload, 10)

        distances: dict[int, int] = {}
        for anchor_id, raw_mm in enumerate(raw_distances):
            if raw_mm == 0:
                continue  # anchor offline
            if raw_mm > DISTANCE_NOISY_THRESHOLD_MM:
                continue  # anchor noisy

            distances[anchor_id] = self._smooth(anchor_id, raw_mm)

        return {"ts": ts, "seq": seq, "distances": distances}

    def _smooth(self, anchor_id: int, value_mm: int) -> int:
        """Apply a simple moving average and return the smoothed value."""
        if anchor_id not in self._sma_buffers:
            self._sma_buffers[anchor_id] = deque(maxlen=self.sma_window)
        buf = self._sma_buffers[anchor_id]
        buf.append(value_mm)
        return int(sum(buf) / len(buf))
