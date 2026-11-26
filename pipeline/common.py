"""Shared plumbing for every stage: paths, storyboard loading, logging, caching, retries, FFmpeg.

Every model call goes through `call_logged`, which appends exactly one line to runs.jsonl.
Every generated artefact is named by a hash of the inputs that produced it, so a re-run
regenerates only what changed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
STORYBOARD = ROOT / "storyboard.json"
SCHEMA = ROOT / "schema" / "storyboard.schema.json"
RUNS_LOG = ROOT / "runs.jsonl"
OUT = ROOT / "outputs"
PRICING = ROOT / "pricing.json"

# One id per process, so all calls from one `python run.py film` can be grouped.
RUN_ID = os.environ.get("HS_RUN_ID") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
os.environ["HS_RUN_ID"] = RUN_ID


# ---------------------------------------------------------------- environment

def load_env() -> None:
    """Read .env without overriding variables already set in the shell."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def require_env(*names: str) -> dict[str, str]:
    load_env()
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(f"Missing {', '.join(missing)}. Copy .env.example to .env and fill it in.")
    return {n: os.environ[n] for n in names}


# ---------------------------------------------------------------- storyboard

def load_storyboard(path: Path = STORYBOARD) -> dict:
    import jsonschema

    data = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        lines = [f"  - {'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in errors]
        sys.exit(f"{path.name} does not match the schema:\n" + "\n".join(lines))
    _check_references(data)
    return data


def _check_references(sb: dict) -> None:
    """Rules JSON Schema cannot express: unique ids and cross references."""
    problems = []
    ids = [s["id"] for s in sb["shots"]]
    if len(ids) != len(set(ids)):
        problems.append("shot ids are not unique")
    char_ids = {c["id"] for c in sb["characters"]}
    cue_ids = {c["id"] for c in sb["music"]["cues"]}
    for s in sb["shots"]:
        for c in s.get("characters", []):
            if c not in char_ids:
                problems.append(f"{s['id']}: unknown character '{c}'")
        if s.get("music_cue") and s["music_cue"] not in cue_ids:
            problems.append(f"{s['id']}: unknown music cue '{s['music_cue']}'")
        if s["video"] == "wan" and not s.get("motion_prompt"):
            problems.append(f"{s['id']}: video=wan needs a motion_prompt")
        if s["narration"].strip() and not s["subtitle_en"].strip():
            problems.append(f"{s['id']}: narration without an English subtitle")
    if problems:
        sys.exit("storyboard.json has broken references:\n" + "\n".join(f"  - {p}" for p in problems))


def select_shots(sb: dict, only: list[str] | None) -> list[dict]:
    if not only:
        return sb["shots"]
    wanted = set(only)
    unknown = wanted - {s["id"] for s in sb["shots"]}
    if unknown:
        sys.exit(f"Unknown shot id(s): {', '.join(sorted(unknown))}")
    return [s for s in sb["shots"] if s["id"] in wanted]


# ---------------------------------------------------------------- hashing / cache

def input_hash(obj: Any, length: int = 10) -> str:
    """Stable hash of whatever went into a generation. Same inputs -> same filename."""
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:length]


def file_hash(path: Path, length: int = 10) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:length]


def outdir(*parts: str) -> Path:
    p = OUT.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_manifest(stage: str, entries: dict) -> None:
    """outputs/<stage>/manifest.json maps shot id -> the current artefact for that shot."""
    path = outdir(stage) / "manifest.json"
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def read_manifest(stage: str) -> dict:
    path = OUT / stage / "manifest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- logging

def _price(model: str, units: float | None) -> float | None:
    """List-price equivalent in USD, from pricing.json (fill it with prices you verified)."""
    if units is None or not PRICING.exists():
        return None
    table = json.loads(PRICING.read_text(encoding="utf-8")).get("models", {})
    entry = table.get(model)
    if not entry or entry.get("usd_per_unit") is None:
        return None
    return round(entry["usd_per_unit"] * units, 6)


