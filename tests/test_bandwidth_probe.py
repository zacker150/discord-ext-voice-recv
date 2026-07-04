# -*- coding: utf-8 -*-

from __future__ import annotations

from unittest.mock import MagicMock, patch

from discord.ext.voice_recv.opus import PacketDecoder
from discord.ext.voice_recv.rtp import RTPPacket


class _DecoderThatMustNotDecode:
    """Opus decoder double: rejects an empty packet at the header probe (as libopus
    does) and fails loudly if decode() is ever reached."""

    SAMPLES_PER_FRAME = 960

    def packet_get_nb_frames(self, payload: bytes) -> int:
        if not payload:
            raise ValueError('empty opus packet')  # libopus returns OPUS_BAD_ARG
        return 1  # non-empty payload would pass the probe and reach decode()

    def packet_get_samples_per_frame(self, payload: bytes) -> int:
        return 960

    def decode(self, *args, **kwargs) -> bytes:
        raise AssertionError('bandwidth probe reached the opus decoder')


def test_bandwidth_probe_is_not_passed_to_opus_decoder():
    # An RTP bandwidth/DTX probe is all padding: P bit set, payload made entirely
    # of padding octets (final octet == length). After strip_padding it is empty
    # and must be skipped at the header probe, never reaching opus_decode.
    probe = RTPPacket(bytes([0xA0, 0x78, 0x00, 0x01, 0, 0, 0, 0, 0, 0, 0, 1]) + b'\x00')
    probe.decrypted_data = probe.strip_padding(b'\xff' * 255)
    assert probe.decrypted_data == b''

    router = MagicMock()
    router.sink.wants_opus.return_value = False  # PCM path -> __init__ builds a Decoder
    with patch('discord.ext.voice_recv.opus.Decoder', return_value=_DecoderThatMustNotDecode()):
        decoder = PacketDecoder(router, ssrc=1)

    # decode() raises AssertionError if reached; getting a result means it was skipped.
    _, pcm = decoder._decode_packet(probe)

    assert pcm == b''
    router.reader.analysis_stats.inc.assert_any_call('opus_invalid_header_skipped', 1)
