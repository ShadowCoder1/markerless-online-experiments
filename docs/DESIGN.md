# Design notes

Why this repository is shaped the way it is. Read this before making a large
change; most of these decisions have a failure mode behind them.

## Goal

Someone who has never built an online study should be able to collect real
markerless-tracking data from remote participants in an afternoon, and should be
able to turn the included finger-tapping task into their own task by editing one
file.

## Decisions

**No build step.** Plain ES modules, MediaPipe and Firebase loaded from CDNs. No
npm, no bundler, no `node_modules`. Editing a file and reloading the page is the
whole development loop. The cost is that the page must be served over HTTP
rather than opened from disk, which `check.html` detects and explains.

**The site sits at the repository root.** GitHub Pages "deploy from a branch"
then works with no configuration and no CI, which also means the repo needs no
`workflow` permissions. `.nojekyll` stops Pages from trying to process it.

**A core plus experiment files, rather than one file per experiment.** The
camera, tracker, recorder, upload, and screen flow live in `js/core/` and are
written once. An experiment is a single file declaring five hooks. Copy-pasting
the plumbing per experiment would have been simpler to read on day one and
unmaintainable by the third experiment.

**Landmarks only; video never leaves the browser.** Smaller, faster, and a far
easier IRB conversation. MediaPipe runs locally, so this costs nothing
scientifically for the tasks this is aimed at.

**Two collections, because Firestore documents cap at 1 MiB.** One frame of hand
tracking is ~1.2 KB, so a 30-second trial does not fit in a single document. The
small `sessions/{id}` document holds identity and summary numbers and is what
most queries touch; raw frames go to `sessions/{id}/chunks/{trial}_{n}` at
`chunkFrames` (250) per document, about 300 KB each. `fetch_data.py` reassembles
them so this never surfaces.

**Chunks upload after every trial; the session document is written last.** A
participant who quits halfway still leaves usable data. It also gives a free
integrity check: chunks with no parent session document are exactly the dropouts,
and `fetch_data.py` reports them separately rather than mixing partial sessions
into the dataset.

**Create-only security rules, with anonymous auth.** Participants can add their
own data and can do nothing else — no reads, no updates, no deletes. Analysis
authenticates as the project owner and bypasses rules entirely. Firebase's "test
mode" was rejected twice over: it exposes every participant's data to the
internet, and it silently expires after 30 days, which for a running study means
a week of failed uploads before anyone notices.

**Tap detection runs twice, on purpose.** The browser detects taps live so the
participant sees a counter; `analysis/metrics.py` re-derives every tap from the
raw landmarks and is authoritative. This decouples the detection threshold from
data collection: you can change your mind after seeing the data without
recollecting it. `DATA_FORMAT.md` says so wherever the live number appears.

**World landmarks for measuring, image landmarks for drawing.** MediaPipe's
image coordinates are normalised separately by width and height, so distances in
those units are distorted by the frame's aspect ratio and by how far the
participant sits from the camera. World landmarks are metric. Aperture is
additionally divided by each participant's own wrist-to-knuckle distance, making
it comparable across hand sizes.

**Frames with no detection are stored as nulls, not dropped.** A dropped frame
is indistinguishable from a fast movement once the timestamps are gone. Keeping
the gap visible is what makes the next decision possible.

**Tracking dropouts are excluded from statistics rather than patched over.**
This was found by testing, not by design. A simulated trial with a three-second
camera dropout originally reported a movement halt and a rhythm variability
twenty times too high, because:

- the dropout appeared as one enormous inter-tap interval;
- `rate_hz` divided by trial length, including the dead time; and
- `find_peaks` treated the truncated edge of the gap as a local minimum, adding
  two taps that never happened.

All three are now handled: intervals spanning a gap are dropped, the rate
denominator is `analysed_sec`, and a closure must have valid data on both sides
(`edge_guard_seconds`) to be believed. After the fix the dropout trial's metrics
are within 1.5% of the clean ones. In a patient study the original behaviour
would have read as a clinical finding rather than a camera problem — which is
the kind of bug worth a paragraph.

**Text lives in HTML, not on the canvas.** The video and its overlay are
mirrored with a CSS transform so participants see themselves the right way
round; anything drawn on the canvas is therefore mirrored too. Live numbers go
into a DOM element positioned over the video, and experiments receive a
`setReadout()` callback rather than drawing text.

## How this was verified

- **Ground truth recovery.** `make_example_data.py` generates sessions at known
  tapping rates; the pipeline recovers all of them within 2.6%, including one
  with a three-second dropout.
- **Live detector.** Driven with synthetic hands at 2, 4, and 6 Hz in a real
  browser: exact at 2 and 4 Hz, one tap short at 6 Hz.
- **End to end.** A headless browser runs a full session with mocked Firebase,
  confirming every screen transition, per-trial chunk upload, and the session
  document's shape.
- **Round trip.** A synthetic hand tapping at exactly 4.0 Hz was recorded
  through the real browser recorder, chunked, reassembled, and analysed: 3.93
  and 4.00 Hz out.

`make_example_data.py` ships partly because it was the test harness — it lets
anyone re-run these checks, and lets a new user exercise the analysis before
recruiting a single participant.

## Deliberately not included

- **A backend of our own.** Firebase means no server to maintain, and rules that
  are auditable in one screenful.
- **A JavaScript test suite.** Would need the toolchain this design exists to
  avoid. The verification above runs from the repo with Playwright and Python.
- **More experiments.** One complete, heavily commented task plus a template
  teaches more than four thin ones. Reach-to-target, postural tremor, and
  sit-to-stand are all straightforward additions on this core.
