"""Stage: compose (fallback score). Writes original instrumental candidates in code when the
ACE-Step GPU run is unavailable (FAILURES F10). Deterministic: same cue + seed -> same file.

Musical plan, from the cue's spotting note:
  - Scale: tizita major pentatonic on A (A B C# E F#), the scale of Ethiopian nostalgia songs.
  - Krar-like plucks (additive synthesis: decaying harmonics + a short noise attack) over a warm A/E drone.
  - A 6-note theme stated early, varied in the middle, and restated an octave higher for the
    father-to-child reveal (from ~70% of the cue), then resolving on A and fading out.
  - Sparse at first (room for the narration), denser in the middle, open at the end.

    python run.py compose        -> outputs/music/candidates/tizita_seed<seed>_<hash>.wav
"""
from __future__ import annotations

import wave

import numpy as np

from common import call_logged, input_hash, load_storyboard, outdir, rel

SR = 44100
VERSION = "tizita-synth-v2"  # v2: drone -7 dB so the plucked theme leads (v1 was 87% drone energy)
SCALE = [0, 2, 4, 7, 9]  # tizita major: A B C# E F# as semitones above A
A3 = 220.0


def note_freq(degree: int, octave: int = 0) -> float:
    o, d = divmod(degree, len(SCALE))
    return A3 * 2 ** ((SCALE[d] + 12 * (o + octave)) / 12)


def pluck(freq: float, dur: float, amp: float, rng: np.random.Generator) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for h in range(1, 9):  # brighter harmonics die faster, like a gut/nylon string
        inharm = 1 + 0.0004 * h * h
        out += (0.9 ** h / h) * np.sin(2 * np.pi * freq * h * inharm * t + rng.uniform(0, 6.28)) * np.exp(-t * (1.6 + 1.1 * h))
    attack = rng.normal(0, 1, min(n, int(0.012 * SR))) * np.linspace(1, 0, min(n, int(0.012 * SR)))
    out[: len(attack)] += 0.25 * attack
    out *= np.minimum(1, t / 0.004)  # 4 ms fade-in to avoid clicks
    return amp * out


def drone(total: float) -> np.ndarray:
    t = np.arange(int(total * SR)) / SR
    d = np.zeros_like(t)
    for f, a, lfo in ((110.0, 0.10, 0.05), (164.81, 0.06, 0.07), (220.0, 0.035, 0.031)):
        d += a * np.sin(2 * np.pi * f * t) * (0.65 + 0.35 * np.sin(2 * np.pi * lfo * t))
    return d * np.minimum(1, t / 4) * np.minimum(1, (total - t) / 5)


def reverb(x: np.ndarray, rng: np.random.Generator, seconds: float = 2.2) -> np.ndarray:
    n = int(seconds * SR)
    ir = rng.normal(0, 1, n) * np.exp(-np.arange(n) / SR * 3.0)
    ir[0] = 0
    size = 1 << int(np.ceil(np.log2(len(x) + n)))
    wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x)]
    return x + 0.12 * wet / (np.abs(wet).max() + 1e-9) * np.abs(x).max()


def compose(cue: dict, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    total = float(cue["duration_s"])
    beat = 60.0 / cue["bpm"]
    left = np.zeros(int((total + 3) * SR))
    right = np.zeros_like(left)

    theme = [int(x) for x in rng.choice([0, 1, 2, 3, 4, 5, 6], size=6)]  # scale degrees, re-used throughout
    theme[-1] = 0  # the theme always comes home to A

    def place(sig: np.ndarray, start: float, pan: float) -> None:
        i = int(start * SR)
        j = min(len(left), i + len(sig))
        left[i:j] += sig[: j - i] * (1 - pan)
        right[i:j] += sig[: j - i] * pan

    t, phrase = beat * 2, 0
    while t < total - 4:
        frac = t / total
        if frac < 0.25:
            density, octave, step = 0.55, 0, 2      # sparse: leave room for the opening narration
        elif frac < 0.7:
            density, octave, step = 0.8, 0, 1
        else:
            density, octave, step = 0.85, 1, 1      # the lift: the theme an octave up
        notes = theme if phrase % 2 == 0 else [d + int(rng.integers(-1, 2)) for d in theme]
        for k, deg in enumerate(notes):
            if t >= total - 4:
                break
            if rng.random() < density or k == 0:
                amp = 0.32 if k == 0 else 0.22
                place(pluck(note_freq(deg, octave), beat * 3, amp, rng), t + rng.normal(0, 0.008), 0.35 + 0.3 * rng.random())
                if octave and rng.random() < 0.4:   # octave doubling in the lift
                    place(pluck(note_freq(deg, 0), beat * 3, 0.12, rng), t + 0.01, 0.6)
            t += beat * step
        place(pluck(note_freq(0, -1), beat * 6, 0.22, rng), t, 0.5)  # bass A at each phrase end
        t += beat * (2 if frac < 0.7 else 1)
        phrase += 1
    place(pluck(note_freq(0, 0), beat * 8, 0.3, rng), total - 4, 0.5)  # final resolution on A

    d = 0.45 * drone(total + 3)
    left, right = reverb(left + d, rng), reverb(right + d, rng)
    fade = np.minimum(1, (total + 3 - np.arange(len(left)) / SR) / 4).clip(0, 1)
    stereo = np.stack([left * fade, right * fade], axis=1)
    return stereo / (np.abs(stereo).max() + 1e-9) * 0.89  # peak about -1 dBFS


def write_wav(path, stereo: np.ndarray) -> None:
    pcm = (stereo * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def run() -> list[str]:
    sb = load_storyboard()
    out = outdir("music", "candidates")
    made = []
    for cue in sb["music"]["cues"]:
        for seed in cue.get("seeds", [0]):
            h = input_hash({"v": VERSION, "cue": cue, "seed": seed})
            path = out / f"tizita_{cue['id']}_seed{seed}_{h}.wav"
            if path.exists():
                print(f"  cached  {rel(path)}")
            else:
                audio = call_logged(stage="music", provider="local", model=VERSION, seed=seed,
                                    params={"cue": cue["id"], "bpm": cue["bpm"], "duration": cue["duration_s"],
                                            "scale": "A tizita major pentatonic"},
                                    fn=lambda: compose(cue, seed), max_attempts=1)
                write_wav(path, audio)
                print(f"  wrote   {rel(path)}")
            made.append(path.name)
    return made


if __name__ == "__main__":
    run()
