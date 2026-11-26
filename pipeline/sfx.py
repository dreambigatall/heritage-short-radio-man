"""Effects and ambience beds, generated in code (user test 1: "the sound lacks some taste").

A film soundtrack has four layers: dialogue, effects, ambience and music. The first cut had
two. Each shot's `sfx` field picks a bed from the kinds below; every bed is deterministic
(seeded by shot id) and cached by a hash of its inputs.

    street  morning town: distant voices murmur, a few birds
    static  a radio between stations: band-limited hiss with crackle
    tuning  static, a whistle as the dial turns, then the station comes in (soft tizita chord)
    crowd   neighbours waiting: a closer babble
    typing  laptop keys in short phrases
    room    quiet room tone
"""
from __future__ import annotations

import numpy as np

SR = 48000
VERSION = "sfx-v1"
LEVEL_DB = {"street": -34, "static": -33, "tuning": -31, "crowd": -32, "typing": -31, "room": -46}


def _band(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))


def _smooth_noise(n: int, rate: float, rng) -> np.ndarray:
    """Random envelope that changes `rate` times per second (for murmur and crackle)."""
    k = max(2, int(n / SR * rate) + 2)
    pts = rng.random(k)
    return np.interp(np.linspace(0, k - 1, n), np.arange(k), pts)


def babble(n: int, rng, voices: int, lo: float = 250, hi: float = 1800) -> np.ndarray:
    out = np.zeros(n)
    for _ in range(voices):
        v = _band(rng.normal(0, 1, n), lo * rng.uniform(0.8, 1.2), hi * rng.uniform(0.8, 1.2))
        out += v * _smooth_noise(n, rng.uniform(3, 6), rng) ** 2   # syllable-rate amplitude
    return out


def birds(n: int, rng) -> np.ndarray:
    out = np.zeros(n)
    for _ in range(max(1, n // (SR * 3))):
        start = int(rng.uniform(0, max(1, n - SR // 2)))
        for c in range(int(rng.integers(2, 5))):  # a short chirp phrase
            m = int(SR * 0.07)
            t = np.arange(m) / SR
            f0 = rng.uniform(3200, 4800)
            chirp = np.sin(2 * np.pi * (f0 * t + rng.uniform(-6000, 6000) * t * t)) * np.hanning(m)
            i = start + c * int(SR * 0.11)
            if i + m < n:
                out[i:i + m] += 0.4 * chirp
    return out


def static(n: int, rng) -> np.ndarray:
    hiss = _band(rng.normal(0, 1, n), 700, 5500) * (0.6 + 0.4 * _smooth_noise(n, 9, rng))
    pops = np.zeros(n)
    for i in rng.integers(0, n, size=max(1, n // 2500)):
        pops[i:i + 40] += rng.normal(0, 3, min(40, n - i))
    return hiss + _band(pops, 300, 6000)


def tuning(n: int, rng) -> np.ndarray:
    t = np.arange(n) / SR
    p = t / t[-1]
    st = static(n, rng) * np.clip(1.2 - 1.6 * p, 0, 1)               # static fades as the dial lands
    sweep_env = np.clip(np.sin(np.pi * np.clip((p - 0.15) / 0.4, 0, 1)), 0, 1)
    freq = 2400 - 1500 * np.clip((p - 0.15) / 0.4, 0, 1)
    whistle = 0.25 * np.sin(2 * np.pi * np.cumsum(freq) / SR) * sweep_env
    station_env = np.clip((p - 0.5) / 0.15, 0, 1)
    chord = sum(np.sin(2 * np.pi * f * t) for f in (220.0, 277.18, 329.63, 440.0)) / 4
    station = _band(chord * (0.7 + 0.3 * np.sin(2 * np.pi * 1.5 * t)), 300, 3000) * station_env  # "radio" band
    return st + whistle + 0.8 * station


def typing(n: int, rng) -> np.ndarray:
    out = np.zeros(n)
    i = int(SR * rng.uniform(0.3, 0.8))
    while i < n - SR // 10:
        for _ in range(int(rng.integers(4, 14))):                     # one typed phrase
            m = int(SR * 0.012)
            click = rng.normal(0, 1, m) * np.exp(-np.arange(m) / (SR * 0.002))
            if i + m < n:
                out[i:i + m] += click * rng.uniform(0.6, 1.0)
            i += int(SR * rng.uniform(0.08, 0.2))
        i += int(SR * rng.uniform(0.4, 1.2))                          # pause to think
    return _band(out, 1500, 7000)


def room(n: int, rng) -> np.ndarray:
    return _band(np.cumsum(rng.normal(0, 1, n)), 40, 400)


def bed(kind: str, seconds: float, seed: int) -> np.ndarray:
    n = int(seconds * SR)
    if kind == "none" or n <= 0:
        return np.zeros(max(n, 0))
    rng = np.random.default_rng(seed)
    x = {"street": lambda: babble(n, rng, 6) + 0.6 * birds(n, rng),
         "static": lambda: static(n, rng),
         "tuning": lambda: tuning(n, rng),
         "crowd": lambda: babble(n, rng, 10, 200, 2200),
         "typing": lambda: typing(n, rng),
         "room": lambda: room(n, rng)}[kind]()
    rms = np.sqrt(np.mean(x ** 2)) + 1e-12
    x = x / rms * 10 ** (LEVEL_DB[kind] / 20)
    fade = np.minimum(1, np.minimum(np.arange(n), n - 1 - np.arange(n)) / (0.4 * SR))
    return np.clip(x * fade, -1, 1)
