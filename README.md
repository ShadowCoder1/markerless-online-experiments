# Markerless online experiments

A starting point for running hand and body movement experiments over the web.
Participants open a link, their webcam is analysed on their own computer, and
only the numeric positions of their joints are sent back to you. No video is
uploaded, and there is nothing for them to install.

Tracking uses [MediaPipe](https://ai.google.dev/edge/mediapipe). Data is stored
in [Firebase](https://firebase.google.com/). Analysis is in Python. There is no
build step: you edit a file and reload the page.

A finger-tapping experiment is included and works as-is. You can
[try it here](https://shadowcoder1.github.io/markerless-online-experiments/).

Until you connect a Firebase project, the site runs in demo mode. The task works
and you see your tap count as you go, but nothing is uploaded. You can download
your own session at the end and run the analysis scripts on it.

## Contents

```
index.html              the page participants see
check.html              tests your setup and reports what is wrong
config.js               the file you edit
firestore.rules         paste into the Firebase console (SETUP.md step 4)

js/core/                camera, tracker, recorder, uploads, screen flow
experiments/            one file per experiment, plus _template.js
analysis/               fetch, compute metrics, draw figures
docs/                   setup, customisation, troubleshooting, data format
```

## Trying the analysis without collecting data

The analysis scripts work on invented data, so you can see what comes out before
setting anything up.

```bash
git clone https://github.com/ShadowCoder1/markerless-online-experiments.git
cd markerless-online-experiments
pip install -r analysis/requirements.txt

python analysis/make_example_data.py
python analysis/compute_metrics.py --raw data/example
python analysis/visualize.py --raw data/example --out data/example_figures
```

Then open `data/example_figures/`. Each figure marks every tap the software
found, so you can check whether it agrees with what you see in the trace.

## Running the experiment

### 1. Serve the folder

Browsers do not allow webcam access on pages opened directly from disk, so run a
local server:

```bash
python3 -m http.server 8000
```

Open <http://localhost:8000/>. The task runs in demo mode straight away. Open
<http://localhost:8000/check.html> to test your setup; some checks will fail
until you have done step 2.

### 2. Connect Firebase

Follow [docs/SETUP.md](docs/SETUP.md). It takes about 15 minutes and you do it
once. When you are finished, every check on `check.html` should pass.

### 3. Collect data

Run the study on yourself, then:

```bash
gcloud auth application-default login     # once per computer
python analysis/fetch_data.py
python analysis/compute_metrics.py
python analysis/visualize.py
```

### 4. Put it online

Push your copy to GitHub, then go to Settings, Pages, and set the source to
"Deploy from a branch" with `main` and `/ (root)`. Your study will be at
`https://<your-username>.github.io/<your-repo>/` about a minute later.

That address is what you give to Prolific. Prolific's identifiers are read from
the URL automatically, so there is nothing to configure. See
[docs/SETUP.md](docs/SETUP.md#step-6--going-live-with-prolific).

## Writing your own experiment

```bash
cp experiments/_template.js experiments/my-task.js
```

Set `id` to `"my-task"`, set `ACTIVE_EXPERIMENT: "my-task"` in `config.js`, and
reload. There are four hooks, called in this order:

```js
onTrialStart(trial)     // set up whatever you need to keep track of
onFrame({ ... })        // runs once per camera frame, do your measuring here
draw(ctx, { ... })      // paint the overlay the participant sees
onTrialEnd({ ... })     // return the summary numbers for the trial
```

To track the whole body instead of a hand, set `tracker: "pose"`.

[docs/CUSTOMIZE.md](docs/CUSTOMIZE.md) lists common changes and the lines to
change for each.

## How the data is stored

```
sessions/{sessionId}                      one small document per session: who,
                                          when, and the per-trial summaries
sessions/{sessionId}/chunks/{trial}_{n}   the raw frame-by-frame landmarks
```

The raw landmarks are split across several documents because a Firestore
document cannot exceed 1 MiB. `fetch_data.py` puts them back together, so this
does not affect how you work with the data.
[docs/DATA_FORMAT.md](docs/DATA_FORMAT.md) describes every field.

Taps are detected twice. The browser detects them during the session so the
participant can see a count, and `analysis/metrics.py` detects them again from
the raw landmarks afterwards. The second one is the one to report, and it means
you can change the detection settings after collecting data rather than before.

## Privacy

No image or video leaves the participant's computer. MediaPipe runs in their
browser and only joint coordinates are uploaded. The consent text in `config.js`
says this. Edit it to match what your ethics board approved.

## If something is not working

Open `check.html` first. It tests the camera, the model, your Firebase settings,
sign-in, and a test write, and reports which step failed and what to do about
it. [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) is organised by the error
message you are seeing.

## Licence

MIT. See [LICENSE](LICENSE).
