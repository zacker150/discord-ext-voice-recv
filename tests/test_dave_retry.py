import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from discord.ext.voice_recv.reader import AudioReader, PacketDecryptor, ReceiveAnalysisStats


@pytest.fixture
def decryptor():
    state = SimpleNamespace(protocol_version=1, ready=True, downgrade_allowed=False,
                            last_epoch_change=1.0, epoch_prepared_at=None)
    bridge = MagicMock()
    bridge.snapshot.return_value = state
    bridge.decrypt_audio.return_value = (b'opus', 'ok')
    client = SimpleNamespace(_dave_bridge=bridge, _get_id_from_ssrc=lambda ssrc: ssrc)
    decryptor = PacketDecryptor('aead_xchacha20_poly1305_rtpsize', bytes(32),
                               voice_client=client, stats=ReceiveAnalysisStats())
    decryptor._decrypt_rtp_transport_aead_xchacha20_poly1305_rtpsize = lambda p: p.data
    return decryptor


def packet(seq=1, ssrc=42, payload=b'not-parseable\xfa\xfa'):
    return SimpleNamespace(ssrc=ssrc, sequence=seq, timestamp=seq * 960,
                           data=payload, decrypted_data=None, extension_data={})


def test_parser_failure_does_not_gate_encrypted_audio(decryptor):
    p = packet()
    assert decryptor.decrypt_rtp(p) == b'opus'
    decryptor._voice_client._dave_bridge.decrypt_audio.assert_called_once_with(42, p.data)
    assert decryptor._stats._counters['dave_parse_fail'] == 1


def test_ready_encrypted_session_rejects_unmarked_plaintext(decryptor):
    p = packet(payload=b'plain opus')
    assert decryptor.decrypt_rtp(p) == b''
    assert p.extension_data['_voice_recv_dropped']
    decryptor._voice_client._dave_bridge.decrypt_audio.assert_not_called()
    assert decryptor._stats._counters['dave_plaintext_rejected'] == 1


@pytest.mark.parametrize('version,ready,downgrade,expect_bridge', [
    (0, False, False, False), (1, False, False, True), (1, True, True, True),
])
def test_plaintext_policy_preserves_version_zero_and_transition_paths(decryptor, version, ready, downgrade, expect_bridge):
    bridge = decryptor._voice_client._dave_bridge
    state = bridge.snapshot.return_value
    state.protocol_version, state.ready, state.downgrade_allowed = version, ready, downgrade
    p = packet(payload=b'plain opus')
    assert decryptor.decrypt_rtp(p) == (b'opus' if expect_bridge else b'plain opus')
    assert bridge.decrypt_audio.called == expect_bridge
    assert not p.extension_data.get('_voice_recv_dropped')


def test_retry_is_age_bounded_not_attempt_bounded(decryptor):
    bridge = decryptor._voice_client._dave_bridge
    bridge.decrypt_audio.return_value = (None, 'busy')
    with patch('discord.ext.voice_recv.reader.time.monotonic', return_value=100):
        decryptor.decrypt_rtp(packet())
        for _ in range(40):
            assert decryptor.pop_recovered_rtp_packets() == []
    assert len(decryptor._pending_inner_packets[42]) == 1
    with patch('discord.ext.voice_recv.reader.time.monotonic', return_value=110):
        assert decryptor.pop_recovered_rtp_packets() == []
    assert not decryptor._pending_inner_packets
    assert decryptor._stats._counters['dave_inner_defer_drop_expired'] == 1


@pytest.mark.parametrize('prepared,queued,expected_age', [(100, 104.9, 15), (100, 105, 10), (None, 104, 10)])
def test_initial_epoch_grace_is_captured_per_packet(decryptor, prepared, queued, expected_age):
    bridge = decryptor._voice_client._dave_bridge
    bridge.snapshot.return_value.epoch_prepared_at = prepared
    bridge.decrypt_audio.return_value = (None, 'session_not_ready')
    with patch('discord.ext.voice_recv.reader.time.monotonic', return_value=queued):
        decryptor.decrypt_rtp(packet())
    assert decryptor._pending_inner_packets[42][0].max_age == expected_age
    with patch('discord.ext.voice_recv.reader.time.monotonic', return_value=queued + expected_age - .1):
        assert not decryptor.pop_recovered_rtp_packets()
    assert decryptor._pending_inner_packets
    with patch('discord.ext.voice_recv.reader.time.monotonic', return_value=queued + expected_age):
        assert not decryptor.pop_recovered_rtp_packets()
    assert not decryptor._pending_inner_packets


