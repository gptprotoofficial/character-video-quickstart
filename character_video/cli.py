"""Command line entry point.

Usage
-----
    python -m character_video cards ./cards             # inspect cards, no API call
    python -m character_video dry-run card.png          # print the request, no API call
    python -m character_video selftest                  # check endpoints + key
    python -m character_video run card.png -o out.mp4   # create -> poll -> download
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .card import load_card
from .gptproto import VideoClient, build_payload, image_payload
from .prompt import build_prompt, summarise


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def _resolve_image(card_path: str, override: str | None) -> str:
    """The reference frame must be an image; JSON cards point to one with --image."""
    if override:
        return override
    if Path(card_path).suffix.lower() in IMAGE_SUFFIXES:
        return card_path
    raise SystemExit(
        f"{card_path} is a JSON card, so there is no reference image in it.\n"
        "Pass the portrait explicitly:  --image ./cards/mira.png"
    )


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("card", help="path to a character card (.png or .json)")
    p.add_argument("--image", default=None, help="reference image (defaults to the card PNG)")
    p.add_argument("--camera", default="push-in", choices=["push-in", "orbit", "static", "handheld"])
    p.add_argument("--scene", default=None, help="override the card scenario in the prompt")
    p.add_argument("--line", default=None, help="optional spoken line (audio-capable models)")
    p.add_argument("--duration", type=int, default=5, help="clip length in seconds")
    p.add_argument("--aspect", default="9:16")
    p.add_argument("-v", "--verbose", action="store_true")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="character_video")
    sub = parser.add_subparsers(dest="command", required=True)

    p_cards = sub.add_parser("cards", help="list cards in a folder with parsed fields")
    p_cards.add_argument("folder")

    p_dry = sub.add_parser("dry-run", help="build the prompt and payload, print it, send nothing")
    _add_common(p_dry)
    p_dry.add_argument("--json", action="store_true")

    p_run = sub.add_parser("run", help="create the video task, poll it, download the mp4")
    _add_common(p_run)
    p_run.add_argument("-o", "--out", default="out/character.mp4")
    p_run.add_argument("--api-key", default=None)

    p_self = sub.add_parser("selftest", help="verify key + endpoint paths against the live API")
    p_self.add_argument("--api-key", default=None)

    args = parser.parse_args(argv)

    if args.command == "cards":
        folder = Path(args.folder)
        found = sorted(list(folder.glob("*.png")) + list(folder.glob("*.json")))
        if not found:
            print(f"no .png/.json cards in {folder}")
            return 1
        for path in found:
            try:
                print(f"{path.name}: {summarise(load_card(path))}")
            except Exception as exc:  # noqa: BLE001 - keep going through the folder
                print(f"{path.name}: SKIP ({exc})")
        return 0

    if args.command == "dry-run":
        card = load_card(args.card)
        prompt = build_prompt(card, args.camera, args.scene, args.line, args.duration)
        image = _resolve_image(args.card, args.image)
        payload = build_payload("kling-4.0", prompt, image_payload(image), args.duration, args.aspect)
        payload["image"] = payload["image"][:80] + "...(base64 truncated)"
        if args.json:
            print(json.dumps({"card": card.to_dict(), "prompt": prompt, "payload": payload}, indent=2))
        else:
            print(f"card    : {summarise(card)}")
            print(f"prompt  : {prompt}\n")
            print("payload :")
            print(json.dumps(payload, indent=2))
        return 0

    if args.command == "selftest":
        client = VideoClient.from_env(args.api_key)
        if not client.api_key:
            print("GPTPROTO_API_KEY is not set (put it in .env)")
            return 2
        print(f"base_url    : {client.base_url}")
        print(f"create_path : {client.create_path}")
        print(f"query_path  : {client.query_path}")
        print(f"model       : {client.model}")
        try:
            # A deliberately tiny request: 3s, no reference image.
            task_id = client.create(
                {"model": client.model, "prompt": "test pattern, plain gradient", "duration": 3}
            )
            print(f"\ncreate OK -> task {task_id}")
            print("now polling once (Ctrl-C is safe, the task keeps running server-side)")
            url = client.poll(task_id)
            print(f"poll OK   -> {url}")
        except Exception as exc:  # noqa: BLE001 - selftest reports, never raises
            print(f"\nselftest FAILED: {type(exc).__name__}: {exc}")
            print(
                "\nIf this is a 404, the path in your account's API reference differs:\n"
                "  set GPTPROTO_VIDEO_CREATE_PATH / GPTPROTO_VIDEO_QUERY_PATH in .env\n"
                "  reference: https://docs.gptproto.com (Kling -> gptproto-format)"
            )
            return 1
        return 0

    if args.command == "run":
        card = load_card(args.card)
        prompt = build_prompt(card, args.camera, args.scene, args.line, args.duration)
        client = VideoClient.from_env(args.api_key)
        if not client.api_key:
            print("GPTPROTO_API_KEY is not set (put it in .env)")
            return 2

        print(f"card  : {summarise(card)}")
        print(f"model : {client.model}")
        image = _resolve_image(args.card, args.image)
        task_id = client.create(
            build_payload(client.model, prompt, image_payload(image), args.duration, args.aspect)
        )
        print(f"task  : {task_id}")
        url = client.poll(task_id)
        out = client.download(url, args.out)
        print(f"saved : {out}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
