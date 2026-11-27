"""Bounded voice diagnostics. Never add audio samples or transcriptions here."""
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

LOG = logging.getLogger("jarvis.voice")
LOG_NAME = "voz.log"


def configure():
    local = os.getenv("LOCALAPPDATA")
    if not local or LOG.handlers:
        return
    path = Path(local) / "JARVIS" / LOG_NAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=256 * 1024, backupCount=1, encoding="utf-8")
    except OSError:
        return
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOG.setLevel(logging.INFO)
    LOG.addHandler(handler)
    LOG.propagate = False