def test_recovery_preserves_sequence_order_across_wrap_and_arrival_reordering(decryptor):
    bridge = decryptor._voice_client._dave_bridge
    bridge.decrypt_audio.return_value = (None, 'no_decryptor')
    packets = [packet(seq) for seq in (65535, 1, 0)]
    for p in packets:
        decryptor.decrypt_rtp(p)
    bridge.decrypt_audio.return_value = (b'opus', 'ok')
    recovered = decryptor.pop_recovered_rtp_packets()
    assert [p.sequence for p in recovered] == [65535, 0, 1]
    assert all(p.decrypted_data == b'opus' for p in recovered)
    assert all(not decryptor.is_deferred_packet(p) for p in recovered)
    assert not decryptor.pop_recovered_rtp_packets()


def test_blocked_speaker_does_not_block_other_ssrc(decryptor):
    bridge = decryptor._voice_client._dave_bridge
    bridge.decrypt_audio.return_value = (None, 'no_decryptor')
    for seq, ssrc in [(1,42), (2,42), (1,43)]:
        decryptor.decrypt_rtp(packet(seq,ssrc))
    bridge.decrypt_audio.side_effect = lambda uid, data: (None,'busy') if uid==42 else (b'opus','ok')
    assert [p.ssrc for p in decryptor.pop_recovered_rtp_packets()] == [43]
    assert len(decryptor._pending_inner_packets[42]) == 2


def test_queue_cap_drops_oldest_and_counts_overflow(decryptor):
    decryptor._voice_client._dave_bridge.decrypt_audio.return_value = (None,'busy')
    first = packet(0)
    decryptor.decrypt_rtp(first)
    for seq in range(1,1025):
        decryptor.decrypt_rtp(packet(seq))
    assert len(decryptor._pending_inner_packets[42]) == 1024
    assert first.extension_data['_voice_recv_dropped']
    assert decryptor._stats._counters['dave_inner_defer_drop_overflow'] == 1


def test_queued_unmarked_packet_is_rechecked_when_session_becomes_ready(decryptor):
    bridge=decryptor._voice_client._dave_bridge
    bridge.snapshot.return_value.ready=False
    bridge.decrypt_audio.return_value=(None,'session_not_ready')
    p=packet(payload=b'plaintext')
    decryptor.decrypt_rtp(p)
    bridge.snapshot.return_value.ready=True
    bridge.decrypt_audio.reset_mock()
    assert not decryptor.pop_recovered_rtp_packets()
    assert p.extension_data['_voice_recv_dropped']
    bridge.decrypt_audio.assert_not_called()


def test_epoch_observation_resets_nonce_history_without_discarding_queue(decryptor):
    bridge=decryptor._voice_client._dave_bridge
    bridge.decrypt_audio.return_value=(None,'busy')
    decryptor.decrypt_rtp(packet())
    decryptor._stats.add_dave_nonce(42,1,1)
    bridge.snapshot.return_value.last_epoch_change=2.0
    assert not decryptor.pop_recovered_rtp_packets()
    assert not decryptor._stats._dave_nonce_last
    assert not decryptor._stats._dave_seq_last
    assert decryptor._pending_inner_packets[42]


@pytest.mark.parametrize('wake', [False, True])
def test_silent_channel_retry_routes_recovered_audio_and_stops(decryptor, wake):
    bridge=decryptor._voice_client._dave_bridge
    bridge.decrypt_audio.return_value=(None,'busy')
    p=packet()
    decryptor.decrypt_rtp(p)
    reader=object.__new__(AudioReader)
    reader.voice_client=decryptor._voice_client
    reader.decryptor=decryptor
    reader._receive_lock=threading.RLock()
    reader._retry_wake=threading.Event()
    reader._retry_stop=threading.Event()
    received=threading.Event()
    reader._route_rtp_packet=MagicMock(side_effect=lambda p: received.set())
    reader.stop=MagicMock()
    bridge.decrypt_audio.return_value=(b'opus','ok')
    thread=threading.Thread(target=reader._retry_loop)
    thread.start()
    try:
        if wake: reader.wake_dave_retry()
        assert received.wait(2)
    finally:
        reader._retry_stop.set()
        reader._retry_wake.set()
        thread.join(2)
    assert not thread.is_alive()
    reader._route_rtp_packet.assert_called_once_with(p)
    reader.stop.assert_not_called()
