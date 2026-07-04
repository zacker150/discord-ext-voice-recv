# -*- coding: utf-8 -*-

from __future__ import annotations

from unittest.mock import MagicMock

from discord.ext.voice_recv.buffer import HeapJitterBuffer
from discord.ext.voice_recv.opus import PacketDecoder


class Packet:
    def __init__(self, sequence: int, *, ssrc: int = 1):
        self.ssrc = ssrc
        self.sequence = sequence
        self.timestamp = sequence * 960
        self.decrypted_data = b'opus'
        self.extension_data = {}

    def __lt__(self, other: Packet) -> bool:
        return self.sequence < other.sequence


def make_gap_buffer(start_sequence: int, next_sequence: int) -> HeapJitterBuffer:
    buffer = HeapJitterBuffer(maxsize=4, prefsize=0, prefill=0)
    buffer._threshold = 65535

    assert buffer.push(Packet(start_sequence))
    assert buffer.pop(timeout=0).sequence == start_sequence
    assert buffer.push(Packet(next_sequence))
    assert buffer.pop(timeout=0) is None

    return buffer


def make_decoder(buffer: HeapJitterBuffer, *, max_conceal_frames: int = 25) -> PacketDecoder:
    # wants_opus=True keeps __init__ from constructing a real Decoder(); these tests
    # exercise the jitter buffer, not decoding. Stats calls land on the mock router.
    router = MagicMock()
    router.sink.wants_opus.return_value = True
    decoder = PacketDecoder(router, ssrc=1, max_conceal_frames=max_conceal_frames)
    # Point the decoder at the pre-built gap buffer and align its tx cursor with it.
    decoder._buffer = buffer
    decoder._last_seq = buffer._last_tx_seq
    decoder._last_ts = buffer._last_tx_seq * 960
    return decoder


def test_large_gap_resyncs_to_next_packet_without_synthetic_frames():
    buffer = make_gap_buffer(10, 60011)
    decoder = make_decoder(buffer)

    assert buffer.gap() == 60000
    assert decoder._get_next_packet(0) is None
    assert buffer.gap() == 0
    assert buffer.pop(timeout=0).sequence == 60011


def test_small_gap_still_emits_synthetic_concealment_packet():
    buffer = make_gap_buffer(10, 13)
    decoder = make_decoder(buffer)

    packet = decoder._get_next_packet(0)

    assert packet is not None
    assert not packet
    assert packet.sequence == 11
    assert buffer.gap() == 1


def test_heap_jitter_buffer_resync_bounds_manual_concealment_loop():
    buffer = make_gap_buffer(10, 60011)
    synthetic_count = 0
    max_conceal_frames = 25

    while True:
        packet = buffer.pop(timeout=0)
        if packet is not None:
            break

        gap = buffer.gap()
        if gap > max_conceal_frames:
            buffer.resync_to_next()
            break

        if gap <= 0:
            break

        buffer.advance()
        synthetic_count += 1

    assert synthetic_count <= max_conceal_frames
    assert synthetic_count == 0
    assert buffer.pop(timeout=0).sequence == 60011
