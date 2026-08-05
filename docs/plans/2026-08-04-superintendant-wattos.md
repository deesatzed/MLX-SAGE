# Superintendant + WattOS Implementation Plan

> **For Codex / implementers:** Execute task-by-task. Validate each task before the next. No mocks, no fake Grok verdicts, no placeholder stats. H-track only (human product).

**Goal:** Add real propellant-capped Grok burns and a honest WattOS end report to Nex supervise / grok-claude / grok-codex so a daily-driver wrap proves safety + selective escalation with real counters.

**Architecture:** Thin wrapper first. New pure modules `nex/propellant.py` and `nex/wattos.py`; wire into existing `supervise` loop and grok-* scripts; keep Sentinel/PTY/enforcer behavior; always print WattOS in `finally`. Optional agent path last.

**Tech Stack:** Python 3.11+, Typer, Rich, existing `nex.sentinel.*`, `nex.grok_escalator`, optional `openai` client for xAI.

**Design source of truth:** `docs/plans/2026-08-04-superintendant-wattos-design.md`

**Success criteria (must all pass before claiming complete):** S1–S6 and V1–V7, V9 from design. V8 optional if `XAI_API_KEY` present.

**Working directory for all commands:** `/Volumes/WS4TB/MLX-LM_RAG/OptiqMTPMLX` (or clone root of this package).

```bash
cd /Volumes/WS4TB/MLX-LM_RAG/OptiqMTPMLX
export PYTHONPATH=.
# Prefer project venv if present:
# source .venv/bin/activate
```

---

## Preflight (before Task 1)

**Step 0.1:** Confirm package imports.

```bash
cd /Volumes/WS4TB/MLX-LM_RAG/OptiqMTPMLX
PYTHONPATH=. python -c "from nex.sentinel.policy import SentinelPolicy; from nex.engine import SessionOversight; print('ok')"
```

Expected: `ok`

**Step 0.2:** Snapshot current supervise help (baseline).

```bash
PYTHONPATH=. python -m nex.cli supervise --help
```

Expected: help text without `--max-grok` / `--wattos` yet.

**Step 0.3:** Read (do not edit yet):

- `docs/plans/2026-08-04-superintendant-wattos-design.md`
- `nex/cli.py` lines ~764–931 (`supervise`, `_print_supervise_report`)
- `nex/grok_escalator.py` (`is_available`, no-key return shape)
- `scripts/grok_claude.py`, `scripts/grok_codex.py`
- `nex/agent.py` `_print_oversight_report` (optional Task 7 only)

---

### Task 1: PropellantLedger (TDD)

**Files:**
- Create: `nex/propellant.py`
- Create: `tests/test_propellant.py`
- Modify: none yet

**Step 1.1: Write failing tests**

Create `tests/__init__.py` (empty) and `tests/test_propellant.py`:

```python
"""Unit tests for PropellantLedger — real logic only, no mocks."""
from nex.propellant import PropellantLedger


def test_default_max_is_3():
    led = PropellantLedger()
    assert led.max_burns == 3
    assert led.used == 0
    assert led.remaining == 3
    assert led.denied == 0


def test_can_burn_and_burn_decrements():
    led = PropellantLedger(max_burns=2)
    assert led.can_burn() is True
    assert led.burn() is True
    assert led.used == 1
    assert led.remaining == 1
    assert led.burn() is True
    assert led.used == 2
    assert led.can_burn() is False
    assert led.burn() is False
    assert led.denied == 1
    assert led.used == 2


def test_max_zero_denies_immediately():
    led = PropellantLedger(max_burns=0)
    assert led.can_burn() is False
    assert led.burn() is False
    assert led.denied == 1


def test_record_denied_without_burn():
    led = PropellantLedger(max_burns=1)
    led.record_denied()
    assert led.denied == 1
    assert led.used == 0


def test_snapshot_dict():
    led = PropellantLedger(max_burns=5)
    led.burn()
    snap = led.snapshot()
    assert snap["propellant_max"] == 5
    assert snap["propellant_used"] == 1
    assert snap["propellant_remaining"] == 4
    assert snap["propellant_denied"] == 0
```

**Step 1.2: Run tests — expect FAIL**

```bash
PYTHONPATH=. python -m pytest tests/test_propellant.py -v
```

If pytest missing:

```bash
PYTHONPATH=. python -c "import tests.test_propellant"  # will fail import
# or: pip install pytest
```

