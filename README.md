# Markerless online experiments

Run hand- and body-movement experiments over the web. Participants open a link,
their webcam is analysed **on their own computer**, and only the numeric joint
positions come back to you. No app to install, no lab visit, no video uploaded.

Built on [MediaPipe](https://ai.google.dev/edge/mediapipe) for tracking and
[Firebase](https://firebase.google.com/) for storage. There is no build step and
no `npm install` — you edit a file and refresh the page.

A complete **finger-tapping** experiment is included and ready to run:
**[try it live](https://shadowcoder1.github.io/markerless-online-experiments/)**
(it will ask for your camera, then stop at the Firebase step — that part is
yours to set up).

---

## What you get

| | |
|---|---|
| **A working experiment** | Finger tapping, with live feedback, two hands, and per-trial summary numbers |
| **A template** | `experiments/_template.js` — five commented hooks, and you have your own task |
| **A setup checker** | `check.html` runs every part of the pipeline and tells you exactly what is broken |
| **Real security rules** | Participants can only ever add data. Nobody can read or delete it through the website |
| **Analysis in Python** | Download → metrics table → figures, in three commands |
| **Example data** | Try the whole analysis pipeline before you recruit anyone |

---

## Try it in two minutes, with no accounts and no setup

You can see the analysis half working right now:

```bash
git clone https://github.com/ShadowCoder1/markerless-online-experiments.git
cd markerless-online-experiments
pip install -r analysis/requirements.txt

python analysis/make_example_data.py                                  # invent 3 participants
python analysis/compute_metrics.py --raw data/example                 # -> a metrics table
python analysis/visualize.py --raw data/example --out data/example_figures   # -> figures
```

Open `data/example_figures/` and look at the pictures. Every tap the software
found is marked, so you can check its work by eye.

---

## Run the actual experiment

### 1. Serve the folder

Browsers block webcam access for pages opened directly from disk, so run a tiny
local server:

```bash
python3 -m http.server 8000
```

Then open **<http://localhost:8000/check.html>**. Some checks will fail until you
have done step 2 — that is expected and the page will tell you so.

### 2. Connect Firebase

Follow **[docs/SETUP.md](docs/SETUP.md)**. It takes about 15 minutes and you only
do it once. When you are done, `check.html` should be all green.

### 3. Collect data

Open **<http://localhost:8000/>** and do the experiment on yourself. Then:

```bash
gcloud auth application-default login     # once per computer
python analysis/fetch_data.py
python analysis/compute_metrics.py
python analysis/visualize.py
```

### 4. Put it online

Push your copy to GitHub, then **Settings → Pages → Source: Deploy from a
branch → `main` / root**. A minute later your study is live at
`https://<your-username>.github.io/<your-repo>/`.

That URL is what you paste into Prolific. Prolific's identifiers are picked up
from the link automatically — see [docs/SETUP.md](docs/SETUP.md#step-6--going-live-with-prolific).

---

## Making it your own experiment

```bash
cp experiments/_template.js experiments/my-task.js
```

Change `id` to `"my-task"`, set `ACTIVE_EXPERIMENT: "my-task"` in `config.js`,
and reload. There are five hooks and they happen in the order you would guess:

```js
onTrialStart(trial)     // set up whatever you need to count
onFrame({ ... })        // runs once per camera frame — do your measuring here
draw(ctx, { ... })      // paint the overlay the participant sees
onTrialEnd({ ... })     // return the summary numbers for this trial
```

Switching from hands to the whole body is one line: `tracker: "pose"`.

[docs/CUSTOMIZE.md](docs/CUSTOMIZE.md) is a list of "I want to change X" with the
lines to change.

---

## How your data is stored

```
sessions/{sessionId}                      one small document: who, when, and the
                                          per-trial summary numbers
sessions/{sessionId}/chunks/{trial}_{n}   the raw frame-by-frame landmarks
```

The raw landmarks are split across several documents because a Firestore
document tops out at 1 MiB. `fetch_data.py` glues them back together, so you
never deal with it. Full description in
[docs/DATA_FORMAT.md](docs/DATA_FORMAT.md).

**Tap detection runs twice, deliberately.** The browser detects taps live so the
participant sees a counter. `analysis/metrics.py` re-derives every tap from the
raw landmarks, and that is the version you should report. It means you can
change your mind about detection thresholds *after* collecting data, without
recollecting.

---

## Privacy

No image or video ever leaves the participant's computer. MediaPipe runs
locally in their browser; what gets uploaded is a list of joint coordinates.
The consent text in `config.js` says exactly this — edit it to match what your
IRB approved.

---

## Repository layout

```
index.html              the experiment participants see
check.html              setup checker — run this whenever something is wrong
config.js               the only file you have to edit
firestore.rules         paste into the Firebase console (docs/SETUP.md step 4)

js/core/                camera, tracker, recorder, firebase, screens
experiments/            one file per experiment  (+ _template.js)
analysis/               fetch → metrics → figures, in Python
docs/                   SETUP, CUSTOMIZE, TROUBLESHOOTING, DATA_FORMAT
```

## Getting help

Something not working? Start with `check.html`, then
[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md), which is organised by the
exact error message you are seeing.

## Licence

MIT — use it, change it, publish with it.
