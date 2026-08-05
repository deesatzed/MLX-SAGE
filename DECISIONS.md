# DECISIONS.md — Nex / Grok-in-the-Loop

Architectural, scope, feature, and strategy decisions. Updated on change. Per AGENTS.md.

Treat as project source of truth alongside EXPANSION_PLAN.md and ARCHITECTURE_MERGE.md.

## 2026-08-04: Superintendant + WattOS v1 (H-track)

**Decision:** Ship thin-wrapper Superintendant (Approach A) with PropellantLedger + WattOS end report on `nex supervise` and grok-claude/codex. H-track only (human product). No SI claims. No hardware watt meters in v1.

**Rationale:**
- Portfolio brainstorm locked recommended stack: daily-driver wrap + selective Grok + efficiency proof.
- Build on existing PTY/policy/enforcer; add burn gate honesty (no burn without API; refund if remote not called).
- WattOS brand = efficiency proof; v1 fields = wall, policy, blocks, reviews, escalations, propellant, local tok n/a for child agents.

**Rejected for v1:** always-on daemon (Approach B), fleet, wiki/RAG, omlxurus router, mock Grok for CI.

**Evidence:** design + plan under `docs/plans/2026-08-04-superintendant-wattos*`; pytest 8/8; demo PASS; see PROGRESS.

---

## 2025 (this session): Needs-First Feature Gate (User Directive)
**Decision**: Every new or refined feature must be derived from explicit, articulated unmet needs ("Features MUST be needs based. Lets think of Needs not being met by others first"). No tech-for-tech, no "wow" detached from pain.

**Rationale / Evidence**:
- Direct from repeated user directive + workspace rules (no mock, validation, quality).
- Current docs (README "The Real Problem (Needs First...)", showpiece, video script, "Extra Big Wow", "Make Elon Proud") already list 5-6 specific pains that ONLY the fused stack (local OptiQ+MTP + Sentinel deterministic policy/enforcer/PTY + MCP-Cortex contracts + real Grok escalation + unified traces) solves.
- Audit (grep + source read) showed strong implementation of core (PTY wrappers, policy, grok_escalator, stats in Engine, PendingApproval skeleton) but weak *visibility* of the value delivered to the user (efficiency proof, oversight counts, "Grok was used X times for these reasons, local did the rest at Y t/s").
- This visibility directly serves multiple needs at once:
  1. Efficiency at the Hardware Level (Apple Silicon) — user sees tokens/s, local dominance in real agentic runs.
  2. Frontier Intelligence Only When It Matters — explicit escalation count + context in reports.
  3. Auditability & Replay — summary is the at-a-glance proof + points to full trace.
  4. Use the Agents I Already Love (supervise claude/codex etc) — the report is the "what did the wrapper buy me?" evidence that makes the Extra Big Wow credible and sticky.
  5. Safety that Actually Works — blocks/reviews/rollbacks counted and explained.

**Satz First Principles Applied**:
- User goal: Trustworthy, efficient, auditable agentic work *without abandoning existing daily tools or paying cloud tax for everything*.
- Non-neg: real code, no mocks, small changes, validate before claim, follow AGENTS (read 5 files — absent so created PROGRESS/DECISIONS), update plans.
- Assumptions: Users (and xAI/Tesla reviewers) will only believe "local 80-95% + Grok on hard + deterministic rails" if they *see the numbers* in their own sessions.
- Smallest useful: One additive "Session Oversight & Efficiency Summary" (counters + t/s aggregate + decision breakdown) printed at natural termination points and reflected live where possible. Leverages 100% existing data paths.
- Removable: Full interactive TUI approval queue (higher value but larger delta; defer), new deps, server changes.

**Alien Goggles / Alternatives Considered**:
- Inverted: Agent calls a "get_oversight_score" tool mid-run (meta, interesting for self-reflection need; smaller than UI but less user-visible for "wow").
- Overlooked simple: Just `nex trace summary <id>` that computes aggregates from existing JSONL (low risk, high audit value; chosen as complementary).
- Outside: Compliance-officer web dashboard for traces (too big; would duplicate TUI/CLI value).
- Risky fancy: Real power/thermal sampling on macOS (SMC) for true watts — cool for "tokens-per-watt" but hardware-specific, fragile, not core to current needs (deferred).