Expected: FAIL (`ModuleNotFoundError: nex.propellant` or import error).

**Step 1.3: Implement minimal `nex/propellant.py`**

```python
"""Propellant ledger: cap Grok escalation burns per session.

1 burn = 1 Grok escalation API attempt that was actually started.
No mocks. Local MLX does not consume propellant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class PropellantLedger:
    max_burns: int = 3
    used: int = 0
    denied: int = 0

    def __post_init__(self) -> None:
        if self.max_burns < 0:
            raise ValueError("max_burns must be >= 0")

    @property
    def remaining(self) -> int:
        return max(0, self.max_burns - self.used)

    def can_burn(self) -> bool:
        return self.used < self.max_burns

    def burn(self) -> bool:
        """Consume one burn if available. Returns True if burned, False if denied."""
        if not self.can_burn():
            self.denied += 1
            return False
        self.used += 1
        return True

    def record_denied(self) -> None:
        """Count a would-be burn blocked without calling burn() (e.g. pre-check path)."""
        self.denied += 1

    def snapshot(self) -> Dict[str, Any]:
        return {
            "propellant_max": self.max_burns,
            "propellant_used": self.used,
            "propellant_remaining": self.remaining,
            "propellant_denied": self.denied,
        }
```

**Step 1.4: Run tests — expect PASS**

```bash
PYTHONPATH=. python -m pytest tests/test_propellant.py -v
```

Expected: all PASSED.

**Step 1.5: Commit (if git desired)**

```bash
git add nex/propellant.py tests/__init__.py tests/test_propellant.py
git commit -m "feat(nex): PropellantLedger for capped Grok escalations"
```

Only commit if the user asked for commits or this is an agreed workflow.

---

### Task 2: WattOSReport (TDD)

**Files:**
- Create: `nex/wattos.py`
- Create: `tests/test_wattos.py`
- Modify: none

**Step 2.1: Write failing tests**

```python
"""WattOS report honesty — no fake local tokens for child-agent wraps."""
from nex.propellant import PropellantLedger
from nex.wattos import WattOSReport, render_wattos_text


def test_child_agent_local_tokens_are_na_not_zero():
    rep = WattOSReport(
        mode="supervise",
        agent="claude",
        wall_time_s=1.5,
        policy_decisions=2,
        blocks=1,
        reviews=0,
        grok_escalations=0,
        propellant=PropellantLedger(max_burns=3),
        local_generation_tokens=None,  # not measured
        avg_generation_tps=None,
        note="test",
        grok_status="skipped (no key)",
    )
    text = render_wattos_text(rep)
    assert "n/a" in text.lower()
    assert "child agent" in text.lower() or "not local" in text.lower()
    # Must not claim measured zero tokens as efficiency
    assert "local gen tokens: 0" not in text.lower().replace(" ", "")


def test_local_agent_shows_token_counts():
    rep = WattOSReport(
        mode="agent",
        agent="nex",
        wall_time_s=2.0,
        policy_decisions=1,
        blocks=0,
        reviews=1,
        grok_escalations=1,
        propellant=PropellantLedger(max_burns=3, used=1),
        local_generation_tokens=100,
        avg_generation_tps=40.0,
        note="local mlx",
        grok_status="ok",
    )
    text = render_wattos_text(rep)
    assert "100" in text
    assert "40" in text
    assert "1/3" in text or "propellant" in text.lower()


def test_propellant_denied_in_text():
    led = PropellantLedger(max_burns=0)
    led.burn()  # denied
    rep = WattOSReport(
        mode="supervise",
        agent="demo",
        wall_time_s=0.1,
        policy_decisions=1,
        blocks=0,
        reviews=1,
        grok_escalations=0,
        propellant=led,
        local_generation_tokens=None,
        avg_generation_tps=None,
        note="denied demo",
        grok_status="propellant empty",
    )
    text = render_wattos_text(rep)
    assert "denied" in text.lower() or str(led.denied) in text
```

**Step 2.2: Run — expect FAIL**

```bash
PYTHONPATH=. python -m pytest tests/test_wattos.py -v
```

**Step 2.3: Implement `nex/wattos.py`**

Requirements:

