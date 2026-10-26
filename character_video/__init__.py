"""character-video-quickstart: SillyTavern card -> Kling video, in one command."""

from .card import CharacterCard, load_card
from .prompt import build_prompt

__all__ = ["CharacterCard", "load_card", "build_prompt"]
__version__ = "0.1.0"
