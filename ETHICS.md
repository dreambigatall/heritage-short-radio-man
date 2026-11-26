# Ethics: consent, licences, labelling

## Consent (recorded BEFORE generating anything of a real person)

| Person | Relationship | Appears as | Consent given for | How recorded | Date |
|---|---|---|---|---|---|
| My father | Father | An **illustrated character inspired by him**, at about 20 and in his sixties. Not generated from any photo of him: the images come from a text description and an AI reference portrait, so it is not a likeness of his real face. He is not named in the film. | His story as told in the 9 narration lines in storyboard.json, the illustrated depiction, and public posting with an AI label | TODO: e.g. "WhatsApp voice note, 26 Nov 2026, after hearing the radio cut" (kept privately, not in this repo) | TODO |
| Me (narrator) | – | Hands and a laptop only, never a face | – | – | – |

- **No real voice is cloned or used.** The narration is Gemini's synthetic voice "Kore", reading words I wrote. It is not my father's voice or mine.
- **His words:** the quote in s07 ("Everything that is broken can be understood…") is TODO: confirm it is something he really said, or that he agrees to it being attributed to him.

## Private data
Family details sent to free endpoints may be used for training. What I kept out of every prompt and narration line: my father's name, the name of the town, any address, photos of family members, and anything about health or money. The prompts describe only a generic 1980s Ethiopian town and an illustrated character.

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
