# -*- coding: utf-8 -*-

from __future__ import annotations

from types import SimpleNamespace

from discord.ext.voice_recv.video import VideoStreamInfo, VideoStreamResolution, VoiceVideoStreams


def stream_payload(**overrides):
    payload = {
        'type': 'video',
        'active': True,
        'max_bitrate': 2500,
        'max_framerate': 60,
        'max_resolution': {'height': 720, 'width': 1280, 'type': 'fixed'},
        'quality': 100,
        'rid': '100',
        'rtx_ssrc': 222,
        'ssrc': 111,
    }
    payload.update(overrides)
    return payload


def test_video_stream_resolution_maps_payload_fields_and_repr():
    resolution = VideoStreamResolution({'height': 720, 'width': 1280, 'type': 'fixed'})

    assert resolution.height == 720
    assert resolution.width == 1280
    assert resolution.type == 'fixed'


def test_video_stream_info_maps_payload_fields():
    info = VideoStreamInfo(data=stream_payload(type='screen'))

    assert info.type == 'screen'
    assert info.active is True
    assert info.max_bitrate == 2500
    assert info.max_framerate == 60
    assert info.max_resolution.width == 1280
    assert info.quality == 100
    assert info.rid == '100'
    assert info.rtx_ssrc == 222
    assert info.ssrc == 111
    assert 'VideoStreamInfo' in repr(info)


def test_video_stream_info_preserves_explicit_none_type():
    info = VideoStreamInfo(data=stream_payload(type=None))

    assert info.type is None


def test_video_stream_info_uses_default_type_and_bitrate_when_keys_missing():
    payload = stream_payload()
    del payload['type']
    del payload['max_bitrate']

    info = VideoStreamInfo(data=payload)

    assert info.type == 'video'
    assert info.max_bitrate == 0


def test_voice_video_streams_maps_member_and_streams():
    member = object()
    guild = SimpleNamespace(get_member=lambda user_id: member if user_id == 123 else None)
    vc = SimpleNamespace(guild=guild)
    data = {
        'audio_ssrc': 10,
        'video_ssrc': 20,
        'user_id': '123',
        'streams': [
            stream_payload(rid='100', ssrc=111),
            stream_payload(rid='50', ssrc=222, active=False, type='screen'),
        ],
    }

    streams = VoiceVideoStreams(data=data, vc=vc)

    assert streams.audio_ssrc == 10
    assert streams.video_ssrc == 20
    assert streams.member is member
    assert [stream.rid for stream in streams.streams] == ['100', '50']
    assert [stream.active for stream in streams.streams] == [True, False]
