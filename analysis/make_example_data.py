#!/usr/bin/env python3
"""Invent some plausible finger-tapping sessions, so you can try the whole
analysis pipeline before you have collected any real data.

    python analysis/make_example_data.py
    python analysis/compute_metrics.py
    python analysis/visualize.py

The files it writes look exactly like the ones fetch_data.py downloads, so
anything that works here will work on your real data. They go into
data/example/ rather than data/raw/ so they can never be mistaken for
participants.

    python analysis/compute_metrics.py --raw data/example
    python analysis/visualize.py       --raw data/example --out data/example_figures
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from config_reader import REPO_ROOT

# Where the fake hand's joints sit, so that the distances metrics.py measures
# come out to exactly the values we asked for.
WRIST, THUMB_TIP, INDEX_TIP, MIDDLE_MCP = 0, 4, 8, 9


def fake_hand(aperture_m: float, span_m: float) -> list[float]:
    """A 21-landmark hand with a known thumb-to-index gap and a known size."""
    points = np.zeros((21, 3))
    points[MIDDLE_MCP] = [0.0, span_m, 0.0]
    points[THUMB_TIP] = [-aperture_m / 2, span_m * 1.5, 0.0]
    points[INDEX_TIP] = [+aperture_m / 2, span_m * 1.5, 0.0]
    # Everything else just needs to be somewhere sensible.
    for i in range(21):
        if i not in (WRIST, THUMB_TIP, INDEX_TIP, MIDDLE_MCP):
            points[i] = [0.01 * (i % 5), span_m * (0.3 + 0.05 * i), 0.0]
    return [round(float(v), 4) for v in points.reshape(-1)]


def make_trial(index: int, trial_id: str, hand: str, *, duration=15.0, fps=30.0,
               rate_hz=4.0, decrement=0.25, jitter=0.06, dropout=(), rng=None) -> dict:
    """One simulated trial.

    rate_hz    how fast they tap
    decrement  fraction of amplitude lost by the end of the trial
    jitter     rhythm irregularity, as a fraction of the interval
    dropout    list of (start_s, end_s) stretches where the hand is lost
    """
    rng = rng or np.random.default_rng(0)
    span_m = 0.085                      # a typical wrist-to-knuckle distance

    # Build the phase by integrating a jittery instantaneous rate, so intervals
    # vary the way a real person's do rather than being perfectly periodic.
    t = np.arange(0, duration, 1.0 / fps)
    inst_rate = rate_hz * (1 + rng.normal(0, jitter, len(t)))
    phase = np.cumsum(inst_rate) * (2 * np.pi / fps)

    # A cosine between "closed" and "open", shrinking over the trial.
    openness = 0.5 * (1 - np.cos(phase))
    envelope = np.linspace(1.0, 1.0 - decrement, len(t))
    ratio = 0.15 + 0.95 * openness * envelope
    ratio += rng.normal(0, 0.012, len(t))          # tracker noise

    frames = []
    for i, (time_s, r) in enumerate(zip(t, ratio)):
        lost = any(lo <= time_s <= hi for lo, hi in dropout)
        # Real frames do not arrive on a perfect clock.
        stamp = round(float(time_s * 1000 + rng.normal(0, 3)), 1)
        if lost:
            frames.append({"t": stamp, "lm": None, "wl": None, "d": {}})
        else:
            aperture_m = float(r) * span_m
            frames.append({
                "t": stamp,
                "lm": [round(float(v), 4) for v in
                       np.clip(rng.normal(0.5, 0.12, 63), 0, 1)],
                "wl": fake_hand(aperture_m, span_m),
                "d": {"aperture": round(float(r), 5)},
            })

    return {
        "index": index,
        "id": trial_id,
        "hand": hand,
        "durationSec": duration,
        "frameCount": len(frames),
        "detectionRate": round(sum(f["wl"] is not None for f in frames) / len(frames), 4),
        "frames": frames,
        "events": [],
    }


def make_session(participant: str, seed: int, *, right_rate: float, left_rate: float,
                 decrement: float, jitter: float, dropout=(), demographics=None) -> dict:
    rng = np.random.default_rng(seed)
    return {
        "sessionId": f"example_{participant}",
        "experimentId": "finger-tapping",
        "experimentTitle": "Finger Tapping",
        "participantId": participant,
        "participantSource": "example",
        "startedAt": f"2026-01-0{seed % 9 + 1}T10:00:00.000Z",
        "schemaVersion": 1,
        "consent": {
            "document": "consent/consent-form.pdf",
            "agreedTo": ["I am age 18 or older.",
                         "I have read and understand the information above.",
                         "I want to participate in this research and continue with the task."],
            "agreedAt": f"2026-01-0{seed % 9 + 1}T09:58:00.000Z",
        },
        "demographics": demographics or {},
        "trials": [
            make_trial(0, "right", "right", rate_hz=right_rate,
                       decrement=decrement, jitter=jitter, rng=rng),
            make_trial(1, "left", "left", rate_hz=left_rate,
                       decrement=decrement * 1.2, jitter=jitter * 1.15,
                       dropout=dropout, rng=rng),
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/example")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir = out_dir if out_dir.is_absolute() else REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # A small spread of "people": a fast steady one, a slower irregular one with
    # a strong decrement, and one whose camera lost the hand for a few seconds.
    people = [
        dict(participant="EX01", seed=1, right_rate=5.2, left_rate=4.8,
             decrement=0.10, jitter=0.05,
             demographics={"age": 24, "sexAtBirth": "Female", "dominantHand": "Right",
                           "device": "Laptop", "participantId": "EX01"}),
        dict(participant="EX02", seed=2, right_rate=3.4, left_rate=3.0,
             decrement=0.35, jitter=0.14,
             demographics={"age": 67, "sexAtBirth": "Male", "dominantHand": "Right",
                           "device": "Desktop computer", "participantId": "EX02"}),
        dict(participant="EX03", seed=3, right_rate=4.3, left_rate=4.1,
             decrement=0.20, jitter=0.08, dropout=[(6.0, 9.0)],
             demographics={"age": 41, "sexAtBirth": "Female", "dominantHand": "Left",
                           "device": "Laptop", "participantId": "EX03"}),
    ]

    for person in people:
        session = make_session(**person)
        path = out_dir / f"{session['sessionId']}.json"
        path.write_text(json.dumps(session, indent=1), encoding="utf-8")
        print(f"  {path.relative_to(REPO_ROOT)}")

    print(f"\n{len(people)} example sessions written to {out_dir}")
    print("\nNow try:")
    print("  python analysis/compute_metrics.py --raw data/example")
    print("  python analysis/visualize.py --raw data/example --out data/example_figures")


if __name__ == "__main__":
    main()
