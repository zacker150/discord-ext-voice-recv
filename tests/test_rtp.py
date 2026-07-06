# -*- coding: utf-8 -*-

from __future__ import annotations

import struct

import pytest

from discord.ext.voice_recv import rtp
from discord.ext.voice_recv.rtp import (
    APPPacket,
    BYEPacket,
    FakePacket,
    RTPPacket,
    ReceiverReportPacket,
    SDESPacket,
    SenderReportPacket,
    SilencePacket,
)


def rtp_header(
    *,
    first: int = 0x80,
    second: int = 0x78,
    sequence: int = 0x1234,
    timestamp: int = 0x01020304,
    ssrc: int = 0xAABBCCDD,
) -> bytes:
    return bytes([first, second]) + struct.pack('>HII', sequence, timestamp, ssrc)


def rtcp_header(*, count: int, packet_type: int, length: int = 0, padding: bool = False) -> bytes:
    first = 0x80 | count
    if padding:
        first |= 0x20
    return bytes([first, packet_type]) + struct.pack('>H', length)


def report_block(
    *,
    ssrc: int = 0x11111111,
    fraction_lost: int = 7,
    cumulative_lost: int = 0x010203,
    last_seq: int = 0x22222222,
    jitter: int = 0x33333333,
    lsr: int = 0x44444444,
    dlsr: int = 0x55555555,
) -> bytes:
    return (
        struct.pack('>IB', ssrc, fraction_lost)
        + cumulative_lost.to_bytes(3, 'big')
        + struct.pack('>4I', last_seq, jitter, lsr, dlsr)
    )


def test_decode_rejects_non_rtp_version():
    with pytest.raises(ValueError, match='Invalid packet header'):
        rtp.decode(b'\x40\x78' + b'\x00' * 10)


def test_decode_selects_rtp_or_rtcp_packet_type():
    audio = rtp_header(second=0x78) + b'opus'
    receiver_report = rtcp_header(count=0, packet_type=201) + struct.pack('>I', 0x12345678)

    assert isinstance(rtp.decode(audio), RTPPacket)
    assert isinstance(rtp.decode(receiver_report), ReceiverReportPacket)
    assert rtp.is_rtcp(receiver_report) is True
    assert rtp.is_rtcp(audio) is False


def test_decode_unknown_rtcp_like_type_falls_back_to_rtp_packet():
    data = rtp_header(second=205) + b'payload'

    packet = rtp.decode(data)

    assert isinstance(packet, RTPPacket)
    assert packet.payload == 77
    assert rtp.is_rtcp(data) is False


def test_rtp_packet_parses_header_payload_and_csrcs():
    first = 0x80 | 0x20 | 0x10 | 0x02
    second = 0x80 | 0x78
    csrcs = struct.pack('>2I', 0x10101010, 0x20202020)
    packet = RTPPacket(rtp_header(first=first, second=second) + csrcs + b'payload')

    assert packet.version == 2
    assert packet.padding is True
    assert packet.extended is True
    assert packet.cc == 2
    assert packet.marker is True
    assert packet.payload == 0x78
    assert packet.sequence == 0x1234
    assert packet.timestamp == 0x01020304
    assert packet.ssrc == 0xAABBCCDD
    assert packet.header == rtp_header(first=first, second=second)
    assert packet.csrcs == (0x10101010, 0x20202020)
    assert packet.data == b'payload'
    assert packet.decrypted_data is None
    assert packet.nonce == b''


def test_packet_comparison_and_silence_helpers():
    first = FakePacket(ssrc=1, sequence=10, timestamp=9600)
    second = FakePacket(ssrc=1, sequence=11, timestamp=10560)
    other_ssrc = FakePacket(ssrc=2, sequence=11, timestamp=10560)
    silence = SilencePacket(ssrc=1, timestamp=123)
    audio = RTPPacket(rtp_header(ssrc=1) + b'opus')

    audio.decrypted_data = rtp.OPUS_SILENCE

    assert first < second
    assert second > first
    assert first == FakePacket(ssrc=1, sequence=10, timestamp=9600)
    assert first != other_ssrc
    assert bool(first) is False
    assert silence.is_silence() is True
    assert audio.is_silence() is True
    with pytest.raises(TypeError, match='packet ssrc mismatch'):
        first < other_ssrc
    with pytest.raises(TypeError, match='packet ssrc mismatch'):
        first > other_ssrc


