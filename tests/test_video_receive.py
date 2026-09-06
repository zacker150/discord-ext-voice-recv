import queue
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import davey
import pytest

from discord.ext.voice_recv.reader import AudioReader, ReceiveAnalysisStats
from discord.ext.voice_recv.video_reader import VideoFrameAssembler, vp8_fragment
from test_dave_bridge import bridge_state


def packet(seq=1, *, timestamp=10, marker=False, ssrc=42):
    return SimpleNamespace(sequence=seq, timestamp=timestamp, marker=marker, ssrc=ssrc, payload=103)


def test_vp8_reassembles_reordered_fragments_across_rollover():
    frames = VideoFrameAssembler()
    assert frames.push(packet(0, marker=True), b'\x00end') is None
    assert frames.push(packet(65534), b'\x10start') is None
    assert frames.push(packet(65535), b'\x00middle') == b'startmiddleend'


def test_extended_vp8_descriptor_is_removed_but_codec_header_preserved():
    assert vp8_fragment(b'\x90\xf0\x80\x01\x02\x03encoded') == (True, b'encoded')


@pytest.mark.parametrize('payload', [b'', b'\x80', b'\x80\x80', b'\x90\xf0\x80'])
def test_truncated_descriptor_is_rejected(payload):
    with pytest.raises(ValueError):
        VideoFrameAssembler().push(packet(), payload)


def test_partial_frame_drops_on_reset_expiry_or_new_timestamp():
    for boundary in ('reset', 'expiry', 'timestamp'):
        frames = VideoFrameAssembler()
        with patch('discord.ext.voice_recv.video_reader.time.monotonic', return_value=1):
            frames.push(packet(), b'\x10start')
        if boundary == 'reset':
            frames.reset()
        with patch('discord.ext.voice_recv.video_reader.time.monotonic', return_value=3 if boundary == 'expiry' else 1):
            assert frames.push(packet(2, timestamp=11 if boundary == 'timestamp' else 10, marker=True), b'\x00end') is None


def test_frame_size_and_stream_count_are_bounded():
    frames = VideoFrameAssembler()
    for ssrc in range(20):
        frames.push(packet(ssrc=ssrc), b'\x10start')
    assert len(frames._frames) == 16
    with pytest.raises(ValueError, match='limit'):
        frames.push(packet(ssrc=99), b'\x10' + bytes(4 * 1024 * 1024 + 1))
    assert 99 not in frames._frames


def test_bridge_uses_video_media_type_under_shared_lock(bridge_state):
    bridge, state = bridge_state
    assert bridge.decrypt_video(42, b'frame\xfa\xfa') == (b'opus', 'ok')
    assert state.dave_session.calls == [(42, davey.MediaType.video, b'frame\xfa\xfa')]
    assert bridge.decrypt_video(42, b'plain') == (None, 'plaintext_rejected')
    state.dave_protocol_version = 0
    assert bridge.decrypt_video(42, b'plain') == (b'plain', 'ok')


def make_video_reader():
    reader = object.__new__(AudioReader)
    bridge = MagicMock()
    bridge.lock = threading.RLock()
    bridge.snapshot.return_value.generation = 1
    bridge.decrypt_video.return_value = (b'encoded VP8', 'ok')
    reader.voice_client = SimpleNamespace(_dave_bridge=bridge, video_payload_types={103: 'vp8'},
                                         _get_id_from_ssrc=lambda ssrc: 99)
    reader._video_frames = VideoFrameAssembler()
    reader._video_generation = None
    reader.analysis_stats = ReceiveAnalysisStats()
    reader.decryptor = MagicMock()
    reader.event_router = MagicMock()
    reader.event_router._buffer = queue.SimpleQueue()
    return reader, bridge


def test_video_only_decrypts_complete_frames_and_dispatches_without_session_lock():
    reader, bridge = make_video_reader()
    reader.decryptor.decrypt_rtp_transport.return_value = b'\x10first'
    reader._receive_video(packet(), 'screen')
    bridge.decrypt_video.assert_not_called()
    reader.decryptor.decrypt_rtp_transport.return_value = b'\x00last\xfa\xfa'
    def dispatch(event, frame):
        assert not bridge.lock._is_owned()
        assert (event, frame.user_id, frame.data, frame.media_kind) == ('video_packet', 99, b'encoded VP8', 'screen')
    reader.event_router.dispatch.side_effect = dispatch
    reader._receive_video(packet(2, marker=True), 'screen')
    bridge.decrypt_video.assert_called_once_with(99, b'firstlast\xfa\xfa')


def test_new_group_cannot_complete_old_video_frame():
    reader, bridge = make_video_reader()
    reader.decryptor.decrypt_rtp_transport.return_value = b'\x10first'
    reader._receive_video(packet(), 'video')
    bridge.snapshot.return_value.generation = 2
    reader.decryptor.decrypt_rtp_transport.return_value = b'\x00last\xfa\xfa'
    reader._receive_video(packet(2, marker=True), 'video')
    bridge.decrypt_video.assert_not_called()
