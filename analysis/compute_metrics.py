#!/usr/bin/env python3
"""Turn downloaded sessions into two tidy tables you can open in anything.

    python analysis/compute_metrics.py

    data/processed/trial_metrics.csv   one row per trial  <- start here
    data/processed/taps.csv            one row per individual tap
    data/processed/settings.json       the settings used, for your methods section

Change the detection settings with flags, e.g.

    python analysis/compute_metrics.py --prominence 0.20 --min-iti 120

Nothing is ever overwritten in data/raw/, so you can run this as often as you
like with different settings.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

import metrics as M
from config_reader import REPO_ROOT


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default="data/raw", help="folder of session JSON files")
    ap.add_argument("--out", default="data/processed", help="where to write the tables")
    ap.add_argument("--min-iti", type=float, help="shortest allowed gap between taps, ms")
    ap.add_argument("--prominence", type=float,
                    help="how deep a dip must be to count, 0-1 of the participant's range")
    ap.add_argument("--smooth", type=float, help="smoothing window in seconds")
    args = ap.parse_args()

    params = M.TapParams()
    if args.min_iti is not None:
        params.min_iti_ms = args.min_iti
    if args.prominence is not None:
        params.prominence_fraction = args.prominence
    if args.smooth is not None:
        params.smooth_seconds = args.smooth

    raw_dir = _resolve(args.raw)
    out_dir = _resolve(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    sessions = M.load_all(raw_dir)
    if not sessions:
        raise SystemExit(
            f"No session files found in {raw_dir}.\n"
            "Run  python analysis/fetch_data.py  first."
        )

    trial_rows, tap_rows = [], []

    for session in sessions:
        who = {
            "sessionId": session.get("sessionId"),
            "participantId": session.get("participantId"),
            "experimentId": session.get("experimentId"),
            "startedAt": session.get("startedAt"),
            "condition": session.get("condition"),
        }
        for trial in session.get("trials", []):
            trial_rows.append({**who, **M.analyse_trial(trial, params)})

            # Per-tap detail, for anyone who wants to model tap-by-tap.
            frames = trial.get("frames", [])
            if not frames:
                continue
            t_raw, ratio, _ = M.aperture_signal(frames)
            t, y = M.resample(t_raw, ratio, params)
            if len(t) == 0:
                continue
            taps = M.detect_taps(t, M.smooth(y, params), params)
            itis = list(taps["itis_ms"])
            for n, (time_s, amp) in enumerate(zip(taps["tap_times"], taps["amplitudes"])):
                tap_rows.append({
                    **who,
                    "trialIndex": trial.get("index"),
                    "trialId": trial.get("id"),
                    "hand": trial.get("hand"),
                    "tapNumber": n + 1,
                    "timeSec": round(float(time_s), 4),
                    "amplitude": _num(amp),
                    "itiFromPreviousMs": _num(itis[n - 1]) if n > 0 else None,
                })

    _write_csv(out_dir / "trial_metrics.csv", trial_rows)
    _write_csv(out_dir / "taps.csv", tap_rows)
    (out_dir / "settings.json").write_text(
        json.dumps(M.params_as_dict(params), indent=2), encoding="utf-8")

    print(f"{len(sessions)} session(s), {len(trial_rows)} trial(s), {len(tap_rows)} tap(s)")
    print(f"  {out_dir / 'trial_metrics.csv'}")
    print(f"  {out_dir / 'taps.csv'}")
    print(f"  {out_dir / 'settings.json'}")

    _warn_about_bad_trials(trial_rows)


def _warn_about_bad_trials(rows: list[dict]) -> None:
    """Point out trials worth looking at by eye before they go into an analysis."""
    problems = []
    for r in rows:
        label = f"{r.get('participantId')} / {r.get('trialId')}"
        if (r.get("detection_rate") or 1) < 0.9:
            problems.append(f"  {label}: hand visible only "
                            f"{100 * r['detection_rate']:.0f}% of frames")
        rate, fft = r.get("rate_hz"), r.get("fft_peak_hz")
        if rate and fft and abs(rate - fft) > 0.5 * max(rate, fft):
            problems.append(f"  {label}: counted {rate:.2f} Hz but the signal's own "
                            f"frequency is {fft:.2f} Hz, check the detection settings")
        if (r.get("n_taps") or 0) < 5:
            problems.append(f"  {label}: only {r.get('n_taps')} taps detected")

    if problems:
        print("\nWorth a look before you analyse these:")
        print("\n".join(problems))
        print("\nPlot them with:  python analysis/visualize.py")


def _resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else REPO_ROOT / path


def _num(v):
    return None if v is None or not np.isfinite(v) else round(float(v), 5)


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
