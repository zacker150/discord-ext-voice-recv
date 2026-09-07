# -*- coding: utf-8 -*-
from importlib.metadata import version as _distribution_version

from .voice_client import *
from .reader import *
from .sinks import *
from .video import *
from .video_reader import VideoPacket as VideoPacket
from .opus import *
from .rtp import *
from .dave import *
from .enums import *

from . import (
    rtp as rtp,
    extras as extras,
)

__title__ = 'discord.ext.voice_recv'
__author__ = 'Imayhaveborkedit'
__license__ = 'MIT'
__copyright__ = 'Copyright 2021-present Imayhaveborkedit'
__version__ = _distribution_version('discord-ext-voice-recv')
