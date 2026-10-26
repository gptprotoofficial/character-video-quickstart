# character-video-quickstart

Turn a SillyTavern character card into a short video clip with one command.

Reads a character card (PNG or JSON), takes the card image as the reference frame,
builds a motion prompt from the card fields, submits a reference-to-video task to
the Kling 4.0 API, polls until it finishes, and saves the `.mp4`.

```
card.png  ->  prompt  ->  reference-to-video task  ->  poll  ->  out.mp4
```

## Why this exists

Most character-video snippets assume you already have a prompt. Roleplay users
already have something better: a character card that describes the face, the
outfit, the setting and the tone. This tool reads that card instead of asking you
to re-describe your own character.

## Demo

```
$ python -m character_video cards ./cards
mira.png: Mira (original character, roleplay) - A calm night-shift librarian with silver hair...

$ python -m character_video run ./cards/mira.png -o out/mira.mp4
card  : Mira (original character, roleplay)
task  : task_8f21c...
saved : out/mira.mp4
```

## Quick start

```bash
git clone https://github.com/<your-org>/character-video-quickstart.git
cd character-video-quickstart
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # then put your key in .env
```

1. Check the card parses correctly - no API call, no cost:

```bash
python -m character_video cards ./cards
```

2. Preview the exact prompt and request body that will be sent:

```bash
python -m character_video dry-run ./cards/mira.png
```

3. Verify the key and the endpoint paths against the live API:

```bash
python -m character_video selftest
```

4. Generate the clip:

```bash
python -m character_video run ./cards/mira.png -o out/mira.mp4 --camera push-in --duration 5
```

## What the prompt looks like

The card supplies the look and the mood; the tool writes only the motion:

```
The character from the reference image, keeping her exact face, hair, outfit and
art style unchanged. Subtle idle motion only: breathing, hair and fabric moving
slightly, eyes blinking naturally, head turning a few degrees toward the camera.
Slow cinematic push-in. Soft rim light, shallow depth of field.
Setting: A rain-soaked reading room at 2am, one desk lamp on.
Performance note (do not render as text): Warm, precise, quietly teasing.
no text, no captions, no subtitles, no watermark, no logo, no UI elements
```

Camera presets: `push-in` (default), `orbit`, `static`, `handheld`.

## Supported cards

- PNG character cards exported from SillyTavern (V2 `chara` or V3 `ccv3` chunk)
- Plain JSON cards, V1 flat or V2 wrapped in `{"data": {...}}`

Fields used: `name`, `description`, `personality`, `scenario`, `first_mes`,
`appearance` (falls back to `description`), `tags`.

## Using it inside a SillyTavern workflow

1. In SillyTavern: **Card -> Export as PNG** for the character you want to animate.
2. Drop the PNG into `./cards/`.
3. Run `python -m character_video run ./cards/<name>.png -o out/<name>.mp4`.
4. The output is a 9:16 clip you can drop back into your character's gallery,
   or post as a character reveal.

Because the reference image is the card itself, faces stay consistent between
the still card and the clip - no re-describing, no drift between prompts.

## Endpoints and models

Paths follow the video API reference (provider -> `gptproto-format` ->
`image-to-video`). Defaults:

```
GPTPROTO_BASE_URL           https://gptproto.com/v1
GPTPROTO_VIDEO_CREATE_PATH  /videos/generations
GPTPROTO_VIDEO_QUERY_PATH   /videos/generations/{task_id}
GPTPROTO_MODEL              kling-4.0
```

If your account's reference lists different paths, override them in `.env` - no
code changes needed. `python -m character_video selftest` prints the raw request
and the raw response, which is the fastest way to see whether a 404 is a path
mismatch or a key problem.

## Cost and failure behaviour

- A **failed task still counts as one request**. The model was called, the bill
  was written; you do not get the request back.
- `run` therefore does **not** auto-retry a failed task. It retries only
  transport-level errors (timeout, 429, 5xx) with exponential backoff and jitter.
- A 5-second 720p clip costs roughly 【官网实测价】 at the time of writing. Check
  the model page for the current per-second rate before batch runs.
- Batch tip: run `dry-run` on the whole folder first, then generate one clip
  before committing to a batch.

## Project layout

```
character_video/
  card.py      parse PNG/JSON cards, extract the reference image
  prompt.py    card fields -> motion prompt, camera presets
  gptproto.py  create task, poll, download, tolerant response parsing
  retry.py     backoff + jitter, transport errors only
  cli.py       cards / dry-run / selftest / run
```

## Roadmap

- [ ] Multi-keyframe direction (first frame + last frame)
- [ ] Optional generated voice line from the card's `first_mes`
- [ ] Batch mode with a per-card prompt override file
- [ ] Backend adapter interface so the same pipeline works with other video APIs

## License

MIT
