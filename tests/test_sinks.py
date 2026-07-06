# -*- coding: utf-8 -*-

from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from discord.ext.voice_recv.opus import VoiceData
from discord.ext.voice_recv.sinks import (
    AudioSink,
    BasicSink,
    ConditionalFilter,
    FFmpegSink,
    MultiAudioSink,
    PCMVolumeTransformer,
    TimedFilter,
    UserFilter,
    VoiceRecvException,
)


class CollectingSink(AudioSink):
    def __init__(self, destination=None, *, opus: bool = False):
        super().__init__(destination)
        self.opus = opus
        self.writes = []
        self.cleaned = False

    def wants_opus(self) -> bool:
        return self.opus

    def write(self, user, data) -> None:
        self.writes.append((user, data))

    def cleanup(self) -> None:
        self.cleaned = True


class ParentSink(CollectingSink):
    pass


class ConcreteMultiAudioSink(MultiAudioSink):
    def wants_opus(self) -> bool:
        return False

    def write(self, user, data) -> None:
        for child in self.children:
            child.write(user, data)

    def cleanup(self) -> None:
        pass


def voice_data(*, pcm: bytes = b'\x01\x00\x02\x00', opus: bytes = b'opus') -> VoiceData:
    packet = SimpleNamespace(decrypted_data=opus)
    return VoiceData(packet, source=None, pcm=pcm)


def test_audio_sink_registers_child_and_walks_depth_first():
    leaf = CollectingSink()
    middle = ParentSink(leaf)
    root = ParentSink(middle)

    assert leaf.parent is middle
    assert middle.parent is root
    assert root.child is middle
    assert middle.child is leaf
    assert leaf.root is root
    assert list(root.walk_children()) == [middle, leaf]
    assert list(root.walk_children(with_self=True)) == [root, middle, leaf]


def test_audio_sink_rejects_duplicate_child_registration():
    leaf = CollectingSink()
    root = ParentSink(leaf)

    with pytest.raises(RuntimeError, match='already registered'):
        root._register_child(leaf)


def test_multi_audio_sink_registers_multiple_children_without_exposing_mutable_list():
    first = CollectingSink()
    second = CollectingSink()
    root = ConcreteMultiAudioSink([first, second])

    assert first.parent is root
    assert second.parent is root
    assert root.child is first
    assert list(root.children) == [first, second]
    with pytest.raises(AttributeError):
        root.children.append(CollectingSink())


def test_listener_decorator_registers_inherited_and_overridden_listeners():
    class Base(CollectingSink):
        @AudioSink.listener('on_custom')
        def base_listener(self):
            pass

        @AudioSink.listener()
        def on_replaced(self):
            pass

    class Child(Base):
        @AudioSink.listener()
        def on_replaced(self):
            pass

        @staticmethod
        @AudioSink.listener('on_static')
        def static_listener():
            pass

    assert ('on_custom', 'base_listener') in Child.__sink_listeners__
    assert ('on_replaced', 'on_replaced') in Child.__sink_listeners__
    assert ('on_static', 'static_listener') in Child.__sink_listeners__
    assert Child.__sink_listeners__.count(('on_replaced', 'on_replaced')) == 1


def test_listener_decorator_rejects_coroutines():
    async def async_listener():
        pass

    with pytest.raises(TypeError, match='must not be a coroutine'):
        AudioSink.listener()(async_listener)


def test_basic_sink_forwards_audio_and_optional_rtcp_callbacks():
    cb = MagicMock()
    rtcp_cb = MagicMock()
    sink = BasicSink(cb, rtcp_event=rtcp_cb, decode=False)
    data = voice_data()
    packet = object()

    sink.write('user', data)
    sink.on_rtcp_packet(packet, guild=object())

    assert sink.wants_opus() is True
    cb.assert_called_once_with('user', data)
    rtcp_cb.assert_called_once_with(packet)


