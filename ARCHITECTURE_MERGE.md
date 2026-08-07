# Architecture Merge: Nex (OptiqMTPMLX) + gemOptq (Cortex Sentinel + MCP-Cortex)

> **Status (2026-08-07):** Merge executed. Product front door is **MLX-SAGE** (Sage partner + hive + Superintendant). Package import remains `nex` / `nex-cli`. Gaps below under “historical pre-merge” are **closed or largely closed** — see **Post-merge remaining**.

## Goal
Create "Grok in the Loop" — a local-first, auditable, hybrid-reasoning agent supervisor where:
- Fast local OptiQ/MLX models (Nex, Qwen, Gemma variants with MTP) handle the bulk of work.
- Deterministic policy + local auditor provide fast safety rails.
- Ambiguous/high-risk decisions escalate to real Grok (xAI API) with rich structured context.
- Full traces, human oversight, and MCP-structured tool effects.

This combines the strengths of both repos into one compelling product.

## Post-merge remaining (honest, current)

| Area | State |
|------|--------|
| Sentinel policy + PTY Superintendant | **Live** (`nex/sentinel/*`, `superintend`, propellant, WattOS) |
| Grok escalation | **Live** when `XAI_API_KEY` set; graceful skip without |
| Nex TUI tool gates | **Live** via `tui_policy` + real `SentinelPolicy` (not synthetic) |
| Sage partner TUI | **Live** (`nex sage tui`) |
| Hive + joint beneficence | **Live** (`nex we`, tests) |
| OpenAI server / MCP | **Live**; unit smokes for `/health` + `/v1/models` |
| Full multi-agent hive runtime | **Not claimed** |
| Hardware watt meters | **Not claimed** (WattOS = efficiency report brand) |
| Screenshot / asciinema media | **Not recorded yet** (docs must not imply otherwise) |
| Live Grok V8 proof | Optional; needs key |

## Current State Mapping

### From Nex (current main project)
- **Strengths**:
  - Multi-model OptiQ registry (`nex/models.py`) — supports Nex-N2, Qwen3.5/3.6 OptiQ, Gemma-4 OptiQ, Nemotron, etc.
  - MTP / speculative decoding for ~1.3-1.5x speedup.
  - Agent with safe sandbox tools (`list_dir`, `read_file`, `write_file`, `run_python`, `shell`) + robust parser (XML, JSON, ReAct tolerant).
  - Textual TUI (`nex/tui.py`) with real `ChatSession` + persistence, model switching, MTP toggle, stats + **policy-gated tools**.
  - OpenAI-compatible server (`nex/server.py`) — streaming, model selection, basic tool_calls passthrough.
  - MCP server with tools for ask/chat/agent/search.
  - History RAG (optional `[rag]` extra).
  - Plugin system (lazy-load from `~/.nex/plugins/` / `./plugins` on tool use).
  - Config system with per-model overrides.
  - uv-first setup, self-update/doctor.
  - `EXPANSION_PLAN.md` and multi-model substrate under Sage-first product.

- **Historical pre-merge gaps for Grok-in-the-Loop** (closed unless noted):
  - ~~No strong deterministic policy / hard blocks for protected paths.~~ → `SentinelPolicy`
  - ~~No continuous enforcement.~~ → `ContinuousEnforcer` + `FileEffectObserver` (rollback depth still evolving)
  - ~~No structured Grok escalation.~~ → `grok_escalator` + auditor
  - ~~No PTY runner.~~ → `pty_runner` + `supervise`
  - MCP is still primarily server-focused, not a full policy proxy overlay.

### From gemOptq (Cortex Sentinel + MCP-Cortex)
- **Strengths** (highly relevant):
  - **Sentinel core**: PTY runner, file effect observation, deterministic `SentinelPolicy` (protected_paths, secrets, network:external, deploy:production, risk thresholds, overrides).
  - Continuous `Enforcer` + rollback for protected files.
  - Structured local MLX auditor (Gemma-4-12B-it-OptiQ-4bit) that forces strict JSON: `{"verdict":"allow|block|review","risk":"green|yellow|orange|red","reason":"..."}`.
  - Textual TUI with approval queue, pending decisions, manual overrides, FIFO.
  - Persistent `SessionTraceStore` with stable digests, policy decisions, file effects, user actions, rollback events, process lifecycle.
  - Trace replay (JSON + human-readable).
  - **MCP-Cortex**: `CapabilityContract`, `Intent`, `PolicyDecision`, `ContextFabric`, `TraceEvent`, effect vocabulary (read:secrets, write:workspace, network:external, etc.), schemas.
  - `CortexBridge` and `CortexGateway` for recording decisions.
  - Strong safety boundary documentation ("local supervision, not a kernel sandbox").
  - Many smoke tests, readiness matrix, real-agent harness (Claude Code trust prompt, Codex exec + full TUI).

