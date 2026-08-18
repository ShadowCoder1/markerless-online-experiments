# What the data looks like

## In Firestore

```
sessions/{sessionId}                      small: who, when, per-trial summaries
sessions/{sessionId}/chunks/{trial}_{n}   large: the raw landmarks
```

A `sessionId` looks like `20260118T143052_a7f3k2`. It is the time the session
started plus a few random characters, so ids sort chronologically and do not
collide.

### The session document

Written **once, at the very end** of a session.

```jsonc
{
  "sessionId": "20260118T143052_a7f3k2",
  "uid": "…",                    // anonymous Firebase id for this participant
  "experimentId": "finger-tapping",
  "participantId": "5f2a…",      // Prolific id, ?pid= value, or typed in
  "participantSource": "prolific",
  "prolific": { "pid": "…", "studyId": "…", "sessionId": "…" },
  "condition": null,             // from ?condition= in the URL
  "startedAt": "2026-01-18T14:30:52.123Z",
  "finishedAt": "<server timestamp>",

  "consent": {
    "document": "consent/consent-form.pdf",   // which form they were shown
    "agreedTo": ["I am age 18 or older.", "..."],  // the exact wording ticked
    "agreedAt": "2026-01-18T14:29:40.010Z"
  },

  // Answers to the questions in questions.js, keyed by question id.
  // Unanswered optional questions are absent rather than empty.
  "demographics": { "age": 29, "dominantHand": "Left", "device": "Laptop" },

  "trials": [
    {
      "index": 0,
      "id": "right",
      "hand": "right",
      "durationSec": 15,
      "frameCount": 448,
      "detectionRate": 0.982,
      "events": [ { "t": 412.3, "type": "tap", "aperture": 0.19 } ],
      "tapCount": 61                  // live estimate, see the note below
    }
  ],
  "settings": { … },             // the config in force, so you can tell later
  "environment": { … },          // browser, screen size, timezone, CPU count
  "schemaVersion": 1
}
```

> **`tapCount` is not your result.** It comes from the simple detector running
> live in the browser. The number to report comes from `analysis/metrics.py`,
> which recomputes everything from the raw landmarks. They will not always
> agree, and when they disagree the Python one is right.

### The chunk documents

```jsonc
{
  "uid": "…", "sessionId": "…", "experimentId": "finger-tapping",
  "trialIndex": 0, "trialId": "right",
  "chunkIndex": 0, "chunkCount": 2,
  "frames": [ … ]
}
```

Named `{trialIndex:003}_{chunkIndex:003}`, so sorting by document id restores
the original order.

**Why chunks?** A Firestore document cannot exceed 1 MiB. One frame of hand
tracking is about 1.2 KB, so 15 seconds at 30 fps is roughly 540 KB and 30
seconds would not fit. `RECORDING.chunkFrames` (default 250) keeps each document
around 300 KB. `fetch_data.py` reassembles them, so this never reaches you.

### One frame

```jsonc
{
  "t": 133.4,                    // milliseconds since this trial started
  "lm": [x0, y0, z0, x1, y1, z1, …],   // 63 numbers: 21 landmarks, screen coords
  "wl": [x0, y0, z0, …],               // 63 numbers: the same, in metres
  "d":  { "aperture": 0.83 }           // whatever your onFrame() returned
}
```

- `lm` holds image coordinates. `x` and `y` run from 0 to 1 across the frame.
  Use these for drawing. Because `x` is scaled by the width and `y` by the
  height, distances measured in these units are distorted whenever the video is
  not square.
- `wl` holds world coordinates, in metres, with the origin at the middle of the
  hand. Use these for measurement. They do not change when the participant leans
  towards the camera.
- `lm` and `wl` are **`null`** on frames where nothing was detected. They are
  kept rather than dropped, so gaps in tracking stay visible in your data
  instead of quietly closing up.

Landmark *i* occupies elements `3i`, `3i+1`, `3i+2`. The
[hand landmark map](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker)
tells you which joint is which; `js/core/tracker.js` has them as named
constants.

---

## On your computer

`analysis/fetch_data.py` writes one file per session:

```
data/raw/20260118T143052_a7f3k2.json    the session document, with each trial's
                                        chunks glued back into trial["frames"]
data/raw/_sessions.csv                  an index of everything you have
```

`analysis/compute_metrics.py` then writes:

```
data/processed/trial_metrics.csv   one row per trial   <- start here
data/processed/taps.csv            one row per tap
data/processed/settings.json       the detection settings used
```

### Columns in `trial_metrics.csv`

| Column | Meaning |
|---|---|
| `n_taps` | taps detected |
| `rate_hz` | taps per second **of analysed time** |
| `fft_peak_hz` | dominant frequency of the signal, found without peak detection, so it is an independent check on `rate_hz` |
| `iti_mean_ms`, `iti_sd_ms`, `iti_cv` | inter-tap intervals: speed and rhythm variability |
| `amplitude_mean/sd/cv` | how wide the fingers opened |
| `amplitude_slope` | change in amplitude per tap. Negative = shrinking (the sequence effect / decrement) |
| `amplitude_decrement_pct_per_tap` | the same, as a percentage of the opening amplitude |
| `rate_slope_hz_per_tap` | whether tapping slowed across the trial |
| `n_halts` | pauses longer than `halt_multiplier` × this person's median interval |
| `detection_rate` | fraction of frames with a visible hand. Below ~0.9 deserves a look |
| `analysed_sec` | time the hand was actually visible |
| `lost_to_tracking_sec` | time lost to dropouts |
| `n_intervals_used` / `n_intervals_dropped` | intervals kept vs discarded for spanning a dropout |
| `fps` | median frame rate achieved on that participant's machine |
| `demo_*` | one column per question in `questions.js`. `id: "age"` becomes `demo_age` |

**Tracking dropouts are excluded, not patched over.** `rate_hz` divides by
`analysed_sec` rather than trial length, intervals spanning a gap are dropped
from the rhythm statistics, and a peak at the truncated edge of a gap is not
counted as a tap. Without this, three seconds of lost tracking shows up as a
movement halt and inflates rhythm variability by a factor of twenty. In a
patient study that would read as a clinical finding rather than a camera
problem.
