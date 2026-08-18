# Troubleshooting

Run `check.html` first. It tests each part of the setup in order and names the
step that failed. Most of what follows is what that page will tell you.

This is organized by the message you are seeing.

---

## Setting up

### The page is blank and nothing happens

Open the browser console (F12, or Cmd+Option+J on a Mac) and read the error
text. There are two common causes.

- `Failed to load module script ... MIME type "text/plain"` means you opened the
  file directly. Run `python3 -m http.server 8000` and use
  `http://localhost:8000/` instead.
- A `SyntaxError` naming one of your files means there is a typo in the file you
  are editing. The message gives the line number.

### "Browsers only allow camera access over HTTPS"

You are on a `file://` address. Use the local server, or your GitHub Pages URL.
`http://localhost` counts as secure; `http://192.168.x.x` does not.

### It says "Demo mode, nothing is being saved"

Working as intended. `config.js` still has its `PASTE_YOUR…` placeholders, so
there is nowhere to send data. The task runs normally and you can download your
own session at the end; nothing is uploaded.

To start collecting data, fill in `FIREBASE` in `config.js`. See
[SETUP.md step 2](SETUP.md#step-2--register-a-web-app-and-copy-the-config). The
banner disappears once it is set.

> If you are **recruiting participants** and you see this banner, stop. Their
> data is not being recorded. Run `check.html` on your live URL before opening
> a study.

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

The database has not been created yet. Go to Build, Firestore Database, Create
database. Also check `projectId` in `config.js` for typos.

### `auth/api-key-not-valid`

The `apiKey` is wrong, or you copied the config from an iOS/Android app instead
of a **web** app. Re-copy from Project settings → Your apps → the `</>` one.

---

## While running the experiment

### The hand is not detected

In rough order of how often each one is the cause:

1. Lighting. A window behind the participant turns them into a silhouette. The
   light should come from in front of them.
2. Distance. About 40 to 60 cm from the camera works well.
3. Background. Busy or skin-colored backgrounds make detection less reliable.
4. The wrong camera. On a machine with more than one, the browser may have
   picked a different one. Change it using the camera icon in the address bar.

The positioning screen is there so participants can correct these themselves
before any data is recorded.

### "kGpuService ... emscripten_webgl_create_context() returned error 0"

This means the browser could not give MediaPipe access to the graphics card. It
happens when hardware acceleration is turned off, on some virtual machines and
remote desktops, with older or blocklisted graphics drivers, and occasionally
when many other tabs are already using WebGL.

You should not see this error any more. When the graphics card is unavailable,
tracking falls back to the CPU automatically and a notice appears at the top of
the page. The task still works; the frame rate is lower. On a recent laptop, CPU
tracking runs at roughly 50 frames per second, which is faster than the camera
delivers frames, so most participants will not notice a difference.

If you want to control this yourself:

- `MEDIAPIPE.delegate` in `config.js` accepts `"auto"` (the default, try the
  graphics card and fall back), `"CPU"`, or `"GPU"`.
- Add `?delegate=cpu` to the URL to force one participant onto the CPU without
  changing the file.

Which one was used is recorded with every session as
`environment.trackerDelegate`, and `check.html` reports it. If a participant's
frame rate looks low, check that field first.

To fix the graphics card properly, turn on hardware acceleration in the browser
settings (in Chrome: Settings, System, "Use graphics acceleration when
available") and restart the browser.

### Tracking stopped partway through

If the browser loses the graphics card mid-session, for example because the
machine went to sleep, single frames are recorded as "nothing detected" and the
session continues. Only a sustained failure of about three seconds stops the
session and asks the participant to reload. The number of frames affected is
stored as `environment.trackerErrors`.

### It is slow, or the frame rate is low

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

Their finished trials are already uploaded. `fetch_data.py` lists these
separately as incomplete sessions rather than mixing them into your dataset.

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
- Setup-check records are ignored on purpose, because they are not real sessions.
- If you passed `--experiment`, confirm the name matches `id` in the experiment
  file exactly.

### The tap counts look wrong

Look at the figures before changing anything. The figures in `data/figures/`
mark every tap the software found on the raw signal, so you can see whether it
is counting too many or too few.

- Too many taps means noise is being counted. Raise the threshold:
  `python analysis/compute_metrics.py --prominence 0.25`
- Too few taps means small taps are being missed. Lower it:
  `python analysis/compute_metrics.py --prominence 0.08`
- If `rate_hz` disagrees with `fft_peak_hz`, `compute_metrics.py` warns you. The
  FFT does not use peak detection, so a large disagreement means the detection
  settings are wrong for that participant.

### `detection_rate` is low for a participant

Below about 0.9, the trial is worth checking by hand. `compute_metrics.py` flags
these. Check `lost_to_tracking_sec` to see how much time was lost, and open the
figure, where dropouts are shaded in orange.

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
