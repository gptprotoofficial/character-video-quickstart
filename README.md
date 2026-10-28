# character-video-quickstart

Turn a SillyTavern character card into a short video clip with one command — and rebuild a 30-second AI ad from 12 open prompts. One API, any video model.

![30-second soda ad — six generated clips](docs/preview.gif)

**▶ Watch the full 30-second film on TikTok:**
https://www.tiktok.com/@bestgptproto/video/7701614456182164767

The moving preview above is cut from that film. Every prompt behind it — 6
text-to-image keyframes, 6 image-to-video clips, the timeline variant and the
VO script — lives in
**[`prompts/ad_30s_gptproto.md`](prompts/ad_30s_gptproto.md)**, with the
reference stills in [`prompts/assets/`](prompts/assets/). Clone it, add your
key, make your own version.

---

*Everything below documents the character-card tooling.*

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

$ python -m character_video run ./cards/mira.png \
    --image-url https://your-host/mira.png -o out/mira.mp4
card  : Mira (original character, roleplay)
model : kling-4.0
image : https://your-host/mira.png
task  : 943646625628160600
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

3. Verify the key and the endpoint paths - this costs nothing:

```bash
python -m character_video selftest
```

It makes three plain GETs: the key (`/v1/models`), the create route, and the query
route. A `404` means the path is wrong; any other status means the route exists.
Nothing is created and nothing is billed. Add `--spend` to also submit one real
3-second task and watch the whole chain end to end.

4. Generate the clip:

```bash
python -m character_video run ./cards/mira.png \
  --image-url https://your-host/mira.png \
  -o out/mira.mp4 --camera push-in --duration 5
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
3. Put that PNG somewhere public and run:

```bash
python -m character_video run ./cards/<name>.png \
  --image-url https://your-host/<name>.png -o out/<name>.mp4
```

4. The output is a 9:16 clip you can drop back into your character's gallery,
   or post as a character reveal.

Because the reference image is the card itself, faces stay consistent between
the still card and the clip - no re-describing, no drift between prompts. That is
also why the image has to be a real URL: the card art is the anchor.

## Endpoints and models

Verified against the live API on 2026-10-26:

```
create   POST https://gptproto.com/api/v3/kwaivgi/{model}/reference-to-video
query    GET  https://gptproto.com/api/v3/predictions/{task_id}/result
auth     Authorization: <api key>        # no "Bearer " prefix
```

The model id is part of the **create path**, not the request body:

```
GPTPROTO_BASE_URL          https://gptproto.com
GPTPROTO_VIDEO_CREATE_PATH /api/v3/kwaivgi/{model}/reference-to-video
GPTPROTO_VIDEO_QUERY_PATH  /api/v3/predictions/{task_id}/result
GPTPROTO_MODEL             kling-4.0
```

A create response carries the task id; a finished task carries the file:

```json
{"code": 200, "data": {"id": "9436...", "status": "processing",
                       "outputs": [], "error": null}}
{"code": 200, "data": {"id": "9436...", "status": "completed",
                       "outputs": ["https://oss-us.gptproto.com/.../clip.mp4"]}}
```

`status` is one of `processing` / `completed` / `failed`. Poll until it leaves
`processing`. If your account's reference lists different paths, override them in
`.env` - no code changes needed.

## Reference images must be URLs

The endpoint takes `"images": ["https://..."]` - a list of **publicly reachable
URLs**. There is no file-upload endpoint, so a local PNG cannot be sent as-is.

- `--image-url https://...` is the documented path and always works.
- `--image ./cards/mira.png` is still accepted: the file is inlined as a `data:`
  URL. That form is **not in the reference**, so if the task comes back `failed`
  with an image error, host the file and switch to `--image-url`.

Anything works as hosting: your own S3 bucket, a CDN, GitHub raw, or the
`oss.gptproto.com` URLs the API reference uses in its examples.

## Cost and failure behaviour

- A **failed task still counts as one request**. The model was called, the bill
  was written; you do not get the request back.
- `run` therefore does **not** auto-retry a failed task. It retries only
  transport-level errors (timeout, 429, 5xx) with exponential backoff and jitter.

- Billing is per second of generated video and varies by model and resolution.
  Check the model page for the current rate before a batch run - prices move.
- Billable durations follow the tiers listed on the model page (3 / 5 / 10 / 30 s
  for 720p). `--duration` is passed through as-is, so stick to a listed tier.
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
prompts/
  ad_30s_gptproto.md   30s soda ad reproduction pack (12 prompts + timeline)
  assets/              the six reference keyframes, in ad order
```

## Make this ad yourself

We turned 12 prompts into a 30-second soda commercial (a fictional brand — gptproto cola does not exist). Every prompt is in the repo:

- **Prompts:** [`prompts/ad_30s_gptproto.md`](prompts/ad_30s_gptproto.md) — 6 text-to-image keyframe prompts, 6 image-to-video clip prompts, a single-generation 30s timeline variant, the VO script, and consistency locks
- **Reference keyframes:** [`prompts/assets/`](prompts/assets/) — the six stills this pack reproduces, in ad order

Three steps:

1. **Verify your key** (free):

```bash
python -m character_video selftest
```

2. **Generate the six clips** — send the 6 keyframe prompts to a text-to-image model, then animate each still with a seedance image-to-video call (`doubao-seedance-2-0-260128`, 9:16, 5s, 720p). The exact cURL calls are at the bottom of the prompt pack.

3. **Stitch** — concat the six 5s clips with ffmpeg (command included in the pack), add the VO script and SFX markers, grade with one LUT.

Consistency rules (same bottle, same grade, same characters across all six shots) are written into every prompt — copy them verbatim or the six clips will not cut together as one film.

## Roadmap

- [ ] Multi-keyframe direction (first frame + last frame)
- [ ] Optional generated voice line from the card's `first_mes`
- [ ] Batch mode with a per-card prompt override file
- [ ] Backend adapter interface so the same pipeline works with other video APIs

## License

MIT
