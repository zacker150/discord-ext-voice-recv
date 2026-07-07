# -*- coding: utf-8 -*-

from __future__ import annotations

import threading
from collections import defaultdict, deque
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from nacl.exceptions import CryptoError

from discord.ext.voice_recv import rtp
from discord.ext.voice_recv.reader import AudioReader, PendingUnknownPacket


class Stats:
    def __init__(self):
        self.counters = defaultdict(int)
        self.non_audio = []

    def inc(self, key: str, value: int = 1) -> None:
        self.counters[key] += value

    def add_non_audio_rtp_packet(self, **kwargs) -> None:
        self.non_audio.append(kwargs)


class Packet:
    def __init__(self, ssrc: int, *, silence: bool = False, payload: int = 120):
        self.ssrc = ssrc
        self.sequence = 10
        self.timestamp = 9600
        self.payload = payload
        self.extended = False
        self.data = b'payload'
        self.decrypted_data = None
        self._silence = silence

    def is_silence(self) -> bool:
        return self._silence


def make_reader(*, known_ssrcs: dict[int, int] | None = None, media_kind='audio') -> AudioReader:
    reader = object.__new__(AudioReader)
    reader.analysis_stats = Stats()
    reader._pending_unknown_lock = threading.RLock()
    reader._pending_unknown_packets = defaultdict(deque)
    reader._pending_unknown_max_age_sec = 1.0
    reader._pending_unknown_max_per_ssrc = 2
    reader._unknown_ssrc_notice = set()
    reader._unknown_ssrc_drop_count = {}
    reader._unknown_ssrc_last_info_at = {}
    reader._unknown_ssrc_last_info_count = {}
    reader._unknown_ssrc_info_every_packets = 100
    reader._unknown_ssrc_info_every_sec = 60.0
    reader._unexpected_rtcp_count = {}
    reader._unexpected_rtcp_last_info_at = {}
    reader._unexpected_rtcp_last_info_count = {}
    reader._unexpected_rtcp_info_every_packets = 100
    reader._unexpected_rtcp_info_every_sec = 60.0
    reader.packet_router = MagicMock()
    reader.speaking_timer = MagicMock()
    reader.decryptor = MagicMock()
    reader.error = None
    reader.stop = MagicMock()

    voice_client = MagicMock()
    voice_client._ssrc_to_id = known_ssrcs or {}
    voice_client._get_ssrc_media_kind.side_effect = lambda ssrc: media_kind(ssrc) if callable(media_kind) else media_kind
    voice_client._get_id_from_ssrc.side_effect = lambda ssrc: voice_client._ssrc_to_id.get(ssrc)
    voice_client.secret_key = b'secret'
    reader.voice_client = voice_client

    return reader


def receiver_report_packet() -> rtp.ReceiverReportPacket:
    return rtp.ReceiverReportPacket(b'\x80\xc9\x00\x00' + (123).to_bytes(4, 'big'))


def test_pending_unknown_packets_queue_overflows_and_expires():
    reader = make_reader()
    first = Packet(1)
    second = Packet(1)
    third = Packet(1)

    with patch('discord.ext.voice_recv.reader.time.monotonic', side_effect=[100.0, 100.1, 100.2]):
        reader._queue_pending_unknown_packet(first)
        reader._queue_pending_unknown_packet(second)
        reader._queue_pending_unknown_packet(third)

    assert [item.packet for item in reader._pending_unknown_packets[1]] == [second, third]
    assert reader.analysis_stats.counters['unknown_ssrc_queued'] == 3
    assert reader.analysis_stats.counters['unknown_ssrc_overflow'] == 1

    with patch('discord.ext.voice_recv.reader.time.monotonic', return_value=102.0):
        assert reader._flush_pending_unknown_for_ssrc(1) == []

    assert 1 not in reader._pending_unknown_packets
    assert reader.analysis_stats.counters['unknown_ssrc_expired'] == 2


