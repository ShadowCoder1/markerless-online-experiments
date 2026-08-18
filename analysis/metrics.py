"""Turn raw hand landmarks into finger-tapping measurements.

This is the file to read (and change) if you disagree with how a tap is
defined. Everything here works from the raw landmarks that were saved during
the session, so you can re-run it with different settings as many times as you
like without collecting new data.

WHAT IT MEASURES, and why each one is here
    rate_hz              taps per second, overall speed
    iti_*                inter-tap intervals, rhythm and its variability
    amplitude_*          how wide the fingers opened on each tap
    amplitude_slope      whether amplitude shrinks across the trial. Clinicians
                         call this the sequence effect / decrement, and it is
                         part of MDS-UPDRS item 3.4.
    rate_slope           whether tapping slows across the trial
    n_halts              momentary freezes: gaps far longer than the person's
                         own median interval
    fft_peak_hz          dominant frequency straight from the signal. It does
                         not depend on peak detection at all, so if it
                         disagrees badly with rate_hz, your peak-detection
                         settings are probably wrong for that participant.
    detection_rate       fraction of frames where the hand was actually
                         visible. Treat a trial below ~0.9 with suspicion.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks, savgol_filter, welch

# Landmark positions inside the flat coordinate array.
# Landmark i occupies elements [3i, 3i+1, 3i+2].
WRIST, THUMB_TIP, INDEX_TIP, MIDDLE_MCP = 0, 4, 8, 9


@dataclass
class TapParams:
    """Everything you might want to tune, in one place.

    Change these and re-run compute_metrics.py, no new data collection needed.
    """

    resample_hz: float = 60.0
    """Frames arrive at irregular intervals, so we put the signal on an even
    time grid first. Everything downstream assumes this rate."""

    smooth_seconds: float = 0.10
    """Width of the smoothing window. Long enough to remove tracker jitter,
    short enough not to blunt a fast tap."""

    min_iti_ms: float = 90.0
    """Two closures closer together than this are treated as one. 90 ms is
    roughly 11 taps/second, faster than people actually tap."""

    prominence_fraction: float = 0.15
    """How deep a dip must be to count as a tap, as a fraction of the
    participant's own aperture range. Raise it if noise is being counted;
    lower it if small late taps are being missed."""

    max_gap_ms: float = 150.0
    """Tracking dropouts shorter than this are bridged by interpolation.
    Longer ones stay as gaps so they cannot invent taps."""

    halt_multiplier: float = 2.0
    """An interval longer than this many times the median counts as a halt."""

    edge_guard_seconds: float = 0.05
    """How much valid data a closure needs on either side to be believed.
    Stops the truncated edge of a tracking dropout being counted as a tap."""


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_session(path: str | Path) -> dict:
    """Read one of the JSON files written by fetch_data.py."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_all(folder: str | Path) -> list[dict]:
    """Read every session in a folder, oldest first."""
    files = sorted(p for p in Path(folder).glob("*.json") if not p.name.startswith("_"))
    return [load_session(p) for p in files]


# ---------------------------------------------------------------------------
# From landmarks to a single number per frame
# ---------------------------------------------------------------------------

