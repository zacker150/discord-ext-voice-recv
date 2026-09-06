import json
import davey
from types import SimpleNamespace
from unittest.mock import patch

from discord.ext.voice_recv.reader import ReceiveAnalysisStats
from test_dave_bridge import bridge_state
from test_dave_lifecycle import client_state


def test_diagnostics_copy_native_stats_and_clear_on_reset(bridge_state):
    bridge, state = bridge_state
    session = state.dave_session
    def members():
        session.check_lock()
        return ['42', '9']
    native = SimpleNamespace(successes=3, failures=1, duration=20, attempts=4, passthroughs=0)
    def stats(uid, media):
        session.check_lock()
        return native if uid == 42 else None
    session.get_user_ids = members
    session.get_decryption_stats = stats
    snapshot = bridge.diagnostics({100: 42, 200: 99})
    assert bridge.member_ids() == (9, 42)
    assert snapshot['member_count'] == 2
    assert snapshot['decryption_stats']['100']['successes'] == 3
    assert '200' not in snapshot['decryption_stats']
    native.successes = 5
    assert snapshot['decryption_stats']['100']['successes'] == 3
    assert bridge.diagnostics({100: 42})['decryption_stats']['100']['successes'] == 5
    json.dumps(snapshot)
    state.dave_session = None
    state.dave_protocol_version = 0
    assert bridge.diagnostics({100: 42})['decryption_stats'] == {}
    assert bridge.member_ids() == ()


def test_stats_snapshot_includes_session_without_holding_counter_lock():
    stats = ReceiveAnalysisStats()
    def snapshot():
        assert stats._lock.acquire(blocking=False)
        stats._lock.release()
        return {'ready': True}
    stats._dave_snapshot = snapshot
    assert stats.snapshot()['dave_session'] == {'ready': True}


def test_client_verification_accepts_id_and_member():
    client, _ = client_state()
    with patch('discord.VoiceClient.get_dave_verification_code', return_value='123') as get:
        assert client.get_dave_verification_code(42) == '123'
        get.assert_called_with(42)
        assert client.get_dave_verification_code(SimpleNamespace(id=43)) == '123'
        get.assert_called_with(43)


def test_native_missing_decryptor_does_not_break_diagnostics(bridge_state):
    bridge, state = bridge_state
    state.dave_session = davey.DaveSession(1, 42, 999)
    snapshot = bridge.diagnostics({100: 99})
    assert snapshot['decryption_stats'] == {}
    json.dumps(snapshot)
