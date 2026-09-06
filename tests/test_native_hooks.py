import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from discord.gateway import DiscordVoiceWebSocket
from discord.ext.voice_recv import gateway, voice_client


def test_connection_uses_native_hooks_without_patching_websocket():
    original = DiscordVoiceWebSocket.received_binary_message
    client = object.__new__(voice_client.VoiceRecvClient)
    client.client = MagicMock()
    state = client.create_connection_state()
    assert client._dave_bridge.lock is state.dave_lock
    assert not client._dave_bridge.snapshot().ready
    assert state.hook is gateway.hook
    assert state.binary_hook is gateway.binary_hook
    assert DiscordVoiceWebSocket.received_binary_message is original


def test_unsupported_dependency_fails_before_constructing_state(monkeypatch):
    class UnsupportedState:
        def __init__(self, client, *, hook=None):
            pytest.fail('Unsupported state must not be constructed')

    monkeypatch.setattr(voice_client, 'VoiceConnectionState', UnsupportedState)
    client = object.__new__(voice_client.VoiceRecvClient)
    with pytest.raises(RuntimeError, match='zacker150/discord.py.*binary_hook'):
        client.create_connection_state()


def test_binary_hook_routes_payload_and_sequence_to_own_client():
    clients = [MagicMock(), MagicMock()]
    for index, client in enumerate(clients):
        ws = SimpleNamespace(_connection=SimpleNamespace(voice_client=client))
        asyncio.run(gateway.binary_hook(ws, 25, index, b'payload'))
    for index, client in enumerate(clients):
        client._update_voice_ws_binary_state.assert_called_once_with(
            25, b'payload', seq=index, raw_len=10
        )
