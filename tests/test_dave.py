# -*- coding: utf-8 -*-

from __future__ import annotations

import pytest

from discord.ext.voice_recv.dave import DaveSupplemental, _read_uleb128, parse_dave_payload


def uleb128(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def dave_payload(*, ciphertext: bytes = b'cipher', nonce: int = 1, ranges: tuple[tuple[int, int], ...] = ()) -> bytes:
    supplemental_body = b'\x00' * 8 + uleb128(nonce)
    for offset, size in ranges:
        supplemental_body += uleb128(offset) + uleb128(size)

    supplemental_size = len(supplemental_body) + 3
    return ciphertext + supplemental_body + bytes([supplemental_size]) + b'\xfa\xfa'


def test_read_uleb128_decodes_single_and_multi_byte_values():
    assert _read_uleb128(b'\x00', 0, 1) == (0, 1)
    assert _read_uleb128(uleb128(300) + b'tail', 0, 3) == (300, 2)
    assert _read_uleb128(b'xx' + uleb128(624485) + b'yy', 2, 8) == (624485, 5)


@pytest.mark.parametrize(
    'buf, start, end',
    [
        (b'', 0, 0),
        (b'\x80', 0, 1),
        (b'\x80' * 10, 0, 10),
    ],
    ids=['empty', 'unterminated', 'too_wide'],
)
def test_read_uleb128_rejects_incomplete_or_too_large_values(buf, start, end):
    with pytest.raises(ValueError, match='invalid_uleb128'):
        _read_uleb128(buf, start, end)


def test_parse_dave_payload_returns_supplemental_metadata_with_ranges():
    payload = dave_payload(
        ciphertext=b'cipher',
        nonce=300,
        ranges=((1, 2), (130, 500)),
    )

    parsed = parse_dave_payload(payload)

    assert parsed == DaveSupplemental(
        supplemental_size=19,
        supplemental_start=6,
        nonce=300,
        ranges=((1, 2), (130, 500)),
        ciphertext_len=6,
    )
    assert parsed.ranges_count == 2


def test_parse_dave_payload_accepts_payload_with_no_ranges():
    payload = dave_payload(ciphertext=b'audio', nonce=7)

    parsed = parse_dave_payload(payload)

    assert parsed is not None
    assert parsed.supplemental_size == 12
    assert parsed.supplemental_start == len(b'audio')
    assert parsed.nonce == 7
    assert parsed.ranges == ()
    assert parsed.ranges_count == 0
    assert parsed.ciphertext_len == len(b'audio')


def test_parse_dave_payload_rejects_supplemental_size_11_without_nonce():
    payload = b'cipher' + b'\x00' * 8 + bytes([11]) + b'\xfa\xfa'

    assert parse_dave_payload(payload) is None


def test_parse_dave_payload_accepts_widest_nine_byte_uleb128_nonce():
    nonce = (1 << 63) - 1
    payload = dave_payload(ciphertext=b'audio', nonce=nonce)

    parsed = parse_dave_payload(payload)

    assert parsed is not None
    assert parsed.supplemental_size == 20
    assert parsed.nonce == nonce
    assert parsed.ranges == ()


@pytest.mark.parametrize(
    'payload',
    [
        b'',
        b'not-dave',
        b'\x00' * 10 + b'\xfa\xfa',
        b'cipher' + b'\x00' * 8 + b'\x01' + b'\x09' + b'\xfa\xfa',
        b'\x00' * 12 + bytes([50]) + b'\xfa\xfa',
    ],
    ids=[
        'empty',
        'missing_marker',
        'supplemental_size_zero_rejected',
        'supplemental_size_below_minimum',
        'supplemental_size_exceeds_payload',
    ],
)
def test_parse_dave_payload_rejects_invalid_framing(payload):
    assert parse_dave_payload(payload) is None


def test_parse_dave_payload_rejects_payload_without_ciphertext():
    payload = dave_payload(ciphertext=b'', nonce=1)

    assert parse_dave_payload(payload) is None


def test_parse_dave_payload_rejects_unterminated_nonce():
    supplemental_body = b'\x00' * 8 + b'\x80'
    supplemental_size = len(supplemental_body) + 3
    payload = b'cipher' + supplemental_body + bytes([supplemental_size]) + b'\xfa\xfa'

    assert parse_dave_payload(payload) is None


def test_parse_dave_payload_rejects_range_without_size():
    supplemental_body = b'\x00' * 8 + uleb128(1) + uleb128(99)
    supplemental_size = len(supplemental_body) + 3
    payload = b'cipher' + supplemental_body + bytes([supplemental_size]) + b'\xfa\xfa'

    assert parse_dave_payload(payload) is None


def test_parse_dave_payload_rejects_unterminated_range_value():
    supplemental_body = b'\x00' * 8 + uleb128(1) + b'\x80'
    supplemental_size = len(supplemental_body) + 3
    payload = b'cipher' + supplemental_body + bytes([supplemental_size]) + b'\xfa\xfa'

    assert parse_dave_payload(payload) is None
