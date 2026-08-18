/* tracker.js — a thin wrapper around MediaPipe Tasks Vision.
 *
 * Two things happen here:
 *   1. we download the WASM runtime + the model file (a few MB, cached after
 *      the first visit), and
 *   2. we expose one simple call, `track(video, timestampMs)`, that returns
 *      the landmarks for the current video frame.
 *
 * To use a different body part, add a case to createTracker() below.
 * Everything else in the codebase is tracker-agnostic. */

import { MEDIAPIPE } from "../../config.js";

const CDN = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE.version}`;

let visionFileset = null;   // shared WASM runtime, loaded once

/**
 * Build a landmark tracker.
 *
 * @param {"hand"|"pose"} kind
 * @param {object} options  passed through to MediaPipe, e.g. { numHands: 2 }
 * @returns {Promise<{kind:string, numLandmarks:number, track:Function, close:Function}>}
 *
 * The returned `track(video, tMs)` gives you:
 *   {
 *     landmarks:      [[{x,y,z}, ...21], ...]   image coords, 0..1, for drawing
 *     worldLandmarks: [[{x,y,z}, ...21], ...]   metres, origin at hand centre,
 *                                               use these for real measurements
 *     handedness:     ["Left"|"Right", ...]     (hand tracker only)
 *   }
 * Each outer array has one entry per detected hand/person. It is EMPTY when
 * nothing was detected in that frame — always check `.landmarks.length`.
 */
export async function createTracker(kind = "hand", options = {}) {
  const { FilesetResolver, HandLandmarker, PoseLandmarker } =
    await import(`${CDN}/vision_bundle.mjs`);

  if (!visionFileset) {
    visionFileset = await FilesetResolver.forVisionTasks(`${CDN}/wasm`);
  }

  if (kind === "hand") {
    const landmarker = await HandLandmarker.createFromOptions(visionFileset, {
      baseOptions: { modelAssetPath: MEDIAPIPE.models.hand, delegate: "GPU" },
      runningMode: "VIDEO",
      numHands: options.numHands ?? 1,
      minHandDetectionConfidence: options.minDetectionConfidence ?? 0.5,
      minHandPresenceConfidence:  options.minPresenceConfidence  ?? 0.5,
      minTrackingConfidence:      options.minTrackingConfidence  ?? 0.5,
    });
    return {
      kind: "hand",
      numLandmarks: 21,
      track(video, tMs) {
        const r = landmarker.detectForVideo(video, tMs);
        return {
          landmarks: r.landmarks ?? [],
          worldLandmarks: r.worldLandmarks ?? [],
          handedness: (r.handedness ?? []).map((h) => h[0]?.categoryName ?? "?"),
        };
      },
      close: () => landmarker.close(),
    };
  }

  if (kind === "pose") {
    const landmarker = await PoseLandmarker.createFromOptions(visionFileset, {
      baseOptions: { modelAssetPath: MEDIAPIPE.models.pose, delegate: "GPU" },
      runningMode: "VIDEO",
      numPoses: options.numPoses ?? 1,
    });
    return {
      kind: "pose",
      numLandmarks: 33,
      track(video, tMs) {
        const r = landmarker.detectForVideo(video, tMs);
        return {
          landmarks: r.landmarks ?? [],
          worldLandmarks: r.worldLandmarks ?? [],
          handedness: [],
        };
      },
      close: () => landmarker.close(),
    };
  }

  throw new Error(`Unknown tracker "${kind}". Use "hand" or "pose".`);
}

/* ---------------------------------------------------------------------------
 * Named landmark indices, so your code can say HAND.INDEX_TIP instead of 8.
 * Full maps: https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker
 * -------------------------------------------------------------------------*/
export const HAND = {
  WRIST: 0,
  THUMB_CMC: 1, THUMB_MCP: 2, THUMB_IP: 3, THUMB_TIP: 4,
  INDEX_MCP: 5, INDEX_PIP: 6, INDEX_DIP: 7, INDEX_TIP: 8,
  MIDDLE_MCP: 9, MIDDLE_PIP: 10, MIDDLE_DIP: 11, MIDDLE_TIP: 12,
  RING_MCP: 13, RING_PIP: 14, RING_DIP: 15, RING_TIP: 16,
  PINKY_MCP: 17, PINKY_PIP: 18, PINKY_DIP: 19, PINKY_TIP: 20,
};

export const POSE = {
  NOSE: 0, LEFT_SHOULDER: 11, RIGHT_SHOULDER: 12, LEFT_ELBOW: 13,
  RIGHT_ELBOW: 14, LEFT_WRIST: 15, RIGHT_WRIST: 16, LEFT_HIP: 23,
  RIGHT_HIP: 24, LEFT_KNEE: 25, RIGHT_KNEE: 26, LEFT_ANKLE: 27, RIGHT_ANKLE: 28,
};

/** Straight-line 3-D distance between two landmarks. */
export function distance3d(a, b) {
  const dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}
