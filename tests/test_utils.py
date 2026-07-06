# -*- coding: utf-8 -*-

from __future__ import annotations

from unittest.mock import patch

import pytest

from discord.ext.voice_recv.utils import Bidict, Defaultdict, LoopTimer, MultiDataEvent, add_wrapped, gap_wrapped


def test_wrapped_arithmetic_handles_normal_and_wraparound_values():
    assert gap_wrapped(10, 13) == 2
    assert gap_wrapped(65535, 0) == 0
    assert gap_wrapped(65534, 1) == 2
    assert add_wrapped(65535, 1) == 0
    assert add_wrapped(1, -2) == 65535
    assert add_wrapped(9, 5, wrap=10) == 4


def test_bidict_initializes_and_maintains_reverse_mappings():
    mapping = Bidict({1: 'a'})

    assert mapping[1] == 'a'
    assert mapping['a'] == 1

    mapping[1] = 'b'

    assert 'a' not in mapping
    assert mapping[1] == 'b'
    assert mapping['b'] == 1

    mapping['b'] = 2

    assert 1 not in mapping
    assert mapping['b'] == 2
    assert mapping[2] == 'b'


def test_bidict_delete_pop_setdefault_update_and_copy_keep_pairs_in_sync():
    mapping = Bidict()

    assert mapping.setdefault('a', 1) == 1
    assert mapping.setdefault('a', 99) == 1
    assert mapping.setdefault('other', 1) == 1
    assert 'other' not in mapping

    mapping.update({'b': 2}, c=3)
    clone = mapping.copy()

    assert isinstance(clone, Bidict)
    assert clone == mapping
    assert clone is not mapping
    assert mapping.pop('b') == 2
    assert 2 not in mapping

    del mapping['a']
    assert 1 not in mapping
    assert 'a' not in mapping

    assert mapping.pop('missing', 'default') == 'default'
    with pytest.raises(KeyError):
        mapping.pop('missing')


def test_bidict_handles_self_mapping_delete_and_popitem():
    mapping = Bidict()
    mapping['same'] = 'same'

    assert mapping['same'] == 'same'
    del mapping['same']
    assert mapping == {}

    mapping.update([('a', 1), ('b', 2)])
    key, value = mapping.popitem()

    assert key not in mapping
    assert value not in mapping


def test_defaultdict_passes_missing_key_to_factory():
    mapping = Defaultdict(lambda key: f'value:{key}')

    assert mapping['x'] == 'value:x'
    assert mapping['x'] == 'value:x'

    no_factory = Defaultdict()
    with pytest.raises(KeyError) as exc:
        no_factory['missing']
    assert exc.value.args == (('missing',),)


def test_loop_timer_tracks_loops_and_sleep_duration():
    now = 10.0

    def timefunc():
        return now

    timer = LoopTimer(5.0, timefunc=timefunc)
    timer.start()

    assert timer.start_time == 10.0
    assert timer.loops == 0
    assert timer.remaining_time == 5.0

    timer.mark()
    now = 12.0
    assert timer.loops == 1
    assert timer.remaining_time == 8.0

    now = 30.0
    assert timer.remaining_time == -10.0
    with patch('discord.ext.voice_recv.utils.time.sleep') as sleep:
        timer.sleep()
    sleep.assert_called_once_with(0)


def test_multi_data_event_tracks_readiness_items_and_clearing():
    event = MultiDataEvent[str]()

    assert event.is_ready() is False
    assert event.wait(timeout=0) is False

    event.notify()
    assert event.is_ready() is False

    event.register('a')
    event.register('b')
    assert event.is_ready() is True
    assert event.wait(timeout=0) is True

    items = event.items
    items.append('mutated')
    assert event.items == ['a', 'b']

    event.unregister('missing')
    assert event.items == ['a', 'b']
    event.unregister('a')
    assert event.items == ['b']
    event.clear()
    assert event.items == []
    assert event.is_ready() is False
