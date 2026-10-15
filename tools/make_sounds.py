"""Generates the game's sound effects from scratch (so they're 100% copyright-free).

Run:  python tools/make_sounds.py
Output: assets/sounds/*.wav  (48 kHz, 16-bit, mono)
"""
import math
import random
import wave
from pathlib import Path

RATE = 48000
OUT = Path(__file__).resolve().parent.parent / "assets" / "sounds"


def osc(kind: str, phase: float) -> float:
    p = phase % 1.0
    if kind == "sine":
        return math.sin(2 * math.pi * p)
    if kind == "square":
        return 1.0 if p < 0.5 else -1.0
    if kind == "saw":
        return 2 * p - 1
    return 4 * abs(p - 0.5) - 1  # triangle


def tone(freq, dur, kind="sine", vol=0.5, attack=0.01, release=0.08, f_end=None, vibrato=0.0):
    n = int(RATE * dur)
    out, phase = [], 0.0
    for i in range(n):
        t = i / RATE
        f = freq if f_end is None else freq + (f_end - freq) * (i / n)
        if vibrato:
            f *= 1 + vibrato * math.sin(2 * math.pi * 6 * t)
        phase += f / RATE
        a = min(1.0, t / attack) if attack > 0 else 1.0
        r = max(0.0, min(1.0, (dur - t) / release)) if release > 0 else 1.0
        out.append(osc(kind, phase) * vol * a * r)
    return out


def bell(freq, dur, vol=0.5):
    n = int(RATE * dur)
    return [math.sin(2 * math.pi * freq * i / RATE) * vol * math.exp(-5 * i / n) for i in range(n)]


def noise(dur, vol, lp_start, lp_end, wobble=0.0):
    n = int(RATE * dur)
    out, y = [], 0.0
    for i in range(n):
        frac = i / n
        alpha = lp_start + (lp_end - lp_start) * frac
        y += alpha * (random.uniform(-1, 1) - y)
        env = math.sin(math.pi * frac) ** 0.7
        mod = 1 + wobble * math.sin(2 * math.pi * 4 * i / RATE)
        out.append(y * 3.0 * vol * env * mod)
    return out


def silence(dur):
    return [0.0] * int(RATE * dur)


def mix(*tracks):
    length = max(len(t) for t in tracks)
    return [sum(t[i] for t in tracks if i < len(t)) for i in range(length)]


def save(name, samples):
    OUT.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    for s in samples:
        v = int(max(-1.0, min(1.0, s)) * 32000)
        frames += v.to_bytes(2, "little", signed=True)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))
    print(f"made {name}.wav ({len(samples) / RATE:.2f}s)")


def main():
    random.seed(7)
    # HONK: two nasal saw blasts
    save("honk", tone(360, 0.22, "saw", 0.45, 0.01, 0.05, f_end=320)
         + silence(0.05) + tone(330, 0.32, "saw", 0.45, 0.01, 0.1, f_end=260))
    # FLUSH: swirling noise
    save("flush", noise(1.6, 0.8, 0.03, 0.45, wobble=0.25))
    # BETRAY: dramatic "dun... DUN"
    save("betray", tone(196, 0.28, "saw", 0.4, 0.01, 0.06) + silence(0.06)
         + tone(147, 0.6, "saw", 0.45, 0.01, 0.3, vibrato=0.01))
    # FAIL: sad trombone wah wah wah wahhh
    save("fail", tone(311, 0.26, "saw", 0.35, 0.02, 0.05) + tone(294, 0.26, "saw", 0.35, 0.02, 0.05)
         + tone(277, 0.26, "saw", 0.35, 0.02, 0.05) + tone(262, 0.7, "saw", 0.35, 0.02, 0.2, f_end=240, vibrato=0.03))
    # SUCCESS: quick double ding
    save("success", mix(bell(880, 0.5, 0.4), bell(1320, 0.5, 0.2))
         + mix(bell(1175, 0.6, 0.4), bell(1760, 0.6, 0.2)))
    # WIN: happy arpeggio
    win = []
    for f in (523, 659, 784, 1047):
        win += tone(f, 0.16, "tri", 0.45, 0.005, 0.05)
    win += mix(tone(1047, 0.6, "tri", 0.4, 0.01, 0.3), tone(784, 0.6, "tri", 0.25, 0.01, 0.3))
    save("win", win)
    # LOSE: falling womp + low rumble
    save("lose", mix(tone(500, 1.1, "saw", 0.4, 0.01, 0.3, f_end=70, vibrato=0.04),
                     noise(0.6, 0.25, 0.02, 0.05)))
    # ALARM: panic siren
    siren = []
    for _ in range(3):
        siren += tone(850, 0.14, "square", 0.22, 0.005, 0.02) + tone(620, 0.14, "square", 0.22, 0.005, 0.02)
    save("alarm", siren)


if __name__ == "__main__":
    main()
