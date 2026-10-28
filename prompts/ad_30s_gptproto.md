# 30-Second Soda Commercial — Complete Prompt Reproduction Pack

We made a 30-second cola commercial with AI: 6 text-to-image prompts for the keyframes, 6 image-to-video prompts to animate them, and the commands that glue it all together. Clone, add your key, and make your own version.

**Reference output** — the six keyframes this pack reproduces are in [`assets/`](assets/), in ad order:

| Shot | Keyframe | Role in the film |
|---|---|---|
| 1 | `shot1-hook-label-macro.jpg` | Hook (0–3s): macro of the cold bottle, condensation and bubbles |
| 2 | `shot2-corner-store-dusk.jpg` | Story (3–12s): grandpa's corner store at dusk |
| 3 | `shot3-the-handover.jpg` | Story: he hands her the first bottle of the day |
| 4 | `shot4-rooftop-sunset.jpg` | Emotion (12–22s): rooftop, city sunset, one sip |
| 5 | `shot5-cap-burst.jpg` | Burst (22–30s): cap twists off, slow-motion spray |
| 6 | `shot6-endcard-product.jpg` | End card: clean product shot, headroom for the logo |

> **Fictional brand.** "gptproto cola" is a made-up brand for this demo film — it is not a real product and this is not a real commercial. One prop warning from our own run: the generation likes to paste real soda brands onto background props (our first corner-store cooler came back with a famous trademark on it). The prompts below explicitly block that — keep those lines if you re-generate.

## Pipeline

```
text-to-image  x6  ->  6 keyframes (9:16)
image-to-video x6  ->  6 clips x 5s (9:16, 720p or 1080p)
concat + VO + SFX  ->  30s film
```

Models used (slugs as they appear in the GPT Proto docs):

- Keyframes: any strong text-to-image model on the platform (we used the built-in generator; the prompts are model-agnostic)
- Video: `doubao-seedance-2-0-260128`, image-to-video, `aspect_ratio: 9:16`, `duration: 5`, `resolution: 720p` (1080p also works)
- The video API is asynchronous: submit, poll `GET /api/v3/predictions/{id}/result`, download the mp4 — the same submit/poll/download loop the `character_video` package in this repo implements

Note on naming: the storefront may advertise a newer Seedance generation than the docs slug above. Use whichever image-to-video slug your model page lists; the prompts do not change. Duration range for this slug is 4–15s per generation — if a future model supports a single 30s multi-shot run, use the timeline version at the bottom; otherwise keep the 6x5s segments (this is the tested path).

## Consistency rules (apply to every prompt)

These are what keep six independent generations looking like one film. Copy them verbatim into each prompt:

- **Bottle lock:** classic contoured glass cola bottle, deep red label, white lowercase serif wordmark `gptproto`, red crown cap
- **Style lock:** shot on 35mm film, warm golden-hour color grade, soft film grain, nostalgic summer mood, 9:16 vertical
- **Character locks:** elderly shop owner — white hair, canvas apron; young woman — early twenties, black hair, white t-shirt, blue jeans
- **Light lock:** single warm key light (tungsten indoors, low sun outdoors), no cool tones anywhere
- **Trademark guard:** no real-world brand logos, unbranded props and packaging, no legible text except the bottle wordmark

**Negative prompt (all six images):**

```
real brand logos, trademark text, garbled letters, watermark, extra fingers, deformed hands, warped faces, cartoon, oversaturated colors, cool color cast, modern glass building interiors
```

---

## Part 1 — Text-to-image prompts (6 keyframes)

### IMG-1 · Hook — label macro

```text
Vertical 9:16 product shot. Extreme close-up of a glass cola bottle with a deep red label and white lowercase serif wordmark "gptproto", covered in condensation droplets, ice cubes around the base, sharp carbonation bubbles rising inside, warm golden sunset backlight, sea horizon soft in the background, shot on 35mm film, shallow depth of field, nostalgic summer mood, cinematic color grade, no people.
```

### IMG-2 · Grandpa's corner store at dusk