def test_flush_pending_unknown_routes_only_audio_packets():
    reader = make_reader(media_kind=lambda ssrc: 'audio' if ssrc == 1 else 'video')
    audio = Packet(1)
    video = Packet(2)

    with reader._pending_unknown_lock:
        reader._pending_unknown_packets[1].append(PendingUnknownPacket(packet=audio, queued_at=100.0))
        reader._pending_unknown_packets[1].append(PendingUnknownPacket(packet=video, queued_at=100.0))

    with patch('discord.ext.voice_recv.reader.time.monotonic', return_value=100.1):
        reader.flush_pending_unknown_for_ssrc(1)

    reader.speaking_timer.notify.assert_called_once_with(1)
    reader.packet_router.feed_rtp.assert_called_once_with(audio)
    assert reader.analysis_stats.counters['unknown_ssrc_flushed'] == 1
    assert reader.analysis_stats.counters['unknown_ssrc_flushed_non_audio'] == 1


def test_route_rtp_known_ssrc_notifies_and_feeds_router():
    reader = make_reader(known_ssrcs={1: 10})
    pkt = Packet(1)

    reader._route_rtp_packet(pkt)

    reader.speaking_timer.notify.assert_called_once_with(1)
    reader.packet_router.feed_rtp.assert_called_once_with(pkt)


def test_route_rtp_unknown_silence_packet_is_dropped_without_queueing():
    reader = make_reader(known_ssrcs={}, media_kind='unknown')
    pkt = Packet(1, silence=True)

    reader._route_rtp_packet(pkt)

    assert reader.analysis_stats.counters['rtp_unknown_ssrc_dropped'] == 1
    assert reader.analysis_stats.counters['rtp_unknown_ssrc_silence_dropped'] == 1
    assert reader._pending_unknown_packets == {}
    reader.packet_router.feed_rtp.assert_not_called()


def test_route_rtp_unknown_audio_packet_is_queued_for_later_resolution():
    reader = make_reader(known_ssrcs={}, media_kind='unknown')
    pkt = Packet(1)

    reader._route_rtp_packet(pkt)

    assert reader.analysis_stats.counters['rtp_unknown_ssrc_dropped'] == 1
    assert reader.analysis_stats.counters['unknown_ssrc_queued'] == 1
    assert reader._pending_unknown_packets[1][0].packet is pkt
    reader.packet_router.feed_rtp.assert_not_called()


def test_route_rtp_known_packet_flushes_pending_unknown_audio_first():
    media_kinds = {1: 'unknown'}
    reader = make_reader(known_ssrcs={}, media_kind=lambda ssrc: media_kinds[ssrc])
    queued = Packet(1)
    current = Packet(1)

    reader._route_rtp_packet(queued)
    media_kinds[1] = 'audio'
    reader.voice_client._ssrc_to_id[1] = 10
    reader._route_rtp_packet(current)

    assert reader.analysis_stats.counters['unknown_ssrc_flushed'] == 1
    assert reader.speaking_timer.notify.call_args_list[0].args == (1,)
    assert reader.speaking_timer.notify.call_args_list[1].args == (1,)
    assert reader.packet_router.feed_rtp.call_args_list[0].args == (queued,)
    assert reader.packet_router.feed_rtp.call_args_list[1].args == (current,)


def test_callback_records_and_drops_non_audio_rtp_before_decrypt():
    reader = make_reader(known_ssrcs={1: 10}, media_kind='video')
    pkt = Packet(1, payload=99)

    with patch('discord.ext.voice_recv.reader.rtp.is_rtcp', return_value=False), patch(
        'discord.ext.voice_recv.reader.rtp.decode_rtp', return_value=pkt
    ):
        reader.callback(b'packet')

    reader.decryptor.decrypt_rtp.assert_not_called()
    reader.packet_router.feed_rtp.assert_not_called()
    assert reader.analysis_stats.counters['rtp_media_packets_total'] == 1
    assert reader.analysis_stats.counters['rtp_media_video_packets'] == 1
    assert reader.analysis_stats.non_audio == [
        {
            'kind': 'video',
            'ssrc': 1,
            'seq': 10,
            'ts': 9600,
            'payload_type': 99,
            'packet_len': 6,
            'known_user': True,
            'extended': False,
        }
    ]


