# -*- coding: utf-8 -*-

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from discord.ext.voice_recv.router import PacketRouter, SinkEventRouter
from discord.ext.voice_recv.sinks import AudioSink


class DummySink(AudioSink):
    def __init__(self):
        super().__init__()
        self.writes = []

    def wants_opus(self) -> bool:
        return True

    def write(self, user, data) -> None:
        self.writes.append((user, data))

    def cleanup(self) -> None:
        pass


class FakeReader:
    def __init__(self):
        self.error = None
        self.voice_client = MagicMock()
        self.event_router = MagicMock()
        self.packet_router = SimpleNamespace(_lock=MagicMock())


def packet(ssrc: int = 1):
    return SimpleNamespace(ssrc=ssrc)


def test_packet_router_creates_reuses_and_updates_decoder_user_id():
    sink = DummySink()
    reader = FakeReader()
    decoder = MagicMock()

    with patch('discord.ext.voice_recv.router.PacketDecoder', return_value=decoder) as decoder_cls:
        router = PacketRouter(sink, reader)

        assert router.get_decoder(123) is decoder
        assert router.get_decoder(123) is decoder
        decoder_cls.assert_called_once_with(router, 123)

        router.set_user_id(123, 456)

    decoder.set_user_id.assert_called_once_with(456)


def test_packet_router_feed_rtp_pushes_packets_to_decoder():
    sink = DummySink()
    reader = FakeReader()
    decoder = MagicMock()

    with patch('discord.ext.voice_recv.router.PacketDecoder', return_value=decoder):
        router = PacketRouter(sink, reader)
        pkt = packet(123)

        router.feed_rtp(pkt)

    decoder.push_packet.assert_called_once_with(pkt)


def test_packet_router_set_sink_replaces_sink():
    router = PacketRouter(DummySink(), FakeReader())
    new_sink = DummySink()

    router.set_sink(new_sink)

    assert router.sink is new_sink


def test_packet_router_destroy_decoder_drops_ssrc_until_user_id_reappears():
    sink = DummySink()
    reader = FakeReader()
    decoder = MagicMock()
    replacement = MagicMock()

    with patch('discord.ext.voice_recv.router.PacketDecoder', side_effect=[decoder, replacement]):
        router = PacketRouter(sink, reader)
        router.get_decoder(123)
        router.destroy_decoder(123)
        router.feed_rtp(packet(123))

        assert 123 in router._dropped_ssrcs
        assert router.decoders == {}
        decoder.destroy.assert_called_once_with()

        router.set_user_id(123, 456)
        router.feed_rtp(packet(123))

    assert 123 not in router._dropped_ssrcs
    replacement.push_packet.assert_called_once()


def test_packet_router_set_user_id_clears_dropped_ssrc_without_decoder():
    router = PacketRouter(DummySink(), FakeReader())
    router._dropped_ssrcs.append(123)

    router.set_user_id(123, 456)

    assert 123 not in router._dropped_ssrcs


def test_packet_router_destroy_all_decoders_marks_each_dropped():
    sink = DummySink()
    reader = FakeReader()
    first = MagicMock()
    second = MagicMock()

    with patch('discord.ext.voice_recv.router.PacketDecoder', side_effect=[first, second]):
        router = PacketRouter(sink, reader)
        router.get_decoder(1)
        router.get_decoder(2)
        router.destroy_all_decoders()

    assert router.decoders == {}
    assert list(router._dropped_ssrcs) == [1, 2]
    first.destroy.assert_called_once_with()
    second.destroy.assert_called_once_with()


def test_packet_router_feed_rtcp_dispatches_to_event_router_with_guild():
    sink = DummySink()
    sink._voice_client = SimpleNamespace(guild='guild')
    reader = FakeReader()
    router = PacketRouter(sink, reader)
    pkt = object()

    router.feed_rtcp(pkt)

    reader.event_router.dispatch.assert_called_once_with('rtcp_packet', pkt, 'guild')


def test_packet_router_do_run_writes_ready_decoder_data_once():
    sink = DummySink()
    reader = FakeReader()
    router = PacketRouter(sink, reader)
    data = SimpleNamespace(source='user')
    decoder = MagicMock()
    decoder.pop_data.return_value = data

    class OneShotWaiter:
        def __init__(self):
            self.items = [decoder]

        def wait(self):
            router._end_thread.set()

    router.waiter = OneShotWaiter()

    router._do_run()

    assert sink.writes == [('user', data)]


def test_packet_router_do_run_skips_decoders_without_data():
    sink = DummySink()
    router = PacketRouter(sink, FakeReader())
    decoder = MagicMock()
    decoder.pop_data.return_value = None

    class OneShotWaiter:
        def __init__(self):
            self.items = [decoder]

        def wait(self):
            router._end_thread.set()

    router.waiter = OneShotWaiter()

    router._do_run()

    assert sink.writes == []


def test_packet_router_run_stores_error_stops_reader_and_clears_waiter():
    reader = FakeReader()
    router = PacketRouter(DummySink(), reader)
    error = RuntimeError('boom')
    router._do_run = MagicMock(side_effect=error)
    router.waiter.clear = MagicMock()

    router.run()

    assert reader.error is error
    reader.voice_client.stop_listening.assert_called_once_with()
    router.waiter.clear.assert_called_once_with()


def test_packet_router_stop_sets_end_event_and_notifies_waiter():
    router = PacketRouter(DummySink(), FakeReader())
    router.waiter.notify = MagicMock()

    router.stop()

    assert router._end_thread.is_set()
    router.waiter.notify.assert_called_once_with()


def test_sink_event_router_registers_dispatches_and_unregisters_nested_listeners():
    calls = []

    class ChildSink(DummySink):
        @AudioSink.listener('on_custom')
        def child_listener(self, value):
            calls.append(('child', value))

    class RootSink(DummySink):
        def __init__(self, child):
            super().__init__()
            self._register_child(child)

        @AudioSink.listener('on_custom')
        def root_listener(self, value):
            calls.append(('root', value))

    child = ChildSink()
    root = RootSink(child)
    router = SinkEventRouter(root, FakeReader())

    router._dispatch_to_listeners('custom', 1)
    router.unregister_events()
    router._dispatch_to_listeners('custom', 2)

    assert calls == [('root', 1), ('child', 1)]


def test_sink_event_router_set_sink_replaces_registered_listeners():
    calls = []

    class FirstSink(DummySink):
        @AudioSink.listener('on_custom')
        def first(self):
            calls.append('first')

    class SecondSink(DummySink):
        @AudioSink.listener('on_custom')
        def second(self):
            calls.append('second')

    router = SinkEventRouter(FirstSink(), FakeReader())
    router.set_sink(SecondSink())
    router._dispatch_to_listeners('custom')

    assert calls == ['second']


def test_sink_event_router_dispatch_queues_event_and_do_run_drains_it():
    reader = FakeReader()
    router = SinkEventRouter(DummySink(), reader)
    router._dispatch_to_listeners = MagicMock(side_effect=lambda *args, **kwargs: router._end_thread.set())

    router.dispatch('custom', 1, named=2)
    router._do_run()

    router._dispatch_to_listeners.assert_called_once_with('custom', 1, named=2)


def test_sink_event_router_listener_exception_does_not_stop_other_listeners():
    calls = []

    class ErrorSink(DummySink):
        @AudioSink.listener('on_custom')
        def bad(self):
            raise RuntimeError('boom')

        @AudioSink.listener('on_custom')
        def good(self):
            calls.append('good')

    router = SinkEventRouter(ErrorSink(), FakeReader())

    router._dispatch_to_listeners('custom')

    assert calls == ['good']
