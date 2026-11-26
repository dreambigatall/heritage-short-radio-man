"""Builds outputs/kaggle/acestep_heritage.ipynb: a self-contained Kaggle notebook with the
ACE-Step jobs from storyboard.json embedded, so nothing has to be uploaded as a dataset.

Import it on kaggle.com (Create -> New Notebook -> File -> Import Notebook), set
Accelerator = GPU T4, Internet = On, Run All, then download results.zip.

API names checked against the ACE-Step-1.5 source on 2026-11-26:
AceStepHandler.initialize_service(project_root, config_path, device, offload_to_cpu, ...),
LLMHandler.initialize(checkpoint_dir, lm_model_path, backend, device, offload_to_cpu, dtype),
GenerationParams(task_type, caption, lyrics, instrumental, bpm, keyscale ("A minor"), duration,
seed, thinking, inference_steps, shift), GenerationConfig(batch_size, use_random_seed, seeds,
audio_format). Pre-Ampere GPUs (T4) are switched to float16 by the library itself.
"""
from __future__ import annotations

import json

from common import outdir, rel

INSTALL = """%%bash
nvidia-smi --query-gpu=name,memory.total --format=csv
pip install -q uv
git clone -q --depth 1 https://github.com/ACE-Step/ACE-Step-1.5.git /kaggle/working/ACE-Step-1.5
cd /kaggle/working/ACE-Step-1.5 && uv sync 2>&1 | tail -3
echo INSTALL DONE"""

JOB = r'''
import json, os, shutil, subprocess, time, traceback, uuid
from datetime import datetime, timezone
from pathlib import Path
REPO = Path("/kaggle/working/ACE-Step-1.5"); WORK = Path("/kaggle/working")
OUT = WORK / "music"; OUT.mkdir(exist_ok=True)
LOG = WORK / "ace_runs.jsonl"
JOBS = json.loads(__JOBS__)
GPU = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()

def log(rec):
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "remote_id": uuid.uuid4().hex, "run_id": "kaggle",
           "provider": "kaggle", "gpu": GPU, "cost_usd_actual": 0.0, **rec}
    with open(LOG, "a") as f: f.write(json.dumps(rec) + "\n")

from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

t0 = time.perf_counter()
dit = AceStepHandler()
msg, ok = dit.initialize_service(project_root=str(REPO), config_path="acestep-v15-turbo", device="cuda", offload_to_cpu=False)
log({"stage": "music_init", "model": "acestep-v15-turbo", "status": "ok" if ok else "error", "latency_s": round(time.perf_counter() - t0, 1), "error": None if ok else msg[:1000]})
print("DiT:", ok, msg[:300])
assert ok, msg

llm, use_lm = LLMHandler(), False
try:
    from acestep.api.model_download import ensure_model_downloaded
    ensure_model_downloaded("acestep-5Hz-lm-0.6B", str(REPO / "checkpoints"))
    t0 = time.perf_counter()
    msg, use_lm = llm.initialize(checkpoint_dir=str(REPO / "checkpoints"), lm_model_path="acestep-5Hz-lm-0.6B",
                                 backend="pt", device="cuda", offload_to_cpu=True)
    log({"stage": "music_init", "model": "acestep-5Hz-lm-0.6B", "status": "ok" if use_lm else "error", "latency_s": round(time.perf_counter() - t0, 1), "error": None if use_lm else msg[:1000]})
    print("LM planner:", use_lm, msg[:200])
except Exception as e:
    traceback.print_exc()
    log({"stage": "music_init", "model": "acestep-5Hz-lm-0.6B", "status": "error", "error": repr(e)[:1000]})
    print("LM planner unavailable -> DiT only (thinking=False)")

for job in JOBS:
    params = GenerationParams(task_type="text2music", caption=job["caption"],
                              lyrics="[Instrumental]" if job["instrumental"] else "", instrumental=job["instrumental"],
                              bpm=job["bpm"], keyscale=job["keyscale"], duration=float(job["duration"]), seed=job["seed"],
                              thinking=use_lm, inference_steps=8, shift=3.0)
    config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[job["seed"]], audio_format="wav")
    t0 = time.perf_counter()
    try:
        res = generate_music(dit, llm, params, config, save_dir=str(OUT / "_raw"))
        ok, err = res.success, res.error
        paths = [a.get("path") for a in res.audios if a.get("path")]
        if ok and paths:
            shutil.copyfile(paths[0], OUT / f"{job['out_name']}.wav")
    except Exception as e:
        ok, err = False, traceback.format_exc()[-1500:]
    dt = time.perf_counter() - t0
    log({"stage": "music", "model": "ACE-Step-1.5-turbo" + ("+lm0.6B" if use_lm else ""), "shot": None, "seed": job["seed"],
         "params": {k: job[k] for k in ("caption", "bpm", "keyscale", "duration", "instrumental")} | {"steps": 8, "thinking": use_lm},
         "status": "ok" if ok else "error", "latency_s": round(dt, 1), "units": round(dt / 60, 3), "unit": "gpu_minutes",
         "error": None if ok else str(err)[:1500]})
    print(job["out_name"], "OK" if ok else "FAILED", f"{dt:.0f}s", "" if ok else str(err)[:500])
'''

ZIP = """%%bash
cd /kaggle/working && rm -rf music/_raw && zip -qr results.zip music ace_runs.jsonl && ls -la music results.zip
echo "Download results.zip from the Output panel (right side) -> unzip into the project"""


def _cell(src: str, kind: str = "code") -> dict:
    cell = {"cell_type": kind, "metadata": {}, "source": src.splitlines(keepends=True)}
    if kind == "code":
        cell.update({"execution_count": None, "outputs": []})
    return cell


def build(jobs: list[dict]) -> str:
    job_src = JOB.replace("__JOBS__", repr(json.dumps(jobs, ensure_ascii=False)))
    nb = {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}},
        "cells": [
            _cell("# Heritage Short: ACE-Step 1.5 score candidates\n"
                  "Settings (right panel): **Accelerator = GPU T4 x2**, **Internet = On**. Then **Run All**.\n"
                  "When it finishes, download `results.zip` from the Output panel.", "markdown"),
            _cell(INSTALL),
            _cell("%%writefile /kaggle/working/ace_job.py\n" + job_src),
            _cell("%%bash\ncd /kaggle/working/ACE-Step-1.5 && uv run python /kaggle/working/ace_job.py 2>&1 | grep -vE 'it/s\\]|s/it\\]' | tail -60"),
            _cell(ZIP),
        ],
    }
    path = outdir("kaggle") / "acestep_heritage.ipynb"
    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    return rel(path)