**Ranked Options** (for this push):
| Option | Success | Evidence from Repo | Main Risk |
|--------|---------|--------------------|-----------|
| End-of-run + TUI-visible Oversight Summary (chosen) | High | Agent already collects List[GenerationStats] + grok paths; supervise has loop + policy/grok calls; TUI has reactive stats_text + Log for tools; rich panels used everywhere. | Low (additive prints/counters; no behavior change to execution). |
| Enhance `nex trace replay` with auto summary section | High | trace_viewer exists, persistence has stats/extra; easy to post-process. | Low. Less "during use" proof. |
| Wire full PendingApproval queue + interactive in TUI + callback from pty | Moderate | Class + imports + tui_callback param exist; gemOptq patterns known. | Higher (UI state, threading for PTY+TUI, approval flow semantics). Defer to keep small. |
| Hook installer + alias for daily claude/codex | Moderate | Scripts + pyproject entrypoints (grok-claude) already there; .grok/hooks example. | Packaging/UX for "permanent". Good future. |

**Chosen**: Option 1 (smallest useful that makes multiple "only we" claims *experientially true* for the user right now). Will also lightly improve trace path if easy.

**Implementation Constraints (self-imposed for this decision)**:
- Edit <= 5 files.
- No new runtime deps.
- Report must be real (use actual stats, actual grok decision dicts, actual step counts).
- Must work for native GROK_IN_LOOP agent and for supervise (even when external agent is black-box).
- Graceful when no Grok key (counts 0 escalations or "unavailable").
- Update this file + PROGRESS + EXPANSION_PLAN on completion.
- Run real validation (demo script, import, supervise dry/help, agent path) and confirm output before marking complete.

**Status**: COMPLETE (verified).

Implementation: SessionOversight in engine.py; tracking + _print_oversight_report (cyan Panel with real local t/s + escalation counts) wired into agent.py returns; counters + _print_supervise_report (green Panel emphasizing no-workflow-change) in cli.py:supervise finally; same for scripts/grok_claude.py; TUI stats reminder.

Validation (real commands, no mocks, see PROGRESS.md):
- Report rendered with live data (1842 local tokens, 38.7 t/s, 2 grok escalations, 1 block etc).
- supervise --help intact + "Extra Big Wow" text.
- grok_claude --dry-run intact.
- TUI/PendingApproval/policy imports + construct OK.
- No behavior change to core loops; reports are additive proof of the needs.

This satisfies the "needs first" gate for this feature. Future features must reference a specific unmet need from the lists + record here.

## Prior Key Decisions (summarized from history / plans)
- Fusion of Nex (OptiQ/MTP/multi-model/CLI/TUI/server/MCP) + gemOptq (Sentinel policy/enforcer/PTY/auditor/traces + MCP-Cortex) into "Grok in the Loop" (see ARCHITECTURE_MERGE.md for diagram and 5 steps; all executed).
- PTY supervision as the "Extra Big Wow" (use exact daily drivers; no workflow change for user).
- Deterministic policy *before* any LLM judgment (including Grok).
- Real Grok (xAI /v1) with strict JSON for escalation; graceful fallback.
- uv-first, optional extras, no mocks ever.
- Needs reframing of all positioning (README, docs/*, video script) — done prior; this decision extends it to code features.

## Open / Future Decisions (needs-tied)
- How to surface full approval queue in unified TUI without fracturing the chat experience (needs: human-in-loop visibility during supervise or agent). **This batch made Pending live + basic pane + actions in existing TUI + constructions everywhere (incremental, no full modal HUD yet).**
- Permanent integration story for Cursor/Aider/etc (OpenAI server + policy layer is partial; full "supervise the editor agent" needs more). **This batch added --install for shell aliases + hooks (big step for daily driver permanence).**
- Public trace artifacts (redacted gallery) for credibility / "make Elon proud" demos. **Implemented in this batch as `nex trace-gallery` + export_gallery (real scans + redaction + MD output).**
- Hardening + new showpiece on fresh clone copy (this task): All docs/landing/README updated, scripts hardened for real enforcer, new `hardened_supervision_showpiece.py` created as the canonical reproducible demo. Run on clean clone extraction to prove gains are not dev-environment dependent.

Any change to scope, arch, or "what counts as needs-based" must be recorded here before implementation.
