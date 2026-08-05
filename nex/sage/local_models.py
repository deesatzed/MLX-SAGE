"""Discover fully downloaded local MLX chat models on this machine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class LocalModel:
    path: str
    label: str
    size_gb: float
    complete: bool
    notes: str = ""


# Known roots to scan (no network)
_SCAN_ROOTS = [
    Path.home() / ".mtplx" / "models",
    Path.home() / ".mlx-manager" / "models",
    Path.home() / ".cache" / "huggingface" / "hub",
    Path.home() / "MLXModels",
    Path.home() / ".optiq" / "lab" / "models",
]


def _dir_size_gb(path: Path) -> float:
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    except OSError:
        return 0.0
    return total / (1024**3)


def _looks_complete(path: Path) -> bool:
    if not (path / "config.json").exists():
        return False
    # weights present
    safes = list(path.glob("*.safetensors")) + list(path.glob("**/*.safetensors"))
    if not safes:
        return False
    # incomplete HF download stubs are tiny
    if _dir_size_gb(path) < 0.2:
        return False
    return True


def discover_local_models() -> List[LocalModel]:
    found: List[LocalModel] = []
    seen = set()

    candidates: List[Path] = []
    for root in _SCAN_ROOTS:
        if not root.exists():
            continue
        # direct model dirs
        for child in root.iterdir() if root.is_dir() else []:
            if child.is_dir():
                candidates.append(child)
                # HF hub layout: models--org--name/snapshots/<hash>
                snaps = child / "snapshots"
                if snaps.is_dir():
                    for snap in snaps.iterdir():
                        if snap.is_dir():
                            candidates.append(snap)

    for path in candidates:
        try:
            key = str(path.resolve())
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        complete = _looks_complete(path)
        size = _dir_size_gb(path)
        if not complete and size < 0.05:
            continue  # skip empty stubs
        label = path.name
        if path.parent.name == "snapshots":
            label = path.parent.parent.name.replace("models--", "").replace("--", "/")
        notes = "ready" if complete else "incomplete/missing weights"
        # skip pure embedding tiny if not chat
        if "sentence-transformers" in label or "MiniLM" in label:
            notes = "embedding (not chat)"
            complete = False
        found.append(
            LocalModel(
                path=str(path),
                label=label,
                size_gb=round(size, 2),
                complete=complete and "embedding" not in notes,
                notes=notes,
            )
        )

    # Prefer complete, larger first among complete
    found.sort(key=lambda m: (not m.complete, -m.size_gb, m.label))
    return found


def pick_default_local() -> Optional[LocalModel]:
    for m in discover_local_models():
        if m.complete:
            return m
    return None
