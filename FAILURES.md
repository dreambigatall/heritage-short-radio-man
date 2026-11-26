# Failures

What broke, what I tried, what fixed it. Newest at the bottom.

## F1: No FFmpeg or `make` on Windows
- **What broke:** `ffmpeg` and `make` were not installed, so "one command from a clean clone" would fail on Windows.
- **Tried / fixed:** Added `imageio-ffmpeg` to `requirements.txt`. It ships a static FFmpeg build (9.0.2 essentials, with libass, zoompan, sidechaincompress and loudnorm). `common.ffmpeg_exe()` uses the system FFmpeg if there is one, and the bundled one otherwise. The entry point is `python run.py film`, and the `Makefile` is a thin wrapper for machines that have `make`.
- **Also:** no `ffprobe` in that build, so durations are read from FFmpeg's `Duration:` banner, and WAV lengths with Python's `wave` module.

## F2: FLUX.2 klein parameters are not documented on its model page
- **What broke:** The Cloudflare page for `@cf/black-forest-labs/flux-2-klein-4b` says the input is `multipart/form-data`, but its input schema only lists `{multipart: {body, contentType}}`. The field names for the prompt, size, seed and reference images are not given.
- **Tried:** `providers.cf_image` sends `prompt`, `steps`, `width`, `height`, `seed` and `input_image_<n>` as form fields. `run.py smoke` probes it.
- **Result (2026-11-26, run 20261126T061816Z):** these field names work. `input_image_0` is honoured: a reference pot placed in a new night scene kept its shape, colour and texture (outputs/smoke/klein_with_ref.png). klein-4b is now the keyframe model, with `use_reference_images: true`.

## F3: FLUX.1 schnell: docs say `seed`, schema says no
- **What broke:** The docs' curl example passes `seed`, but the input schema has `additionalProperties: false` and lists only `prompt` and `steps`. Without a seed, keyframes are not reproducible.
- **Tried:** The smoke test sends the seed first and retries without it if rejected. `models.send_seed` in the storyboard switches this off.
- **Result (run 20261126T061632Z):** HTTP 400 `Additional or unevaluated properties '/seed' ... not allowed`. The schema was right and the docs were wrong: schnell cannot be seeded through the REST API.

## F4: Wan 2.2 TI2V-5B needs more VRAM than a Kaggle T4 has
- **What broke (on paper, before running):** The Wan 2.2 README says TI2V-5B with `--offload_model True --convert_model_dtype --t5_cpu` needs at least 24 GB of VRAM. A T4 has 16 GB and no bf16 hardware.
- **Also:** `generate.py` defaults to `--size 1280*720`, which `ti2v-5B` rejects. The supported sizes are `1280*704` and `704*1280`.
- **Plan:** 81 frames and 30 steps first. If it runs out of memory, fewer frames. If it still fails, those shots stay on Ken Burns, which the pipeline does automatically.
- **Decision (26 Nov, deadline day):** Not run. With a documented 24 GB minimum against a 16 GB T4, an install of 20+ minutes, and a 10-call/day TTS budget already shaping the day, I spent the Kaggle GPU time on the score (ACE-Step) instead. Every shot uses `video: kenburns`, which the brief accepts as a fallback. The pipeline and notebook for Wan stay in place (`video: wan` on any shot queues it).

## F5: FLUX.2 klein accepts a seed but ignores it
- **What broke:** Two calls with the same prompt and `seed=7` gave different images. The mean absolute pixel difference was about 37/255 per channel: a different pot, a different glaze (outputs/smoke/klein_seed7_0.png and _1.png; run 20261126T061816Z).
- **Consequence:** No hosted image model here is reproducible from a seed. Reproducibility therefore comes from the cache: every keyframe is stored under the hash of its inputs, and the stored file is the source of truth. A clean clone that keeps `outputs/` rebuilds the same film with zero image calls.
- **Still logged:** The seed is still sent and logged, so if Cloudflare starts honouring it the runs become comparable.

## F6: Gemini 3.8 Flash overloaded on deadline morning
- **What broke:** The storyboard draft call to `gemini-3.8-flash` hit a 180 s read timeout, then `HTTP 503 "This model is currently experiencing high demand"`, then hung on the third attempt (run 20261126T062623Z, all attempts in runs.jsonl).
- **Tried:** The exponential-backoff retries in `call_logged` worked as designed, but retrying one overloaded model can still eat 10+ minutes.
- **Fixed:** `pipeline/script.py` now has a model fallback chain (`gemini-3.8-flash` → `gemini-3.5-flash` → `gemini-2.5-flash`), with 3 attempts each, and logs which model drafted the storyboard.
- **Lesson:** Retries handle blips. Fallbacks handle outages. A pipeline needs both.

## F7: Gemini TTS read my English style instruction aloud
- **What broke:** The first full Amharic narration was 151 s, against a 60–90 s target. Every clip began with about 5 s of speech, then a pause, then the Amharic (silencedetect on s01 and s09). The style sentence "Read slowly and warmly, like telling a story…" was being spoken.
- **Tried:** Rephrasing it as `"Say warmly, at a calm natural storytelling pace: <text>"` on one line. Still read aloud: s04 went from 6.4 s to 11.4 s.
- **Fixed:** No style instruction for Amharic (`voice.style_instruction: ""`). s04 dropped to 4.1 s (EXPERIMENTS E3), and the whole narration to 67 s.

## F8: Gemini TTS free tier is 10 requests per day, per model
- **What broke:** HTTP 429 on `gemini-3.8-flash-tts`, quota id `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, `quotaValue: "10"`, retryDelay 4690 s. Smoke tests plus two narration passes used it all by 09:40 EAT.
- **Also wasted:** The retry loop retried the daily cap 3 times with backoff, which was pointless.
- **Fixed:** `http_check` now treats a per-day 429 as fatal, with the reset time in the message, while per-minute 429s are still retried (they cleared within 8 s during the lite run). Narration switched to `gemini-3.8-flash-lite-tts`, which has its own 10/day.
- **Planning rule this created:** 9 shots means 9 TTS calls per full pass, so every narration change has to be deliberate. For the live walkthrough I regenerate a *keyframe* (Cloudflare: about 80 images/day) rather than a narration line.

## F9: Cloudflare's content filter flagged an innocent prompt
- **What broke:** s07 "…radio … rests in his two hands on his lap…" returned `HTTP 400 AiError 3030: Your output has been flagged`. The stage stopped, because it is a non-retryable 4xx.
- **Fixed:** Reworded to "he holds up an old wooden transistor radio…". Lesson: body-position phrasing ("on his lap") with a person can trip the output filter, so describe the object and the action instead.