- **Current Gaps**:
  - Auditor is tied to one specific Gemma model (no multi-model or MTP).
  - No native "Grok escalation" path.
  - MCP-Cortex is trace/metadata only (no full proxy yet).
  - Less focus on pure local multi-model inference speed (MTP, OpenAI server).
  - TUI is approval-focused but not a full chat/agent experience.

## Proposed Merged Architecture (Grok in the Loop)

```
User / External Agent (Claude Code, Codex, local Nex agent, or via OpenAI server)
          |
          v
Nex Inference Layer (multi-model OptiQ + MTP)
  - Local fast models for planning, tool use, code gen
  - MTP for decode speed
          |
          v
Cortex Sentinel Supervision Layer (from gemOptq)
  - PTY runner or direct integration
  - File/Command effect observation
  - SentinelPolicy (deterministic hard blocks + risk classes)
  - Continuous Enforcer + rollback
  - SessionTraceStore (full audit)
          |
          +--> Local OptiQ Auditor (fast path, using registry)
          |
          v
Grok Escalation (when REVIEW or high risk/uncertainty)
  - Rich context: Intent + CapabilityContract (from MCP-Cortex) + effects + trace + diffs
  - Call xAI Grok API with strict JSON schema for verdict + reasoning + safe alternative
  - Record escalation in trace (local vs Grok, latency, cost)
          |
          v
Human-in-the-Loop (TUI approval queue, overrides)
  - Approve / Block / Override / Ask Grok for alternative
          |
          v
Execution + Trace + Rollback
  - MCP-Cortex for structured tool effects (when using MCP tools)
  - Full replayable session
```

### Key Integration Points
- **Models/Registry**: Use Nex's `models.py` as the source of truth for all local OptiQ workers + auditor models. Add `grok_escalation` profile.
- **Policy**: Port/adapt `gemOptq/src/sentinel/policy.py` + `SessionOverrideStore` into Nex (or as a dependency). Extend with "grok_review" tier.
- **Auditor**: Generalize gemOptq's `Auditor` to support multiple backends (local OptiQ via Nex engine, Grok via xAI).
- **MCP**: Combine Nex's MCP server with gemOptq's MCP-Cortex. Make Nex agents produce `CapabilityContract`s before tool calls.
- **TUI**: Evolve Nex's `tui.py` with Sentinel's approval queue + pending panel. Add "Grok Escalated" badges and "Ask Grok" actions.
- **Traces**: Unify on gemOptq's `SessionTraceStore` + digests. Extend with `escalated_to_grok`, `grok_verdict`, `grok_reason`.
- **Runner**: Add option to wrap external agents (Claude Code etc.) via gemOptq's PTY runner, or run pure local Nex agents.
- **Config**: Merge configs. Add `grok_in_loop: true`, `xai_api_key`, escalation thresholds.
- **Server**: Enhance Nex's OpenAI server to surface Sentinel policy decisions and Grok escalations.

### Phased Implementation (this session)
See the 5 concrete next steps below.

## Benefits for "Grok in the Loop" Product
- **Efficiency**: 80-95% of decisions stay on fast local MTP OptiQ models.
- **Quality**: Grok handles the hard cases with full context.
- **Safety**: Deterministic policy + structured traces + human override (proven in gemOptq).
- **Auditability**: Every decision, local or Grok, is in replayable traces.
- **MCP-native**: Structured effects for modern agents.
- **Wow Factor**: Local speed + frontier judgment + provable oversight. Perfect for developers who want powerful agents without sending everything to the cloud or trusting them blindly.
- **xAI Alignment**: Directly showcases Grok as the "smart escalation" layer on top of efficient local infrastructure.

This merge turns two solid projects into something that could genuinely stand out.

## Status of 5 Concrete Next Steps (Executed)

1. **ARCHITECTURE_MERGE.md** — Created (this file) with detailed mapping of Nex + gemOptq, proposed fused architecture for Grok in the Loop, and synergy analysis.

2. **Grok Escalation Path** — Implemented `nex/grok_escalator.py` (xAI API client with strict JSON schema). Wired into `nex/agent.py` with `GROK_IN_LOOP=true` env var. Logs escalations, supports fallback. Simple heuristic for risky steps.

3. **MCP-Cortex Integration** — Created `nex/mcp_cortex_adapter.py` (lightweight CapabilityContract generator for Nex tools). Integrated into agent so tool calls emit structured effects (ready for gemOptq PolicyEngine or richer Grok prompts).

4. **TUI + Trace Polish** — Enhanced `nex/tui.py` with dedicated tool execution Log pane, improved think tag rendering in Markdown, theme integration. Agent escalations are traceable via the shared persistence layer (visible in future unified traces).

5. **Demo & Positioning** — Created `scripts/grok_in_loop_demo.py`. Major updates to `README.md` (new Grok in the Loop section + usage). Updated `EXPANSION_PLAN.md` with implementation status. All changes committed and pushed.

See the GitHub repo for the current state. The foundation for a compelling "Grok in the Loop" product using both repos is now in place.