def test_update_ext_headers_noops_when_packet_is_not_extended():
    packet = RTPPacket(rtp_header(first=0x80) + b'payload')

    assert packet.update_ext_headers(b'\xbe\xde\x00\x01\x10A\x00\x00') == 0
    assert packet.extension is None
    assert packet.extension_data == {}


def test_update_ext_headers_handles_short_extension_payload():
    packet = RTPPacket(rtp_header(first=0x90) + b'payload')

    assert packet.update_ext_headers(b'\xbe\xde') == 0
    assert packet.extension.profile == b''
    assert packet.extension.length == 0
    assert packet.extension.values == ()
    assert packet.extension_data == {}


def test_update_ext_headers_parses_bede_extension_elements_and_padding():
    packet = RTPPacket(rtp_header(first=0x90) + b'payload')
    ext_words = b'\x10A\x00\x91BC\x00\x00'
    payload = b'\xbe\xde\x00\x02' + ext_words + b'opus'

    assert packet.update_ext_headers(payload) == 12
    assert packet.extension.profile == b'\xbe\xde'
    assert packet.extension.length == 2
    assert packet.extension.values == struct.unpack('>2I', ext_words)
    assert packet.extension_data == {1: b'A', 9: b'BC'}


def test_update_ext_headers_clamps_declared_length_to_available_words():
    packet = RTPPacket(rtp_header(first=0x90) + b'payload')
    ext_word = b'\x10A\x00\x00'
    payload = b'\xbe\xde\x00\x04' + ext_word

    assert packet.update_ext_headers(payload) == 8
    assert packet.extension.length == 1
    assert packet.extension.values == struct.unpack('>I', ext_word)
    assert packet.extension_data == {1: b'A'}


def test_update_ext_headers_for_rtpsize_uses_extension_header_from_rtp_header():
    packet = RTPPacket(rtp_header(first=0x90) + b'\xbe\xde\x00\x01ciphertext' + b'\x00\x00\x00\x09')
    packet.adjust_rtpsize()

    assert packet.nonce == b'\x00\x00\x00\x09'
    assert packet.header[-4:] == b'\xbe\xde\x00\x01'
    assert packet.data == b'ciphertext'
    assert packet.update_ext_headers(b'\x10A\x00\x00opus') == 4
    assert packet.extension.length == 1
    assert packet.extension_data == {1: b'A'}


def test_sender_report_packet_parses_sender_info_reports_and_extension():
    data = (
        rtcp_header(count=1, packet_type=200, length=7)
        + struct.pack('>I', 0xAABBCCDD)
        + struct.pack('>5I', 10, 0x80000000, 0x01020304, 20, 30)
        + report_block()
        + b'ext'
    )

    packet = rtp.decode_rtcp(data)

    assert isinstance(packet, SenderReportPacket)
    assert packet.report_count == 1
    assert packet.ssrc == 0xAABBCCDD
    assert packet.info.ntp_ts == 10.5
    assert packet.info.rtp_ts == 0x01020304
    assert packet.info.packet_count == 20
    assert packet.info.octet_count == 30
    assert packet.reports[0].ssrc == 0x11111111
    assert packet.reports[0].perc_loss == 7
    assert packet.reports[0].total_lost == 0x010203
    assert packet.extension == b'ext'


def test_compound_rtcp_packet_bytes_are_exposed_as_sender_report_extension():
    sender_report = (
        rtcp_header(count=0, packet_type=200)
        + struct.pack('>I', 0xAABBCCDD)
        + struct.pack('>5I', 1, 0, 2, 3, 4)
    )
    receiver_report = rtcp_header(count=0, packet_type=201) + struct.pack('>I', 0x12345678)

    packet = rtp.decode_rtcp(sender_report + receiver_report)

    assert isinstance(packet, SenderReportPacket)
    assert packet.report_count == 0
    assert packet.extension == receiver_report


