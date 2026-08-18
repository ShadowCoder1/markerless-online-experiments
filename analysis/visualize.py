#!/usr/bin/env python3
"""Draw the figures.

    python analysis/visualize.py

    data/figures/<session>_<trial>.png   the aperture trace with every detected
                                         tap marked. LOOK AT THESE FIRST, they
                                         are how you find out whether the tap
                                         detector agrees with your eyes.
    data/figures/_group_summary.png      rate, rhythm variability and decrement
                                         across everyone you have collected.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")          # write files without needing a screen
import matplotlib.pyplot as plt
import numpy as np

import metrics as M
from config_reader import REPO_ROOT


def plot_trial(session: dict, trial: dict, params: M.TapParams, out_dir: Path) -> Path | None:
    frames = trial.get("frames", [])
    if not frames:
        return None

    t_raw, ratio, _ = M.aperture_signal(frames)
    t, y_raw = M.resample(t_raw, ratio, params)
    if len(t) == 0:
        return None
    y = M.smooth(y_raw, params)
    taps = M.detect_taps(t, y, params)
    summary = M.analyze_trial(trial, params)

    fig, axes = plt.subplots(3, 1, figsize=(11, 8),
                             gridspec_kw={"height_ratios": [2.2, 1, 1]})

    # --- the signal itself, with taps marked ---------------------------------
    ax = axes[0]
    ax.plot(t, y_raw, lw=0.7, color="#c7ccd6", label="raw")
    ax.plot(t, y, lw=1.6, color="#1f77b4", label="smoothed")
    if len(taps["tap_times"]):
        ax.plot(taps["tap_times"], y[taps["tap_indices"]], "v",
                color="#d62728", ms=8, label=f"taps (n={len(taps['tap_times'])})")
    # Shade any stretch where the hand was lost.
    _shade_gaps(ax, t, y_raw)
    ax.set_ylabel("aperture\n(thumb–index / hand size)")
    trial_id, hand = trial.get("id"), trial.get("hand")
    label = trial_id if trial_id == hand or not hand else f"{trial_id} ({hand})"
    ax.set_title(
        f"{session.get('participantId')}, {label}   "
        f"{summary.get('rate_hz')} Hz · CV {summary.get('iti_cv')} · "
        f"detection {100 * (summary.get('detection_rate') or 0):.0f}%"
    )
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)

    # --- rhythm --------------------------------------------------------------
    ax = axes[1]
    itis, ok = taps["itis_ms"], taps["iti_valid"]
    if len(itis):
        x = np.arange(2, len(itis) + 2)
        ax.plot(x[ok], itis[ok], "o-", ms=4, color="#2ca02c", label="used")
        if (~ok).any():
            # These intervals span a tracking dropout, so they measure how long
            # the camera lost the hand, not how long the participant paused.
            # The metrics ignore them and so should your eye.
            ax.plot(x[~ok], itis[~ok], "x", ms=9, mew=2, color="#f0ad4e",
                    label="excluded (tracking gap)")
        if ok.any():
            ax.axhline(float(np.nanmedian(itis[ok])), ls="--", lw=1,
                       color="#888", label="median")
        ax.legend(fontsize=8)
    ax.set_ylabel("interval\nsince last tap (ms)")

    # --- amplitude, with the decrement line ----------------------------------
    ax = axes[2]
    amps, amp_ok = taps["amplitudes"], taps["amp_valid"]
    if len(amps) > 2:
        x = np.arange(1, len(amps) + 1)
        good = np.isfinite(amps) & amp_ok
        ax.plot(x[good], amps[good], "o-", ms=4, color="#9467bd", label="used")
        if (~good).any():
            ax.plot(x[~good], amps[~good], "x", ms=9, mew=2, color="#f0ad4e",
                    label="excluded (tracking gap)")
        if good.sum() > 2:
            fit = np.polyfit(x[good], amps[good], 1)
            ax.plot(x, np.polyval(fit, x), "--", color="#333", lw=1.2,
                    label=f"slope {fit[0]:+.4f} / tap")
        ax.legend(fontsize=8)
    ax.set_ylabel("tap amplitude")
    ax.set_xlabel("tap number")

    for a in axes:
        a.grid(alpha=0.25)

    fig.tight_layout()
    path = out_dir / f"{session.get('sessionId')}_{trial.get('id')}.png"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def _shade_gaps(ax, t: np.ndarray, y: np.ndarray) -> None:
    missing = ~np.isfinite(y)
    if not missing.any():
        return
    edges = np.diff(missing.astype(int))
    starts = list(np.where(edges == 1)[0] + 1)
    ends = list(np.where(edges == -1)[0] + 1)
    if missing[0]:
        starts.insert(0, 0)
    if missing[-1]:
        ends.append(len(t) - 1)
    for s, e in zip(starts, ends):
        ax.axvspan(t[s], t[e], color="#f0ad4e", alpha=0.25, lw=0)


def plot_group(rows: list[dict], out_dir: Path) -> Path | None:
    usable = [r for r in rows if r.get("rate_hz")]
    if not usable:
        return None

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    panels = [
        ("rate_hz", "tapping rate (Hz)", "#1f77b4"),
        ("iti_cv", "rhythm variability (CV of interval)", "#2ca02c"),
        ("amplitude_decrement_pct_per_tap", "amplitude change (% per tap)", "#9467bd"),
    ]

    for ax, (key, label, color) in zip(axes, panels):
        by_hand: dict[str, list[float]] = {}
        for r in usable:
            v = r.get(key)
            if v is not None:
                by_hand.setdefault(r.get("hand") or "hand", []).append(float(v))
        if not by_hand:
            ax.set_visible(False)
            continue

        names = sorted(by_hand)
        for i, name in enumerate(names):
            vals = by_hand[name]
            jitter = np.random.default_rng(0).normal(0, 0.045, len(vals))
            ax.scatter(np.full(len(vals), i) + jitter, vals, s=26,
                       color=color, alpha=0.65, edgecolor="none")
            ax.hlines(np.mean(vals), i - 0.22, i + 0.22, color="#111", lw=2)
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names)
        ax.set_title(label, fontsize=10)
        ax.grid(alpha=0.25, axis="y")
        if key == "amplitude_decrement_pct_per_tap":
            ax.axhline(0, color="#888", lw=1)

    fig.suptitle(f"{len(usable)} trials from "
                 f"{len({r.get('participantId') for r in usable})} participants",
                 fontsize=11)
    fig.tight_layout()
    path = out_dir / "_group_summary.png"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="data/figures")
    ap.add_argument("--participant", help="only plot this participant")
    args = ap.parse_args()

    raw_dir = _resolve(args.raw)
    out_dir = _resolve(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    params = M.TapParams()
    sessions = M.load_all(raw_dir)
    if not sessions:
        raise SystemExit(f"No session files in {raw_dir}. Run fetch_data.py first.")

    rows = []
    made = 0
    for session in sessions:
        if args.participant and session.get("participantId") != args.participant:
            continue
        for trial in session.get("trials", []):
            path = plot_trial(session, trial, params, out_dir)
            if path:
                made += 1
                print(f"  {path.name}")
            rows.append({**M.analyze_trial(trial, params),
                         "participantId": session.get("participantId")})

    group = plot_group(rows, out_dir)
    print(f"\n{made} trial figure(s) in {out_dir}")
    if group:
        print(f"Group summary: {group}")


def _resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    main()
