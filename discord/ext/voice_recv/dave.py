# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Optional, TYPE_CHECKING

import davey

if TYPE_CHECKING:
    from discord.voice_state import VoiceConnectionState

__all__ = (
    'DaveSupplemental',
    'parse_dave_payload',
)

_DAVE_MARKER = b'\xfa\xfa'


@dataclass(frozen=True)
class DaveState:
    """An immutable observation of the fork's session under its shared lock."""

    protocol_version: int
    epoch: Optional[int]
    status: Optional[davey.SessionStatus]
    pending_transition_ids: frozenset[int]
    # Time this bridge observed an epoch change or session replacement.
    last_epoch_change: Optional[float]
    ready: bool
    downgrade_allowed: bool = False
    epoch_prepared_at: Optional[float] = None


class DaveBridge:
    """Own extension-side session access; never decrypt through a cached session.

    The connection owns the session and may replace it during recovery. Both
    metadata reads and audio decryption use its lock, shared with MLS updates.
    State is refreshed on demand; lifecycle notifications are handled separately.
    """

    def __init__(self, connection: VoiceConnectionState):
        self._connection = connection
        self.lock = connection.dave_lock
        self._epoch_prepared_at: Optional[float] = None
        self._session: Optional[davey.DaveSession] = None
        self._state = DaveState(0, None, None, frozenset(), None, False)

    def _refresh_locked(self) -> DaveState:
        session = self._connection.dave_session
        version = self._connection.dave_protocol_version
        epoch = session.epoch if session is not None else None
        changed_at = self._state.last_epoch_change
        if session is not self._session or epoch != self._state.epoch:
            changed_at = time.monotonic()
        self._session = session
        self._state = DaveState(
            protocol_version=version,
            epoch=epoch,
            status=session.status if session is not None else None,
            pending_transition_ids=frozenset(self._connection.dave_pending_transitions),
            last_epoch_change=changed_at,
            ready=version > 0 and session is not None and session.ready,
            downgrade_allowed=self._connection.dave_downgraded or 0 in self._connection.dave_pending_transitions.values(),
            epoch_prepared_at=self._epoch_prepared_at,
        )
        return self._state

    def epoch_prepared(self, epoch: int) -> None:
        if epoch == 1:
            with self.lock:
                self._epoch_prepared_at = time.monotonic()

    def snapshot(self) -> DaveState:
        with self.lock:
            return self._refresh_locked()

    def decrypt_audio(self, user_id: int, payload: bytes) -> tuple[Optional[bytes], str]:
        try:
            with self.lock:
                state = self._refresh_locked()
                if not state.ready:
                    return None, 'session_not_ready'
                if not state.downgrade_allowed and not payload.endswith(b'\xfa\xfa'):
                    return None, 'plaintext_rejected'
                session = self._connection.dave_session
                assert session is not None
                return bytes(session.decrypt(user_id, davey.MediaType.audio, payload)), 'ok'
        except RuntimeError:
            return None, 'busy'
        except ValueError as exc:
            return None, 'no_decryptor' if 'NoDecryptorForUser' in str(exc) else 'decrypt_error'


@dataclass(frozen=True)
class DaveSupplemental:
    supplemental_size: int
    supplemental_start: int
    nonce: int
    ranges: tuple[tuple[int, int], ...]
    ciphertext_len: int

    @property
    def ranges_count(self) -> int:
        return len(self.ranges)


def parse_dave_payload(payload: bytes) -> Optional[DaveSupplemental]:
    if payload[-2:] != _DAVE_MARKER:
        return None
    if len(payload) <= 10:
        return None

    supplemental_size = payload[-3]
    if supplemental_size > len(payload) or supplemental_size <= 10:
        return None

    supplemental_start = len(payload) - supplemental_size
    nonce_start = supplemental_start + 8
    supplemental_end = len(payload) - 3
    if nonce_start > supplemental_end:
        return None

    try:
        nonce, cursor = _read_uleb128(payload, nonce_start, supplemental_end)
    except ValueError:
        return None

    ranges: list[tuple[int, int]] = []
    while cursor < supplemental_end:
        try:
            offset, cursor = _read_uleb128(payload, cursor, supplemental_end)
            size, cursor = _read_uleb128(payload, cursor, supplemental_end)
        except ValueError:
            return None
        ranges.append((offset, size))

    ciphertext_len = len(payload) - supplemental_size
    if ciphertext_len <= 0:
        return None

    return DaveSupplemental(
        supplemental_size=supplemental_size,
        supplemental_start=supplemental_start,
        nonce=nonce,
        ranges=tuple(ranges),
        ciphertext_len=ciphertext_len,
    )

def _read_uleb128(buf: bytes, start: int, end: int) -> tuple[int, int]:
    shift = 0
    value = 0
    index = start

    while index < end and shift <= 63:
        byte = buf[index]
        index += 1
        value |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            return value, index
        shift += 7

    raise ValueError("invalid_uleb128")
