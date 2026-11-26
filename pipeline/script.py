"""Stage: script. Turns your notes about the story (story.md) into a draft storyboard that
matches the schema. It writes storyboard.draft.json and never overwrites storyboard.json:
you review the draft, edit it, and copy it over yourself.

    python run.py script --story story.md
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from common import ROOT, SCHEMA, STORYBOARD, call_logged, rel

FALLBACKS = ["gemini-3.5-flash", "gemini-2.5-flash"]  # used when the primary model is overloaded (503)

PROMPT = """You are a documentary film editor planning a 60-90 second vertical short film.

Write a storyboard as JSON that validates against this JSON Schema:
{schema}

Use this existing storyboard as the template for every non-shot field (models, voice, music,
output, end_card, style); keep their values unless the notes say otherwise:
{template}

Rules:
- 8 to 10 shots. Total narration 130-200 words in the film's language ({language}).
- Write narration for the ear: short sentences, concrete images, no tongue-twisters.
- subtitle_en is a faithful English translation of the narration line.
- One idea and one gentle movement per shot. Vary shot sizes (wide to set place, close-ups for feeling).
- image_prompt describes only what is in frame; do NOT repeat character descriptions or the style block.
- No text, signs or writing inside images.
- motion_prompt describes only motion and camera, never the subject.
- reason: one sentence on why the shot exists.
- Give each shot a distinct seed.
- The film should end on the feeling stated in "intent".

The person's notes about the story:
---
{story}
---
Return only the JSON object."""


def run(story_path: Path) -> None:
    from providers import gemini_text

    story_path = story_path if story_path.is_absolute() else ROOT / story_path
    if not story_path.exists():
        raise SystemExit(f"Write your story notes in {rel(story_path)} first.")
    template = json.loads(STORYBOARD.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    model = template["models"].get("script", "gemini-2.5-flash")
    prompt = PROMPT.format(schema=json.dumps(schema), template=json.dumps({k: v for k, v in template.items() if k != "shots"}, ensure_ascii=False),
                           language=template["language"], story=story_path.read_text(encoding="utf-8"))

    res = None
    for m in dict.fromkeys([model, *FALLBACKS]):  # primary first, then fallbacks, no duplicates
        try:
            res = call_logged(stage="script", provider="gemini", model=m, params={"story_chars": len(prompt)},
                              fn=lambda m=m: gemini_text(m, prompt, json_mode=True, temperature=0.8),
                              cost_units=lambda r: r["usage"].get("totalTokenCount"), unit_name="tokens",
                              max_attempts=3)
            print(f"  drafted with {m}")
            break
        except Exception as e:
            print(f"  {m} unavailable ({str(e)[:100]}); trying the next model")
    if res is None:
        raise SystemExit("Every script model failed; see runs.jsonl.")
    draft = json.loads(res["text"])
    out = ROOT / "storyboard.draft.json"
    out.write_text(json.dumps(draft, indent=2, ensure_ascii=False), encoding="utf-8")
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(draft))
    if errors:
        print(f"  draft written to {rel(out)} but has {len(errors)} schema error(s):")
        for e in errors[:10]:
            print(f"   - {'/'.join(map(str, e.path))}: {e.message}")
    else:
        words = sum(len(s["narration"].split()) for s in draft["shots"])
        print(f"  {rel(out)}: {len(draft['shots'])} shots, {words} narration words. Review it, then copy to storyboard.json.")
