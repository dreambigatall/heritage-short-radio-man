"""Thin clients for the hosted APIs. Each function does one HTTP call and raises
RetryableError / RuntimeError via http_check; logging and retries live in common.call_logged."""
from __future__ import annotations

import base64
import os
import re

import requests

from common import RetryableError, http_check, load_env

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
CF_BASE = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
TIMEOUT = 180


def _post(url: str, **kw) -> requests.Response:
    try:
        return requests.post(url, timeout=TIMEOUT, **kw)
    except (requests.Timeout, requests.ConnectionError) as e:
        raise RetryableError(f"{type(e).__name__}: {e}") from e


# ---------------------------------------------------------------- Gemini

def _gemini_key() -> str:
    load_env()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set (see .env.example)")
    return key


def gemini_list_models() -> list[dict]:
    r = requests.get(f"{GEMINI_BASE}/models", headers={"x-goog-api-key": _gemini_key()},
                     params={"pageSize": 200}, timeout=60)
    http_check(r)
    return r.json().get("models", [])


def gemini_text(model: str, prompt: str, *, json_mode: bool = False, temperature: float = 0.7) -> dict:
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    r = _post(f"{GEMINI_BASE}/models/{model}:generateContent",
              headers={"x-goog-api-key": _gemini_key()}, json=body)
    http_check(r)
    data = r.json()
    try:
        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected Gemini response: {str(data)[:500]}") from e
    return {"text": text, "usage": data.get("usageMetadata", {})}


def gemini_tts(model: str, text: str, voice_name: str, style_instruction: str) -> dict:
    """Returns raw 16-bit PCM plus its sample rate. Style is steered by a plain-language preamble."""
    # Gemini TTS treats a leading "Say ...:" clause as direction, but reads a free-standing sentence
    # aloud (FAILURES.md F7). So the instruction always ends in a colon on the same line as the text.
    prompt = f"{style_instruction.strip().rstrip('.:;, ')}: {text.strip()}" if style_instruction else text
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}}},
        },
    }
    r = _post(f"{GEMINI_BASE}/models/{model}:generateContent",
              headers={"x-goog-api-key": _gemini_key()}, json=body)
    http_check(r)
    data = r.json()
    try:
        part = data["candidates"][0]["content"]["parts"][0]["inlineData"]
    except (KeyError, IndexError) as e:
        # A finished response with no audio is usually a transient refusal/empty turn: retry it.
        raise RetryableError(f"No audio in response: {str(data)[:300]}") from e
    mime = part.get("mimeType", "")
    m = re.search(r"rate=(\d+)", mime)
    pcm, rate = unwrap_wav(base64.b64decode(part["data"]), int(m.group(1)) if m else 24000)
    return {"pcm": pcm, "rate": rate, "mime": mime, "usage": data.get("usageMetadata", {})}


def unwrap_wav(data: bytes, default_rate: int = 24000) -> tuple[bytes, int]:
    """Some TTS models return a whole WAV file, not raw PCM. Treating it as PCM plays the
    header as a click and the trailing metadata chunk as ~100 ms of noise (FAILURES F11)."""
    if data[:4] != b"RIFF":
        return data, default_rate
    import io
    import wave

    with wave.open(io.BytesIO(data)) as w:
        return w.readframes(w.getnframes()), w.getframerate()


# ---------------------------------------------------------------- Cloudflare Workers AI

def _cf_auth() -> tuple[str, str]:
    load_env()
    acct, tok = os.environ.get("CLOUDFLARE_ACCOUNT_ID"), os.environ.get("CLOUDFLARE_API_TOKEN")
    if not acct or not tok:
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN are not set (see .env.example)")
    return acct, tok


def cf_image(model: str, prompt: str, *, seed: int | None, steps: int = 4,
             width: int = 1024, height: int = 1024, reference_images: list[bytes] | None = None,
             send_seed: bool = True) -> bytes:
    """Generate one image. FLUX.1 schnell takes JSON; FLUX.2 models take multipart/form-data.

    The FLUX.2 multipart field names are not fully documented on the model page; the smoke
    test probes them and FAILURES.md records what actually worked."""
    acct, tok = _cf_auth()
    url = CF_BASE.format(account=acct, model=model)
    headers = {"Authorization": f"Bearer {tok}"}

    if "flux-2" in model:
        fields = {"prompt": (None, prompt), "steps": (None, str(steps)),
                  "width": (None, str(width)), "height": (None, str(height))}
        if seed is not None and send_seed:
            fields["seed"] = (None, str(seed))
        for i, img in enumerate(reference_images or []):
            fields[f"input_image_{i}"] = (f"ref{i}.png", img, "image/png")
        r = _post(url, headers=headers, files=fields)
    else:
        body = {"prompt": prompt[:2048], "steps": min(steps, 8)}
        if seed is not None and send_seed:
            body["seed"] = seed
        r = _post(url, headers=headers, json=body)

    http_check(r)
    if r.headers.get("content-type", "").startswith("image/"):
        return r.content
    data = r.json()
    img = (data.get("result") or {}).get("image") or data.get("image")
    if not img:
        raise RuntimeError(f"No image in Cloudflare response: {str(data)[:400]}")
    return base64.b64decode(img)


def flux_neurons(model: str, width: int, height: int, steps: int, n_refs: int = 0) -> float:
    """Neuron estimate from Cloudflare's published pricing (checked 2026-11-25; see COSTS.md)."""
    tiles = max(1, round(width / 512) * round(height / 512))
    if "flux-1-schnell" in model:
        return tiles * 4.80 + steps * 9.60
    if "flux-2-klein-4b" in model:
        return tiles * 26.05 + n_refs * tiles * 5.37
    return float("nan")
