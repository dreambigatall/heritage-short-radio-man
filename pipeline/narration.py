"""Stage: narration. One WAV per shot from Gemini TTS, named by a hash of its inputs.

Reads:  storyboard.json (voice, language, shots[].narration)
Writes: outputs/narration/<shot>_<hash>.wav, outputs/narration/manifest.json
"""
from __future__ import annotations

import argparse
import wave
from pathlib import Path

from common import call_logged, input_hash, load_storyboard, outdir, read_manifest, rel, select_shots, write_manifest

WORDS_PER_SECOND = 2.3  # only used for --placeholders timing


def write_wav(path: Path, pcm: bytes, rate: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


def repair_wrapped(path: Path) -> bool:
    """Fix clips saved before unwrap_wav existed: the frames hold a whole WAV file."""
    from providers import unwrap_wav

    with wave.open(str(path), "rb") as w:
        frames, rate = w.readframes(w.getnframes()), w.getframerate()
    if frames[:4] != b"RIFF":
        return False
    pcm, rate = unwrap_wav(frames, rate)
    write_wav(path, pcm, rate)
    return True


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def shot_key(sb: dict, shot: dict) -> dict:
    v = sb["voice"]
    return {"model": v["model"], "voice": v["voice_name"], "style": v["style_instruction"],
            "language": sb["language"], "text": shot["narration"].strip()}


def run(only: list[str] | None = None, placeholders: bool = False, force: bool = False) -> dict:
    sb = load_storyboard()
    out = outdir("narration")
    manifest = read_manifest("narration")
    v = sb["voice"]

    for shot in select_shots(sb, only):
        sid, text = shot["id"], shot["narration"].strip()
        if not text:
            manifest[sid] = {"file": None, "duration_s": 0.0, "hash": None}
            print(f"  {sid}: no narration")
            continue
        key = shot_key(sb, shot)
        h = input_hash(key)
        path = out / (f"{sid}_{h}.wav" if not placeholders else f"{sid}_{h}_placeholder.wav")

        if path.exists() and not force:
            print(f"  {sid}: cached  {rel(path)}")
        elif placeholders:
            secs = max(1.5, len(text.split()) / WORDS_PER_SECOND)
            write_wav(path, b"\x00\x00" * int(24000 * secs), 24000)
            print(f"  {sid}: PLACEHOLDER silence {secs:.1f}s (no TTS call)")
        else:
            from providers import gemini_tts

            print(f"  {sid}: generating with {v['model']} ...")
            res = call_logged(
                stage="narration", provider="gemini", model=v["model"], shot=sid, seed=None,
                params={"voice": v["voice_name"], "style_instruction": v["style_instruction"],
                        "language": sb["language"], "chars": len(text), "hash": h},
                fn=lambda: gemini_tts(v["model"], text, v["voice_name"], v["style_instruction"]),
                cost_units=lambda r: r["usage"].get("candidatesTokenCount"), unit_name="output_tokens",
            )
            write_wav(path, res["pcm"], res["rate"])
        if not placeholders and repair_wrapped(path):
            print(f"        repaired: removed embedded WAV header/trailer (F11)")
        manifest[sid] = {"file": rel(path), "duration_s": round(wav_duration(path), 3), "hash": h,
                         "placeholder": placeholders}
        print(f"        {manifest[sid]['duration_s']:.2f}s")

    write_manifest("narration", manifest)
    total = sum(m["duration_s"] for m in manifest.values())
    print(f"  narration total: {total:.1f}s across {len(manifest)} shots")
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", help="shot ids, e.g. s03 s07")
    ap.add_argument("--placeholders", action="store_true", help="silent timing stand-ins, no API calls")
    ap.add_argument("--force", action="store_true", help="ignore the cache")
    a = ap.parse_args()
    run(a.only, a.placeholders, a.force)
