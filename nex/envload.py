"""Load project .env into os.environ (no third-party dependency).

Does not override variables already set in the process environment.
Never logs secret values. OpenRouter and multi-provider routing are tabled —
current Grok path uses XAI_API_KEY → api.x.ai only.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_LOADED = False


def find_dotenv(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up from start (or cwd) looking for a .env file."""
    cur = (start or Path.cwd()).resolve()
    for _ in range(8):
        candidate = cur / ".env"
        if candidate.is_file():
            return candidate
        if cur.parent == cur:
            break
        cur = cur.parent
    # Also try package repo root (…/nex/envload.py → parents[1])
    repo = Path(__file__).resolve().parents[1] / ".env"
    if repo.is_file():
        return repo
    return None


def load_dotenv(path: Optional[Path] = None, *, override: bool = False) -> bool:
    """Parse KEY=VALUE lines into os.environ.

    Returns True if a file was found and read (even if empty).
    """
    global _LOADED
    env_path = path or find_dotenv()
    if env_path is None:
        return False

    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return False

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not override and key in os.environ and os.environ[key] != "":
            continue
        os.environ[key] = value

    _LOADED = True
    return True


def ensure_env_loaded() -> None:
    """Idempotent: load .env once per process."""
    if _LOADED:
        return
    load_dotenv()
