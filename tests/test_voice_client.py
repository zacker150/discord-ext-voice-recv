# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import discord
import pytest

from discord.ext.voice_recv.sinks import AudioSink
from discord.ext.voice_recv.voice_client import DAVE_AND_MLS_OPCODES, VoiceRecvClient


class DummySink(AudioSink):
    def wants_opus(self) -> bool:
        return True

    def write(self, user, data) -> None:
        pass

    def cleanup(self) -> None:
        pass


def make_voice_client() -> VoiceRecvClient:
    vc = object.__new__(VoiceRecvClient)
    vc._reader = None
    vc._ssrc_to_id = {}
    vc._id_to_ssrc = {}
    vc._ssrc_media_kind = {}
    vc._user_stream_ssrcs = {}
    vc._event_listeners = {}
    vc._voice_ws_recent_ops = []
    vc._voice_ws_last_payloads = {}
    vc._voice_ws_pending_events = []
    vc._dave_ws_recent_ops = []
    vc._dave_ws_last_payloads = {}
    vc._player = None
    vc.client = MagicMock()
    vc.client.dispatch = MagicMock()
    vc.client.loop = MagicMock()
    vc.channel = SimpleNamespace(id=123, guild=MagicMock())
    vc.is_connected = MagicMock(return_value=True)
    return vc


def test_add_ssrc_tracks_audio_mapping_and_updates_reader():
    vc = make_voice_client()
    vc._reader = SimpleNamespace(packet_router=MagicMock(), flush_pending_unknown_for_ssrc=MagicMock())

    vc._add_ssrc(user_id=10, ssrc=123, kind='audio')

    assert vc._ssrc_to_id == {123: 10}
    assert vc._id_to_ssrc == {10: 123}
    assert vc._ssrc_media_kind == {123: 'audio'}
    vc._reader.packet_router.set_user_id.assert_called_once_with(123, 10)
    vc._reader.flush_pending_unknown_for_ssrc.assert_called_once_with(123)


def test_add_ssrc_ignores_zero_and_tracks_non_audio_without_id_reverse_map():
    vc = make_voice_client()

    vc._add_ssrc(user_id=10, ssrc=0, kind='audio')
    vc._add_ssrc(user_id=10, ssrc=456, kind='video')

    assert vc._ssrc_to_id == {456: 10}
    assert vc._id_to_ssrc == {}
    assert vc._ssrc_media_kind == {456: 'video'}


def test_update_video_ssrcs_tracks_current_streams_and_removes_stale_entries():
    vc = make_voice_client()
    vc._ssrc_to_id = {999: 10}
    vc._ssrc_media_kind = {999: 'video'}
    vc._user_stream_ssrcs = {10: {999}}
    streams = SimpleNamespace(
        audio_ssrc=100,
        video_ssrc=200,
        streams=[
            SimpleNamespace(ssrc=201, type='screen', rtx_ssrc=202),
            SimpleNamespace(ssrc=203, type='unknown-kind', rtx_ssrc=None),
        ],
    )

    vc._update_video_ssrcs(10, streams)

    assert vc._id_to_ssrc[10] == 100
    assert vc._ssrc_to_id == {100: 10, 200: 10, 201: 10, 202: 10, 203: 10}
    assert vc._ssrc_media_kind == {
        100: 'audio',
        200: 'video',
        201: 'screen',
        202: 'rtx',
        203: 'video',
    }
    assert vc._user_stream_ssrcs[10] == {200, 201, 202, 203}


def test_remove_ssrc_clears_audio_and_stream_mappings_and_drops_speaking_state():
    vc = make_voice_client()
    vc._id_to_ssrc = {10: 100}
    vc._ssrc_to_id = {100: 10, 200: 10}
    vc._ssrc_media_kind = {100: 'audio', 200: 'video'}
    vc._user_stream_ssrcs = {10: {200}}
    vc._reader = SimpleNamespace(speaking_timer=MagicMock())

    vc._remove_ssrc(user_id=10)

    assert vc._id_to_ssrc == {}
    assert vc._ssrc_to_id == {}
    assert vc._ssrc_media_kind == {}
    assert vc._user_stream_ssrcs == {}
    vc._reader.speaking_timer.drop_ssrc.assert_called_once_with(100)


def test_get_ssrc_helpers_and_media_kind_default():
    vc = make_voice_client()
    vc._id_to_ssrc = {10: 100}
    vc._ssrc_to_id = {100: 10}
    vc._ssrc_media_kind = {100: 'audio'}

    assert vc._get_ssrc_from_id(10) == 100
    assert vc._get_id_from_ssrc(100) == 10
    assert vc._get_ssrc_media_kind(100) == 'audio'
    assert vc._get_ssrc_media_kind(999) == 'unknown'


def test_record_voice_ws_event_stores_recent_ops_dave_ops_and_pending_events():
    vc = make_voice_client()
    op = next(iter(DAVE_AND_MLS_OPCODES))
    event = {'transport': 'json', 'op': op, 'd': {'epoch': 1}}

    vc._record_voice_ws_event(event)

    assert vc._voice_ws_recent_ops == [op]
    assert vc._voice_ws_last_payloads[op] == {'epoch': 1}
    assert vc._dave_ws_recent_ops == [op]
    assert vc._dave_ws_last_payloads[op] == {'epoch': 1}
    assert vc._voice_ws_pending_events == [event]


