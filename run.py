"""One command for the whole pipeline.

    python run.py film               validate -> narration -> keyframes -> shots -> music -> assemble (both ratios)
    python run.py radio              validate -> narration -> music -> radio cut (narration over black)
    python run.py <stage> [--only s03 s07]
                                     stages: validate, smoke, script, narration, keyframes, shots, music,
                                             assemble, import-kaggle, costs, compose
    --placeholders                   no API calls: silent timing + drawn keyframes (tests the plumbing)

Every stage is cached by a hash of its inputs, so re-running `film` after editing one shot in
storyboard.json makes exactly one new model call for that shot.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "pipeline"))

import common  # noqa: E402


def stage(name: str, fn, *a, **kw):
    print(f"\n== {name} ==")
    t0 = time.perf_counter()
    result = fn(*a, **kw)
    print(f"   ({time.perf_counter() - t0:.1f}s)")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", choices=["film", "radio", "validate", "smoke", "script", "narration", "keyframes",
                                       "shots", "music", "assemble", "import-kaggle", "costs", "compose"])
    ap.add_argument("--only", nargs="*", help="limit narration/keyframes/shots to these shot ids")
    ap.add_argument("--placeholders", action="store_true", help="no API calls; stand-in audio and images")
    ap.add_argument("--force", action="store_true", help="ignore caches for narration/keyframes")
    ap.add_argument("--story", default="story.md", help="input for the script stage")
    a = ap.parse_args()

    import assemble, keyframes, music, narration, shots  # noqa: E401

    print(f"run_id {common.RUN_ID}")
    if a.target == "smoke":
        import smoke_test
        return smoke_test.run()
    if a.target == "compose":
        import compose
        return compose.run()
    if a.target == "costs":
        import costs
        return costs.run()
    if a.target == "script":
        import script
        return script.run(Path(a.story))

    sb = stage("validate", common.load_storyboard)
    print(f"   storyboard OK: {len(sb['shots'])} shots, language={sb['language']}")
    t = a.target
    if t == "validate":
        return
    if t == "import-kaggle":
        return stage("import-kaggle", shots.import_kaggle_logs)
    if t in ("film", "radio", "narration"):
        stage("narration", narration.run, a.only, a.placeholders, a.force)
    if t in ("film", "keyframes"):
        stage("keyframes", keyframes.run, a.only, a.placeholders, a.force)
    if t in ("film", "shots"):
        stage("shots", shots.run, a.only)
    if t in ("film", "radio", "music"):
        stage("music", music.run)
    if t in ("film", "assemble"):
        stage("assemble", assemble.run, False)
    if t == "radio":
        stage("assemble (radio cut)", assemble.run, True)


if __name__ == "__main__":
    main()
