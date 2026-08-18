# I want to change…

Each entry says which file to open and what to change. Nothing here needs a
rebuild — save and reload the page.

---

## …the wording participants see

| What | Where |
|---|---|
| Study title, lab name, contact | `config.js` → `STUDY` |
| Consent text | `config.js` → `STUDY.consentHtml` |
| Task instructions | `experiments/finger-tapping.js` → `instructions` |
| The prompt during a trial | the `prompt` field on each entry in `trials` |
| Everything else (buttons, screens) | `index.html` — it is plain HTML |

## …how long, or how many, the trials are

`experiments/finger-tapping.js` → `trials`. Each entry is one trial:

```js
trials: [
  { id: "right", hand: "right", durationSec: 15, prompt: "Tap with your RIGHT hand." },
  { id: "left",  hand: "left",  durationSec: 15, prompt: "Now your LEFT hand." },
],
```

Add, remove, or reorder freely. Any extra field you invent (`condition`,
`targetSize`, …) is handed to your hooks and saved with the data.

Four 20-second trials, alternating hands:

```js
trials: [
  { id: "r1", hand: "right", durationSec: 20, prompt: "RIGHT hand" },
  { id: "l1", hand: "left",  durationSec: 20, prompt: "LEFT hand"  },
  { id: "r2", hand: "right", durationSec: 20, prompt: "RIGHT hand again" },
  { id: "l2", hand: "left",  durationSec: 20, prompt: "LEFT hand again"  },
],
```

## …which body part is tracked

In your experiment file:

```js
tracker: "pose",                    // instead of "hand"
trackerOptions: { numPoses: 1 },
```

You then get 33 whole-body landmarks instead of 21 hand ones, and you index them
with `POSE.LEFT_WRIST` and friends (see `js/core/tracker.js`). Everything else —
recording, uploading, analysis plumbing — is unchanged.

To track both hands: `trackerOptions: { numHands: 2 }`. Note that `onFrame`
receives only the first detected hand; for two-handed tasks, read
`res.landmarks[1]` by editing `recordTrial` in `js/core/experiment.js`.

## …what counts as a tap

Two separate places, on purpose:

- **The live counter participants see** — the constants at the bottom of
  `experiments/finger-tapping.js` (`CLOSE_FRACTION`, `REFRACTORY_MS`, …).
- **Your actual results** — `TapParams` at the top of `analysis/metrics.py`.
  These are the ones that matter. You can also override them per run:

```bash
python analysis/compute_metrics.py --prominence 0.20 --min-iti 120
```

Raise `prominence_fraction` if noise is being counted as taps; lower it if small
late taps are being missed. Always check the change against the figures.

## …which measurements come out

`analysis/metrics.py` → `_summarise()`. Add a line, re-run
`compute_metrics.py`, and it appears as a new column in `trial_metrics.csv`.

For something you want computed *during* the session (so the participant can see
it, or so it lands in the small session document), use `onTrialEnd` in your
experiment file instead.

## …how it looks

`css/style.css`. The colour variables at the top drive everything:

```css
:root {
  --bg: #0f1115;      /* page background */
  --accent: #4f8cff;  /* buttons, progress bar */
  --good: #4ade80;    /* landmark overlay when fingers are apart */
  --bad: #f87171;     /* …and when they are closed */
}
```

For a light theme, swap `--bg` to `#ffffff` and `--text` to `#111`.

## …how much data is recorded

`config.js` → `RECORDING`.

- `video: { width, height }` — lower it if participants report lag.
- `decimals` — coordinate precision. 4 is already well below the tracker's noise.
- `chunkFrames` — how many frames per Firestore document. **Only lower this**,
  never raise it much: documents are capped at 1 MiB and a chunk that exceeds it
  fails to upload. See [DATA_FORMAT.md](DATA_FORMAT.md).
- `alsoDownloadLocally: true` — also hand the participant a JSON copy. Handy
  while piloting; turn it off for real collection.

## …running more than one experiment at the same time

Every experiment lives in its own file, and the URL picks which one runs:

```
https://you.github.io/your-repo/?exp=finger-tapping
https://you.github.io/your-repo/?exp=my-task
```

Give each Prolific study a different `?exp=` link. The data separates itself:
`experimentId` is stored on every session, and

```bash
python analysis/fetch_data.py --experiment my-task
```

downloads only that one.

## …assigning participants to conditions

Add `?condition=fast` to the link and it is saved with the session, ready to
group by later. Inside an experiment, read it with:

```js
import { getParticipant } from "../js/core/participant.js";
const { condition } = getParticipant();
```
