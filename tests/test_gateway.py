import asyncio
import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from discord.gateway import DiscordVoiceWebSocket
from discord.ext.voice_recv import gateway
from discord.ext.voice_recv.voice_client import VoiceRecvClient


@pytest.fixture
def connection():
    client = object.__new__(VoiceRecvClient)
    client._reader = None
    for attr in ('_ssrc_to_id', '_id_to_ssrc', '_ssrc_media_kind',
                 '_user_stream_ssrcs', '_event_listeners',
                 '_voice_ws_last_payloads', '_dave_ws_last_payloads'):
        setattr(client, attr, {})
    for attr in ('_voice_ws_recent_ops', '_voice_ws_pending_events', '_dave_ws_recent_ops'):
        setattr(client, attr, [])
    client.client = MagicMock()
    client.channel = SimpleNamespace(guild=MagicMock())
    client.guild.me.id = 99
    client.guild.get_member.side_effect = lambda uid: SimpleNamespace(id=uid)
    ws = object.__new__(DiscordVoiceWebSocket)
    ws._connection = SimpleNamespace(voice_client=client, dave_session=None)
    ws._binary_hook = gateway.binary_hook
    ws.secret_key = list(range(32))
    ws.seq_ack = -1
    return client, ws


def deliver(ws, op, data, **extra):
    asyncio.run(gateway.hook(ws, {'op': op, 'd': data, **extra}))


def test_ready_and_speaking_establish_audio_ownership(connection):
    client, ws = connection
    deliver(ws, 2, {'ssrc': 100})
    deliver(ws, 5, {'user_id': '42', 'ssrc': 200, 'speaking': 1})
    assert client._ssrc_to_id == {100: 99, 200: 42}
    assert client._id_to_ssrc == {99: 100, 42: 200}
    event, member, ssrc, speaking = client.client.dispatch.call_args.args
    assert (event, member.id, ssrc, speaking.value) == ('voice_member_speaking_state', 42, 200, 1)


def test_member_list_and_video_opcodes_remain_distinct(connection):
    client, ws = connection
    deliver(ws, 11, {'user_ids': ['42', '43']})
    assert [(c.args[0], c.args[1].id) for c in client.client.dispatch.call_args_list] == [
        ('voice_member_connect', 42), ('voice_member_connect', 43)]
    assert client._ssrc_to_id == {}
    deliver(ws, 12, {'user_id': '42', 'audio_ssrc': 100, 'video_ssrc': 200, 'streams': []})
    assert client._ssrc_to_id == {100: 42, 200: 42}
    assert client._id_to_ssrc == {42: 100}
    assert client._ssrc_media_kind == {100: 'audio', 200: 'video'}
    assert client.client.dispatch.call_args.args[0] == 'voice_member_video'


@pytest.mark.parametrize('listening', [False, True])
@pytest.mark.parametrize('known', [False, True])
def test_disconnect_cleans_mappings_and_only_destroys_known_decoder(connection, listening, known):
    client, ws = connection
    if known:
        deliver(ws, 12, {'user_id': '42', 'audio_ssrc': 100, 'video_ssrc': 200, 'streams': []})
    reader = MagicMock()
    client._reader = reader if listening else None
    deliver(ws, 13, {'user_id': '42'})
    assert client._ssrc_to_id == {}
    assert client._id_to_ssrc == {}
    assert client._ssrc_media_kind == {}
    if listening and known:
        reader.packet_router.destroy_decoder.assert_called_once_with(100)
    else:
        reader.packet_router.destroy_decoder.assert_not_called()
    event, member, ssrc = client.client.dispatch.call_args.args
    assert (event, member.id, ssrc) == ('voice_member_disconnect', 42, 100 if known else None)


@pytest.mark.parametrize('listening', [False, True])
def test_session_description_updates_active_reader_key(connection, listening):
    client, ws = connection
    reader = MagicMock()
    client._reader = reader if listening else None
    deliver(ws, 4, {})
    if listening:
        reader.update_secret_key.assert_called_once_with(bytes(range(32)))
    else:
        reader.update_secret_key.assert_not_called()


@pytest.mark.parametrize('op', [21, 22, 24])
@pytest.mark.parametrize('listening', [False, True])
def test_only_execute_transition_resets_reader_nonces(connection, op, listening):
    client, ws = connection
    reader = MagicMock()
    client._reader = reader if listening else None
    payload = {'transition_id': 7}
    deliver(ws, op, payload)
    if listening and op == 22:
        reader.analysis_stats.reset_all_dave_nonces.assert_called_once_with()
    else:
        reader.analysis_stats.reset_all_dave_nonces.assert_not_called()
    client.client.dispatch.assert_called_once_with('voice_dave_opcode', op, payload)


def test_unknown_opcode_retains_diagnostics_without_dispatch(connection):
    client, ws = connection
    deliver(ws, 255, {'future': True}, seq=9)
    event = client._voice_ws_pending_events[-1]
    assert event['d'] == {'future': True}
    assert event['extra'] == {'seq': 9}
    client.client.dispatch.assert_not_called()


@pytest.mark.parametrize('handler_fails', [False, True])
def test_native_binary_boundary_records_diagnostics_after_mls_processing(connection, handler_fails):
    client, ws = connection
    ws._connection.dave_session = object()
    client._dave_state_changed = MagicMock()

    async def handle(op, frame):
        assert not client._voice_ws_pending_events
        assert (op, frame) == (27, b'\x00\x07\x1bpayload')
        if handler_fails:
            raise ValueError('invalid MLS proposal')

    ws._handle_dave_binary = handle
    asyncio.run(ws.received_binary_message(b'\x00\x07\x1bpayload'))
    event = client._voice_ws_pending_events[-1]
    assert event['transport'] == 'binary'
    assert event['op'] == 27
    assert base64.b64decode(event['d']['_binary_b64']) == b'payload'
    assert event['extra'] == {'seq': 7, 'payload_len': 7, 'raw_len': 10}
    assert ws.seq_ack == 7
    client._dave_state_changed.assert_called_once_with('binary_op_27')


@pytest.mark.parametrize('frame', [b'', b'\x00', b'\x00\x07'])
def test_truncated_binary_frames_do_not_create_diagnostics(connection, frame):
    client, ws = connection
    ws._handle_dave_binary = AsyncMock()
    asyncio.run(ws.received_binary_message(frame))
    assert not client._voice_ws_pending_events
    assert ws.seq_ack == -1
    ws._handle_dave_binary.assert_not_called()