def test_conditional_and_user_filters_forward_only_matching_packets():
    destination = CollectingSink()
    allowed_data = voice_data()
    blocked_data = voice_data()
    conditional = ConditionalFilter(destination, lambda user, data: data is allowed_data)

    conditional.write('user', allowed_data)
    conditional.write('user', blocked_data)

    assert destination.writes == [('user', allowed_data)]

    user_destination = CollectingSink()
    user_filter = UserFilter(user_destination, user='target')
    user_filter.write('target', allowed_data)
    user_filter.write('other', allowed_data)

    assert user_destination.writes == [('target', allowed_data)]


def test_timed_filter_starts_on_first_write_and_expires():
    class FakeTimedFilter(TimedFilter):
        now = 100.0

        def get_time(self) -> float:
            return self.now

    destination = CollectingSink()
    filt = FakeTimedFilter(destination, duration=5.0)
    first = voice_data()
    second = voice_data()

    filt.write('user', first)
    filt.now = 104.9
    filt.write('user', second)
    filt.now = 105.1
    filt.write('user', voice_data())

    assert destination.writes == [('user', first), ('user', second)]


def test_pcm_volume_transformer_validates_destination_and_clamps_volume():
    opus_destination = CollectingSink(opus=True)

    with pytest.raises(TypeError):
        PCMVolumeTransformer(object())  # type: ignore[arg-type]
    with pytest.raises(VoiceRecvException, match='must not request Opus'):
        PCMVolumeTransformer(opus_destination)

    destination = CollectingSink()
    transformer = PCMVolumeTransformer(destination, volume=10.0)
    data = voice_data(pcm=b'\x01\x00')

    transformer.write('user', data)
    transformer.volume = -1

    assert data.pcm == b'\x02\x00'
    assert transformer.volume == 0.0
    assert destination.writes == [('user', data)]


class FakeStdin(io.BytesIO):
    def __init__(self):
        super().__init__()
        self.closed_by_sink = False

    def close(self) -> None:
        self.closed_by_sink = True
        super().close()


class FakeProcess:
    pid = 1234

    def __init__(self):
        self.stdin = FakeStdin()
        self.stdout = None
        self.stderr = None
        self.wait_calls = []
        self.kill_calls = 0
        self.returncode = 0

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        return self.returncode

    def kill(self) -> None:
        self.kill_calls += 1

    def poll(self):
        return self.returncode


class BrokenStdin:
    closed = False

    def close(self) -> None:
        self.closed = True

    def write(self, data: bytes) -> None:
        raise OSError('pipe closed')


def test_ffmpeg_sink_builds_process_writes_pcm_and_cleans_up():
    process = FakeProcess()
    with patch('discord.ext.voice_recv.sinks.subprocess.Popen', return_value=process) as popen:
        sink = FFmpegSink(filename='out.wav', executable='ffmpeg', before_options='-nostdin', options='-vn')

    args = popen.call_args.args[0]
    assert args[:3] == ['ffmpeg', '-hide_banner', '-nostdin']
    assert args[-2:] == ['-vn', 'out.wav']

    sink.write('user', voice_data(pcm=b'abcd'))
    assert process.stdin.getvalue() == b'abcd'

    sink.cleanup()

    assert process.stdin.closed_by_sink is True
    assert process.wait_calls == [5]
    assert process.kill_calls == 1


def test_ffmpeg_sink_invokes_error_callback_when_stdin_write_fails():
    process = FakeProcess()
    process.stdin = BrokenStdin()
    on_error = MagicMock()

    with patch('discord.ext.voice_recv.sinks.subprocess.Popen', return_value=process):
        sink = FFmpegSink(filename='out.wav', on_error=on_error)

    data = voice_data(pcm=b'abcd')
    sink.write('user', data)

    assert process.kill_calls == 1
    assert on_error.call_args.args[0] is sink
    assert on_error.call_args.args[2] is data
