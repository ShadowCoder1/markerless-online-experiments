/* experiment.js — the runner.
 *
 * You should not need to change this file to build a new experiment. It takes
 * an experiment definition (see experiments/_template.js) and walks the
 * participant through: consent -> camera -> instructions -> trials -> upload.
 *
 * THE FRAME LOOP, in one paragraph:
 * Every time the browser paints (~60x per second), we check whether the webcam
 * has produced a new picture. If it has, we send it to MediaPipe, get back the
 * hand landmarks, hand them to your experiment's onFrame(), store the frame,
 * and let your draw() paint the overlay. Frames where no hand was visible are
 * still stored, as nulls, so gaps in your data stay visible instead of silently
 * disappearing. */

import { STUDY, RECORDING, ACTIVE_EXPERIMENT } from "../../config.js";
import { startCamera, stopCamera } from "./camera.js";
import { createTracker } from "./tracker.js";
import { Recorder } from "./recorder.js";
import * as fb from "./firebase.js";
import { getParticipant, getEnvironment, requestedExperiment } from "./participant.js";
import * as ui from "./ui.js";

export async function main() {
  const name = requestedExperiment(ACTIVE_EXPERIMENT);

  let exp;
  try {
    exp = (await import(`../../experiments/${name}.js`)).default;
  } catch (err) {
    return ui.fatal(
      `Could not load the experiment "${name}".`,
      `Check that experiments/${name}.js exists and has no syntax errors. ` +
      `Original error: ${err.message}`
    );
  }

  try {
    await run(exp);
  } catch (err) {
    ui.fatal("Something went wrong.", err?.message || String(err));
  }
}