```text
Vertical 9:16 cinematic still. A cozy old corner store at dusk, warm tungsten light glowing from the open doorway, an elderly shop owner with white hair and a canvas apron standing behind the counter wiping a glass, wooden shelves crowded with unbranded glass bottles, an unbranded vintage red soda cooler glowing in the corner, a dog asleep on the doorstep, warm golden hour tones, shot on 35mm film, film grain, nostalgic summer mood.
```

### IMG-3 · The handover

```text
Vertical 9:16 cinematic still. Inside the corner store, the elderly shop owner with white hair and a canvas apron smiles as he hands a cold glass cola bottle (deep red label, white lowercase serif "gptproto") to a young woman in her early twenties with black hair and a white t-shirt, she reaches for it with both hands, condensation on the glass, unbranded vintage red cooler behind her, warm tungsten light, shot on 35mm film, shallow depth of field, consistent characters, nostalgic summer mood.
```

### IMG-4 · Rooftop at sunset

```text
Vertical 9:16 cinematic still. The same young woman (early twenties, black hair, white t-shirt, blue jeans) sits on a rooftop ledge at sunset holding the glass cola bottle with the deep red "gptproto" label, city skyline in warm haze behind her, wind in her hair, golden rim light, potted plants beside her, shot on 35mm film, nostalgic summer mood, cinematic color grade.
```

### IMG-5 · Cap burst

```text
Vertical 9:16 macro shot. A hand twists the red crown cap off a glass cola bottle with a deep red "gptproto" label, fine spray of soda mist and carbonation bubbles exploding upward, droplets frozen mid-air, backlit by warm sunset light with a hazy city skyline behind, shot on 35mm film, high-speed photography look, dramatic and refreshing.
```

### IMG-6 · End card — product shot

```text
Vertical 9:16 clean product photography. A glass contoured cola bottle standing on crushed ice, deep red label with white lowercase serif "gptproto" wordmark, red crown cap, water droplets on the glass, soft studio lighting with a warm key light, clean cream-colored background with generous empty space at the top for a logo, minimalist commercial style.
```

---

## Part 2 — Image-to-video prompts (6 clips x 5s)

Upload each keyframe as the first-frame image, then animate. Same submit/poll/download flow as `quickstart.py`. Every clip: `aspect_ratio 9:16`, `duration 5`, `resolution 720p`.

### CLIP-1 (from IMG-1)

```text
The camera drifts slowly sideways around the cold glass bottle as condensation droplets slide down the glass and carbonation bubbles rise steadily, ice cubes shifting subtly, the warm sunset backlight flaring gently through the glass. Slow cinematic drift, shallow depth of field. Label stays sharp and legible, no morphing, no text artifacts, natural liquid physics.
```

### CLIP-2 (from IMG-2)

```text
Dusk light flickers softly as the elderly man wipes a glass with a cloth behind the counter, then looks up toward the door with a warm smile; a ceiling fan spins slowly overhead; the cooler light glows; the dog on the doorstep barely stirs. Static camera with a very slow push-in, warm film grain. Keep face consistent, no morphing, no extra people, cooler stays unbranded.
```

### CLIP-3 (from IMG-3)

```text
The old man hands the cold bottle to the young woman; she takes it with both hands, smiles and looks down at the bottle; condensation drips; warm tungsten light breathes softly. Gentle handheld feel, medium shot, slight rack focus from his face to the bottle. Characters stay consistent, hands natural with five fingers, no morphing, cooler stays unbranded.
```

### CLIP-4 (from IMG-4)

```text
The young woman takes a sip from the bottle, closes her eyes and smiles as the sunset light flares behind the skyline, her hair moving in the breeze. Slow lateral dolly right to left, golden rim light pulsing softly. Face consistent with the reference frame, no warping, natural hair physics.
```

### CLIP-5 (from IMG-5)

```text
The cap twists off and the soda sprays upward in fine mist, bubbles bursting in slow motion, droplets catching the warm backlight, the bottle rocking slightly from the twist. High-speed slow-motion look, macro lens, dramatic and refreshing. Liquid physics accurate, label stays sharp, no text artifacts.
```