- Dataclass `WattOSReport` with fields from design §6.
- `render_wattos_text(report) -> str` for tests and non-Rich paths.
- `print_wattos_report(report, console=None)` using Rich Table/Panel when Rich available (same style as `_print_supervise_report`).
- When `local_generation_tokens is None`: display  
  `n/a (child agent, not local MLX)` (or mode-specific reason via optional `local_stats_reason: str | None`).
- Include propellant used/max, remaining, denied, wall, policy, blocks, reviews, grok escalations, grok_status, note.
- Title something like `WattOS — Safety & Efficiency`.
- Dim footnote: v1 metrics are counters/propellant/wall; not hardware watt meters.

**Step 2.4: Run — expect PASS**

```bash
PYTHONPATH=. python -m pytest tests/test_wattos.py tests/test_propellant.py -v
```

**Step 2.5: Commit (optional)**

```bash
git add nex/wattos.py tests/test_wattos.py
git commit -m "feat(nex): WattOS report with honest n/a local tokens"
```

---

### Task 3: Wire supervise CLI (flags + ledger + WattOS)

**Files:**
- Modify: `nex/cli.py` (`supervise` ~764–931, replace `_print_supervise_report` usage)
- Keep: `_print_supervise_report` temporarily as thin wrapper calling WattOS **or** delete after switch (prefer replace call sites only)

**Step 3.1: Add Typer options to `supervise`**

Add parameters (names can match design):

```python
max_grok: int = typer.Option(3, "--max-grok", help="Propellant: max Grok escalations this session"),
use_grok: bool = typer.Option(True, "--grok/--no-grok", help="Allow Grok escalation when policy reviews (needs key)"),
on_empty: str = typer.Option(
    "human_or_block",
    "--on-empty",
    help="When propellant empty on REVIEW: human_or_block | block | allow_local_only",
),
wattos: bool = typer.Option(True, "--wattos/--no-wattos", help="Print WattOS end report"),
```

**Compatibility:** Keep existing `--grok-in-loop` as alias that sets `use_grok=True` if still referenced in docs, or map:
- `--grok-in-loop` remains; if either `--grok-in-loop` or `--grok`, enable escalator when key present.

Recommended mapping:

```text
effective_grok = (grok_in_loop or use_grok) and key_available_or_attempt
```

Design preferred: `--grok/--no-grok` is primary; keep `--grok-in-loop` as deprecated synonym setting the same flag so existing docs don’t break.

**Step 3.2: Create ledger at start of supervise (after install early-return)**

```python
from .propellant import PropellantLedger
from .wattos import WattOSReport, print_wattos_report

ledger = PropellantLedger(max_burns=max_grok)
```

**Step 3.3: Gate Grok on REVIEW**

Replace the current pattern that always increments `grok_escalations` and calls auditor without propellant:

**Current anti-pattern (cli.py ~873–880):** increments escalations even when Grok may be fake/unavailable counting.

**Target logic:**

```python
if decision.action.value in ("review", "confirm"):
    reviews += 1  # policy review observed
    if not effective_grok:
        # no grok requested
        ...
    elif not ledger.can_burn():
        ledger.record_denied()  # or burn() which denies
        # on_empty: if human_or_block and sys.stdin.isatty(): prompt; else BLOCK (write "n")
        ...
    else:
        # Only burn when we will actually call escalator
        if auditor/grok available:
            if ledger.burn():
                grok = auditor.audit(...)
                if grok.get("escalated") is False and "no XAI" in reason:
                    # Design: no key short-circuit should NOT consume burn.
                    # Prefer check is_available BEFORE burn.
                    pass
```

**Critical honesty rule (implement carefully):**

```python
# CORRECT order:
if not grok_escalator.is_available():
    grok_status_parts.append("skipped (no key)")
    # do NOT burn
elif not ledger.can_burn():
    ledger.record_denied()
    # apply on_empty
else:
    ledger.burn()  # request about to start
    grok = auditor.audit(...)
    grok_escalations += 1
    # handle verdict
```

Inspect `GrokAugmentedAuditor.audit` and `GrokEscalator.is_available` so no-key path never burns.

**Step 3.4: `finally` always WattOS when wattos=True**

Replace `_print_supervise_report(...)` with:

```python
rep = WattOSReport(
    mode="supervise",
    agent=str(agent),
    wall_time_s=wall,
    policy_decisions=policy_decisions,
    blocks=blocks,
    reviews=reviews,
    grok_escalations=grok_escalations,
    propellant=ledger,
    local_generation_tokens=None,
    avg_generation_tps=None,
    note=f"workspace={workspace}; external agent under Sentinel",
    grok_status=...,  # build string during run
)
if wattos:
    print_wattos_report(rep)
```

