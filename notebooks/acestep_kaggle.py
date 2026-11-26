# ACE-Step 1.5 score candidates on a Kaggle GPU notebook.
#
# How to use:
#   1. Locally: `python run.py music` -> writes outputs/kaggle/music_jobs.json.
#   2. Include it in the "heritage-jobs" Kaggle dataset (same upload as the Wan jobs).
#   3. GPU notebook, Internet ON. CELL 1 installs, CELL 2 writes a job script, CELL 3 runs it.
#   4. Download /kaggle/working/music/* into outputs/music/candidates/ and
#      /kaggle/working/ace_runs.jsonl into outputs/kaggle/, then `python run.py import-kaggle`.
#   5. Listen under the narration, set storyboard.music.chosen to the file name and write why.
#
# The API below follows docs/en/INFERENCE.md of the ACE-Step-1.5 repo (read 2026-11-25).
# Not yet run on a T4: if initialisation fails, check the repo's INSTALL/GPU_COMPATIBILITY docs
# and record what you changed in FAILURES.md.

# ---------------- CELL 1: install
"""
!pip install -q uv
!git clone --depth 1 https://github.com/ACE-Step/ACE-Step-1.5.git /kaggle/working/ACE-Step-1.5
!cd /kaggle/working/ACE-Step-1.5 && uv sync
"""

# ---------------- CELL 2: job script (run inside the repo's uv environment)
JOB_SCRIPT = r'''
import json, subprocess, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

DATA = Path("/kaggle/input/heritage-jobs"); WORK = Path("/kaggle/working")
OUT = WORK / "music"; OUT.mkdir(exist_ok=True)
GPU = subprocess.run(["nvidia-smi","--query-gpu=name","--format=csv,noheader"],capture_output=True,text=True).stdout.strip()

dit = AceStepHandler()
dit.initialize_service(project_root=str(WORK / "ACE-Step-1.5"), config_path="acestep-v15-turbo", device="cuda")
llm = LLMHandler()
llm.initialize(checkpoint_dir=str(WORK / "ACE-Step-1.5" / "checkpoints"), lm_model_path="acestep-5Hz-lm-0.6B",
               backend="pt", device="cuda")

for job in json.loads((DATA / "music_jobs.json").read_text()):
    params = GenerationParams(caption=job["caption"], lyrics="[Instrumental]" if job["instrumental"] else "",
                              instrumental=job["instrumental"], bpm=job["bpm"], keyscale=job["keyscale"],
                              duration=job["duration"], seed=job["seed"])
    config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[job["seed"]], audio_format="wav")
    t0 = time.perf_counter()
    res = generate_music(dit, llm, params, config, save_dir=str(OUT / job["out_name"]))
    dt = time.perf_counter() - t0
    files = [a["path"] for a in res.audios] if res.success else []
    for p in files:
        Path(p).rename(OUT / f"{job['out_name']}.wav")
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "remote_id": uuid.uuid4().hex, "run_id": "kaggle",
           "stage": "music", "provider": "kaggle", "model": "ACE-Step-1.5-turbo", "shot": None, "seed": job["seed"],
           "params": {k: job[k] for k in ("caption", "bpm", "keyscale", "duration", "instrumental")},
           "status": "ok" if res.success else "error", "latency_s": round(dt, 1), "gpu": GPU,
           "units": round(dt / 60, 2), "unit": "gpu_minutes", "cost_usd_actual": 0.0,
           "error": None if res.success else str(res.error)[:1500]}
    with open(WORK / "ace_runs.jsonl", "a") as f: f.write(json.dumps(rec) + "\n")
    print(job["out_name"], "OK" if res.success else f"FAILED: {res.error}", f"{dt:.0f}s")
'''
from pathlib import Path
Path("/kaggle/working/ace_job.py").write_text(JOB_SCRIPT)

# ---------------- CELL 3: run
"""
!cd /kaggle/working/ACE-Step-1.5 && uv run python /kaggle/working/ace_job.py
"""
