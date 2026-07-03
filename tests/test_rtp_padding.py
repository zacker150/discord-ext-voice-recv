# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RTP_PATH = ROOT / 'discord' / 'ext' / 'voice_recv' / 'rtp.py'


def _load_rtp():
    # rtp.py only depends on the stdlib, so it can be loaded in isolation without
    # importing the whole (nacl/davey-heavy) package.
    spec = importlib.util.spec_from_file_location('voice_recv_rtp_under_test', RTP_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _packet(rtp, *, padding: bool):
    flags = 0x80  # RTP version 2
    if padding:
        flags |= 0x20  # padding (P) bit
    header = bytes([flags, 0x78, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01])
    return rtp.RTPPacket(header + b'\x00')


def test_padding_bit_parsed_from_header():
    rtp = _load_rtp()
    assert _packet(rtp, padding=True).padding is True
    assert _packet(rtp, padding=False).padding is False


def test_strip_padding_restores_dave_marker():
    # Captured live: a DAVE frame decrypts to "...0d fa fa" followed by RTP
    # padding (last octet = pad count). Without stripping, the 0xFAFA marker is
    # hidden and the ciphertext is fed to libopus -> "corrupted stream".
    rtp = _load_rtp()
    pkt = _packet(rtp, padding=True)
    payload = bytes.fromhex('a1b2c3') + b'\x0d\xfa\xfa' + b'\x04\x04\x04\x04'
    stripped = pkt.strip_padding(payload)
    assert stripped == bytes.fromhex('a1b2c3') + b'\x0d\xfa\xfa'
    assert stripped.endswith(b'\xfa\xfa')


def test_strip_padding_empties_all_padding_probe_packet():
    # All-0xff, len 255, last octet 0xff == 255 == full length: a bandwidth-probe
    # packet carrying no media. It should collapse to empty, not reach the decoder.
    rtp = _load_rtp()
    pkt = _packet(rtp, padding=True)
    assert pkt.strip_padding(b'\xff' * 255) == b''


def test_no_padding_bit_leaves_payload_untouched():
    rtp = _load_rtp()
    pkt = _packet(rtp, padding=False)
    payload = b'\x0d\xfa\xfa\x04\x04\x04\x04'
    assert pkt.strip_padding(payload) == payload


@pytest.mark.parametrize(
    'payload',
    [
        b'',  # empty payload
        b'\xfa\xfa\x00',  # pad count 0 -> nothing to strip
        b'\xfa\xfa\x10',  # pad count 16 > len -> corrupt count, leave untouched
    ],
)
def test_strip_padding_guards_bad_counts(payload):
    rtp = _load_rtp()
    pkt = _packet(rtp, padding=True)
    assert pkt.strip_padding(payload) == payload
