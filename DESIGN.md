# Design

## Brief (written before generating any picture)
- **Title:** The Radio Man (የሬዲዮ ሰው)
- **Logline:** My father taught himself to repair radios in a small Ethiopian town, and that is why I write code today.
- **Whose story:** my father. Consent is recorded in ETHICS.md before any likeness is generated.
- **Audience:** My family (parents, siblings, cousins at home and in the diaspora) and young Ethiopians learning tech; watching on phones, mostly vertical, shared on WhatsApp and Telegram.
- **Intent:** Feel pride in an ordinary man's curiosity, and see that fixing radios and writing code are the same gift passed from father to child.
- **How might we…** help my family, and young Ethiopians learning tech, see an ordinary man's curiosity as the start of a line that runs to today's code?
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

## User test 1: radio cut (narration + placeholder music, black screen)
File tested: `outputs/film/radio_16x9_draft.mp4` (82 s)
- **Date, format:** TODO (WhatsApp / in person / Slack)
- **People (≥3, from the audience):** P1 TODO (e.g. "sister, 24"), P2 TODO, P3 TODO
- **Questions asked:** What did you feel at the end? Was anything unclear? Is the Amharic pronunciation natural, and are any words wrong?
- **What they said (as close to their words as possible):**
  - P1:
  - P2:
  - P3:
- **Insights:**
- **What changed in storyboard.json because of it:** (shot id: before → after)

## User test 2: near-final cut (pictures + chosen score)
File tested: `outputs/film/film_9x16_*.mp4`
- **Date, format:** TODO
- **People (≥3):** TODO
- **What they said:**
- **What changed:**
