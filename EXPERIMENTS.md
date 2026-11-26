# Experiments

One entry per change. Keep the seed fixed when comparing prompts. Change one thing at a time. Point to the `runs.jsonl` lines (by `run_id`) as evidence.

Template:

## E<n>: <short title>
- **Hypothesis:**
- **Change:** (one thing; seed fixed?)
- **Result:** (what you saw or heard, plus numbers: latency, LUFS, words/second…)
- **Evidence:** run_id …, files …
- **Decision:**

## E1: Does a reference image hold an object's identity in a new scene? (FLUX.2 klein 4B)
- **Hypothesis:** Passing a reference image keeps the subject's identity better than re-describing it in text.
- **Change:** Same model, new scene prompt ("the same coffee pot ... on a stone windowsill at night"), plus the first pot as `input_image_0`.
- **Result:** Shape, handle, spout, colour and speckled texture all carried over. The background changed fully, as asked. Cost about 125 neurons instead of 104 without a reference.
- **Evidence:** run 20261126T061816Z; outputs/smoke/flux-2-klein-4b.png → klein_with_ref.png
- **Decision:** Keyframes use klein-4b with the character reference sheet attached (`use_reference_images: true`).

## E2: Is a fixed seed enough for reproducible keyframes?
- **Hypothesis:** The same prompt and seed give the same image, so seeds make runs reproducible.
- **Change:** The same klein-4b call twice with seed 7. Also tried schnell with a seed.
- **Result:** klein: different images (mean pixel difference ≈37/255). schnell: rejects `seed` with HTTP 400.
- **Evidence:** runs 20261126T061632Z, 20261126T061816Z; FAILURES F3 and F5
- **Decision:** Hypothesis rejected. Reproducibility comes from hashed, committed outputs, not seeds.

## E3: Does a style instruction improve Amharic TTS, or hurt it?
- **Hypothesis:** A short delivery note ("warm, calm storytelling") improves the voice, as the brief suggests.
- **Change:** The same s04 line on gemini-3.8-flash-tts, voice Kore: with the English instruction vs with none.
- **Result:** With the instruction: 11.4 s, and silencedetect shows about 5.5 s of extra speech before a pause, i.e. the instruction itself is spoken. With none: 4.1 s, only the line. The same pattern on s01 and s09.
- **Evidence:** runs 20261126T063554Z, 20261126T063921Z and the E3 lines in runs.jsonl; outputs/smoke/tts_style/s04_none.wav
- **Decision:** No style instruction for Amharic. This is the suggested practice that did **not** work for my language. An Amharic-language instruction is still untested because the quota ran out first.

## E4: Is 2–2.5 words per second right for Amharic narration?
- **Hypothesis:** The brief's 130–220 words for 60–90 s applies to Amharic.
- **Change:** Measured the real narration: 113 Amharic words, gemini-3.8-flash-lite-tts, no style instruction.
- **Result:** 67.3 s of speech, i.e. **1.68 words/s**. Amharic words carry more syllables (fused prepositions and suffixes), so the English rate overestimates. With lead and pad per shot plus the end card, the radio cut is 82.0 s.
- **Evidence:** outputs/narration/manifest.json, outputs/edit/timeline_radio.json
- **Decision:** Budget about 100–145 Amharic words for 60–90 s, not 130–220.

## E5: Reference images lock identity, and also pose and props
- **Hypothesis:** Attaching the character reference to every keyframe gives consistency with no downside.
- **Change:** Keyframes for all 9 shots with `use_reference_images: true`, then 3 prompt rewrites for the shots that failed.
- **Result:** Identity was excellent: the young father has the same face in s02–s04. But the reference also imposed its **pose**: s04 came back as a front-facing portrait 3 times, even with "seen from the side, not looking at the camera". The old father's reference (glasses, cardigan) produced a **book** in his hands 3 times, even with "no book", until the reference was removed. The ref-free versions follow the action, and identity still holds closely because the text description is detailed (hair, moustache, glasses, cardigan).
- **Evidence:** runs 20261126T07* keyframes lines in runs.jsonl; the superseded keyframes are kept in outputs/keyframes/ by hash
- **Decision:** A new per-shot field `use_reference` (default true). Off for s04 and s07, the two action/prop shots. Rule: the reference for identity shots, text-only for action shots.

