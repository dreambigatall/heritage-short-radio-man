# Wan 2.2 TI2V-5B image-to-video on a Kaggle GPU notebook.
#
# How to use:
#   1. Locally: `python run.py shots` -> creates outputs/kaggle/ (jobs.json + keyframes/).
#   2. Upload outputs/kaggle/ as a private Kaggle dataset named "heritage-jobs".
#   3. New notebook -> Accelerator: GPU T4 x2 (or P100) -> Internet ON -> add the dataset.
#   4. Paste each CELL below into its own notebook cell and run.
#   5. Download /kaggle/working/clips/*.mp4 into outputs/clips/ and
#      /kaggle/working/wan_runs.jsonl into outputs/kaggle/, then `python run.py import-kaggle`.
#
# Known risk (see FAILURES.md): the Wan 2.2 README says the 5B model with offloading needs
# >= 24 GB VRAM; a T4 has 16 GB. The settings below are the cheapest we could find. If it OOMs,
# lower FRAME_NUM, then fall back to Ken Burns for that shot (the pipeline does this automatically).

# ---------------- CELL 1: install (about 5-10 min, once per session)
"""
!git clone --depth 1 https://github.com/Wan-Video/Wan2.2.git /kaggle/working/Wan2.2
!grep -v flash_attn /kaggle/working/Wan2.2/requirements.txt > /tmp/req.txt && pip install -q -r /tmp/req.txt
!pip install -q "huggingface_hub[cli]"
!huggingface-cli download Wan-AI/Wan2.2-TI2V-5B --local-dir /kaggle/working/Wan2.2-TI2V-5B
"""

# ---------------- CELL 2: run every queued job, logging each one
import json, os, subprocess, time, uuid
from datetime import datetime, timezone
from pathlib import Path

DATA = Path("/kaggle/input/heritage-jobs")          # change if your dataset has another name
WORK = Path("/kaggle/working")
CLIPS = WORK / "clips"; CLIPS.mkdir(exist_ok=True)
LOG = WORK / "wan_runs.jsonl"
FRAME_NUM = 81          # must be 4n+1; 81 frames = 3.4 s at 24 fps (assembly slows it to fit the shot)
STEPS = 30              # draft quality; README default is higher
GPU = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                     capture_output=True, text=True).stdout.strip()

jobs = json.loads((DATA / "jobs.json").read_text())
print(f"{len(jobs)} job(s) on {GPU}")
for job in jobs:
    out = CLIPS / f"{job['shot']}_{job['clip_hash']}.mp4"
    if out.exists():
        print("skip (exists)", out.name); continue
    cmd = ["python", "generate.py", "--task", "ti2v-5B", "--size", job["size_16x9"],
           "--ckpt_dir", str(WORK / "Wan2.2-TI2V-5B"), "--offload_model", "True", "--convert_model_dtype",
           "--t5_cpu", "--image", str(DATA / "keyframes" / job["keyframe"]), "--prompt", job["prompt"],
           "--frame_num", str(FRAME_NUM), "--sample_steps", str(STEPS), "--base_seed", str(job["seed"]),
           "--save_file", str(out)]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=WORK / "Wan2.2", capture_output=True, text=True)
    dt = time.perf_counter() - t0
    ok = proc.returncode == 0 and out.exists()
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "remote_id": uuid.uuid4().hex, "run_id": "kaggle",
           "stage": "shots", "provider": "kaggle", "model": job["model"], "shot": job["shot"], "seed": job["seed"],
           "params": {"prompt": job["prompt"], "frame_num": FRAME_NUM, "steps": STEPS, "size": job["size_16x9"]},
           "status": "ok" if ok else "error", "latency_s": round(dt, 1), "gpu": GPU,
           "units": round(dt / 60, 2), "unit": "gpu_minutes", "cost_usd_actual": 0.0,
           "error": None if ok else proc.stderr[-1500:]}
    with open(LOG, "a") as f: f.write(json.dumps(rec) + "\n")
    print(job["shot"], "OK" if ok else "FAILED", f"{dt / 60:.1f} min")
    if not ok: print(proc.stderr[-1500:])
