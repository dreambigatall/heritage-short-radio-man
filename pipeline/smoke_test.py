"""Smoke test: call each hosted provider once, log latency to runs.jsonl, and print what this
account can actually use today (model names move fast; trust this output over the README).

    python run.py smoke
"""
from __future__ import annotations

import io
import wave

from common import OUT, call_logged, load_env, outdir


def _ok(msg): print(f"  OK    {msg}")
def _fail(msg): print(f"  FAIL  {msg}")


def run() -> None:
    load_env()
    out = outdir("smoke")
    from providers import cf_image, flux_neurons, gemini_list_models, gemini_text, gemini_tts

    # 1. Gemini: list models so we pick real ids
    try:
        models = gemini_list_models()
        names = [m["name"].split("/")[-1] for m in models]
        tts = [n for n in names if "tts" in n]
        flash = [n for n in names if "flash" in n and "tts" not in n and "image" not in n]
        _ok(f"Gemini key works; {len(names)} models visible")
        print("        TTS models:   " + (", ".join(tts) or "none"))
        print("        Flash models: " + ", ".join(flash[:12]))
    except Exception as e:
        _fail(f"Gemini list models: {e}")
        tts, flash = [], []

    # 2. Gemini text
    text_model = next((m for m in flash if "lite" not in m), flash[0] if flash else "gemini-2.5-flash")
    try:
        r = call_logged(stage="smoke", provider="gemini", model=text_model, params={"prompt": "ping"},
                        fn=lambda: gemini_text(text_model, "Reply with the single word: ready"),
                        cost_units=lambda r: r["usage"].get("totalTokenCount"), unit_name="tokens")
        _ok(f"{text_model}: {r['text'].strip()[:40]!r}")
    except Exception as e:
        _fail(f"{text_model}: {e}")

    # 3. Gemini TTS, in Amharic, because that is the language most likely to surprise us
    tts_model = tts[0] if tts else "gemini-2.5-flash-preview-tts"
    try:
        r = call_logged(stage="smoke", provider="gemini", model=tts_model, params={"voice": "Kore", "lang": "am"},
                        fn=lambda: gemini_tts(tts_model, "ሰላም። ይህ የድምፅ ሙከራ ነው።", "Kore", "Say calmly:"),
                        cost_units=lambda r: r["usage"].get("candidatesTokenCount"), unit_name="output_tokens")
        path = out / "tts_am.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(r["rate"]); w.writeframes(r["pcm"])
        _ok(f"{tts_model}: {len(r['pcm']) / 2 / r['rate']:.1f}s of audio -> {path.relative_to(OUT.parent)} (listen to it!)")
    except Exception as e:
        _fail(f"{tts_model}: {e}")

    # 4. Cloudflare FLUX: with seed, then without if the seed is rejected
    for model in ("@cf/black-forest-labs/flux-1-schnell", "@cf/black-forest-labs/flux-2-klein-4b"):
        for send_seed in (True, False):
            try:
                raw = call_logged(stage="smoke", provider="cloudflare", model=model, seed=7,
                                  params={"prompt": "a clay coffee pot on a wooden table", "send_seed": send_seed},
                                  fn=lambda: cf_image(model, "a clay coffee pot on a wooden table, warm light",
                                                      seed=7, steps=4, width=1024, height=1024, send_seed=send_seed),
                                  cost_units=lambda _r: flux_neurons(model, 1024, 1024, 4), unit_name="cf_neurons",
                                  max_attempts=2)
                from PIL import Image
                img = Image.open(io.BytesIO(raw))
                name = model.split("/")[-1]
                img.save(out / f"{name}.png")
                _ok(f"{model}: {img.size[0]}x{img.size[1]} (seed sent: {send_seed})")
                break
            except Exception as e:
                _fail(f"{model} (seed sent: {send_seed}): {str(e)[:200]}")

    print("\n  Every call above is now a line in runs.jsonl. Put the model ids that worked into storyboard.json.")
