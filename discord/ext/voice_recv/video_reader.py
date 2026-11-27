"""Bounded VP8 RTP frame assembly before DAVE frame decryption (RFC 7741)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class VideoPacket:
    """A decrypted encoded frame. No pixel decoding is performed."""

    user_id: int
    ssrc: int
    timestamp: int
    codec: str
    data: bytes
    media_kind: str


def vp8_fragment(payload: bytes) -> tuple[bool, bytes]:
    """Remove the RTP payload descriptor, retaining the encoded VP8 header."""
    if not payload:
        raise ValueError('empty VP8 payload')
    first = bool(payload[0] & 0x10) and payload[0] & 0x0F == 0
    offset = 1
    if payload[0] & 0x80:
        flags = payload[offset]
        offset += 1
        if flags & 0x80:
            picture_id = payload[offset]
            offset += 2 if picture_id & 0x80 else 1
        if flags & 0x40:
            offset += 1
        if flags & 0x30:
            offset += 1
    if offset >= len(payload):
        raise ValueError('truncated VP8 payload descriptor')
    return first, payload[offset:]


@dataclass
class _Frame:
    timestamp: int
    started: float
    fragments: dict[int, bytes] = field(default_factory=dict)
    first: Optional[int] = None
    last: Optional[int] = None
    size: int = 0


class VideoFrameAssembler:
    """One in-progress frame per SSRC, at most 16 streams and 4 MiB per frame.

    Reordering within a frame and 16-bit sequence rollover are supported.
    Loss, timestamp replacement, expiry, and group reset discard partial frames.
    """

    def __init__(self):
        self._frames: dict[int, _Frame] = {}

    def reset(self) -> None:
        self._frames.clear()

    def push(self, packet, payload: bytes) -> Optional[bytes]:
        now = time.monotonic()
        for ssrc, frame in list(self._frames.items()):
            if now - frame.started >= 1.0:
                del self._frames[ssrc]
        try:
            first, fragment = vp8_fragment(payload)
        except (IndexError, ValueError):
            self._frames.pop(packet.ssrc, None)
            raise ValueError('invalid VP8 payload descriptor') from None
        frame = self._frames.get(packet.ssrc)
        if frame is None or frame.timestamp != packet.timestamp:
            if len(self._frames) >= 16 and packet.ssrc not in self._frames:
                del self._frames[next(iter(self._frames))]
            frame = self._frames[packet.ssrc] = _Frame(packet.timestamp, now)
        if packet.sequence in frame.fragments:
            return None
        frame.fragments[packet.sequence] = fragment
        frame.size += len(fragment)
        if frame.size > 4 * 1024 * 1024 or len(frame.fragments) > 4096:
            del self._frames[packet.ssrc]
            raise ValueError('video frame limit exceeded')
        if first:
            frame.first = packet.sequence
        if packet.marker:
            frame.last = packet.sequence
        if frame.first is None or frame.last is None:
            return None
        count = ((frame.last - frame.first) & 0xFFFF) + 1
        if count > 4096:
            del self._frames[packet.ssrc]
            raise ValueError('video sequence span exceeds limit')
        sequence = [(frame.first + i) & 0xFFFF for i in range(count)]
        if any(seq not in frame.fragments for seq in sequence):
            return None
        result = b''.join(frame.fragments[seq] for seq in sequence)
        del self._frames[packet.ssrc]
        return result