def test_receiver_report_packet_parses_reports_and_extension():
    data = rtcp_header(count=1, packet_type=201) + struct.pack('>I', 0xAABBCCDD) + report_block() + b'ext'

    packet = rtp.RTCPPacket.from_data(data)

    assert isinstance(packet, ReceiverReportPacket)
    assert packet.report_count == 1
    assert packet.ssrc == 0xAABBCCDD
    assert packet.reports[0].last_seq == 0x22222222
    assert packet.reports[0].jitter == 0x33333333
    assert packet.reports[0].lsr == 0x44444444
    assert packet.reports[0].dlsr == 0x55555555
    assert packet.extension == b'ext'


def test_sdes_packet_parses_items_and_empty_chunks():
    item = bytes([1, 4]) + b'test'
    end = b'\x00\x00'
    first_chunk = struct.pack('>I', 0x11111111) + item + end
    second_chunk = struct.pack('>I', 0x22222222) + b'\x00\x00\x00\x00'
    data = rtcp_header(count=2, packet_type=202) + first_chunk + second_chunk

    packet = rtp.decode_rtcp(data)

    assert isinstance(packet, SDESPacket)
    assert packet.source_count == 2
    assert packet.chunks[0].ssrc == 0x11111111
    assert packet.chunks[0].items[0].type == 1
    assert packet.chunks[0].items[0].length == 4
    assert packet.chunks[0].items[0].text == 'test'
    assert packet.chunks[0].items[1].type == 0
    assert packet.chunks[1].ssrc == 0x22222222
    assert packet.chunks[1].items == ()


def test_sdes_packet_skips_chunk_padding_before_next_chunk():
    item = bytes([1, 1]) + b'a'
    end = b'\x00\x00'
    first_chunk = struct.pack('>I', 0x11111111) + item + end + b'\x00\x00\x00'
    second_chunk = struct.pack('>I', 0x22222222) + b'\x00\x00\x00\x00'
    data = rtcp_header(count=2, packet_type=202) + first_chunk + second_chunk

    packet = rtp.decode_rtcp(data)

    assert isinstance(packet, SDESPacket)
    assert packet.chunks[0].ssrc == 0x11111111
    assert packet.chunks[0].items[0].text == 'a'
    assert packet.chunks[1].ssrc == 0x22222222
    assert packet.chunks[1].items == ()


def test_bye_packet_parses_sources_and_reason():
    data = (
        rtcp_header(count=2, packet_type=203)
        + struct.pack('>2I', 0x11111111, 0x22222222)
        + bytes([3])
        + b'bye'
    )

    packet = rtp.decode_rtcp(data)

    assert isinstance(packet, BYEPacket)
    assert packet.source_count == 2
    assert packet.ssrcs == (0x11111111, 0x22222222)
    assert packet.reason == 'bye'


def test_bye_packet_without_reason_leaves_reason_none():
    data = rtcp_header(count=1, packet_type=203) + struct.pack('>I', 0x11111111)

    packet = rtp.decode_rtcp(data)

    assert isinstance(packet, BYEPacket)
    assert packet.ssrcs == (0x11111111,)
    assert packet.reason is None


def test_bye_packet_ignores_reason_padding_bytes():
    data = rtcp_header(count=1, packet_type=203) + struct.pack('>I', 0x11111111) + bytes([3]) + b'bye' + b'\x00'

    packet = rtp.decode_rtcp(data)

    assert isinstance(packet, BYEPacket)
    assert packet.reason == 'bye'


def test_bye_packet_raises_for_non_utf8_reason():
    data = rtcp_header(count=1, packet_type=203) + struct.pack('>I', 0x11111111) + bytes([1]) + b'\xff'

    with pytest.raises(UnicodeDecodeError):
        rtp.decode_rtcp(data)


def test_app_packet_parses_subtype_name_and_data():
    data = rtcp_header(count=17, packet_type=204, padding=True) + struct.pack('>I4s', 0x11111111, b'TEST') + b'data'

    packet = rtp.decode_rtcp(data)

    assert isinstance(packet, APPPacket)
    assert packet.subtype == 17
    assert packet.padding is True
    assert packet.ssrc == 0x11111111
    assert packet.name == 'TEST'
    assert packet.data == b'data'
