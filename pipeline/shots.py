"""Stage: moving shots. Decides, per shot, whether the edit uses a generated clip or a Ken Burns
move over the keyframe, and prepares the GPU job for the shots that still need a clip.

Wan 2.2 does not run on this machine. The flow is:
  1. `python run.py shots` writes outputs/kaggle/jobs.json plus the keyframes those jobs need.
  2. Upload outputs/kaggle/ as a Kaggle dataset, run notebooks/wan22_kaggle.py on a GPU.
  3. Download its clips into outputs/clips/ and its log into outputs/kaggle/wan_runs.jsonl,
     then `python run.py import-kaggle` merges the log into runs.jsonl.
A clip is named <shot>_<hash>.mp4, where the hash covers the keyframe and the motion prompt,
so changing either makes the old clip stale and the shot falls back to Ken Burns until re-run.

Reads:  storyboard.json, outputs/keyframes/manifest.json
Writes: outputs/shots/manifest.json, outputs/kaggle/jobs.json, outputs/kaggle/keyframes/*.png
"""
from __future__ import annotations

import argparse
import json
import shutil

from common import OUT, input_hash, load_storyboard, outdir, read_manifest, rel, select_shots, write_manifest

WAN = {"model": "Wan2.2-TI2V-5B", "steps": 30, "frame_num": 121, "size_16x9": "1280*704", "size_9x16": "704*1280"}


def clip_key(shot: dict, keyframe_hash: str) -> dict:
    return {"keyframe": keyframe_hash, "motion": shot.get("motion_prompt", ""), "seed": shot["seed"], **WAN}


def run(only: list[str] | None = None) -> dict:
    sb = load_storyboard()
    kf = read_manifest("keyframes")
    clips_dir = outdir("clips")
    kaggle = outdir("kaggle")
    (kaggle / "keyframes").mkdir(exist_ok=True)
    manifest = read_manifest("shots")
    jobs = []

    for shot in select_shots(sb, only):
        sid = shot["id"]
        if sid not in kf:
            raise SystemExit(f"{sid}: no keyframe yet. Run `python run.py keyframes` first.")
        still = kf[sid]["file"]
        entry = {"type": "kenburns", "file": still, "camera": shot["camera"], "keyframe_hash": kf[sid]["hash"]}

        if shot["video"] == "wan":
            h = input_hash(clip_key(shot, kf[sid]["hash"]))
            clip = clips_dir / f"{sid}_{h}.mp4"
            if clip.exists():
                entry = {"type": "clip", "file": rel(clip), "clip_hash": h, "keyframe_hash": kf[sid]["hash"]}
                print(f"  {sid}: clip ready   {rel(clip)}")
            else:
                src = OUT.parent / still
                dst_name = f"{sid}_{kf[sid]['hash']}.png"
                shutil.copyfile(src, kaggle / "keyframes" / dst_name)
                jobs.append({"shot": sid, "clip_hash": h, "keyframe": dst_name,
                             "prompt": shot["motion_prompt"], "seed": shot["seed"], **WAN})
                print(f"  {sid}: needs Wan clip -> queued for Kaggle (Ken Burns until then)")
        else:
            print(f"  {sid}: Ken Burns ({shot['camera']})")
        manifest[sid] = entry

    (kaggle / "jobs.json").write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")
    write_manifest("shots", manifest)
    if jobs:
        print(f"  {len(jobs)} Kaggle job(s) in {rel(kaggle / 'jobs.json')}")
    return manifest


def import_kaggle_logs() -> None:
    """Append GPU-side log lines (latency, GPU seconds) from Kaggle runs into runs.jsonl, once each."""
    from common import RUNS_LOG

    seen = set()
    if RUNS_LOG.exists():
        for line in RUNS_LOG.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("remote_id"):
                seen.add(rec["remote_id"])
    added = 0
    for log in (OUT / "kaggle").glob("*_runs.jsonl"):
        for line in log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("remote_id") in seen:
                continue
            with open(RUNS_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            seen.add(rec.get("remote_id"))
            added += 1
    print(f"  imported {added} remote log line(s) into runs.jsonl")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    run(a.only)
