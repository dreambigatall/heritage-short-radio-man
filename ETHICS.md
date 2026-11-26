# Ethics: consent, licences, labelling

## Consent: no real person is depicted or voiced

**The Radio Man is a work of fiction.** The father and the narrating son are invented characters, inspired by a novel I read, not my own family. So:
- **No real person's face or likeness is generated.** Both characters come from text descriptions and AI reference portraits, not from any photo.
- **No real voice is used or cloned.** The narration is Gemini's synthetic voice "Kore" reading words written for the film.
- **The film says so:** the end card reads "A work of fiction, inspired by a novel I read", and the public post states it too.
- **Source material:** the film borrows the spirit of a story I read, not its text. Narration, prompts and images are original to this project. Book: TODO (title and author), credited in the post.

## Private data
Family details sent to free endpoints may be used for training. What I kept out of every prompt and narration line: names of real people, photos of anyone, addresses, and anything about health or money. The prompts describe only a generic 1980s Ethiopian town and an illustrated character.

## Licences

| Component | Licence / terms | Notes |
|---|---|---|
| Wan 2.2 TI2V-5B | Apache 2.0 | notebook prepared, not used in the final film (see FAILURES F4) |
| Score (`pipeline/compose.py`) | My own code; the audio is original and generated deterministically, with no samples or training data | used in the final film |
| ACE-Step 1.5 | MIT; trained on licensed, royalty-free and synthetic data; outputs usable commercially | notebook prepared, not used (FAILURES F10) |
| FLUX.1 schnell | Apache 2.0 | smoke test only |
| FLUX.2 klein 4B | Apache 2.0 (the 9B is non-commercial) | used for all keyframes, via Cloudflare Workers AI terms |
| Gemini API: 2.5 Flash (script draft), 3.8 Flash Lite TTS (narration) | Google Gemini API terms (free tier: inputs may be used to improve products) | |
| FFmpeg (imageio-ffmpeg build) | GPL build | used as a tool, not redistributed in the film |
| This repository's code | TODO choose (e.g. MIT) | |

## Labelling
- AI end card in every export (`end_card` in storyboard.json).
- Platform AI-content disclosure switched ON when posting (YouTube "altered or synthetic content" / TikTok AI-generated label / Meta "AI info").
- Generated files are not stripped of metadata or watermarks.
- Style is described by qualities ("warm hand-painted, film grain"), never by naming a living artist.
