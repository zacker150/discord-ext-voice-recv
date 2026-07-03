# -*- coding: utf-8 -*-
"""Wiring tests: every RTP decrypt path must run its decrypted payload through
RTPPacket.strip_padding(). Exercises the real reader.PacketDecryptor methods with
a stubbed box -- no secret key or real decryption involved."""

from __future__ import annotations

from unittest.mock import MagicMock

import nacl.secret

from discord.ext.voice_recv.reader import PacketDecryptor
from discord.ext.voice_recv.rtp import RTPPacket

# opus | 0d fa fa | four RTP padding octets (final octet == pad count == 4)
DECRYPTED = b'\x01\x02\x0d\xfa\xfa\x04\x04\x04\x04'
STRIPPED = b'\x01\x02\x0d\xfa\xfa'


def _padded_packet(*, tail: int = 8) -> RTPPacket:
    # RTP v2 with the padding (P) bit set; no extension, no CSRCs.
    header = bytes([0xA0, 0x78, 0x00, 0x01, 0, 0, 0, 0, 0, 0, 0, 1])
    return RTPPacket(header + b'\x00' * tail)


def _decryptor(box_spec) -> PacketDecryptor:
    # Bypass __init__ (no key/crypto); the decrypt methods only touch self.box.
    dec = object.__new__(PacketDecryptor)
    box = MagicMock(spec=box_spec)  # spec makes isinstance(box, box_spec) hold
    box.decrypt.return_value = DECRYPTED
    dec.box = box
    return dec


def test_aead_rtpsize_transport_strips_padding():
    dec = _decryptor(nacl.secret.Aead)
    out = PacketDecryptor._decrypt_rtp_transport_aead_xchacha20_poly1305_rtpsize(dec, _padded_packet())
    assert out == STRIPPED


def test_xsalsa20_poly1305_strips_padding():
    dec = _decryptor(nacl.secret.SecretBox)
    out = PacketDecryptor._decrypt_rtp_xsalsa20_poly1305(dec, _padded_packet())
    assert out == STRIPPED


def test_xsalsa20_poly1305_suffix_strips_padding():
    dec = _decryptor(nacl.secret.SecretBox)
    out = PacketDecryptor._decrypt_rtp_xsalsa20_poly1305_suffix(dec, _padded_packet(tail=32))
    assert out == STRIPPED


def test_xsalsa20_poly1305_lite_strips_padding():
    dec = _decryptor(nacl.secret.SecretBox)
    out = PacketDecryptor._decrypt_rtp_xsalsa20_poly1305_lite(dec, _padded_packet())
    assert out == STRIPPED