def test_callback_routes_rtcp_packet_after_decrypt():
    reader = make_reader()
    packet = receiver_report_packet()
    assert packet.type == 201

    with patch('discord.ext.voice_recv.reader.rtp.is_rtcp', return_value=True), patch(
        'discord.ext.voice_recv.reader.rtp.decode_rtcp', return_value=packet
    ):
        reader.decryptor.decrypt_rtcp.return_value = b'plain'
        reader.callback(b'cipher')

    reader.decryptor.decrypt_rtcp.assert_called_once_with(b'cipher')
    reader.packet_router.feed_rtcp.assert_called_once_with(packet)
    assert reader.analysis_stats.counters['rtcp_packets_total'] == 1
    assert reader.analysis_stats.counters['rtcp_type_201'] == 1


def test_callback_logs_unexpected_rtcp_packet_before_dispatch():
    reader = make_reader()
    packet = rtp.APPPacket(b'\x80\xcc\x00\x00' + (123).to_bytes(4, 'big') + b'TEST')

    with patch('discord.ext.voice_recv.reader.rtp.is_rtcp', return_value=True), patch(
        'discord.ext.voice_recv.reader.rtp.decode_rtcp', return_value=packet
    ):
        reader.decryptor.decrypt_rtcp.return_value = b'plain'
        reader.callback(b'cipher')

    assert reader._unexpected_rtcp_count[(204, 'APPPacket')] == 1
    reader.packet_router.feed_rtcp.assert_called_once_with(packet)


def test_callback_routes_recovered_rtp_packets_before_current_packet():
    reader = make_reader(known_ssrcs={1: 10}, media_kind='audio')
    recovered = Packet(1)
    current = Packet(1)
    reader._route_rtp_packet = MagicMock()
    reader.decryptor.decrypt_rtp.return_value = b'opus'
    reader.decryptor.pop_recovered_rtp_packets.return_value = [recovered]
    reader.decryptor.is_deferred_packet.return_value = False

    with patch('discord.ext.voice_recv.reader.rtp.is_rtcp', return_value=False), patch(
        'discord.ext.voice_recv.reader.rtp.decode_rtp', return_value=current
    ):
        reader.callback(b'packet')

    assert current.decrypted_data == b'opus'
    assert reader._route_rtp_packet.call_args_list[0].args == (recovered,)
    assert reader._route_rtp_packet.call_args_list[1].args == (current,)


def test_callback_skips_current_deferred_dave_packet_after_recovered_packets():
    reader = make_reader(known_ssrcs={1: 10}, media_kind='audio')
    recovered = Packet(1)
    current = Packet(1)
    reader._route_rtp_packet = MagicMock()
    reader.decryptor.decrypt_rtp.return_value = b'opus'
    reader.decryptor.pop_recovered_rtp_packets.return_value = [recovered]
    reader.decryptor.is_deferred_packet.return_value = True

    with patch('discord.ext.voice_recv.reader.rtp.is_rtcp', return_value=False), patch(
        'discord.ext.voice_recv.reader.rtp.decode_rtp', return_value=current
    ):
        reader.callback(b'packet')

    reader._route_rtp_packet.assert_called_once_with(recovered)
    assert reader.analysis_stats.counters['dave_inner_defer_current_skipped'] == 1


def test_callback_ignores_ip_discovery_decode_errors():
    reader = make_reader()
    data = bytes([0, 0x02]) + b'\x00' * 72

    with patch('discord.ext.voice_recv.reader.rtp.is_rtcp', return_value=False), patch(
        'discord.ext.voice_recv.reader.rtp.decode_rtp', side_effect=ValueError('bad packet')
    ):
        reader.callback(data)

    reader.stop.assert_not_called()
    reader.packet_router.feed_rtp.assert_not_called()


def test_callback_swallows_crypto_errors_without_stopping():
    reader = make_reader(known_ssrcs={1: 10}, media_kind='audio')
    pkt = Packet(1)
    reader.decryptor.decrypt_rtp.side_effect = CryptoError('bad decrypt')

    with patch('discord.ext.voice_recv.reader.rtp.is_rtcp', return_value=False), patch(
        'discord.ext.voice_recv.reader.rtp.decode_rtp', return_value=pkt
    ):
        reader.callback(b'packet')

    reader.stop.assert_not_called()
    reader.packet_router.feed_rtp.assert_not_called()
