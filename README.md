# Heritage Short

A pipeline that turns one file, `storyboard.json`, into a 60–90 second narrated, scored and subtitled short film, in vertical (9:16) and horizontal (16:9). Every model call is logged, and every artefact is cached by a hash of its inputs, so changing one shot regenerates only that shot.

```
storyboard.json ──► narration ──► keyframes ──► shots ──► music ──► assemble ──► outputs/film/*.mp4
 (validated)        Gemini TTS    FLUX on       Wan 2.2 on  ACE-Step on   FFmpeg
                                  Cloudflare    Kaggle /    Kaggle /      (duck, subtitles,
                                                Ken Burns   placeholder   loudness, end card)
```

## Run it

```bash
git clone <this repo> && cd heritage-short
python -m venv .venv
.venv\Scripts\activate          # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env            # then paste your Gemini and Cloudflare keys into .env

python run.py smoke             # one call per provider; shows which model ids your account can use
python run.py film              # the whole pipeline -> outputs/film/film_9x16_*.mp4, film_16x9_*.mp4
```

`make film` does the same on machines that have `make`. FFmpeg does not need to be installed: if it is not on your PATH, the pipeline uses the static build that ships with `imageio-ffmpeg`.

### Other commands

| Command | What it does |
|---|---|
| `python run.py radio` | Narration and score over black, with subtitles (the first user-test prototype) |
| `python run.py film --placeholders` | Runs every stage with no API calls (silent timing, drawn keyframes), to test the plumbing |
| `python run.py narration --only s03` | Re-runs one stage for one shot |
| `python run.py script --story story.md` | Gemini drafts `storyboard.draft.json` from your notes. It never overwrites the real storyboard. |
| `python run.py shots` | Writes `outputs/kaggle/jobs.json` for shots marked `"video": "wan"` |
| `python run.py import-kaggle` | Merges the GPU logs from Kaggle into `runs.jsonl` |
| `python run.py compose` | Writes the fallback score candidates (code-composed, tizita scale) into `outputs/music/candidates/` |
| `python run.py costs` | Per-stage table of calls, failures, latency, units and list price, from `runs.jsonl` |
| `python run.py validate` | Checks the storyboard against `schema/storyboard.schema.json`, plus cross-references |

### GPU stages (Kaggle)

Wan 2.2 and ACE-Step need a GPU, so they run on Kaggle, not on this machine.

- **Music:** `python run.py music` writes `outputs/kaggle/acestep_heritage.ipynb`, a self-contained notebook with the storyboard's music cues built in. On kaggle.com: New Notebook → File → Import Notebook → GPU T4, Internet on → Run All → download `results.zip`. Unzip `music/*.wav` into `outputs/music/candidates/` and `ace_runs.jsonl` into `outputs/kaggle/`, run `python run.py import-kaggle`, then set `music.chosen` in the storyboard.
- **Video:** `notebooks/wan22_kaggle.py` (see FAILURES F4 for why the final film uses Ken Burns moves instead). Until a clip exists for a shot, the edit uses a Ken Burns move over its keyframe. Until a score candidate is chosen, it uses a synthesised placeholder drone. The film always builds.

## Change one shot (the walkthrough demo)

1. Edit one shot's `image_prompt` (or `narration`) in `storyboard.json`. Prefer the image prompt: Gemini TTS allows only 10 calls/day per model on the free tier.
2. Run `python run.py film`.
3. The log shows `cached` for every other shot, and `runs.jsonl` gains one new line for that shot.

## What it costs

On free tiers, $0. Measured latency, GPU minutes and list-price equivalents are in [COSTS.md](COSTS.md).

## Repository map

| Path | Purpose |
|---|---|
| `storyboard.json` | The contract: shots, prompts, seeds, narration, subtitles, music cues |
| `schema/` | JSON Schema, validated before every run |
| `pipeline/` | One script per stage, plus `common.py` (logging, caching, retries, FFmpeg) and `providers.py` (HTTP clients) |
| `notebooks/` | Kaggle GPU jobs for Wan 2.2 and ACE-Step |
| `runs.jsonl` | One line per model call: model, params, seed, latency, units, cost |
| `outputs/` | Generated narration, keyframes and logs, named `<shot>_<input-hash>`. Films and score WAVs are **not** in git (too large to push); `python run.py film` rebuilds them, and the score is recomposed automatically. The finished films are linked in the submission. |
| [DESIGN.md](DESIGN.md) | Audience, intent, both user tests and what they changed |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Stages, contracts, caching, failure handling |
| [EXPERIMENTS.md](EXPERIMENTS.md) | Hypothesis → change → result |
| [FAILURES.md](FAILURES.md) | What broke and what fixed it |
| [COSTS.md](COSTS.md) | Latency, GPU minutes and price per stage |
| [ETHICS.md](ETHICS.md) | Consent, licences, labelling |
