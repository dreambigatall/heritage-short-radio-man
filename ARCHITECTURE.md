# Architecture

## One contract, five stages

`storyboard.json` is the only input that describes the film. It is validated against `schema/storyboard.schema.json` (JSON Schema 2020-12) and then against rules a schema cannot express (unique shot ids, characters and music cues that exist, a `motion_prompt` for every `wan` shot, an English subtitle for every narrated line). If validation fails, nothing runs.

| Stage | Reads | Writes | Runs on |
|---|---|---|---|
| `script` (optional) | `story.md` and the schema | `storyboard.draft.json` (never the real file) | Gemini text API |
| `narration` | `voice`, `language`, `shots[].narration` | `outputs/narration/<shot>_<hash>.wav` and `manifest.json` | Gemini TTS API |
| `keyframes` | `style`, `models`, `characters`, `shots[].image_prompt/seed` | `ref_<character>_<hash>.png`, then `<shot>_<hash>.png` | Cloudflare Workers AI |
| `shots` | the keyframe manifest, `shots[].video/motion_prompt/camera` | the shot manifest (clip or Ken Burns), `outputs/kaggle/jobs.json` | local; Wan 2.2 runs on Kaggle |
| `music` | `music.cues`, `music.chosen` | `outputs/kaggle/music_jobs.json`, the music manifest | local; ACE-Step runs on Kaggle |
| `assemble` | all the manifests | `outputs/edit/*`, `outputs/film/*.mp4` and `.srt` | FFmpeg, local |

Stages talk to each other only through files: the storyboard going in, and a `manifest.json` per stage coming out. Each manifest maps a shot id to its current artefact. Any stage can be re-run on its own, and `--only s03` limits a stage to particular shots.

## Caching

Every artefact is named `<shot>_<hash>`, where the hash is the SHA-256 of the exact inputs that produced it:

- **Narration:** TTS model, voice, style instruction, language, text.
- **Keyframe:** image model, steps, size, the full prompt (character description and style block included), seed, and the reference images used.
- **Clip:** keyframe hash, motion prompt, seed, and the Wan settings.
- **Segment / mix:** source file, camera move, frame count, resolution.

If the file already exists, the stage skips the call. Editing one shot's narration therefore makes one TTS call, re-renders only that shot's segment, and rebuilds the cheap concat and mix. A keyframe change invalidates that shot's Wan clip automatically, because the clip hash includes the keyframe hash. `--force` ignores the cache.

## Timing

The narration sets the pace, as it does in a professional cut. Each shot lasts `max(duration_s, lead + narration length + pad)`, rounded to whole frames. Subtitles are timed from the same numbers. They are wrapped to 40 characters (30 in vertical) with at most two lines per cue, and kept above the bottom 16% of the vertical frame, where phone UI sits.

## Sound

1. The narration WAVs are placed on a timeline (`adelay` + `apad` + `atrim`, then `concat`).
2. The score is looped and trimmed to length, set to `music_gain_db`, and faded in and out.
3. Ducking: `sidechaincompress=threshold=0.02:ratio=6:attack=300:release=1500`, with the voice as the sidechain.
4. Voice and ducked score are mixed, then `loudnorm=I=-14:TP=-1:LRA=11`. The result is measured with `ebur128` and written to `outputs/edit/timeline_*.json`.

## Picture

- **Ken Burns:** the square keyframe is cropped to the target aspect, upscaled 3× (so zoompan's integer steps don't jitter), then `zoompan` applies a push-in, pull-out, pan or tilt.
- **Clips:** the first 0.25 s (often weak) is trimmed, the clip is slowed by up to 1.5× if it is shorter than the shot, cover-cropped, and the last frame held if it is still short.
- **End card:** drawn with Pillow from `end_card.lines`.
- **Encoding:** H.264, yuv420p, constant frame rate, AAC 192k, `+faststart`.

## Failure handling

- **Retries.** `common.call_logged` retries rate limits (HTTP 429), 5xx responses, timeouts and empty TTS responses, with exponential backoff (4 s, 8 s, 16 s), four attempts in total. Other 4xx errors fail fast. Every attempt, failed or not, is a line in `runs.jsonl`.
- **Fallbacks keep the film buildable.** A shot without a clip uses Ken Burns, and no chosen score means the placeholder drone. `--placeholders` lets the whole pipeline run with no keys at all.
- **Secrets** live only in `.env`, which is git-ignored. `.env.example` documents the names.

## Logging

Every line of `runs.jsonl` has: `ts`, `run_id`, `stage`, `provider`, `model`, `shot`, `seed`, `params`, `attempt`, `status`, `latency_s`, `units`, `unit`, `cost_usd_actual` and `cost_usd_list_price`. Kaggle jobs write the same shape, plus `gpu` and GPU minutes, and `run.py import-kaggle` merges them in.
