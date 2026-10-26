"""Parse SillyTavern character cards and extract a usable visual prompt.

Supports:
  * Character Card V2/V3 embedded in a PNG (tEXt/iTXt chunk "chara" or "ccv3")
  * Plain JSON cards (V1 flat format or V2 {"data": {...}})

No network calls, no external services.
"""

from __future__ import annotations

import base64
import json
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CARD_CHUNK_KEYS = ("ccv3", "chara")


@dataclass
class CharacterCard:
    """The fields we actually use when building a video prompt."""

    name: str
    description: str = ""
    personality: str = ""
    scenario: str = ""
    first_mes: str = ""
    appearance: str = ""
    tags: list = field(default_factory=list)
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "personality": self.personality,
            "scenario": self.scenario,
            "first_mes": self.first_mes,
            "appearance": self.appearance,
            "tags": self.tags,
            "source": self.source,
        }


def _read_png_text_chunks(path: Path) -> Dict[str, str]:
    """Return every tEXt/iTXt chunk of a PNG as {keyword: text}."""
    data = path.read_bytes()
    if data[:8] != PNG_SIGNATURE:
        raise ValueError(f"{path} is not a PNG file")

    out: Dict[str, str] = {}
    pos = 8
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        chunk_type = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]

        if chunk_type == b"tEXt":
            key, _, value = chunk.partition(b"\x00")
            out[key.decode("latin-1")] = value.decode("latin-1")
        elif chunk_type == b"iTXt":
            key, _, rest = chunk.partition(b"\x00")
            parts = rest.split(b"\x00", 3)
            if len(parts) == 4:
                out[key.decode("latin-1")] = parts[3].decode("utf-8", "ignore")

        pos += 12 + length
        if chunk_type == b"IEND":
            break
    return out


def _decode_card_payload(raw: str) -> Dict[str, Any]:
    """Card payloads are base64-encoded JSON (V2/V3) or plain JSON (V1)."""
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    padded = text + "=" * (-len(text) % 4)
    decoded = base64.b64decode(padded).decode("utf-8")
    return json.loads(decoded)


def _normalise(payload: Dict[str, Any], source: str) -> CharacterCard:
    body = payload.get("data", payload)  # V2 wraps everything in "data"
    return CharacterCard(
        name=str(body.get("name", "Unnamed character")),
        description=str(body.get("description", "") or ""),
        personality=str(body.get("personality", "") or ""),
        scenario=str(body.get("scenario", "") or ""),
        first_mes=str(body.get("first_mes", "") or ""),
        appearance=str(body.get("appearance", "") or body.get("mes_example", "") or ""),
        tags=list(body.get("tags", []) or []),
        source=source,
    )


def load_card(path: str | Path) -> CharacterCard:
    """Load a character card from a .png or .json file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"card not found: {p}")

    if p.suffix.lower() == ".json":
        payload = json.loads(p.read_text(encoding="utf-8"))
        return _normalise(payload, str(p))

    chunks = _read_png_text_chunks(p)
    for key in CARD_CHUNK_KEYS:
        if key in chunks:
            payload = _decode_card_payload(chunks[key])
            return _normalise(payload, str(p))

    raise ValueError(
        "no character-card chunk found in this PNG. "
        "Export the card from SillyTavern (Card -> Export as PNG) "
        "or pass the JSON version instead."
    )


def extract_avatar(path: str | Path, out_path: str | Path) -> Path:
    """Copy the card image itself out as the reference image for the video model."""
    src, dst = Path(path), Path(out_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())
    return dst
