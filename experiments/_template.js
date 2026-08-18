/* =============================================================================
 *  _template.js — copy this file to start a new experiment.
 * =============================================================================
 *
 *  HOW TO USE IT
 *    1. cp experiments/_template.js experiments/my-experiment.js
 *    2. Change `id` to "my-experiment" (it must match the filename).
 *    3. Set ACTIVE_EXPERIMENT: "my-experiment" in config.js,
 *       or just open index.html?exp=my-experiment while you are testing.
 *
 *  THE FIVE HOOKS, in the order they happen:
 *
 *    onTrialStart(trial)   once per trial, before the countdown.
 *                          Return the starting `state` for this trial.
 *    onFrame({...})        once per camera frame. Do your measuring here.
 *                          Return numbers to be saved with that frame.
 *    draw(ctx, {...})      once per camera frame, after onFrame. Paint the
 *                          overlay the participant sees.
 *    onTrialEnd({...})     once per trial, when the timer runs out. Return
 *                          summary numbers for this trial.
 *
 *  All of them are optional. An experiment with only `trials` still runs — it
 *  just records raw landmarks and nothing else, which is sometimes exactly
 *  what you want.
 * ===========================================================================*/

import { HAND, POSE, distance3d } from "../js/core/tracker.js";
import { drawLandmarks } from "../js/core/experiment.js";

export default {
  /* Must match the filename (without .js). */
  id: "_template",
  title: "My New Experiment",

  /* "hand" (21 landmarks) or "pose" (33 landmarks, whole body). */
  tracker: "hand",
  trackerOptions: { numHands: 1 },

  /* Shown once before the trials start. Plain HTML. */
  instructions: `
    <p>Explain the task here.</p>
    <ul><li>Keep instructions short and concrete.</li></ul>`,

  /* One object per trial. Any extra fields you add (like `hand` or
   * `targetSize` below) are handed to your hooks and saved with the data. */
  trials: [
    { id: "trial1", durationSec: 15, prompt: "Do the thing." },
    { id: "trial2", durationSec: 15, prompt: "Do the thing again." },
  ],

  onTrialStart(trial) {
    // Anything you need to keep track of during the trial goes here.
    return { count: 0 };
  },

  onFrame({ landmarks, worldLandmarks, handedness, tMs, trial, state, addEvent }) {
    // `landmarks`      — on-screen positions, x and y between 0 and 1. Use for drawing.
    // `worldLandmarks` — real-world positions in metres. Use for measuring.
    // Both are null on frames where nothing was detected — always check.
    if (!worldLandmarks) return {};

    const someDistance = distance3d(
      worldLandmarks[HAND.THUMB_TIP],
      worldLandmarks[HAND.INDEX_TIP]
    );

    // Call addEvent() when something noteworthy happens. Events are stored in
    // the small session document, so they are cheap to look at later.
    // addEvent("my_event", { value: someDistance });

    // Whatever you return is saved alongside the raw landmarks for this frame.
    return { someDistance };
  },

  draw(ctx, { landmarks, derived, state, trial, canvas, tMs }) {
    // ctx is a normal 2D canvas context, already cleared for you.
    drawLandmarks(ctx, canvas, landmarks);
  },

  onTrialEnd({ frames, events, trial, state }) {
    // Return per-trial summary numbers. These end up in the session document
    // and in the metrics table, so put anything you want to eyeball here.
    return { count: state.count };
  },
};
