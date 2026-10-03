"""Aim layers. build_layers() returns the (input, output) lists the pipeline runs.

Local checks come first because they cost no Guard quota.
"""
from __future__ import annotations

from ..config import Settings
from .base import Layer
from .canonicaliser import Canonicaliser
from .ghana_lens import GhanaLens
from .language_bridge import LanguageBridge
from .memory import ConversationMemory
from .output_sentinel import OutputSentinel


def build_layers(settings: Settings) -> tuple[list[Layer], list[Layer]]:
    inputs: list[Layer] = [GhanaLens("input"), Canonicaliser(), ConversationMemory(), LanguageBridge()]
    outputs: list[Layer] = [OutputSentinel(settings.canary_token), GhanaLens("output")]
    return inputs, outputs
