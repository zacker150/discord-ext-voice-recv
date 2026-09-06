# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from pprint import pformat

from discord.gateway import DiscordVoiceWebSocket
from discord.enums import SpeakingState, try_enum

from .enums import VoiceFlags, VoicePlatform
from .video import VoiceVideoStreams

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from typing import Dict, Any

    from .voice_client import VoiceRecvClient
    from .video import VoiceVideoPayload

log = logging.getLogger(__name__)


DAVE_AND_MLS_OPCODES = frozenset(
    {
        DiscordVoiceWebSocket.DAVE_PREPARE_TRANSITION,
        DiscordVoiceWebSocket.DAVE_EXECUTE_TRANSITION,
        DiscordVoiceWebSocket.DAVE_TRANSITION_READY,
        DiscordVoiceWebSocket.DAVE_PREPARE_EPOCH,
        DiscordVoiceWebSocket.MLS_EXTERNAL_SENDER,
        DiscordVoiceWebSocket.MLS_KEY_PACKAGE,
        DiscordVoiceWebSocket.MLS_PROPOSALS,
        DiscordVoiceWebSocket.MLS_COMMIT_WELCOME,
        DiscordVoiceWebSocket.MLS_ANNOUNCE_COMMIT_TRANSITION,
        DiscordVoiceWebSocket.MLS_WELCOME,
        DiscordVoiceWebSocket.MLS_INVALID_COMMIT_WELCOME,
    }
)


async def binary_hook(ws: DiscordVoiceWebSocket, op: int, seq: int, payload: bytes) -> None:
    vc: VoiceRecvClient = ws._connection.voice_client  # type: ignore
    vc._update_voice_ws_binary_state(op, payload, seq=seq, raw_len=len(payload) + 3)
    duration = getattr(ws, 'dave_mls_processing_ms', None)
    if op in (DiscordVoiceWebSocket.MLS_ANNOUNCE_COMMIT_TRANSITION, DiscordVoiceWebSocket.MLS_WELCOME) and duration is not None:
        log.debug('DAVE MLS processing: op=%s seq=%s duration_ms=%.3f', op, seq, duration)
        if duration > 20:
            log.warning('Slow DAVE MLS processing: op=%s duration_ms=%.3f', op, duration)


async def hook(self: DiscordVoiceWebSocket, msg: Dict[str, Any]):
    op: int = msg['op']
    data: Dict[str, Any] = msg.get('d', {})
    vc: VoiceRecvClient = self._connection.voice_client  # type: ignore

    if op not in (self.HEARTBEAT, self.HEARTBEAT_ACK):
        log.debug("Received op %s: \n%s", op, pformat(data, compact=True))

        if len(msg.keys()) > 2:
            m = msg.copy()
            m.pop('op')
            m.pop('d')
            log.info("WS payload has extra keys: %s", m)

    vc._update_voice_ws_state(op, data, raw_message=msg)
    vc._dave_state_changed(f'json_op_{op}')

    if op == self.READY:
        vc._add_ssrc(vc.guild.me.id, data['ssrc'])

    elif op == self.SESSION_DESCRIPTION:
        if vc._reader:
            # TODO: remove bytes cast once type is fixed in dpy
            vc._reader.update_secret_key(bytes(self.secret_key))  # type: ignore

    elif op == self.SPEAKING:
        # this event refers to the speaking MODE, e.g. priority speaker
        # it also sends the user's ssrc
        uid = int(data['user_id'])
        ssrc = data['ssrc']
        vc._add_ssrc(uid, ssrc)
        member = vc.guild.get_member(uid)
        state = try_enum(SpeakingState, data['speaking'])
        vc.dispatch("voice_member_speaking_state", member, ssrc, state)

    elif op == self.CLIENTS_CONNECT:
        uids = [int(uid) for uid in data['user_ids']]

        # Multiple user IDs means this is the initial member list
        for uid in uids:
            member = vc.guild.get_member(uid)
            vc.dispatch("voice_member_connect", member)

    elif op == self.CLIENT_CONNECT:
        uid = int(data['user_id'])
        vc._add_ssrc(uid, data['audio_ssrc'])
        member = vc.guild.get_member(uid)
        streams = VoiceVideoStreams(data=cast('VoiceVideoPayload', data), vc=vc)
        vc._update_video_ssrcs(uid, streams)
        vc.dispatch("voice_member_video", member, streams)

    elif op == self.CLIENT_DISCONNECT:
        uid = int(data['user_id'])
        ssrc = vc._get_ssrc_from_id(uid)

        if vc._reader and ssrc is not None:
            log.debug("Destroying decoder for %s, ssrc=%s", uid, ssrc)
            vc._reader.packet_router.destroy_decoder(ssrc)

        vc._remove_ssrc(user_id=uid)
        member = vc.guild.get_member(uid)
        vc.dispatch("voice_member_disconnect", member, ssrc)

    elif op == self.FLAGS:
        uid = int(data['user_id'])
        member = vc.guild.get_member(uid)
        vc.dispatch("voice_member_flags", member, VoiceFlags._from_value(data['flags'] or 0))

    elif op == self.PLATFORM:
        uid = int(data['user_id'])
        member = vc.guild.get_member(uid)
        vc.dispatch(
            "voice_member_platform",
            member,
            try_enum(VoicePlatform, data['platform']) if data['platform'] is not None else None,
        )

    elif op in DAVE_AND_MLS_OPCODES:
        if op == DiscordVoiceWebSocket.DAVE_EXECUTE_TRANSITION and vc._reader:
            vc._reader.analysis_stats.reset_all_dave_nonces()
        vc.dispatch("voice_dave_opcode", op, data)
