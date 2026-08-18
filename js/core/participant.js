/* participant.js — works out who this participant is and where to send them
 * when they are done.
 *
 * PROLIFIC
 * Prolific adds identifiers to the URL it sends people to, e.g.
 *   https://yourname.github.io/your-repo/?PROLIFIC_PID=abc&STUDY_ID=xyz&SESSION_ID=123
 * We read those automatically. Nothing to configure.
 *
 * ANYTHING ELSE (Qualtrics, SONA, an email link, testing on your own machine)
 * Add ?pid=whatever to the URL, or leave it off and the participant is asked
 * to type an ID on the welcome screen. */

const params = new URLSearchParams(location.search);

/** Everything we know about who is sitting in front of the camera. */
export function getParticipant() {
  const prolificPid = params.get("PROLIFIC_PID");
  const manualPid   = params.get("pid") || params.get("participant");

  return {
    participantId: prolificPid || manualPid || null,
    source: prolificPid ? "prolific" : manualPid ? "url" : "manual",
    prolific: prolificPid
      ? {
          pid: prolificPid,
          studyId: params.get("STUDY_ID"),
          sessionId: params.get("SESSION_ID"),
        }
      : null,
    // Handy for debugging a specific participant's data later.
    condition: params.get("condition") || null,
  };
}

/** Which experiment file to load — ?exp=... beats config.js. */
export function requestedExperiment(fallback) {
  const name = params.get("exp");
  // Only allow simple names, so a URL can never be used to load a script from
  // somewhere else.
  return name && /^[a-z0-9_-]+$/i.test(name) ? name : fallback;
}

/** Browser / hardware details worth having when a participant's data looks odd. */
export function getEnvironment() {
  return {
    userAgent: navigator.userAgent,
    platform: navigator.platform || null,
    language: navigator.language || null,
    screenW: window.screen?.width ?? null,
    screenH: window.screen?.height ?? null,
    devicePixelRatio: window.devicePixelRatio ?? null,
    hardwareConcurrency: navigator.hardwareConcurrency ?? null,
    deviceMemoryGb: navigator.deviceMemory ?? null,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    timezoneOffsetMin: new Date().getTimezoneOffset(),
  };
}
