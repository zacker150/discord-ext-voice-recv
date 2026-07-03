# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'discord.ext.voice_recv'
PACKAGE_ROOT = ROOT / 'discord' / 'ext' / 'voice_recv'


class Packet:
    def __init__(self, sequence: int, *, ssrc: int = 1):
        self.ssrc = ssrc
        self.sequence = sequence
        self.timestamp = sequence * 960
        self.decrypted_data = b'opus'
        self.extension_data = {}

    def __lt__(self, other: Packet) -> bool:
        return self.sequence < other.sequence


@pytest.fixture
def voice_recv_modules(monkeypatch):
    managed_names = {'discord', 'discord.ext', 'discord.opus'}

    def is_managed_module(module_name: str) -> bool:
        return module_name in managed_names or module_name == PACKAGE or module_name.startswith(f'{PACKAGE}.')

    for module_name in list(sys.modules):
        if is_managed_module(module_name):
            monkeypatch.delitem(sys.modules, module_name, raising=False)

    for package_name, path in (
        ('discord', ROOT / 'discord'),
        ('discord.ext', ROOT / 'discord' / 'ext'),
        (PACKAGE, PACKAGE_ROOT),
    ):
        package = types.ModuleType(package_name)
        package.__path__ = [str(path)]
        monkeypatch.setitem(sys.modules, package_name, package)

    def load_voice_recv_module(name: str):
        full_name = f'{PACKAGE}.{name}'
        module = sys.modules.get(full_name)
        if module is not None:
            return module

        spec = importlib.util.spec_from_file_location(full_name, PACKAGE_ROOT / f'{name}.py')
        assert spec is not None and spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, full_name, module)
        spec.loader.exec_module(module)
        return module

    def load_opus_module():
        discord_opus = types.ModuleType('discord.opus')

        class Decoder:
            SAMPLES_PER_FRAME = 960

            def decode(self, *args, **kwargs) -> bytes:
                return b''

        class OpusError(Exception):
            pass

        discord_opus.Decoder = Decoder
        discord_opus.OpusError = OpusError
        monkeypatch.setitem(sys.modules, 'discord.opus', discord_opus)
        return load_voice_recv_module('opus')

    yield types.SimpleNamespace(
        load_voice_recv_module=load_voice_recv_module,
        load_opus_module=load_opus_module,
    )

    for module_name in list(sys.modules):
        if is_managed_module(module_name):
            sys.modules.pop(module_name, None)


def make_gap_buffer(voice_recv_modules, start_sequence: int, next_sequence: int):
    buffer_module = voice_recv_modules.load_voice_recv_module('buffer')
    buffer = buffer_module.HeapJitterBuffer(maxsize=4, prefsize=0, prefill=0)
    buffer._threshold = 65535

    assert buffer.push(Packet(start_sequence))
    assert buffer.pop(timeout=0).sequence == start_sequence
    assert buffer.push(Packet(next_sequence))
    assert buffer.pop(timeout=0) is None

    return buffer


def make_decoder(voice_recv_modules, buffer, *, max_conceal_frames: int = 25):
    opus_module = voice_recv_modules.load_opus_module()
    decoder = object.__new__(opus_module.PacketDecoder)
    decoder.ssrc = 1
    decoder._buffer = buffer
    decoder.max_conceal_frames = max_conceal_frames
    decoder._last_seq = buffer._last_tx_seq
    decoder._last_ts = buffer._last_tx_seq * 960
    decoder._stats_inc = lambda *args, **kwargs: None
    return decoder


def test_large_gap_resyncs_to_next_packet_without_synthetic_frames(voice_recv_modules):
    buffer = make_gap_buffer(voice_recv_modules, 10, 60011)
    decoder = make_decoder(voice_recv_modules, buffer)

    assert buffer.gap() == 60000
    assert decoder._get_next_packet(0) is None
    assert buffer.gap() == 0
    assert buffer.pop(timeout=0).sequence == 60011


def test_small_gap_still_emits_synthetic_concealment_packet(voice_recv_modules):
    buffer = make_gap_buffer(voice_recv_modules, 10, 13)
    decoder = make_decoder(voice_recv_modules, buffer)

    packet = decoder._get_next_packet(0)

    assert packet is not None
    assert not packet
    assert packet.sequence == 11
    assert buffer.gap() == 1


def test_heap_jitter_buffer_resync_bounds_manual_concealment_loop(voice_recv_modules):
    buffer = make_gap_buffer(voice_recv_modules, 10, 60011)
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