def aperture_signal(frames: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Distance between thumb tip and index fingertip, over time.

    Returns (t_seconds, ratio, metres). `ratio` divides the distance by the
    participant's own hand size, which makes it comparable between people and
    immune to how far they sit from the camera. NaN marks frames where no hand
    was detected.
    """
    t = np.array([f.get("t", np.nan) for f in frames], dtype=float) / 1000.0
    ratio = np.full(len(frames), np.nan)
    metres = np.full(len(frames), np.nan)

    for i, frame in enumerate(frames):
        world = frame.get("wl")
        if world and len(world) >= 30:
            w = np.asarray(world, dtype=float)
            gap = _dist(w, THUMB_TIP, INDEX_TIP)
            span = _dist(w, WRIST, MIDDLE_MCP)
            metres[i] = gap
            if span > 0:
                ratio[i] = gap / span
        else:
            # Fall back to whatever the browser computed, if world landmarks
            # were not stored for some reason.
            live = (frame.get("d") or {}).get("aperture")
            if live is not None:
                ratio[i] = float(live)

    return t, ratio, metres


def _dist(flat: np.ndarray, a: int, b: int) -> float:
    pa, pb = flat[3 * a:3 * a + 3], flat[3 * b:3 * b + 3]
    return float(np.linalg.norm(pa - pb))


def resample(t: np.ndarray, y: np.ndarray, params: TapParams
             ) -> tuple[np.ndarray, np.ndarray]:
    """Put an irregularly sampled signal onto an even time grid.

    Short tracking dropouts are bridged; long ones stay as NaN so that a gap
    can never masquerade as a tap.
    """
    good = np.isfinite(t) & np.isfinite(y)
    if good.sum() < 4:
        return np.array([]), np.array([])

    t_g, y_g = t[good], y[good]
    grid = np.arange(t_g[0], t_g[-1], 1.0 / params.resample_hz)
    out = np.interp(grid, t_g, y_g)

    # Blank out anything that fell inside a long dropout.
    gaps = np.diff(t_g)
    for start, gap in zip(t_g[:-1], gaps):
        if gap > params.max_gap_ms / 1000.0:
            out[(grid > start) & (grid < start + gap)] = np.nan

    return grid, out


def smooth(y: np.ndarray, params: TapParams) -> np.ndarray:
    """Savitzky-Golay smoothing, which preserves peak height better than a
    plain moving average. NaNs are bridged for filtering, then restored."""
    window = int(params.smooth_seconds * params.resample_hz) | 1  # must be odd
    if len(y) <= window or window < 5:
        return y

    missing = ~np.isfinite(y)
    if missing.all():
        return y

    filled = y.copy()
    idx = np.arange(len(y))
    filled[missing] = np.interp(idx[missing], idx[~missing], y[~missing])

    out = savgol_filter(filled, window_length=window, polyorder=2)
    out[missing] = np.nan
    return out


# ---------------------------------------------------------------------------
# Finding taps
# ---------------------------------------------------------------------------

def detect_taps(t: np.ndarray, y: np.ndarray, params: TapParams) -> dict:
    """Find each finger closure, and how wide the fingers were beforehand.

    A tap is a local minimum in the aperture signal that is deep enough
    (`prominence_fraction` of the participant's range) and far enough from the
    previous one (`min_iti_ms`).
    """
    empty = {"tap_times": np.array([]), "tap_indices": np.array([], dtype=int),
             "amplitudes": np.array([]), "itis_ms": np.array([]),
             "iti_valid": np.array([], dtype=bool),
             "amp_valid": np.array([], dtype=bool)}
    if len(y) == 0 or not np.isfinite(y).any():
        return empty

    finite = y[np.isfinite(y)]
    spread = float(np.percentile(finite, 97) - np.percentile(finite, 3))
    if spread <= 0:
        return empty

    # find_peaks cannot handle NaN, so fill gaps with a high value: that makes
    # them look like "fingers wide open", which can never be mistaken for a tap.
    searchable = np.where(np.isfinite(y), y, np.nanmax(finite))

    closures, _ = find_peaks(
        -searchable,
        distance=max(1, int(params.min_iti_ms / 1000.0 * params.resample_hz)),
        prominence=params.prominence_fraction * spread,
    )

    # Drop anything that is not a real minimum. Where tracking cuts out
    # mid-movement, the last sample before the gap looks like a dip simply
    # because the signal stops there. A genuine closure has valid data on BOTH
    # sides of it, so that is what we require.
    guard = max(1, int(params.edge_guard_seconds * params.resample_hz))
    closures = np.array(
        [i for i in closures
         if np.isfinite(y[max(0, i - guard):i + guard + 1]).all()],
        dtype=int,
    )
    if len(closures) == 0:
        return empty

    # Amplitude of a tap = how far the fingers opened before closing.
    # An amplitude measured across a tracking dropout is not trustworthy, so we
    # record whether each one is clean.
    amplitudes, amp_valid = [], []
    for n, close_idx in enumerate(closures):
        start = closures[n - 1] if n > 0 else 0
        window = y[start:close_idx + 1]
        amp_valid.append(bool(np.isfinite(window).all()))
        window = window[np.isfinite(window)]
        amplitudes.append(float(window.max() - y[close_idx]) if len(window) else np.nan)

    # Same for the intervals. An interval that spans a dropout tells you how
    # long the camera lost the hand for, NOT how long the participant paused, # counting it as either a slow tap or a movement halt would be wrong.
    iti_valid = np.array(
        [bool(np.isfinite(y[a:b + 1]).all()) for a, b in zip(closures[:-1], closures[1:])],
        dtype=bool,
    )

    tap_times = t[closures]
    return {
        "tap_times": tap_times,
        "tap_indices": closures,
        "amplitudes": np.array(amplitudes),
        "amp_valid": np.array(amp_valid, dtype=bool),
        "itis_ms": np.diff(tap_times) * 1000.0,
        "iti_valid": iti_valid,
    }


def dominant_frequency(t: np.ndarray, y: np.ndarray, params: TapParams) -> float:
    """Strongest oscillation frequency between 0.5 and 10 Hz.

    Computed straight from the signal, with no peak detection involved, so it
    is a useful independent check on `rate_hz`.
    """
    finite = np.isfinite(y)
    if finite.sum() < params.resample_hz * 2:      # need at least ~2 seconds
        return float("nan")

    signal = y.copy()
    idx = np.arange(len(y))
    signal[~finite] = np.interp(idx[~finite], idx[finite], y[finite])
    signal = signal - signal.mean()

    freqs, power = welch(signal, fs=params.resample_hz,
                         nperseg=min(len(signal), int(params.resample_hz * 4)))
    band = (freqs >= 0.5) & (freqs <= 10)
    if not band.any():
        return float("nan")
    return float(freqs[band][np.argmax(power[band])])


# ---------------------------------------------------------------------------
# One trial, start to finish
# ---------------------------------------------------------------------------

def analyse_trial(trial: dict, params: TapParams | None = None) -> dict:
    """Everything above, applied to one trial. Returns a flat dict of numbers."""
    params = params or TapParams()
    frames = trial.get("frames", [])

    result = {
        "trialIndex": trial.get("index"),
        "trialId": trial.get("id"),
        "hand": trial.get("hand"),
        "durationSec": trial.get("durationSec"),
        "frameCount": len(frames),
        "liveTapCount": trial.get("tapCount"),
    }

    if not frames:
        return {**result, "n_taps": 0, "note": "no frames recorded"}

    t_raw, ratio, _ = aperture_signal(frames)
    result["detection_rate"] = float(np.isfinite(ratio).mean())
    result["fps"] = _median_fps(t_raw)

    t, y = resample(t_raw, ratio, params)
    if len(t) == 0:
        return {**result, "n_taps": 0, "note": "hand was never detected"}

    y = smooth(y, params)
    taps = detect_taps(t, y, params)
    result.update(_summarise(taps, t, y, params))
    return result


def _summarise(taps: dict, t: np.ndarray, y: np.ndarray, params: TapParams) -> dict:
    times = taps["tap_times"]
    amps = taps["amplitudes"][taps["amp_valid"]] if len(taps["amplitudes"]) else np.array([])
    duration = float(t[-1] - t[0]) if len(t) else np.nan

    # Only intervals that do not span a tracking dropout say anything about the
    # participant's rhythm.
    itis = taps["itis_ms"][taps["iti_valid"]] if len(taps["itis_ms"]) else np.array([])

    # Time the hand was actually visible. Using this as the denominator stops a
    # camera dropout from looking like the participant slowed down.
    analysed = float(np.isfinite(y).sum()) / params.resample_hz
    # max(0, ...) because the sample count and the end-to-end duration differ by
    # one sample period on a trial with no dropouts at all.
    lost = max(0.0, duration - analysed) if np.isfinite(duration) else np.nan

    out = {
        "n_taps": int(len(times)),
        "recorded_sec": _round(duration, 2),
        "analysed_sec": _round(analysed, 2),
        "lost_to_tracking_sec": _round(lost, 2),
        "rate_hz": _round(len(times) / analysed if analysed > 0 else np.nan, 3),
        "fft_peak_hz": _round(dominant_frequency(t, y, params), 3),
        "iti_mean_ms": _round(_nanmean(itis), 1),
        "iti_sd_ms": _round(_nanstd(itis), 1),
        "iti_cv": _round(_nanstd(itis) / _nanmean(itis) if _nanmean(itis) else np.nan, 4),
        "amplitude_mean": _round(_nanmean(amps), 4),
        "amplitude_sd": _round(_nanstd(amps), 4),
        "amplitude_cv": _round(_nanstd(amps) / _nanmean(amps) if _nanmean(amps) else np.nan, 4),
    }

    # Decrement: does amplitude shrink as the trial goes on? Negative slope
    # means yes. Also expressed as percent of the starting amplitude per tap,
    # which is easier to compare between participants.
    out["amplitude_slope"] = _round(_slope(amps), 6)
    first = _nanmean(amps[:max(1, len(amps) // 3)]) if len(amps) else np.nan
    out["amplitude_decrement_pct_per_tap"] = _round(
        100 * out["amplitude_slope"] / first if first else np.nan, 4)

    # Does tapping slow down? Slope of instantaneous rate across taps.
    inst_rate = 1000.0 / itis if len(itis) else np.array([])
    out["rate_slope_hz_per_tap"] = _round(_slope(inst_rate), 6)

    # Halts: the participant pausing. Only genuine intervals can qualify, an
    # interval spanning a dropout was already excluded above.
    if len(itis) >= 3:
        median = float(np.nanmedian(itis))
        out["n_halts"] = int(np.nansum(itis > params.halt_multiplier * median))
        out["longest_iti_ms"] = _round(float(np.nanmax(itis)), 1)
    else:
        out["n_halts"] = 0
        out["longest_iti_ms"] = None

    out["n_intervals_used"] = int(len(itis))
    out["n_intervals_dropped"] = int(len(taps["itis_ms"]) - len(itis))

    return out


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _median_fps(t_seconds: np.ndarray) -> float | None:
    diffs = np.diff(t_seconds[np.isfinite(t_seconds)])
    diffs = diffs[diffs > 0]
    return _round(float(1.0 / np.median(diffs)), 1) if len(diffs) else None


def _slope(values: np.ndarray) -> float:
    """Least-squares slope of `values` against its own index."""
    good = np.isfinite(values)
    if good.sum() < 3:
        return float("nan")
    x = np.arange(len(values))[good]
    return float(np.polyfit(x, values[good], 1)[0])


def _nanmean(a: np.ndarray) -> float:
    return float(np.nanmean(a)) if len(a) and np.isfinite(a).any() else float("nan")


def _nanstd(a: np.ndarray) -> float:
    return float(np.nanstd(a, ddof=1)) if len(a) > 1 and np.isfinite(a).sum() > 1 else float("nan")


def _round(v, decimals):
    if v is None:
        return None
    try:
        return None if not np.isfinite(v) else round(float(v), decimals)
    except TypeError:
        return None


def params_as_dict(params: TapParams) -> dict:
    """Handy for recording which settings produced a results table."""
    return asdict(params)
