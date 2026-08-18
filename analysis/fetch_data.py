#!/usr/bin/env python3
"""Download your study data from Firebase onto this computer.

    python analysis/fetch_data.py

Writes one JSON file per session into data/raw/, with the frame chunks already
glued back together, plus data/raw/_sessions.csv listing everything you have.

FIRST TIME SETUP (once per computer)
    pip install -r analysis/requirements.txt
    gcloud auth application-default login

That second command signs you in as yourself. It does not create or download a
key file, so there is no secret to accidentally commit. If your institution
blocks it, you can instead point GOOGLE_APPLICATION_CREDENTIALS at a service
account key file.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from config_reader import REPO_ROOT, firebase_project_id


def connect(project_id: str):
    try:
        from google.cloud import firestore
    except ImportError:
        sys.exit(
            "The Firestore library is not installed.\n"
            "Fix:  pip install -r analysis/requirements.txt"
        )
    try:
        return firestore.Client(project=project_id)
    except Exception as err:  # noqa: BLE001 - we want the friendly message
        sys.exit(
            f"Could not connect to Firebase project '{project_id}'.\n\n"
            f"Original error: {err}\n\n"
            "Most likely fix:  gcloud auth application-default login\n"
            "(and check that the project id in config.js is spelled correctly)."
        )


def fetch(db, experiment: str | None, limit: int | None):
    """Pull session documents, newest first."""
    query = db.collection("sessions")
    if experiment:
        query = query.where("experimentId", "==", experiment)
    if limit:
        query = query.limit(limit)
    return list(query.stream())


def fetch_frames(db, session_id: str) -> dict[int, list]:
    """Reassemble a session's chunk documents into {trial_index: [frames]}.

    Chunks are named  {trial:03d}_{chunk:03d}  so sorting by document id puts
    them back in the right order.
    """
    by_trial: dict[int, list[tuple[int, list]]] = defaultdict(list)
    chunks = db.collection("sessions").document(session_id).collection("chunks")
    for snap in chunks.stream():
        data = snap.to_dict() or {}
        by_trial[int(data.get("trialIndex", 0))].append(
            (int(data.get("chunkIndex", 0)), data.get("frames", []))
        )

    out: dict[int, list] = {}
    for trial_index, pieces in by_trial.items():
        pieces.sort(key=lambda p: p[0])
        frames: list = []
        for _, chunk in pieces:
            frames.extend(chunk)
        out[trial_index] = frames
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", help="Firebase project id (default: read from config.js)")
    ap.add_argument("--experiment", help="only download one experiment, e.g. finger-tapping")
    ap.add_argument("--out", default="data/raw", help="output folder (default: data/raw)")
    ap.add_argument("--limit", type=int, help="stop after this many sessions")
    ap.add_argument("--force", action="store_true",
                    help="re-download sessions already saved locally")
    args = ap.parse_args()

    project_id = firebase_project_id(args.project)
    out_dir = (REPO_ROOT / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Project : {project_id}")
    print(f"Output  : {out_dir}")

    db = connect(project_id)
    sessions = fetch(db, args.experiment, args.limit)
    print(f"Found   : {len(sessions)} session document(s)\n")

    index_rows, downloaded, skipped, selftests = [], 0, 0, 0

    for snap in sessions:
        session = snap.to_dict() or {}
        session_id = snap.id

        if session.get("experimentId") == "_selftest":
            selftests += 1
            continue

        target = out_dir / f"{session_id}.json"
        if target.exists() and not args.force:
            skipped += 1
        else:
            frames_by_trial = fetch_frames(db, session_id)
            for i, trial in enumerate(session.get("trials", [])):
                trial["frames"] = frames_by_trial.get(trial.get("index", i), [])
            target.write_text(json.dumps(session, indent=1, default=str), encoding="utf-8")
            downloaded += 1
            print(f"  saved {session_id}  "
                  f"({len(session.get('trials', []))} trials, "
                  f"{sum(len(t.get('frames', [])) for t in session.get('trials', []))} frames)")

        stored = json.loads(target.read_text(encoding="utf-8"))
        for trial in stored.get("trials", []):
            index_rows.append({
                "sessionId": session_id,
                "participantId": stored.get("participantId"),
                "experimentId": stored.get("experimentId"),
                "startedAt": stored.get("startedAt"),
                "trialIndex": trial.get("index"),
                "trialId": trial.get("id"),
                "hand": trial.get("hand"),
                "durationSec": trial.get("durationSec"),
                "frameCount": len(trial.get("frames", [])),
                "detectionRate": trial.get("detectionRate"),
                "liveTapCount": trial.get("tapCount"),
            })

    if index_rows:
        index_path = out_dir / "_sessions.csv"
        with index_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(index_rows[0].keys()))
            writer.writeheader()
            writer.writerows(index_rows)
        print(f"\nIndex   : {index_path}")

    # A session folder with chunks but no session document is someone who quit
    # partway through. Surfacing that is better than quietly losing them.
    #
    # This has to look at ALL session documents, not just the ones downloaded
    # above: with --experiment set, every session from a different experiment
    # would otherwise look like a dropout. select([]) fetches ids only.
    known = {s.id for s in db.collection("sessions").select([]).stream()}
    orphans = [
        d.id for d in db.collection("sessions").list_documents()
        if d.id not in known and not d.id.startswith("_selftest")
    ]

    print(f"\nDownloaded {downloaded}, already had {skipped}, "
          f"ignored {selftests} setup-check record(s).")
    if orphans:
        print(f"\nNOTE: {len(orphans)} incomplete session(s), these participants "
              f"started but did not finish, so only partial data exists:")
        for o in orphans[:10]:
            print(f"  {o}")
        if len(orphans) > 10:
            print(f"  ... and {len(orphans) - 10} more")


if __name__ == "__main__":
    main()
