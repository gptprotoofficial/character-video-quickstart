"""Command line entry point.

Usage
-----
    python -m character_video cards ./cards             # inspect cards, no API call
    python -m character_video dry-run card.png          # print the request, no API call
    python -m character_video selftest                  # check key + paths, no cost
    python -m character_video selftest --spend          # also run one real 3s task
    python -m character_video run card.png -o out.mp4   # create -> poll -> download
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .card import load_card
from .gptproto import VideoClient, build_payload, is_url, resolve_image
from .prompt import build_prompt, summarise


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def _load_dotenv() -> None:
    """Read .env from the cwd or the repo root. Keeps python-dotenv out of deps."""
    for base in (Path.cwd(), Path(__file__).resolve().parent.parent):
        env = base / ".env"
        if not env.is_file():
            continue
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip().strip('"').strip("'")
        return


def _resolve_reference(card_path: str, image: str | None, image_url: str | None) -> str:
    """Return the value that goes into `images`: a public URL or a local file."""
    if image_url:
        if not is_url(image_url):
            raise SystemExit("--image-url must start with http:// or https://")
        return image_url
    if image:
        return image
    if Path(card_path).suffix.lower() in IMAGE_SUFFIXES:
        return card_path
    raise SystemExit(
        f"{card_path} is a JSON card, so there is no reference image in it.\n"
        "Pass one of:\n"
        "  --image-url https://...   (recommended, the API expects a URL)\n"
        "  --image ./cards/mira.png  (sent as a data URL)"
    )


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("card", help="path to a character card (.png or .json)")
    p.add_argument("--image", default=None, help="reference image: local path or URL (defaults to the card PNG)")
    p.add_argument("--image-url", default=None, help="public URL of the reference image (recommended)")
    p.add_argument("--camera", default="push-in", choices=["push-in", "orbit", "static", "handheld"])
    p.add_argument("--scene", default=None, help="override the card scenario in the prompt")
    p.add_argument("--line", default=None, help="optional spoken line (audio-capable models)")
    p.add_argument("--duration", type=int, default=5, choices=[3, 4, 5, 6, 7, 8, 9, 10],
                   help="clip length in seconds (the endpoint bills per second)")
    p.add_argument("--aspect", default="9:16", choices=["9:16", "16:9", "1:1"])
    p.add_argument("-v", "--verbose", action="store_true")


def _masked(payload: dict) -> dict:
    """Keep dry-run readable: data URLs are thousands of characters."""
    shown = dict(payload)
    images = shown.get("images")
    if images:
        shown["images"] = [img[:64] + "...(truncated)" if img.startswith("data:") else img for img in images]
    return shown


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
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

    p_self = sub.add_parser("selftest", help="verify key + endpoint paths (costs nothing unless --spend)")
    p_self.add_argument("--api-key", default=None)
    p_self.add_argument("--spend", action="store_true", help="also submit one real 3s task (billed)")

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
        reference = _resolve_reference(args.card, args.image, args.image_url)
        payload = build_payload(prompt, resolve_image(reference), args.duration, args.aspect)
        if args.json:
            print(json.dumps({"card": card.to_dict(), "prompt": prompt, "payload": _masked(payload)}, indent=2))
        else:
            print(f"card    : {summarise(card)}")
            print(f"prompt  : {prompt}\n")
            print("payload :")
            print(json.dumps(_masked(payload), indent=2))
        return 0

    if args.command == "selftest":
        client = VideoClient.from_env(args.api_key)
        if not client.api_key:
            print("GPTPROTO_API_KEY is not set (put it in .env)")
            return 2

        print(f"base_url    : {client.base_url}")
        print(f"create_path : {client.create_path.format(model=client.model)}")
        print(f"query_path  : {client.query_path.format(task_id='<id>')}")
        print(f"model       : {client.model}\n")

        failures = 0

        status, text = client.list_models()
        if status == 200:
            print(f"[1/3] api key      OK      GET /v1/models -> 200")
        else:
            failures += 1
            print(f"[1/3] api key      FAIL    GET /v1/models -> {status} | {text[:120]}")

        status, text = client.probe(client.create_path.format(model=client.model))
        if status == 404:
            failures += 1
            print(f"[2/3] create path  FAIL    GET -> 404, path does not exist | {text[:120]}")
        elif status == 0:
            failures += 1
            print(f"[2/3] create path  FAIL    no response | {text[:120]}")
        else:
            print(f"[2/3] create path  OK      GET -> {status} (route exists; POST only)")

        status, text = client.probe(client.query_path.format(task_id="probe0"))
        if status == 404:
            failures += 1
            print(f"[3/3] query path   FAIL    GET -> 404, path does not exist | {text[:120]}")
        elif status == 0:
            failures += 1
            print(f"[3/3] query path   FAIL    no response | {text[:120]}")
        else:
            print(f"[3/3] query path   OK      GET -> {status} (route exists)")

        if failures:
            print(
                f"\n{failures} check(s) failed. If the paths are 404, your account's reference differs:\n"
                "  set GPTPROTO_VIDEO_CREATE_PATH / GPTPROTO_VIDEO_QUERY_PATH in .env\n"
                "  reference: https://docs.gptproto.com -> Kling -> gptproto-format"
            )
            return 1

        if not args.spend:
            print("\nKey and paths look right. Nothing was created and nothing was billed.")
            print("Re-run with --spend to submit one real 3-second task and see the whole chain.")
            return 0

        print("\n--spend: submitting one real 3-second task. This IS billed.")
        try:
            task_id = client.create(build_payload("test pattern, plain gradient", None, 3, "9:16"))
            print(f"create OK -> task {task_id}")
            url = client.poll(task_id)
            print(f"poll OK   -> {url}")
        except Exception as exc:  # noqa: BLE001 - selftest reports, never raises
            print(f"\nselftest FAILED: {type(exc).__name__}: {exc}")
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
        reference = _resolve_reference(args.card, args.image, args.image_url)
        image = resolve_image(reference)
        if image.startswith("data:"):
            print("image : local file -> data URL (if the task fails on the image, host it and use --image-url)")
        else:
            print(f"image : {image}")

        task_id = client.create(build_payload(prompt, image, args.duration, args.aspect))
        print(f"task  : {task_id}")
        url = client.poll(task_id)
        out = client.download(url, args.out)
        print(f"saved : {out}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