def test_record_voice_ws_event_forwards_to_reader_stats_when_reader_exists():
    vc = make_voice_client()
    stats = MagicMock()
    vc._reader = SimpleNamespace(analysis_stats=stats)
    event = {'op': 1, 'd': {'ssrc': 123}}

    vc._record_voice_ws_event(event)

    stats.add_voice_ws_event.assert_called_once_with(event)
    assert vc._voice_ws_pending_events == []


def test_update_voice_ws_binary_state_records_base64_payload_and_extra_metadata():
    vc = make_voice_client()
    payload = b'\x01\x02'

    vc._update_voice_ws_binary_state(22, payload, seq=7, raw_len=9)

    event = vc._voice_ws_pending_events[0]
    assert event['transport'] == 'binary'
    assert event['op'] == 22
    assert event['d']['_binary_b64'] == base64.b64encode(payload).decode('ascii')
    assert event['extra'] == {'seq': 7, 'payload_len': 2, 'raw_len': 9}


def test_flush_voice_ws_pending_events_moves_events_to_reader_stats():
    vc = make_voice_client()
    stats = MagicMock()
    vc._reader = SimpleNamespace(analysis_stats=stats)
    events = [{'op': 1, 'd': {}}, {'op': 2, 'd': {}}]
    vc._voice_ws_pending_events = events.copy()

    vc._flush_voice_ws_pending_events()

    assert stats.add_voice_ws_event.call_count == 2
    assert vc._voice_ws_pending_events == []


def test_get_recv_diagnostics_returns_snapshot_when_available():
    vc = make_voice_client()
    vc._reader = SimpleNamespace(analysis_stats=SimpleNamespace(snapshot=MagicMock(return_value={'ok': True})))

    assert vc.get_recv_diagnostics() == {'ok': True}

    vc._reader = None
    assert vc.get_recv_diagnostics() == {}


def test_listen_validates_connection_sink_type_and_existing_reader():
    vc = make_voice_client()
    vc.is_connected.return_value = False

    with pytest.raises(discord.ClientException, match='Not connected'):
        vc.listen(DummySink())

    vc.is_connected.return_value = True
    with pytest.raises(TypeError, match='sink must be an AudioSink'):
        vc.listen(object())  # type: ignore[arg-type]

    vc._reader = SimpleNamespace(is_listening=MagicMock(return_value=True))
    with pytest.raises(discord.ClientException, match='Already receiving'):
        vc.listen(DummySink())


def test_listen_starts_audio_reader_and_flushes_pending_ws_events():
    vc = make_voice_client()
    sink = DummySink()
    reader = MagicMock()
    vc._voice_ws_pending_events = [{'op': 1, 'd': {}}]

    with patch('discord.ext.voice_recv.voice_client.AudioReader', return_value=reader) as reader_cls:
        vc.listen(sink, after='after', debug_ws_path=' path.jsonl ')

    reader_cls.assert_called_once_with(sink, vc, after='after', ws_jsonl_path='path.jsonl')
    reader.start.assert_called_once_with()
    reader.analysis_stats.add_voice_ws_event.assert_called_once_with({'op': 1, 'd': {}})
    assert vc._voice_ws_pending_events == []


def test_sink_property_requires_active_reader_and_delegates_set_sink():
    vc = make_voice_client()

    with pytest.raises(ValueError, match='Not receiving'):
        vc.sink = DummySink()

    with pytest.raises(TypeError, match='expected AudioSink'):
        vc.sink = object()  # type: ignore[assignment]

    reader = MagicMock()
    reader.sink = 'old'
    vc._reader = reader
    sink = DummySink()

    assert vc.sink == 'old'
    vc.sink = sink

    reader.set_sink.assert_called_once_with(sink)


def test_get_speaking_uses_reader_speaking_timer_for_member_ssrc():
    vc = make_voice_client()
    vc._id_to_ssrc = {10: 100}
    vc._reader = SimpleNamespace(speaking_timer=SimpleNamespace(get_speaking=MagicMock(return_value=True)))
    member = SimpleNamespace(id=10)

    assert vc.get_speaking(member) is True
    vc._reader.speaking_timer.get_speaking.assert_called_once_with(100)
    assert vc.get_speaking(SimpleNamespace(id=999)) is None


def test_listener_registration_requires_coroutine_and_dispatch_schedules_events():
    vc = make_voice_client()

    def not_async():
        pass

    async def on_custom(value):
        return value

    with pytest.raises(TypeError, match='Listeners must be coroutines'):
        vc.add_listener(not_async)

    vc.add_listener(on_custom)
    vc._schedule_event = MagicMock()
    vc.dispatch_sink = MagicMock()

    vc.dispatch('custom', 123)

    vc._schedule_event.assert_called_once_with(on_custom, 'on_custom', 123)
    vc.dispatch_sink.assert_called_once_with('custom', 123)
    vc.client.dispatch.assert_called_once_with('custom', 123)

    vc.remove_listener(on_custom)
    assert vc._event_listeners['on_custom'] == []
