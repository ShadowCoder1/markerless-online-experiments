/* =============================================================================
 *  config.js  —  THE ONLY FILE YOU NEED TO EDIT TO GET STARTED
 * =============================================================================
 *
 *  1. Fill in FIREBASE below (see docs/SETUP.md — takes about 15 minutes).
 *  2. Open check.html to confirm everything works.
 *  3. Open index.html to run the experiment.
 *
 *  Everything in this file is safe to commit to a public repo. Firebase web
 *  API keys are public identifiers, NOT secrets — your data is protected by
 *  firestore.rules, not by hiding this key. (This surprises people. It is
 *  documented by Google: https://firebase.google.com/docs/projects/api-keys)
 * ===========================================================================*/


/* -----------------------------------------------------------------------------
 * 1. FIREBASE  —  where your participants' data gets saved
 * ---------------------------------------------------------------------------
 * Paste the config object from the Firebase Console here.
 * Firebase Console -> Project settings -> Your apps -> Web app -> Config
 * ---------------------------------------------------------------------------*/
export const FIREBASE = {
  apiKey:            "PASTE_YOUR_API_KEY_HERE",
  authDomain:        "PASTE_YOUR_PROJECT_ID_HERE.firebaseapp.com",
  projectId:         "PASTE_YOUR_PROJECT_ID_HERE",
  storageBucket:     "PASTE_YOUR_PROJECT_ID_HERE.firebasestorage.app",
  messagingSenderId: "PASTE_YOUR_SENDER_ID_HERE",
  appId:             "PASTE_YOUR_APP_ID_HERE",
};


/* -----------------------------------------------------------------------------
 * 2. WHICH EXPERIMENT TO RUN
 * ---------------------------------------------------------------------------
 * The name of a file in experiments/ (without the .js).
 * You can also override this in the URL:  index.html?exp=my-experiment
 * ---------------------------------------------------------------------------*/
export const ACTIVE_EXPERIMENT = "finger-tapping";


/* -----------------------------------------------------------------------------
 * 3. STUDY SETTINGS
 * ---------------------------------------------------------------------------*/
export const STUDY = {
  // Shown on the welcome screen.
  title: "Hand Movement Study",
  labName: "Your Lab Name",
  contactEmail: "you@university.edu",

  // Consent text shown before the camera turns on. EDIT THIS to match the
  // wording your IRB approved. Basic HTML is allowed.
  consentHtml: `
    <p>In this study you will be asked to perform simple hand movements in
    front of your webcam.</p>
    <p><strong>What we record:</strong> we do <em>not</em> record or upload any
    video or images. Your webcam feed is processed entirely on your own
    computer. Only the numeric positions of your hand joints (x, y, z
    coordinates) are sent to our secure server.</p>
    <p>Participation is voluntary and you may stop at any time by closing this
    page.</p>`,

  // Where to send participants when they finish. Prolific gives you a URL
  // like https://app.prolific.com/submissions/complete?cc=XXXXXXXX
  // Leave as null to just show a thank-you screen with no redirect.
  completionRedirectUrl: null,

  // Require participants to pass the camera check before starting.
  requireCameraCheck: true,
};


/* -----------------------------------------------------------------------------
 * 4. RECORDING SETTINGS  —  most people never need to change these
 * ---------------------------------------------------------------------------*/
export const RECORDING = {
  // Target camera resolution. Lower = faster on weak laptops.
  video: { width: 640, height: 480 },

  // How many frames go into one Firestore document.
  // WHY THIS EXISTS: a Firestore document can hold at most 1 MiB. One frame of
  // hand data is roughly 1.2 KB, so 250 frames is about 300 KB — a safe margin.
  // If you record many more landmarks per frame, lower this number.
  chunkFrames: 250,

  // Decimal places kept for each coordinate. 4 dp is well below the noise
  // floor of the tracker and roughly halves the storage cost.
  decimals: 4,

  // Save a copy of the data to the participant's computer as well as Firebase.
  // Useful while piloting; usually turned off for real data collection.
  alsoDownloadLocally: false,
};


/* -----------------------------------------------------------------------------
 * 5. MEDIAPIPE VERSIONS  —  pinned on purpose
 * ---------------------------------------------------------------------------
 * Pinned so that your study does not silently change halfway through data
 * collection because Google shipped a new model. Only bump these between
 * studies, and re-run check.html when you do.
 * ---------------------------------------------------------------------------*/
export const MEDIAPIPE = {
  version: "1.0.1",
  models: {
    hand: "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
    pose: "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
  },
};
