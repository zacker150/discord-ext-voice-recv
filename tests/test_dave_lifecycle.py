import threading
from unittest.mock import patch
from types import SimpleNamespace
from unittest.mock import MagicMock

from discord.ext.voice_recv.dave import DaveBridge
from discord.ext.voice_recv.voice_client import VoiceRecvClient
from discord.ext.voice_recv.reader import AudioReader
from test_dave_retry import decryptor, packet


def client_state():
    client = object.__new__(VoiceRecvClient)
    state = SimpleNamespace(dave_lock=threading.RLock(), dave_session=None,
                            dave_protocol_version=0, dave_pending_transitions={},
                            dave_downgraded=False, dave_session_generation=0)
    client._dave_bridge = DaveBridge(state)
    client._dave_event_state = client._dave_bridge.snapshot()
    client._reader = MagicMock()
    client.client = MagicMock()
    client._event_listeners = {}
    return client, state


def test_state_edges_dispatch_to_client_and_sink_once():
    client, state = client_state()
    state.dave_protocol_version = 1
    state.dave_session = SimpleNamespace(epoch=1, ready=True, status=None)
    client._dave_state_changed('binary_op_29')
    client._dave_state_changed('duplicate')
    expected = [('voice_dave_protocol_version', 1), ('voice_dave_epoch_changed', 1), ('voice_dave_ready', True)]
    assert [c.args for c in client.client.dispatch.call_args_list] == expected
    assert [c.args for c in client._reader.event_router.dispatch.call_args_list] == expected
    client._reader.sync_dave_session.assert_not_called()
    state.dave_protocol_version = 0
    state.dave_downgraded = True
    client.on_dave_transition_executed(7, 0)
    assert ('voice_dave_downgraded',) in [c.args for c in client.client.dispatch.call_args_list]
    assert client.client.dispatch.call_args.args == ('voice_dave_execute_transition', 7, 0)


def test_epoch_preparation_grace_survives_in_place_generation_refresh():
    client, state = client_state()
    state.dave_session_generation += 1
    client.on_dave_epoch_prepared(1, 1)
    assert client._dave_bridge.snapshot().epoch_prepared_at is not None
    assert client.client.dispatch.call_args.args == ('voice_dave_prepare_epoch', 1, 1)
    state.dave_session_generation += 1
    assert client._dave_bridge.snapshot().epoch_prepared_at is None


def test_new_group_discards_ciphertext_even_when_epoch_number_is_unchanged(decryptor):
    bridge = decryptor._voice_client._dave_bridge
    bridge.snapshot.return_value.generation = 1
    bridge.decrypt_audio.return_value = (None, 'busy')
    old = packet()
    decryptor.decrypt_rtp(old)
    decryptor._stats.add_dave_nonce(42, 1, 100)
    bridge.snapshot.return_value.generation = 2
    bridge.decrypt_audio.reset_mock()
    assert decryptor.pop_recovered_rtp_packets() == []
    bridge.decrypt_audio.assert_not_called()
    assert old.extension_data['_voice_recv_dropped']
    assert not decryptor._stats._dave_nonce_last
    assert decryptor._stats._counters['dave_inner_defer_drop_session_reset'] == 1


def test_ordinary_epoch_change_preserves_retry_queue(decryptor):
    bridge = decryptor._voice_client._dave_bridge
    bridge.snapshot.return_value.generation = 1
    bridge.decrypt_audio.return_value = (None, 'busy')
    old = packet()
    decryptor.decrypt_rtp(old)
    bridge.snapshot.return_value.last_epoch_change = 2
    bridge.decrypt_audio.return_value = (b'opus', 'ok')
    assert decryptor.pop_recovered_rtp_packets() == [old]


def test_receive_callback_does_not_hold_session_lock_while_routing(decryptor):
    bridge = decryptor._voice_client._dave_bridge
    bridge.lock = threading.RLock()
    reader = object.__new__(AudioReader)
    reader.voice_client = decryptor._voice_client
    reader._receive_lock = threading.RLock()

    def callback(data):
        decryptor.decrypt_rtp(packet())
        acquired = []
        def sink_thread():
            held = bridge.lock.acquire(timeout=0.5)
            acquired.append(held)
            if held:
                bridge.lock.release()
        thread = threading.Thread(target=sink_thread)
        thread.start()
        thread.join(1)
        assert acquired == [True]

    reader._callback = callback
    reader.callback(b'packet')


def test_cleanup_emits_reset_after_last_voice_state_update():
    client, state = client_state()
    state.dave_protocol_version = 1
    state.dave_session = SimpleNamespace(epoch=1, ready=True, status=None)
    client._dave_state_changed('last_voice_state_update')
    client.client.dispatch.reset_mock()
    state.dave_session = None
    state.dave_protocol_version = 0
    state.dave_session_generation += 1
    client.stop = MagicMock()
    with patch('discord.VoiceClient.cleanup'):
        client.cleanup()
    assert ('voice_dave_ready', False) in [call.args for call in client.client.dispatch.call_args_list]


def test_sink_stop_does_not_wait_for_a_receiver_blocked_on_sink():
    client, _ = client_state()
    receiver_lock = threading.Lock()
    def sync():
        with receiver_lock:
            pass
    client._reader.sync_dave_session.side_effect = sync
    client.stop_playing = MagicMock()
    client.stop_listening = MagicMock()
    stopped = threading.Event()
    def sink():
        client.stop()
        stopped.set()
    with receiver_lock:
        thread = threading.Thread(target=sink)
        thread.start()
        completed = stopped.wait(0.5)
    thread.join(1)
    assert completed, 'sink stop waited for the receiver while receiver waited for the sink'
