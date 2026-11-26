"""Stage: music. Resolves the score the edit will use.

ACE-Step 1.5 runs on Kaggle (notebooks/acestep_kaggle.py). This stage writes the job list for it
(one candidate per seed in each cue), and afterwards picks the candidate named in
storyboard.music.chosen. Until a candidate is chosen it synthesises a quiet placeholder drone
with FFmpeg, so the radio cut can be tested before any GPU time is spent.

Reads:  storyboard.json (music)
Writes: outputs/kaggle/music_jobs.json, outputs/music/placeholder_<hash>.wav, outputs/music/manifest.json
"""
from __future__ import annotations

import argparse
import json

from common import OUT, ffmpeg, input_hash, load_storyboard, outdir, rel, write_manifest

PLACEHOLDER_EXPR = (
    "0.16*sin(2*PI*146.83*t)*(0.6+0.4*sin(2*PI*0.07*t))"
    "+0.10*sin(2*PI*220.00*t)*(0.6+0.4*sin(2*PI*0.05*t+1))"
    "+0.08*sin(2*PI*174.61*t)*(0.6+0.4*sin(2*PI*0.09*t+2))"
    "+0.05*sin(2*PI*73.42*t)"
)


def placeholder(duration: float) -> str:
    out = outdir("music")
    h = input_hash({"expr": PLACEHOLDER_EXPR, "d": round(duration, 1)})
    path = out / f"placeholder_{h}.wav"
    if not path.exists():
        ffmpeg(["-f", "lavfi", "-i", f"aevalsrc='{PLACEHOLDER_EXPR}':s=48000:d={duration:.2f}",
                "-af", f"lowpass=f=1800,afade=t=in:d=3,afade=t=out:st={max(0, duration - 4):.2f}:d=4",
                "-ac", "2", str(path)])
    return rel(path)


def run() -> dict:
    sb = load_storyboard()
    music = sb["music"]
    cand_dir = outdir("music", "candidates")

    jobs = []
    for cue in music["cues"]:
        for seed in cue.get("seeds", [0]):
            jobs.append({"cue": cue["id"], "seed": seed, "caption": cue["caption"], "bpm": cue["bpm"],
                         "keyscale": cue.get("key", ""), "duration": cue["duration_s"],
                         "instrumental": cue["instrumental"],
                         "out_name": f"{cue['id']}_seed{seed}_{input_hash(cue)}"})
    kaggle = outdir("kaggle")
    (kaggle / "music_jobs.json").write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  {len(jobs)} ACE-Step job(s) in {rel(kaggle / 'music_jobs.json')}")
    from kaggle_notebook import build

    print(f"  Kaggle notebook with these jobs embedded: {build(jobs)}")

    candidates = sorted(p.name for p in cand_dir.iterdir() if p.suffix.lower() in {".wav", ".flac", ".mp3"})
    if candidates:
        print("  candidates on disk: " + ", ".join(candidates))

    chosen = music.get("chosen")
    if chosen:
        path = cand_dir / chosen
        if not path.exists() and chosen.startswith("tizita_"):
            # code-composed scores are not stored in git; they are rebuilt deterministically
            import compose

            print("  chosen score not on disk: recomposing it (deterministic)")
            compose.run()
        if not path.exists():
            raise SystemExit(f"music.chosen = {chosen!r} but {rel(path)} does not exist.")
        entry = {"file": rel(path), "placeholder": False, "reason": music.get("chosen_reason", "")}
        print(f"  using chosen score {chosen}")
    else:
        longest = max(c["duration_s"] for c in music["cues"])
        entry = {"file": placeholder(longest), "placeholder": True, "reason": "no candidate chosen yet"}
        print(f"  using PLACEHOLDER drone {entry['file']}")
    write_manifest("music", {"score": entry})
    return entry


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    run()
