import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import davey
import pytest

from discord.ext.voice_recv.dave import DaveBridge
from discord.ext.voice_recv.reader import PacketDecryptor


class CheckedSession:
    def __init__(self, lock):
        self.lock = lock
        self.current_epoch = 1
        self.is_ready = True
        self.error = None
        self.calls = []

    def check_lock(self):
        assert self.lock._is_owned(), 'Session accessed without the connection lock'

    @property
    def epoch(self):
        self.check_lock()
        return self.current_epoch

    @property
    def status(self):
        self.check_lock()
        return davey.SessionStatus.inactive

    @property
    def ready(self):
        self.check_lock()
        return self.is_ready

    def decrypt(self, user_id, media_type, payload):
        self.check_lock()
        self.calls.append((user_id, media_type, payload))
        if self.error:
            raise self.error
        return b'opus'


@pytest.fixture
def bridge_state():
    lock = threading.RLock()
    state = SimpleNamespace(dave_lock=lock, dave_session=CheckedSession(lock),
                            dave_protocol_version=1, dave_pending_transitions={})
    return DaveBridge(state), state


def test_decrypt_holds_shared_lock_for_metadata_and_audio(bridge_state):
    bridge, state = bridge_state
    assert bridge.lock is state.dave_lock
    assert bridge.decrypt_audio(42, b'cipher') == (b'opus', 'ok')
    assert state.dave_session.calls == [(42, davey.MediaType.audio, b'cipher')]


@pytest.mark.parametrize('condition', ['missing', 'not_ready', 'version_zero'])
def test_unavailable_session_never_attempts_decryption(bridge_state, condition):
    bridge, state = bridge_state
    session = state.dave_session
    if condition == 'missing':
        state.dave_session = None
    elif condition == 'not_ready':
        session.is_ready = False
    else:
        state.dave_protocol_version = 0
    assert bridge.decrypt_audio(42, b'cipher') == (None, 'session_not_ready')
    assert not session.calls
    assert not bridge.snapshot().ready


@pytest.mark.parametrize('error, reason', [
    (ValueError('Failed to decrypt: NoDecryptorForUser'), 'no_decryptor'),
    (ValueError('invalid authentication tag'), 'decrypt_error'),
    (RuntimeError('Already borrowed'), 'busy'),
])
def test_error_classification_and_lock_release(bridge_state, error, reason):
    bridge, state = bridge_state
    state.dave_session.error = error
    assert bridge.decrypt_audio(42, b'cipher') == (None, reason)
    assert not state.dave_lock._is_owned()
    assert PacketDecryptor._is_retryable_inner_reason(reason)
    state.dave_session.error = None
    assert bridge.decrypt_audio(42, b'cipher') == (b'opus', 'ok')


def test_unexpected_programming_error_is_not_reported_as_retryable(bridge_state):
    bridge, state = bridge_state
    state.dave_session.error = TypeError('bad API usage')
    with pytest.raises(TypeError):
        bridge.decrypt_audio(42, b'cipher')
    assert not state.dave_lock._is_owned()


def test_snapshot_tracks_epoch_session_replacement_and_disconnect(bridge_state):
    bridge, state = bridge_state
    with patch('discord.ext.voice_recv.dave.time.monotonic', side_effect=[10, 20, 30, 40]):
        first = bridge.snapshot()
        assert first.last_epoch_change == 10
        state.dave_pending_transitions[7] = 0
        pending = bridge.snapshot()
        assert pending.pending_transition_ids == frozenset({7})
        assert not first.pending_transition_ids
        assert pending.last_epoch_change == 10
        state.dave_session.current_epoch = 2
        assert bridge.snapshot().last_epoch_change == 20
        old = state.dave_session
        state.dave_session = CheckedSession(state.dave_lock)
        state.dave_session.current_epoch = 2
        assert bridge.snapshot().last_epoch_change == 30
        assert bridge.decrypt_audio(42, b'cipher') == (b'opus', 'ok')
        assert not old.calls
        state.dave_session = None
        state.dave_protocol_version = 0
        state.dave_pending_transitions.clear()
        final = bridge.snapshot()
        assert (final.epoch, final.status, final.ready, final.protocol_version) == (None, None, False, 0)
        assert final.last_epoch_change == 40


def test_waiting_decrypt_uses_replacement_session(bridge_state):
    bridge, state = bridge_state
    entered = threading.Event()
    def decrypt():
        entered.set()
        return bridge.decrypt_audio(42, b'cipher')
    with ThreadPoolExecutor(max_workers=1) as pool:
        with state.dave_lock:
            old = state.dave_session
            future = pool.submit(decrypt)
            assert entered.wait(2)
            assert not future.done()
            state.dave_session = CheckedSession(state.dave_lock)
        assert future.result(timeout=2) == (b'opus', 'ok')
        assert not old.calls
        assert len(state.dave_session.calls) == 1


def test_real_davey_missing_decryptor_error_contract():
    session = davey.DaveSession(1, 1, 2)
    with pytest.raises(ValueError, match='NoDecryptorForUser'):
        session.decrypt(3, davey.MediaType.audio, b'cipher')


@pytest.mark.parametrize('reason', ['ok', 'no_decryptor', 'busy', 'session_not_ready', 'decrypt_error'])
def test_packet_decryptor_uses_bridge_and_preserves_retry_flags(reason):
    bridge = MagicMock()
    bridge.decrypt_audio.return_value = (b'opus' if reason == 'ok' else None, reason)
    client = SimpleNamespace(_dave_bridge=bridge, _get_id_from_ssrc=lambda ssrc: 42)
    decryptor = PacketDecryptor('aead_xchacha20_poly1305_rtpsize', bytes(32), voice_client=client)
    packet = SimpleNamespace(ssrc=7, sequence=1, timestamp=960, extension_data={
        '_voice_recv_needs_dave_inner_decrypt': True,
        '_voice_recv_pending_inner_decrypt': True,
    })
    result = decryptor._try_dave_inner_decrypt(packet, b'cipher')
    assert result == bridge.decrypt_audio.return_value
    bridge.decrypt_audio.assert_called_once_with(42, b'cipher')
    assert packet.extension_data['_voice_recv_needs_dave_inner_decrypt'] == (reason != 'ok')
    assert packet.extension_data['_voice_recv_pending_inner_decrypt'] == (reason != 'ok')