def log_call(record: dict) -> None:
    record = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "run_id": RUN_ID, **record}
    line = json.dumps(record, ensure_ascii=False)
    line = re.sub(r"accounts/[0-9a-f]{6,32}", "accounts/<redacted>", line)  # keep the Cloudflare account id out of the public log
    with open(RUNS_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


class RetryableError(Exception):
    """Raise for rate limits, timeouts and 5xx: the call will be retried."""


def call_logged(
    *,
    stage: str,
    provider: str,
    model: str,
    params: dict,
    fn: Callable[[], Any],
    shot: str | None = None,
    seed: int | None = None,
    cost_units: Callable[[Any], float] | None = None,
    unit_name: str | None = None,
    max_attempts: int = 4,
    base_delay: float = 4.0,
) -> Any:
    """Run one model call with retries. Every attempt, failed or not, is one line in runs.jsonl."""
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        t0 = time.perf_counter()
        try:
            result = fn()
        except RetryableError as e:
            latency = time.perf_counter() - t0
            last_err = e
            log_call({"stage": stage, "provider": provider, "model": model, "shot": shot, "seed": seed,
                      "params": params, "attempt": attempt, "status": "retryable_error",
                      "error": str(e)[:500], "latency_s": round(latency, 3)})
            if attempt < max_attempts:
                delay = base_delay * (2 ** (attempt - 1))
                print(f"    {model}: {str(e)[:120]} -> retry {attempt + 1}/{max_attempts} in {delay:.0f}s")
                time.sleep(delay)
            continue
        except Exception as e:  # non-retryable: log and stop
            latency = time.perf_counter() - t0
            log_call({"stage": stage, "provider": provider, "model": model, "shot": shot, "seed": seed,
                      "params": params, "attempt": attempt, "status": "error",
                      "error": f"{type(e).__name__}: {str(e)[:500]}", "latency_s": round(latency, 3)})
            raise
        latency = time.perf_counter() - t0
        units = cost_units(result) if cost_units else None
        log_call({"stage": stage, "provider": provider, "model": model, "shot": shot, "seed": seed,
                  "params": params, "attempt": attempt, "status": "ok", "latency_s": round(latency, 3),
                  "units": units, "unit": unit_name, "cost_usd_actual": 0.0,
                  "cost_usd_list_price": _price(model, units)})
        return result
    raise RuntimeError(f"{model} failed after {max_attempts} attempts: {last_err}")


def http_check(resp) -> None:
    """Turn an HTTP response into RetryableError / RuntimeError as appropriate."""
    if resp.status_code == 429 and ("PerDay" in resp.text or "per day" in resp.text):
        # A daily free-tier cap will not clear in seconds: fail fast instead of burning retries (FAILURES F8).
        delay = re.search(r'"retryDelay":\s*"(\d+)s"', resp.text)
        hours = f" (resets in ~{int(delay.group(1)) / 3600:.1f} h)" if delay else ""
        raise RuntimeError(f"Daily free-tier quota exhausted{hours}: {resp.text[:300]}")
    if resp.status_code == 429 or resp.status_code >= 500:
        raise RetryableError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")


# ---------------------------------------------------------------- ffmpeg

def ffmpeg_exe() -> str:
    """System FFmpeg if installed, otherwise the static build shipped by imageio-ffmpeg."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def ffmpeg(args: list[str], cwd: Path | None = None, quiet: bool = True) -> None:
    cmd = [ffmpeg_exe(), "-hide_banner", "-y"] + (["-loglevel", "error"] if quiet else []) + args
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n  " + " ".join(cmd) + "\n" + proc.stderr[-3000:])


def ffmpeg_stderr(args: list[str]) -> str:
    cmd = [ffmpeg_exe(), "-hide_banner"] + args
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.stderr


def media_duration(path: Path) -> float:
    """Duration in seconds, parsed from ffmpeg's banner (no ffprobe needed)."""
    err = ffmpeg_stderr(["-i", str(path)])
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if not m:
        raise RuntimeError(f"Could not read duration of {path}")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def resolution(quality: str, aspect: str) -> tuple[int, int]:
    short = 720 if quality == "draft" else 1080
    long = short * 16 // 9
    return (long, short) if aspect == "16x9" else (short, long)


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()
