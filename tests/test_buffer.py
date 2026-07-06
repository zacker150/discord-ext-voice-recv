# -*- coding: utf-8 -*-

from __future__ import annotations

import pytest

from discord.ext.voice_recv.buffer import HeapJitterBuffer


class Packet:
    def __init__(self, sequence: int, *, ssrc: int = 1, timestamp: int | None = None):
        self.ssrc = ssrc
        self.sequence = sequence
        self.timestamp = sequence * 960 if timestamp is None else timestamp
        self.decrypted_data = b'opus'
        self.extension_data = {}

    def __lt__(self, other: Packet) -> bool:
        return self.sequence < other.sequence


def test_heap_jitter_buffer_constructor_validates_sizes():
    with pytest.raises(ValueError, match='maxsize'):
        HeapJitterBuffer(maxsize=0)

    with pytest.raises(ValueError, match='prefsize'):
        HeapJitterBuffer(maxsize=2, prefsize=-1)

    with pytest.raises(ValueError, match='prefsize'):
        HeapJitterBuffer(maxsize=2, prefsize=3)


def test_prefill_and_prefsize_delay_readiness_until_enough_packets_arrive():
    buffer = HeapJitterBuffer(maxsize=4, prefsize=1, prefill=2)

    assert buffer.push(Packet(1)) is True
    assert buffer.pop(timeout=0) is None
    assert buffer.push(Packet(2)) is True

    assert buffer.peek().sequence == 1
    assert buffer.pop(timeout=0).sequence == 1
    assert buffer.pop(timeout=0) is None


def test_overflow_drops_oldest_packets():
    buffer = HeapJitterBuffer(maxsize=2, prefsize=0, prefill=0)

    assert buffer.push(Packet(3)) is True
    assert buffer.push(Packet(1)) is True
    assert buffer.push(Packet(2)) is True

    assert [packet.sequence for packet in buffer.flush()] == [2, 3]


def test_stale_packet_rejected_after_transmit_cursor_advances():
    buffer = HeapJitterBuffer(maxsize=4, prefsize=0, prefill=0)

    assert buffer.push(Packet(10)) is True
    assert buffer.pop(timeout=0).sequence == 10

    assert buffer.push(Packet(9)) is False
    assert len(buffer) == 0


def test_sequence_wraparound_accepts_zero_after_65535():
    buffer = HeapJitterBuffer(maxsize=4, prefsize=0, prefill=0)

    assert buffer.push(Packet(65535, timestamp=1000)) is True
    assert buffer.pop(timeout=0).sequence == 65535
    assert buffer.push(Packet(0, timestamp=1960)) is True

    assert buffer.gap() == 0
    assert buffer.pop(timeout=0).sequence == 0


def test_peek_next_only_returns_sequential_packet():
    buffer = HeapJitterBuffer(maxsize=4, prefsize=0, prefill=0)

    assert buffer.push(Packet(10)) is True
    assert buffer.pop(timeout=0).sequence == 10
    assert buffer.push(Packet(12)) is True

    assert buffer.peek(all=True).sequence == 12
    assert buffer.peek_next() is None

    buffer.advance()

    assert buffer.peek_next().sequence == 12


def test_advance_noops_before_first_packet_or_with_invalid_count():
    buffer = HeapJitterBuffer(maxsize=4, prefsize=0, prefill=0)

    buffer.advance()
    assert buffer._last_tx_seq == -1

    assert buffer.push(Packet(10)) is True
    assert buffer.pop(timeout=0).sequence == 10
    buffer.advance(0)
    assert buffer._last_tx_seq == 10


def test_resync_to_next_moves_cursor_before_buffered_packet():
    buffer = HeapJitterBuffer(maxsize=4, prefsize=0, prefill=0)

    assert buffer.push(Packet(10)) is True
    assert buffer.pop(timeout=0).sequence == 10
    assert buffer.push(Packet(20)) is True
    assert buffer.pop(timeout=0) is None

    buffer.resync_to_next()

    assert buffer.gap() == 0
    assert buffer.pop(timeout=0).sequence == 20


def test_flush_returns_sorted_packets_updates_cursor_and_resets_prefill():
    buffer = HeapJitterBuffer(maxsize=4, prefsize=0, prefill=2)

    assert buffer.push(Packet(3)) is True
    assert buffer.push(Packet(1)) is True

    assert [packet.sequence for packet in buffer.flush()] == [1, 3]
    assert buffer._last_tx_seq == 3
    assert buffer._prefill == 2
    assert buffer.pop(timeout=0) is None


def test_reset_clears_packets_and_internal_counters():
    buffer = HeapJitterBuffer(maxsize=4, prefsize=0, prefill=1)

    assert buffer.push(Packet(1)) is True
    assert buffer.pop(timeout=0).sequence == 1
    assert buffer.push(Packet(2)) is True

    buffer.reset()

    assert len(buffer) == 0
    assert buffer.peek(all=True) is None
    assert buffer._last_tx_seq == -1
    assert buffer._prefill == 1
