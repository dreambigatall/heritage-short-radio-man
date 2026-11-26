# Design

## Brief (written before generating any picture)
- **Title:** The Radio Man (የሬዲዮ ሰው)
- **Logline:** My father taught himself to repair radios in a small Ethiopian town, and that is why I write code today.
- **Whose story:** a fictional father and son, inspired by a novel I read. No real person is depicted (ETHICS.md). The story matters to me because it is the path I am on: curiosity about how things work, turned into code.
- **Audience:** My family (parents, siblings, cousins at home and in the diaspora) and young Ethiopians learning tech; watching on phones, mostly vertical, shared on WhatsApp and Telegram.
- **Intent:** Feel pride in an ordinary man's curiosity, and see that fixing radios and writing code are the same gift passed from father to child.
- **How might we…** help young Ethiopians learning tech, and their families, see an ordinary person's curiosity as the start of a line that runs to today's code?
- **Constraints:** 60–90 s, vertical first, Amharic narration with English subtitles, free tiers only (10 TTS calls/day per model, FAILURES F8).

## Options considered (ideate)
1. "The Third Cup": grandmother's coffee ceremony. The most beautiful visuals, but a weaker link to my own life.
2. **"The Radio Man": chosen.** It ties heritage to what I am building this week, and gives my post and interview a true "why".
3. "Slowly, Slowly": a proverb as a motif. Very shareable, but more abstract.

## Every shot has a reason
From the `reason` field of each shot in storyboard.json:

| Shot | Size | Reason |
|---|---|---|
| s01 | wide | To set the historical context and importance of radios in the community. |
| s02 | medium | To introduce the father and the beginning of his journey with radios. |
| s03 | close up | To highlight the father's hands-on curiosity and the intricate work. |
| s04 | medium close up | To show his dedication and the challenging conditions of his learning. |
| s05 | insert | To show the growth of his skill and the increasing demand for his services. |
| s06 | wide | To illustrate the community's reliance on him and the importance of his work. |
| s07 | medium close up | To convey the father's core wisdom that shaped the narrator's perspective. |
| s08 | medium | To visually bridge the past and present, connecting the father's work to the narrator's. |
| s09 | close up | To provide a final, intimate connection between father and child, fulfilling the film's intent. |

Structure: setting (s01) → the spark (s02–s03) → mastery (s04) → community (s05–s06) → the lesson (s07) → the inheritance (s08–s09). The radio is the motif in every shot, and it is still there beside the laptop in the last frame.

## Decisions made before the first user test
- **Narration length set by measurement, not the brief's estimate.** Amharic speaks at 1.68 words/s (EXPERIMENTS E4), so 113 words fit an 82 s cut.
- **No TTS style instruction**, because it was read aloud (E3).
- **The narrator is never shown full-face** (hands and laptop only), to keep the focus on the father and avoid generating a likeness of me.

## User test 1: first cut (stills with Ken Burns moves, placeholder-then-tizita score)
- **Date, format:** 26 Nov 2026. I showed the film to 4 people (TODO: who they are, e.g. "brother, 22", "friend from class", and whether in person or on WhatsApp).
- **What they said:**
  - Overall: **"it is good"**. All 4 liked the story.
  - **Sound:** "the sound lacks some taste". It felt thin and flat.
  - **Picture:** "it shows images frame by frame, it is not a full video". It read as a slideshow, not a film.
- **Insights:**
  1. The story and narration land. Nobody asked for a script change, so the storyboard's words stay.
  2. "Lacks taste" = one instrument plus a drone, and nothing else in the world of the film. Professional soundtracks have four layers (dialogue, effects, ambience, music); mine had two.
  3. "Frame by frame" = three causes I could see in my own render: hard cuts between stills, zoompan's whole-pixel steps (motion judders instead of gliding), and nothing inside the frame moving.
- **What changed because of it:**
  - **Sound:** score v3 adds a bowed masenqo-like string, a soft kebero-like hand drum and a bass line under the krar theme. A new **effects/ambience layer** adds a street murmur (s01), radio static (s02), static resolving into a tuned station (s04), a waiting crowd (s06) and keyboard typing (s08, s09). Fields `sfx` per shot in storyboard.json.
  - **Voice:** investigating "sound lacks taste" uncovered a real defect. Every narration line started with a click and ended with ~100 ms of digital noise, because the TTS returned a WAV file that I had stored as raw audio (FAILURES F11). Fixed and repaired without new TTS calls. The film is now 81.2 s.
  - **Picture:** a new renderer moves the camera with sub-pixel smoothness and eased motion, **dissolves** between shots instead of hard cuts, adds **flickering kerosene-lamp light** to the night shots (s03, s04) and moving film grain to all shots. Field `effects` per shot in storyboard.json.
  - **Not changed, and why:** true generated video (Wan 2.2) needs a GPU run that failed on Kaggle (FAILURES F4, F10), so motion is created in code instead.

## User test 2: the revised cut
File tested: `outputs/film/film_9x16_final.mp4` after the changes above
- **Date, format:** TODO (show it to the same 4 people)
- **What they said:** TODO
- **Did the changes fix "sound lacks taste" and "frame by frame"?** TODO
