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


@pytest.mark.parametrize(
    'padding, payload, expected',
    [
        # P bit clear -> never modified, even when the trailing octet is a valid count.
        (False, b'', b''),
        (False, b'\x01\x02\x03', b'\x01\x02\x03'),
        (False, b'\xaa\xbb\x02', b'\xaa\xbb\x02'),
        # P bit set, empty payload -> nothing to strip.
        (True, b'', b''),
        # P bit set, valid count in 0 < n <= len -> strip the last n octets.
        (True, b'\xaa\xbb\x01', b'\xaa\xbb'),  # minimum count (1)
        (True, b'\xaa\xbb\xcc\x02', b'\xaa\xbb'),  # count < len
        (True, b'\x03\x03\x03', b''),  # count == len (all padding)
        (True, b'\x01', b''),  # single byte, count == len == 1
        (True, b'\xff' * 255, b''),  # max-size all-padding probe packet
        # P bit set, out-of-range count -> corrupt, leave untouched.
        (True, b'\xaa\xbb\x00', b'\xaa\xbb\x00'),  # count 0
        (True, b'\xaa\xbb\x04', b'\xaa\xbb\x04'),  # count == len + 1 (just over)
        (True, b'\xaa\x7f', b'\xaa\x7f'),  # count far over len
    ],
    ids=[
        'no_pbit_empty',
        'no_pbit_plain',
        'no_pbit_countlike_tail_ignored',
        'pbit_empty',
        'count_min_1',
        'count_lt_len',
        'count_eq_len_all_padding',
        'count_eq_len_single_byte',
        'count_eq_len_max_probe',
        'count_zero_ignored',
        'count_len_plus_1_ignored',
        'count_far_over_len_ignored',
    ],
)
def test_strip_padding_edge_cases(padding, payload, expected):
    rtp = _load_rtp()
    pkt = _packet(rtp, padding=padding)
    assert pkt.strip_padding(payload) == expected