### CLIP-6 (from IMG-6)

```text
Fine bubbles rise inside the bottle as a slow push-in reveals the full bottle on crushed ice; light glints across the glass; the frame settles with clean space above for the end-card logo. Smooth slow push-in, studio-soft lighting. Label stays static and legible, no morphing, no added text.
```

---

## Part 3 — Single-generation 30s timeline (optional)

Some video models accept a multi-shot timeline in one prompt. If your slug supports a 30s run, this is the single-prompt version of the same film. If it doesn't (the documented slug above generates 4–15s), stay with the 6x5s path — it is the tested one.

```text
Vertical 9:16 cinematic cola commercial, 30 seconds, 6 sequential shots, warm 35mm film look throughout, consistent characters (elderly shop owner with white hair and canvas apron; young woman, early twenties, black hair, white t-shirt), glass cola bottle with a deep red "gptproto" label appears in every shot, all props unbranded.
[0-5s]   Macro: condensation and rising bubbles on the cold bottle, slow drift.
[5-10s]  Corner store at dusk, old man wipes a glass, dog asleep on the step, slow push-in.
[10-15s] He hands the bottle to the young woman, she smiles, rack focus to the bottle.
[15-20s] Rooftop at sunset, she sips and closes her eyes, slow lateral dolly.
[20-25s] Cap twists off, soda mist sprays in slow motion, backlit by the sunset.
[25-30s] Bottle on crushed ice, slow push-in, clean space for the logo.
Restrictions: no text overlays, no morphing faces, accurate liquid physics, no extra characters, no real brand logos anywhere, smooth film-grain color grade, nostalgic summer mood.
```

---

## Voice-over and edit notes

English VO (record or TTS; pauses matter):

```
[0-3s]   Grandpa ran the corner store ... for forty years.
[3-12s]  Every summer, the cooler hummed, and he always saved me the first gptproto of the day.
[12-22s] Same rooftop. Same sunset. Some things don't need an update.
[22-30s] gptproto. One prompt. One sip.
```

- Hard-cut the 6 clips in order; a few slowed frames of CLIP-1 (played backwards = falling bubbles) work as a breather between CLIP-4 and CLIP-5
- Sound: ice clink at 0s, the cap "psshh" at 22s (the memory hook), low-end button at 28s
- Grade all 6 clips with the same warm LUT + light film grain to hide generation-to-generation drift
- End card text: `gptproto — One prompt. One sip.`
- If you publish this: label it as AI-generated (required on TikTok/IG), and keep the fictional-brand note — gptproto cola does not exist

## Run it against the API

Zero-cost key check first (lists models, generates nothing):

```bash
python -m character_video selftest
```

Then generate, one clip at a time. The `run` command in this repo targets
reference-to-video; the cola ad uses seedance image-to-video, so the raw calls
are simplest:

```bash
export GPTPROTO_API_KEY=sk-your-key-here   # or source your .env

# submit an image-to-video job (first frame = your keyframe URL)
curl -X POST "https://gptproto.com/api/v3/bytedance/doubao-seedance-2-0-260128/image-to-video" \
  -H "Authorization: $GPTPROTO_API_KEY" -H "Content-Type: application/json" \
  -d '{"prompt": "<CLIP-N prompt from above>", "image": "<IMG-N keyframe URL>",
       "aspect_ratio": "9:16", "duration": "5", "resolution": "720p"}'

# poll until done, then download the mp4 from data.outputs
curl "https://gptproto.com/api/v3/predictions/<id>/result" -H "Authorization: $GPTPROTO_API_KEY"

# stitch
ffmpeg -i clip1.mp4 -i clip2.mp4 -i clip3.mp4 -i clip4.mp4 -i clip5.mp4 -i clip6.mp4 \
  -filter_complex "[0:v][1:v][2:v][3:v][4:v][5:v]concat=n=6:v=1[outv]" \
  -map "[outv]" ad_30s.mp4
```

Pricing is per second of generated video and varies by model and resolution — check the model page for the current number. Failed generations may still be billed, so budget for retries: the failure rate, not the per-second price, is the real cost driver.
