# Report draft: The Radio Man (የሬዲዮ ሰው)

> **Draft for you to rewrite in your own words** before exporting it to PDF or Word. The interviewer checks that you understand every claim, so keep only what you can explain. Every number below comes from a file in the repo; the file is named in brackets.

## 1. What I set out to make, and for whom
An 82-second film in Amharic, with English subtitles: a **fictional** story, inspired by a novel I read, of a young man in a small Ethiopian town in the 1980s who teaches himself to repair radios, told by his son who now writes code. It isn't my family's story, but it's my path: curiosity about how things work, turned into code. It is for my family at home and in the diaspora, and for young Ethiopians learning tech. They watch on phones, vertically, shared on WhatsApp and Telegram. The intent: feel pride in an ordinary man's curiosity, and see that fixing radios and writing code are the same gift passed down. [DESIGN.md]

I considered three stories (coffee ceremony, radio man, proverb) and chose the radio man because it connects my heritage to what I was building that week. [DESIGN.md, "Options considered"]

## 2. What I learned from my audience
**Test 1:** I showed the first cut to 4 people. All said the story was good, but "the sound lacks some taste" and "it shows images frame by frame, it is not a full video". Nobody asked to change the words, so the storyboard's narration stayed. I changed how it sounds and moves:
- **Sound:** the soundtrack went from 2 layers to 3. I added an effects/ambience bed (street murmur, radio static, a dial tuning into a station, a waiting crowd, keyboard typing) and gave the score a bowed string, a hand drum and a bass line. My first version of that was too bassy for phone speakers, and I measured and fixed it (E7).
- **Picture:** I found three causes of the slideshow feel: hard cuts, zoompan's whole-pixel judder, and nothing moving inside the frame. I fixed them with dissolves, a sub-pixel camera renderer, lamp flicker and film grain (E8).
**Test 2:** TODO, after showing the revised cut to the same people. [DESIGN.md]

## 3. The hardest problem and how I solved it
**Making Amharic narration fit, within a 10-calls-a-day quota.** My first full narration came out at 151 s for a 60–90 s film. Using FFmpeg's silencedetect I found that every clip started with about 5 s of extra speech: Gemini TTS was reading my English style instruction aloud (F7). Rephrasing it didn't help (s04 went from 6.4 s to 11.4 s), and removing it entirely brought the line to 4.1 s (E3). By then I had hit a limit I hadn't known about: the free tier allows **10 TTS requests per day per model** (F8). My retry loop was also wasting attempts on a daily cap. I changed the HTTP layer to fail fast on per-day 429s and still retry per-minute ones, moved to a second model with its own quota, and planned the walkthrough demo around a keyframe change instead of a narration change. The final narration is 67 s, measured at 1.68 Amharic words/s against the brief's 2–2.5 English estimate (E4). [FAILURES F7, F8; EXPERIMENTS E3, E4; runs.jsonl]

Runner-up: **reference images lock pose as well as identity.** The old father's reference produced a book in his hands 3 times in a row, even with "no book" in the prompt. A per-shot `use_reference` switch fixed it. [E5]

## 4. A suggested practice that beat my instinct
**A reference sheet before keyframes.** My instinct was to just describe the character carefully in every prompt. Attaching an AI reference portrait to each keyframe gave a recognisably identical young man across s02–s04, and the smoke test showed a reference object surviving a full change of scene (E1). The JSON contract plus hash caching also beat my instinct to "just script it": when the TTS quota ran out mid-run, everything already generated stayed cached, and changing one line cost one call. [E1, E5, ARCHITECTURE.md]

## 5. A suggested practice that did not work for me
**"A short style instruction improves the voice more than switching voices."** For Amharic on Gemini 3.8 Flash TTS it made things worse: the instruction was spoken aloud and tripled clip length (E3, F7). Similarly, **"a fixed seed lets you compare two prompts fairly"** didn't hold: FLUX.1 schnell rejects seeds, and FLUX.2 klein accepts them but ignores them (E2, F5). So reproducibility in my pipeline comes from hashed, committed outputs, not seeds.

## 6. Curiosity beyond the floor
- A measured Amharic speaking rate (E4) and a TTS style-instruction experiment (E3): evidence about my language that the brief said it could not confirm.
- Probing undocumented API behaviour: the FLUX.2 multipart fields, seed handling, and content-filter false positives (F2, F3, F5, F9).
- *If you do more today: a second language (Afaan Oromo or Tigrinya, one line, compare by ear), or a blind preference test of two keyframe versions with 5 people.*

## 7. What I would build next
- Real generated motion for the 2–3 shots that need it most, with Wan 2.2 on a GPU where the setup works (my Kaggle attempt failed, F10).
- A small web form where a relative tells a story by voice, and gets a storyboard draft back to approve.
- Batch narration: one TTS call for the whole script, split at pauses, to get 9× more takes from the daily quota.

## Links
- Repository: TODO
- Film 9:16 / 16:9, walkthrough, post: TODO
