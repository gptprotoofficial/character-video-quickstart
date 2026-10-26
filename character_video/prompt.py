"""Turn character-card fields into a video prompt.

The goal is identity preservation, not storytelling: the reference image already
carries the look, so the prompt only describes motion, camera and light.
"""

from __future__ import annotations

from typing import Optional

from .card import CharacterCard

BASE_MOTION = (
    "The character from the reference image, keeping her exact face, hair, outfit "
    "and art style unchanged. Subtle idle motion only: breathing, hair and fabric "
    "moving slightly, eyes blinking naturally, head turning a few degrees toward the "
    "camera. Slow cinematic push-in. Soft rim light, shallow depth of field."
)

NEGATIVE = "no text, no captions, no subtitles, no watermark, no logo, no UI elements"

CAMERA_PRESETS = {
    "push-in": "slow cinematic push-in, ending on a close-up",
    "orbit": "gentle orbital camera movement around the character",
    "static": "locked-off camera, motion inside the frame only",
    "handheld": "subtle handheld drift, documentary feel",
}


def build_prompt(
    card: CharacterCard,
    camera: str = "push-in",
    scene: Optional[str] = None,
    line: Optional[str] = None,
    duration: int = 5,
) -> str:
    """Compose one prompt string from the card and the shot choices.

    card     : parsed character card
    camera   : one of CAMERA_PRESETS
    scene    : optional override for the scenario (card scenario used by default)
    line     : optional spoken line; only works on models with audio output
    duration : seconds, informational only - the API field is set separately
    """
    camera_text = CAMERA_PRESETS.get(camera, CAMERA_PRESETS["push-in"])

    parts = [BASE_MOTION, f"Camera: {camera_text}."]

    setting = (scene or card.scenario or "").strip()
    if setting:
        parts.append(f"Setting: {setting[:300].rstrip('.')}.")

    mood = " ".join(x for x in (card.personality, card.description) if x).strip()
    if mood:
        parts.append(f"Performance note (do not render as text): {mood[:300].rstrip('.')}.")

    if line:
        parts.append(f'She says, softly and naturally: "{line.strip()[:200]}"')

    parts.append(NEGATIVE)
    parts.append(f"Duration: {duration}s, vertical 9:16.")
    return " ".join(parts)


def summarise(card: CharacterCard) -> str:
    """Short one-line summary, handy for logs and README examples."""
    tag_text = ", ".join(card.tags[:5]) if card.tags else "untagged"
    desc = (card.description or card.personality or "").strip().replace("\n", " ")
    return f"{card.name} ({tag_text}) - {desc[:120]}"