**Step 3.5: Verify help**

```bash
PYTHONPATH=. python -m nex.cli supervise --help
```

Expected: shows `--max-grok`, `--grok/--no-grok`, `--on-empty`, `--wattos`.

**Step 3.6: Syntax check**

```bash
PYTHONPATH=. python -c "from nex.cli import app; print('cli ok')"
```

**Step 3.7: Commit (optional)**

```bash
git add nex/cli.py
git commit -m "feat(nex): supervise propellant gate + WattOS end report"
```

---

### Task 4: Shared supervise-loop helper (DRY) + grok scripts

**Problem:** `cli.supervise`, `grok_claude.py`, and `grok_codex.py` duplicate loops. Avoid three divergent WattOS implementations.

**Files:**
- Create: `nex/superintend.py` (or `nex/supervise_loop.py`)
- Modify: `nex/cli.py` to call helper where practical
- Modify: `scripts/grok_claude.py`
- Modify: `scripts/grok_codex.py`

**Step 4.1: Extract minimal shared function**

Something like:

```python
# nex/superintend.py
def run_supervised_session(
    *,
    cmd: str,
    workspace: str,
    max_grok: int = 3,
    use_grok: bool = True,
    on_empty: str = "human_or_block",
    wattos: bool = True,
    agent_label: str = "agent",
) -> int:
    """Run PTY + enforcer + propellant + WattOS. Returns process exit code."""
    ...
```

Move the loop body from `supervise` into this function. CLI and scripts become thin wrappers.

**If extraction is too risky mid-flight:** duplicate WattOS/ledger wiring carefully in both scripts matching CLI semantics, then extract in a follow-up. Prefer extract if tests pass.

**Step 4.2: Update `scripts/grok_claude.py` argparse**

```text
--max-grok N
--grok / --no-grok  (or --grok-in-loop keep + --max-grok)
--on-empty
--wattos / --no-wattos
--dry-run (existing)
```

End with WattOS report; same burn-before-call order.

**Step 4.3: Mirror `scripts/grok_codex.py`**

**Step 4.4: Dry-run still works**

```bash
PYTHONPATH=. python scripts/grok_claude.py --dry-run
PYTHONPATH=. python scripts/grok_codex.py --dry-run
```

Expected: exit 0, no crash.

**Step 4.5: Commit (optional)**

```bash
git add nex/superintend.py nex/cli.py scripts/grok_claude.py scripts/grok_codex.py
git commit -m "feat(nex): shared superintend loop + WattOS on grok-claude/codex"
```

---

### Task 5: Real demo script (S1–S6 / V4–V7)

**Files:**
- Create: `scripts/wattos_superintendant_demo.py`

**Purpose:** Do **not** require real `claude` binary. Use a controlled child process that creates a risky file so FileEffectObserver + policy can fire.

**Step 5.1: Demo behavior**

1. Create temp workspace.  
2. Configure policy or rely on default + known path (inspect `SentinelPolicy` defaults for what triggers REVIEW/BLOCK).  
3. Run supervised child, e.g.:

```bash
python -c "from pathlib import Path; Path('SECRETS_LEAK.txt').write_text('x')"
# or touch a path under policy-protected patterns
```

4. Run with:
   - `--max-grok 0` → expect `propellant_denied` if REVIEW tried to escalate  
   - `--no-grok` → grok skipped  
   - default → policy counters ≥ 1  

5. Always print WattOS.  
6. Exit 0 if assertions hold:

```python
assert report.policy_decisions >= 1 or report.blocks + report.reviews >= 1
# At least one of: block, review, or enforcer decision observed
```

**Step 5.2: If default policy never fires on simple create**

Then demo must either:
- Use `policy.evaluate([FileEffect(...)])` in a **unit integration** path that still uses real `PropellantLedger` + `WattOSReport`, **and**
- Run enforcer against real FS write under workspace with patterns from `SentinelPolicy` source.

Read `nex/sentinel/policy.py` for protected globs before writing demo. Adjust demo path to match a real rule (e.g. `.env`, credentials pattern).

**Step 5.3: Run demo**

