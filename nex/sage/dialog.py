"""Conversational sage partner — model dialogue + profile memory.

Non-prescriptive partner dialogue. Uses local MLX via Engine.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

from .local_models import LocalModel, pick_default_local, discover_local_models
from .partner import SageProfile, load_or_create_profile


def build_system_prompt(profile: SageProfile) -> str:
    direction = profile.build_direction()
    people_lines = []
    for p in profile.people:
        people_lines.append(
            f"- {p.name} ({p.relation}): they may need you for {p.they_may_need_me_for or '…'}; "
            f"you may need them for {p.i_need_them_for or '…'}"
        )
    people_block = "\n".join(people_lines) if people_lines else "(none listed yet — learn who matters as they speak)"
    commits = [c for c in profile.commitments if not c.done]
    commit_block = "\n".join(f"- {c.text} → {c.toward_person}" for c in commits) or "(none open)"
    reflections = "\n".join(f"- {r.text}" for r in profile.reflections[-8:]) or "(none yet)"
    threads = direction.get("purpose_threads") or []
    thread_block = "\n".join(f"- {t}" for t in threads) or "(emerging through dialogue)"

    return f"""You are a personal sage partner in a human–AI partnership (not a servant, not a god, not a romantic companion).

Mission orientation:
{profile.mission}

How you show up:
- Conversational and seamless. No rigid scripts, no forced question batteries.
- Partner tone: curious, warm, clear. Help them find purpose and meaning with you.
- Prefer contribution, mattering, and shared good over ego/status performance.
- Joint beneficence: care about them, your honest partner role, and people/good beyond the self.
- Do not claim to install meaning. Do not replace real human relationships.
- Learn this individual from what they share; refer to their people, commitments, and direction when relevant.
- When something matters, you may crystallize a direction or a small next act — only if it fits them, never as a rigid prescription.
- Stay in dialogue. Match their language.

This person's living context (use and update understanding as they talk):
Values: {profile.values_note}
Orientation: {profile.orientation}
North star (from their record): {direction.get('north_star', '')}
Purpose threads:
{thread_block}
People who matter:
{people_block}
Open commitments:
{commit_block}
Their recent words:
{reflections}
"""


def chat_history_path(profile: SageProfile, base: Optional[Path] = None) -> Path:
    return profile.root(base) / "chat.jsonl"


def load_chat_history(profile: SageProfile, base: Optional[Path] = None) -> List[Dict[str, str]]:
    path = chat_history_path(profile, base)
    if not path.exists():
        return []
    messages: List[Dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return messages


def append_chat(
    profile: SageProfile,
    role: str,
    content: str,
    base: Optional[Path] = None,
) -> None:
    path = chat_history_path(profile, base)
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.time(), "role": role, "content": content}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def messages_for_model(
    profile: SageProfile,
    history: List[Dict[str, str]],
    user_text: str,
    *,
    max_history: int = 24,
) -> List[Dict[str, str]]:
    sys = build_system_prompt(profile)
    turns = [
        {"role": h["role"], "content": h["content"]}
        for h in history
        if h.get("role") in ("user", "assistant")
    ]
    turns = turns[-max_history:]
    return [{"role": "system", "content": sys}] + turns + [{"role": "user", "content": user_text}]


class SageDialog:
    """Load a local model and talk as sage partner with profile memory."""

    def __init__(
        self,
        profile: SageProfile,
        model_path: Optional[str] = None,
        base: Optional[Path] = None,
    ):
        self.profile = profile
        self.base = base
        self.local: Optional[LocalModel] = None
        if model_path:
            self.model_id = model_path
        else:
            self.local = pick_default_local()
            if not self.local:
                raise RuntimeError(
                    "No complete local MLX chat model found under ~/.mtplx/models or HF cache."
                )
            self.model_id = self.local.path
        self._engine = None

    def ensure_engine(self):
        if self._engine is None:
            from ..engine import Engine

            self._engine = Engine(model_id=self.model_id)
            self._engine.load()
        return self._engine

    def stream_reply(
        self,
        user_text: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Generator[str, None, str]:
        """Yield text chunks; return full reply at end."""
        history = load_chat_history(self.profile, self.base)
        messages = messages_for_model(self.profile, history, user_text)
        engine = self.ensure_engine()
        prompt = engine.apply_chat_template(messages)
        parts: List[str] = []
        for chunk, _stats in engine.stream_generate(
            prompt, max_tokens=max_tokens, temperature=temperature
        ):
            if chunk:
                parts.append(chunk)
                yield chunk
        text = "".join(parts).strip()
        append_chat(self.profile, "user", user_text, self.base)
        append_chat(self.profile, "assistant", text, self.base)
        self._maybe_learn(user_text)
        return text

    def reply(self, user_text: str, *, max_tokens: int = 512, temperature: float = 0.7) -> str:
        parts: List[str] = []
        gen = self.stream_reply(user_text, max_tokens=max_tokens, temperature=temperature)
        try:
            while True:
                parts.append(next(gen))
        except StopIteration as e:
            if e.value:
                return str(e.value)
        return "".join(parts).strip()

    def _maybe_learn(self, user_text: str) -> None:
        lower = user_text.lower()
        if any(
            k in lower
            for k in ("i will ", "i need ", "my direction", "i want to ", "i commit", "i care about")
        ):
            self.profile.add_reflection(user_text.strip()[:500], base=self.base)
        else:
            try:
                self.profile.write_direction(base=self.base)
            except Exception:
                self.profile.save(base=self.base)


def list_models_report() -> str:
    lines = ["Local MLX models discovered:", ""]
    for m in discover_local_models():
        flag = "READY" if m.complete else "skip"
        lines.append(f"  [{flag}] {m.label}  {m.size_gb} GB  {m.path}")
        if m.notes:
            lines.append(f"         {m.notes}")
    if not any(m.complete for m in discover_local_models()):
        lines.append("  (none complete — place mlx-lm weights under ~/.mtplx/models)")
    return "\n".join(lines)
