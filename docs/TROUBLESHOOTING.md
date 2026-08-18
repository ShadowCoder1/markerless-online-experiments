# Troubleshooting

**Run `check.html` first.** It tests each part of the pipeline in order and
names the step that failed. Most of this page is what it will tell you anyway.

Organised by what you actually see.

---

## Setting up

### The page is blank and nothing happens

Open the browser console — **F12**, or **Cmd+Option+J** on a Mac — and read the
red text. Two usual causes:

- `Failed to load module script … MIME type "text/plain"` — you opened the file
  directly. Run `python3 -m http.server 8000` and use
  `http://localhost:8000/` instead.
- `SyntaxError` naming one of your files — you have a typo in the experiment you
  are editing. The message gives the line.

### "Browsers only allow camera access over HTTPS"

You are on a `file://` address. Use the local server, or your GitHub Pages URL.
`http://localhost` counts as secure; `http://192.168.x.x` does not.

### "Firebase is not configured yet"

`config.js` still has `PASTE_YOUR…` placeholders. See
[SETUP.md step 2](SETUP.md#step-2--register-a-web-app-and-copy-the-config).

### "Anonymous sign-in is turned off for this Firebase project"

Firebase Console → **Build → Authentication → Sign-in method → Anonymous →
Enable**. ([SETUP.md step 3](SETUP.md#step-3--turn-on-anonymous-sign-in))

### "Firestore refused the write (permission denied)"

Your rules have not been published. Paste all of `firestore.rules` into Firebase
Console → **Build → Firestore Database → Rules** → **Publish**.
([SETUP.md step 4](SETUP.md#step-4--create-the-database-and-publish-the-rules))

If you have edited the rules yourself, note that a session document is rejected
unless it has `uid`, `sessionId`, `experimentId`, and `startedAt`.

### "Could not reach Firestore" / `NOT_FOUND`

The database has not been created yet — **Build → Firestore Database → Create
database**. Also check `projectId` in `config.js` for typos.

### `auth/api-key-not-valid`

The `apiKey` is wrong, or you copied the config from an iOS/Android app instead
of a **web** app. Re-copy from Project settings → Your apps → the `</>` one.

---

## While running the experiment

### The hand is not detected

In rough order of how often it is the cause:

1. **Lighting.** A window *behind* the participant turns them into a silhouette.
   Light should come from in front.
2. **Distance.** About 40–60 cm from the camera.
3. **Background.** Busy or skin-coloured backgrounds hurt. Plain is better.
4. **The other camera.** On a machine with several, the browser may have picked
   a different one. Change it via the camera icon in the address bar.

The positioning screen exists precisely so participants fix this themselves
before any data is recorded.

### It is laggy, or the frame rate is low

Check `fps` in `trial_metrics.csv`. Below ~20 fps you will start to miss fast
taps.

- Lower `RECORDING.video` in `config.js` to `{ width: 480, height: 360 }`.
- Ask participants to close other tabs, and Zoom in particular.
- Very old laptops fall back from GPU to CPU tracking, which is much slower.
  There is no fix beyond a lighter model.

### It freezes at "Saving…"

Almost always the network. The data uploads after every trial, so anything
already finished is safely stored. Watch the console for
`permission-denied` (rules) or `resource-exhausted` (quota).

### A participant closed the tab halfway through

Their finished trials are already uploaded. `fetch_data.py` reports these
separately as *incomplete sessions* rather than mixing them into your dataset.

---

## Analysis

### `ModuleNotFoundError: No module named 'google.cloud'`

```bash
pip install -r analysis/requirements.txt
```

### "Could not connect to Firebase project"

```bash
gcloud auth application-default login
```

Then check that the account you signed in with can actually see the project, and
that `projectId` in `config.js` is spelled correctly.

### `fetch_data.py` finds no sessions

- Have you completed a session all the way to the "thank you" screen? The
  session document is written at the very end.
- Setup-check records are ignored on purpose — they are not real sessions.
- If you passed `--experiment`, confirm the name matches `id` in the experiment
  file exactly.

### The tap counts look wrong

**Look at the figures before changing anything.** `data/figures/` marks every
tap the software found on the raw signal, so you can see immediately whether it
is over- or under-counting.

- **Too many taps** — noise is being counted. Raise the threshold:
  `python analysis/compute_metrics.py --prominence 0.25`
- **Too few taps** — small taps are being missed. Lower it:
  `python analysis/compute_metrics.py --prominence 0.08`
- **`rate_hz` disagrees with `fft_peak_hz`** — `compute_metrics.py` warns about
  this. The FFT does not use peak detection at all, so a large disagreement
  means your detection settings are wrong for that participant.

### `detection_rate` is low for a participant

Below about 0.9, treat the trial with suspicion; `compute_metrics.py` flags
these. Check `lost_to_tracking_sec` for how much time was lost, and open the
figure — dropouts are shaded in orange.

Metrics are computed only from the periods where the hand was visible, and
intervals that span a dropout are excluded, so a dropout will not silently
inflate your variability numbers. It will still reduce how much data you have.

---

## Still stuck

Open an issue with:

- what `check.html` says (a screenshot is fine)
- the red text from the browser console
- your browser and operating system
- the relevant figure from `data/figures/`, if it is an analysis problem