```bash
PYTHONPATH=. python scripts/wattos_superintendant_demo.py
PYTHONPATH=. python scripts/wattos_superintendant_demo.py --max-grok 0
env -u XAI_API_KEY -u OPENAI_API_KEY PYTHONPATH=. python scripts/wattos_superintendant_demo.py --grok
```

Expected: exit 0; WattOS panel; no traceback.

**Step 5.4: Commit (optional)**

```bash
git add scripts/wattos_superintendant_demo.py
git commit -m "test(nex): real WattOS superintendant demo without mock Grok"
```

---

### Task 6: Docs + PROGRESS evidence

**Files:**
- Modify: `PROGRESS.md`
- Modify: `DECISIONS.md` (short entry: H-track Superintendant+WattOS freeze)
- Modify: `README.md` — short section **Superintendant + WattOS**
  - What it does  
  - Flags  
  - Honesty: no hardware watts in v1; local tokens n/a for external agents  
  - Link design + this plan  

**Step 6.1: PROGRESS entry template**

```markdown
## Superintendant + WattOS (2026-08-04)
- Design: docs/plans/2026-08-04-superintendant-wattos-design.md
- Plan: docs/plans/2026-08-04-superintendant-wattos.md
- Verification:
  - pytest tests/test_propellant.py tests/test_wattos.py: PASS (paste)
  - demo: PASS (paste excerpt of WattOS fields)
  - supervise --help: flags present
  - no-key path: skipped reason shown
- Remaining: V8 if key available; optional agent WattOS unify
```

**Step 6.2: V9 install smoke**

```bash
PYTHONPATH=. python -m nex.cli supervise --install
```

Expected: alias block printed; hooks copy if source exists; no crash.

**Step 6.3: Commit (optional)**

```bash
git add PROGRESS.md DECISIONS.md README.md
git commit -m "docs: Superintendant + WattOS usage and verification evidence"
```

---

### Task 7 (optional): Unify agent path with WattOS

**Files:**
- Modify: `nex/agent.py` (`_print_oversight_report`)

**Step 7.1:** Build `WattOSReport` from `SessionOversight` with **real** local tokens/tps filled in (not None).

**Step 7.2:** Propellant on agent Grok path if agent already escalates — same can_burn/burn order.

**Step 7.3:** Smoke:

```bash
# Only if model available; otherwise skip and note in PROGRESS
PYTHONPATH=. python -c "from nex.wattos import WattOSReport; print('agent path deferred or ok')"
```

**Do not block v1 complete on Task 7** if S1–S6 already met via supervise/demo.

---

## Final verification checklist (gate before “done”)

Run from package root:

```bash
PYTHONPATH=. python -m pytest tests/test_propellant.py tests/test_wattos.py -v
PYTHONPATH=. python -m nex.cli supervise --help | tee /tmp/supervise-help.txt
grep -E 'max-grok|wattos|on-empty' /tmp/supervise-help.txt
PYTHONPATH=. python scripts/wattos_superintendant_demo.py
PYTHONPATH=. python scripts/wattos_superintendant_demo.py --max-grok 0
env -u XAI_API_KEY -u OPENAI_API_KEY PYTHONPATH=. python scripts/grok_claude.py --dry-run
PYTHONPATH=. python -m nex.cli supervise --install
```

| ID | Required | Evidence |
|----|----------|----------|
| V1 | yes | pytest propellant |
| V2 | yes | pytest wattos n/a |
| V3 | yes | help flags |
| V4 | yes | demo exit 0 |
| V5 | yes | policy/block/review counters in demo output |
| V6 | yes | max-grok 0 → denied ≥ 1 or documented if policy never escalates |
| V7 | yes | no-key skip reason |
| V8 | optional | key present → real escalation or honest error |
| V9 | yes | --install runs |

If any required V fails: document gap + action plan in PROGRESS; do not claim complete.

---

## Out of scope (do not implement in this plan)

- optQlab / mlx-rag / omlxurus changes  
- Multi-Mac fleet  
- Hardware power meters  
- Mock Grok for CI  
- Replacing Claude/Codex  

---

## Execution handoff

Plan complete and saved to:

`OptiqMTPMLX/docs/plans/2026-08-04-superintendant-wattos.md`

**Two execution options:**

1. **Subagent-driven (this session)** — one task at a time, review between tasks  
2. **Parallel / separate session** — new session executes this plan with checkpoints  

**Which approach?**