async function run(exp) {
  const participant = getParticipant();
  const startedAt = new Date().toISOString();

  // Flag demo mode up front, before the consent screen: someone should know
  // that nothing is being recorded *before* they agree to anything.
  if (fb.configLooksUnfilled()) {
    ui.$("#demo-banner").hidden = false;
    console.warn(
      "Demo mode: Firebase is not configured, so nothing will be saved. " +
      "Fill in FIREBASE in config.js to collect data (see docs/SETUP.md)."
    );
  }

  /* ---- 1. Welcome + consent ------------------------------------------- */
  ui.setText("#study-title", STUDY.title);
  ui.setText("#study-lab", STUDY.labName);
  ui.setHtml("#consent-text", STUDY.consentHtml);
  ui.setText("#experiment-title", exp.title);

  // Only ask for an ID if the URL did not already supply one.
  const idBlock = ui.$("#manual-id-block");
  if (participant.participantId) idBlock.style.display = "none";

  ui.showScreen("screen-welcome");
  await ui.waitForClick("#btn-consent");

  if (!participant.participantId) {
    const typed = ui.$("#manual-id-input").value.trim();
    participant.participantId = typed || `anon_${Math.random().toString(36).slice(2, 8)}`;
  }

  /* ---- 2. Firebase (optional) ------------------------------------------ */
  // If config.js has not been filled in, the study still runs — it just does
  // not save. That keeps the live demo usable by anyone who clicks the link.
  ui.showScreen("screen-loading");
  ui.setText("#loading-text", "Connecting…");
  const { enabled: saving } = await fb.initFirebase();
  const sessionId = fb.newSessionId();

  /* ---- 3. Camera + tracker --------------------------------------------- */
  ui.setText("#loading-text", "Starting your camera…");
  const video = await startCamera(RECORDING.video);

  ui.setText("#loading-text", "Loading the hand tracking model (a few MB, first visit only)…");
  const tracker = await createTracker(exp.tracker ?? "hand", exp.trackerOptions ?? {});

  const stage = ui.$("#stage");
  const canvas = ui.$("#overlay");
  stage.querySelector(".mirror").prepend(video);
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  stage.hidden = false;

  /* ---- 4. Positioning check -------------------------------------------- */
  // A live preview with the landmarks drawn on top. Participants fix their own
  // lighting and framing here, which is far more effective than instructions.
  ui.showScreen("screen-position");
  await positioningLoop(video, tracker, ctx, canvas, stage);

  /* ---- 5. Instructions -------------------------------------------------- */
  ui.setHtml("#instructions-text", exp.instructions ?? "");
  ui.showScreen("screen-instructions");
  await ui.waitForClick("#btn-start");

  /* ---- 6. Trials -------------------------------------------------------- */
  const trials = typeof exp.trials === "function" ? exp.trials() : exp.trials;
  const recorder = new Recorder();
  const trialSummaries = [];
  const demoFrames = [];    // only used when nothing is being uploaded

  for (let i = 0; i < trials.length; i++) {
    const trial = trials[i];
    const state = exp.onTrialStart?.(trial, { tracker }) ?? {};

    ui.showScreen("screen-trial");
    ui.setProgress(i + 1, trials.length);
    ui.setHtml("#trial-prompt", trial.prompt ?? exp.trialPrompt ?? "");
    ui.setHtml("#live-readout", "");

    await ui.countdown(trial.countdownSec ?? 3);

    recorder.reset();
    await recordTrial({ video, tracker, ctx, canvas, exp, trial, state, recorder });

    const summary = exp.onTrialEnd?.({
      frames: recorder.frames, events: recorder.events, trial, state,
    }) ?? {};

    trialSummaries.push({
      index: i,
      id: trial.id ?? `trial_${i}`,
      ...trial,
      frameCount: recorder.frames.length,
      detectionRate: round(recorder.detectionRate(), 4),
      events: recorder.events,
      ...summary,
    });

    if (saving) {
      /* Upload straight away, so someone who quits mid-study still leaves data. */
      ui.showScreen("screen-saving");
      const chunks = recorder.toChunks();
      await fb.uploadTrialChunks(
        sessionId, i, chunks,
        { experimentId: exp.id, trialId: trial.id ?? `trial_${i}` },
        (done, total) => ui.setText("#saving-text", `Saving… ${done}/${total}`)
      );
    } else {
      // Nowhere to upload to, so hold onto the frames and offer them as a
      // download at the end. The file matches what fetch_data.py produces, so
      // it can go straight into the Python analysis.
      demoFrames[i] = recorder.frames.slice();
    }

    if (i < trials.length - 1) {
      ui.showScreen("screen-rest");
      ui.setText("#rest-progress", `${i + 1} of ${trials.length} done`);
      await ui.waitForClick("#btn-next-trial");
    }
  }

  /* ---- 7. Session summary ----------------------------------------------- */
  if (saving) {
    ui.showScreen("screen-saving");
    ui.setText("#saving-text", "Saving your results…");
  }

  const sessionDoc = {
    experimentId: exp.id,
    experimentTitle: exp.title,
    participantId: participant.participantId,
    participantSource: participant.source,
    prolific: participant.prolific,
    condition: participant.condition,
    startedAt,
    trials: trialSummaries,
    settings: { recording: RECORDING, trackerOptions: exp.trackerOptions ?? {} },
    environment: getEnvironment(),
    schemaVersion: 1,
  };
  await fb.saveSession(sessionId, sessionDoc);

  if (saving && RECORDING.alsoDownloadLocally) {
    ui.downloadJson(`${sessionId}.json`, sessionDoc);
  }

  /* ---- 8. Done ----------------------------------------------------------- */
  stopCamera(video);
  tracker.close();
  stage.hidden = true;

  // Show people what they just did. In demo mode this IS the point of the page.
  ui.setHtml("#done-results", resultsTable(exp, trialSummaries));

  if (saving) {
    ui.setText("#done-session-id", sessionId);
  } else {
    ui.$("#done-saved-line").hidden = true;
    ui.$("#done-demo").hidden = false;
    ui.$("#btn-download-demo").onclick = () => {
      const copy = structuredClone(sessionDoc);
      copy.trials.forEach((t, i) => { t.frames = demoFrames[i] ?? []; });
      ui.downloadJson(`${sessionId}.json`, copy);
    };
  }
  ui.showScreen("screen-done");

  if (saving && STUDY.completionRedirectUrl) {
    ui.setText("#done-redirect-note", "Returning you to Prolific in 5 seconds…");
    await ui.sleep(5000);
    location.href = STUDY.completionRedirectUrl;
  }
}

/* -------------------------------------------------------------------------
 * The positioning preview: run the tracker live until the participant has been
 * visible for a couple of continuous seconds, then let them continue.
 * ---------------------------------------------------------------------- */
async function positioningLoop(video, tracker, ctx, canvas, stage) {
  ui.$("#position-stage-slot").append(stage);

  let stop = false;
  let visibleSince = null;
  const btn = ui.$("#btn-position-done");
  btn.disabled = true;
  ui.waitForClick("#btn-position-done").then(() => { stop = true; });

  let lastVideoTime = -1;
  while (!stop) {
    if (video.currentTime !== lastVideoTime) {
      lastVideoTime = video.currentTime;
      const res = tracker.track(video, performance.now());
      drawLandmarks(ctx, canvas, res.landmarks[0]);

      const seen = res.landmarks.length > 0;
      if (seen && visibleSince === null) visibleSince = performance.now();
      if (!seen) visibleSince = null;

      const heldFor = visibleSince ? performance.now() - visibleSince : 0;
      if (heldFor > 1500) {
        btn.disabled = false;
        ui.setText("#position-status", "Looking good — you can continue.");
        ui.$("#position-status").className = "status good";
      } else {
        btn.disabled = true;
        ui.setText("#position-status",
          seen ? "Hold still…" : "Your hand is not visible. Move it into the frame.");
        ui.$("#position-status").className = seen ? "status" : "status bad";
      }
    }
    await nextFrame();
  }
  // Move the camera view into the trial screen for the rest of the study.
  ui.$("#trial-stage-slot").append(stage);
}

