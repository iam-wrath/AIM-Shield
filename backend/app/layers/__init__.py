"""Aim layers. build_layers() returns the (input, output) lists the pipeline runs.

Local checks come first because they cost no Guard quota.
"""
from __future__ import annotations

from ..config import Settings
from ..kwikpay import AuthStore
from .base import Layer
from .canonicaliser import Base64Decoder
from .ghana_lens import GhanaLens
from .identity_binding import IdentityBinding
from .memory import ConversationMemory
from .output_sentinel import OutputSentinel


def build_layers(settings: Settings, auth: AuthStore | None = None) -> tuple[list[Layer], list[Layer]]:
    auth = auth or AuthStore()
    inputs: list[Layer] = [
        GhanaLens("input", auth),  # masks PINs/IDs, routes the one-time code
        Base64Decoder(),  # the Guard misses base64 but handles the other encodings
        ConversationMemory(),  # before identity so a split scam is caught by what it says
        IdentityBinding(auth),
    ]
    outputs: list[Layer] = [OutputSentinel(settings.canary_token), GhanaLens("output", auth)]
    return inputs, outputs
