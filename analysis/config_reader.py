"""Reads settings out of config.js so there is only one place to edit them.

config.js is JavaScript, not JSON, so we pull the few values we need out with
a regular expression rather than pretending we can parse the whole language.
If that ever fails, every script here also accepts the value on the command
line or in an environment variable.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_JS = REPO_ROOT / "config.js"


def firebase_project_id(explicit: str | None = None) -> str:
    """Work out which Firebase project to talk to.

    Order of preference: --project flag, FIREBASE_PROJECT_ID env var, config.js.
    """
    if explicit:
        return explicit

    env = os.environ.get("FIREBASE_PROJECT_ID")
    if env:
        return env

    if CONFIG_JS.exists():
        text = CONFIG_JS.read_text(encoding="utf-8")
        match = re.search(r'projectId\s*:\s*["\']([^"\']+)["\']', text)
        if match and "PASTE_YOUR" not in match.group(1):
            return match.group(1)

    raise SystemExit(
        "Could not work out your Firebase project id.\n"
        "Either fill in FIREBASE.projectId in config.js, or pass --project "
        "your-project-id on the command line."
    )