/* -------------------------------------------------------------------------
 * One trial's frame loop.
 * ---------------------------------------------------------------------- */
async function recordTrial({ video, tracker, ctx, canvas, exp, trial, state, recorder }) {
  const durationMs = (trial.durationSec ?? 15) * 1000;
  const t0 = performance.now();
  let lastVideoTime = -1;

  while (performance.now() - t0 < durationMs) {
    if (video.currentTime !== lastVideoTime) {
      lastVideoTime = video.currentTime;
      const tMs = performance.now() - t0;
      const res = tracker.track(video, performance.now());

      const lm = res.landmarks[0] ?? null;
      const wl = res.worldLandmarks[0] ?? null;

      const derived = exp.onFrame?.({
        landmarks: lm,
        worldLandmarks: wl,
        handedness: res.handedness[0] ?? null,
        tMs, trial, state,
        addEvent: (type, data) => recorder.addEvent(tMs, type, data),
      }) ?? {};

      recorder.addFrame(tMs, lm, wl, derived);

      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (exp.draw) {
        exp.draw(ctx, {
          landmarks: lm, derived, state, trial, canvas, tMs,
          // Text drawn on the canvas would appear mirrored, so live numbers go
          // into an HTML element sitting on top of the video instead.
          setReadout: (html) => ui.setHtml("#live-readout", html),
        });
      } else {
        drawLandmarks(ctx, canvas, lm);
      }

      ui.setTimeRemaining((durationMs - tMs) / 1000);
    }
    await nextFrame();
  }
}

/* -------------------------------------------------------------------------
 * Default overlay: dots on every landmark, lines along the fingers.
 * ---------------------------------------------------------------------- */
const HAND_BONES = [
  [0,1],[1,2],[2,3],[3,4],          // thumb
  [0,5],[5,6],[6,7],[7,8],          // index
  [5,9],[9,10],[10,11],[11,12],     // middle
  [9,13],[13,14],[14,15],[15,16],   // ring
  [13,17],[17,18],[18,19],[19,20],  // pinky
  [0,17],
];

export function drawLandmarks(ctx, canvas, landmarks, colour = "#4ade80") {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!landmarks) return;
  const W = canvas.width, H = canvas.height;

  ctx.strokeStyle = colour;
  ctx.lineWidth = 3;
  if (landmarks.length === 21) {
    for (const [a, b] of HAND_BONES) {
      ctx.beginPath();
      ctx.moveTo(landmarks[a].x * W, landmarks[a].y * H);
      ctx.lineTo(landmarks[b].x * W, landmarks[b].y * H);
      ctx.stroke();
    }
  }
  ctx.fillStyle = "#ffffff";
  for (const p of landmarks) {
    ctx.beginPath();
    ctx.arc(p.x * W, p.y * H, 4, 0, Math.PI * 2);
    ctx.fill();
  }
}

/** A small table of what happened, shown on the final screen. */
function resultsTable(exp, summaries) {
  const rows = summaries.map((t) => {
    const bits = [];
    if (t.tapCount != null) bits.push(`<td>${t.tapCount}</td>`);
    if (t.tapRateHz != null) bits.push(`<td>${t.tapRateHz.toFixed(2)} Hz</td>`);
    if (t.detectionRate != null) {
      const pct = Math.round(t.detectionRate * 100);
      bits.push(`<td class="${pct < 90 ? "bad" : ""}">${pct}%</td>`);
    }
    return `<tr><th>${t.hand ?? t.id}</th>${bits.join("")}</tr>`;
  });
  if (!rows.length) return "";
  const headers = ["", summaries[0].tapCount != null ? "taps" : null,
                   summaries[0].tapRateHz != null ? "rate" : null,
                   summaries[0].detectionRate != null ? "hand visible" : null]
                  .filter((h) => h !== null);
  return `<table class="results">
    <tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr>
    ${rows.join("")}
  </table>`;
}

function nextFrame() {
  return new Promise((r) => requestAnimationFrame(r));
}

function round(v, d) { const p = 10 ** d; return Math.round(v * p) / p; }