## E6: Prompting against garbled text and the wrong setting
- **Hypothesis:** The style block alone sets "1980s Ethiopian town".
- **Change:** First pass with generic prompts ("a bustling street market"); second pass naming concrete local cues (eucalyptus, tin roofs, netela shawls, gabi) and adding "no signs and no writing".
- **Result:** Pass 1: s01 had fake lettering on the shop signs and a Mediterranean-looking street, and s06's crowd wore turbans and Central Asian dress. Pass 2: both fixed. The brief's "describe qualities and concrete details" beat a generic style label.
- **Evidence:** storyboard.json history; keyframes s01/s06 under both hashes
- **Decision:** Every outdoor prompt names a local material, plant or garment, plus "no writing".

## E7: Score balance: can the melody carry without fighting the voice?
- **Hypothesis:** A drone plus plucked theme sits well under narration as composed.
- **Change:** Measured the spectral energy of the three v1 candidates, then lowered the drone by about 7 dB (v2) and measured again.
- **Result:** v1: 85–87% of the energy below 300 Hz (drone) and 13–15% in the melodic band (300 Hz–3 kHz), which would sound like a hum. v2: 60–66% low, 34–40% melodic. All candidates come out at about -14.4 LUFS, peak -1.0 dBFS, with no energy above 3 kHz (no hiss, and no clash with speech sibilance).
- **Evidence:** runs 20261126T095940Z (v1) and the next compose run (v2); outputs/music/candidates/tizita_* (both versions kept)
- **Decision:** v2. Seed 11 provisionally, as the least melodically busy (34%), following "no strong lead melody under narration".
- **Follow-up after user test 1 ("the sound lacks some taste"):** v3 added a bowed masenqo-like string, a kebero-like hand drum and a bass line, but measured 44–49% of its energy below 150 Hz, which phone speakers can't reproduce and which takes loudness away from the voice after normalisation. v4 moved the string up an octave and lightened the bass: <150 Hz 29–31%, 300 Hz–3 kHz 35–43%. Chosen: v4 seed 11 (35%, still the least busy). The v1–v4 files are all kept in outputs/music/candidates/.

## E8: Why the first cut looked "frame by frame", and what fixed it
- **Hypothesis (from user test 1):** viewers read the film as a slideshow because of how the stills move, not because they are stills.
- **Change:** Replaced FFmpeg `zoompan` (which rounds the crop window to whole pixels, so slow moves step visibly) with a per-frame affine warp at sub-pixel precision and an ease-in-out curve. Added 0.6 s cross-dissolves instead of hard cuts, kerosene-lamp flicker on s03 and s04, and moving film grain on every shot.
- **Result:** Smooth camera glide, with the shots flowing into each other. Rendering cost: PIL's affine warp took **157 ms/frame** at 720×1280 (≈40 min for a 1080p film in two ratios), while OpenCV's `warpAffine` took 45 ms/frame, and a test segment went from 22.7 s to 5.0 s (4.5× faster).
- **Evidence:** pipeline/assemble.py (`camera_frames`, `dissolve_join`, `effects_filter`); timing runs in this session
- **Decision:** Keep it. Audio stays in sync because each shot carries the dissolve overlap at its end, so shot k still starts at the same timestamp. To be validated in user test 2.

Ideas lined up (≈10):
1. Style block on vs off: does the look stay consistent across shots? (same seeds)
2. Character description verbatim in every prompt vs a short name only: identity drift
3. FLUX.1 schnell vs FLUX.2 klein with the reference image: consistency vs neurons per image
4. TTS with vs without a style instruction: native-speaker preference
5. TTS voice A vs voice B for Amharic pronunciation of names
6. Measured words per second in my language vs the brief's 2–2.5 wps estimate
7. Ducking settings: ratio 6 / release 1500 vs ratio 4 / release 800, listened on a phone
8. Single-pass vs two-pass loudnorm: measured LUFS error
9. Wan 2.2 clip vs Ken Burns for the same shot: blind preference from 5 people
10. ACE-Step: 3 seeds, same caption: which sits under the voice best, and why
