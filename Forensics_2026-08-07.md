# MLX-SAGE — Hostile-Committee Forensics (as of 2026-08-07)

> `/build` Stage 2 → `discovery --mode=forensics`. Classifications are evidence-bound.

---

## 1. Executive Summary

**What it is:** A Python Typer monorepo (`nex-cli` / import `nex`) that ships three intertwined products:

1. **Sage partner** — local MLX conversational TUI + living direction FS profile  
2. **Hive cell** — co-goal + roles + joint beneficence + receipt  
3. **Superintendant / Nex multi-model** — chat/agent/serve/MCP + PTY supervision + propellant Grok + WattOS  

**Runtime entrypoints**

| Entry | Kind | Live? |
|-------|------|-------|
| `python -m nex.cli` / `nex` | CLI | LIVE |
| `nex sage tui` | Textual app | LIVE (needs complete local weights) |
| `nex tui` | Textual app | **HYBRID** (real MLX + synth approval queue) |
| `nex serve` | FastAPI | LIVE (optional deps) |
| `nex mcp` | MCP stdio | LIVE |
| `nex supervise` / `grok-claude` / `grok-codex` | PTY wrap | LIVE (child binary + optional key) |
| `scripts/*_demo.py` / showpieces | scripts | LIVE demos (real policy/FS; not product UI) |

**Production-like vs demo-like**

- **Production-like cores:** beneficence evaluator, hive FS, propellant ledger, Sentinel policy on real FS effects, WattOS honesty fields, sage dialog→Engine, OpenAI server routes present.  
- **Demo-like / synth:** Nex TUI approval queue constructs `fake_fx`/`fake_dec` without calling `SentinelPolicy.evaluate`; approval actions only update logs (no enforcer/trace side effects). Screenshot sections are explicit placeholders.  

**Top 10 risks (committee)**

1. TUI “Sentinel queue” looks live but enqueues synthetic REVIEW decisions  
2. Approve/block/override do not affect policy/enforcer/agent  
3. Dual product story (Sage README vs OptiQ Nex packaging) confuses diligence  
4. No CI — regressions invisible  
5. No LICENSE file despite MIT claim  
6. Grok path graceful-fallback can be mistaken for “Grok reviewed” if UI not careful  
7. Agent sandbox tools + shell capability need clear threat model  
8. Plugin auto-load on import surprises operators  
9. Media placeholders if treated as proof  
10. Live MLX / live XAI not re-proved in this forensics pass (deps machine-local)

**Top 10 hostile questions**

1. Does the approvals pane reflect real policy? → **No** for `nex tui` tool path.  
2. Does “a/b/o” stop a dangerous tool? → **No** side effects beyond UI log.  
3. Is WattOS measuring watts? → **No**; efficiency/oversight report brand.  
4. Does hive “mean” anything exists? → **No**; co-goal gate + receipt only.  
5. Is Grok always in the loop? → **No**; key + propellant + flags.  
6. Are showpieces faking policy? → **No** on `.env` BLOCK path (real evaluate).  
7. Is Sage tested end-to-end with MLX in CI? → **No** (unit profile tests only).  
8. Can I ship this as production supervision? → **Not without** real TUI↔policy wiring + CI.  
9. What’s the package name? → `nex-cli` / `nex`, product MLX-SAGE.  
10. Where is the license? → README text only; file missing.

---

## 2. System Map

### Components

| Component | Role | Data/IO |
|-----------|------|---------|
| Typer CLI (`nex/cli.py`) | Primary UX router | argv, Rich console |
| Engine (`engine.py`) | mlx-lm load/generate | local weights, GenerationStats |
| Models registry | aliases/repos | HF hub, local paths |
| Sage (`sage/*`) | partner memory + TUI | `sessions/sage/<id>/` |
| Hive (`hive/cell.py`) | co-goal cells | `sessions/hive/*.json` |
| Mission (`mission.py`) | constitution + beneficence | pure functions |
| Agent + tools | sandbox agent | `./sandbox/` |
| Server | OpenAI-compat | HTTP `/v1/*` |
| MCP | tool protocol | stdio |
| Sentinel policy/enforcer/PTY | supervise rails | workspace FS, child PTY |
| Grok escalator | remote verdict JSON | `XAI_API_KEY` → xAI API |
| Propellant + WattOS | burn cap + report | counters, console panel |
| Trace viewer/gallery | audit artifacts | `sessions/`, `logs/` |
| Plugins | optional tools | `plugins/`, `~/.nex/plugins/` |

### Topology (local)

```
Terminal ──► nex CLI ──┬── Engine (MLX local)
                       ├── Sage TUI ── Engine
                       ├── Nex TUI ── Engine + tools (synth approvals)
                       ├── serve :port ── Engine
                       ├── mcp ── Engine
                       └── supervise ── PTY child + Policy + Enforcer + Propellant ± Grok
```

No remote multi-tenant deploy; single-user local-first.

### Primary user flows (3–7)

1. **Sage talk** — `sage models` → `sage tui` → stream reply → chat.jsonl + direction  
2. **Hive start** — `we start` → beneficence gate → receipt JSON  
3. **Local chat/agent** — `nex chat` / `nex agent` → sandbox tools  
4. **Supervise daily agent** — `supervise` / `grok-claude` → policy on FS → WattOS  
5. **IDE backend** — `nex serve` → client OpenAI SDK  
6. **MCP client** — Cursor/Claude → `nex mcp`  
7. **Showpiece proof** — demo scripts assert real BLOCK/WattOS honesty  

---

## 3. Repo Navigation Guide

| Goal | Start here |
|------|------------|
| Product intent | `README.md`, `docs/sessions/*` |
| Package/deps | `pyproject.toml` |
| All commands | `nex/cli.py` |
| Sage | `nex/sage/` |
| Hive/mission | `nex/hive/cell.py`, `nex/mission.py` |
| Supervise | `nex/superintend.py`, `nex/sentinel/` |
| Architecture merge story | `ARCHITECTURE_MERGE.md` |
| Verified claims | `PROGRESS.md`, `DECISIONS.md` |
| Deepdive | `Analysis_2026-08-07.md` |
| Run | `run.sh`, `pip install -e ".[tui]"` |

---

## 4. Frontend UI-to-Behavior Catalog

### A. Sage TUI (`nex sage tui` → `nex/sage/tui.py`)

| UI Element | Purpose | Trigger | Classification | Evidence | Backend | Failure | Tests |
|------------|---------|---------|----------------|----------|---------|---------|-------|
| Chat input | Talk to partner | Enter | **LIVE BACKEND** | `SageDialog.stream_reply` → `Engine.stream_generate` | local MLX | No complete model → RuntimeError | partner unit, not TUI E2E |
| Ctrl+D direction | Show direction | key | **LIVE BACKEND** | profile `write_direction` / synthesize | FS profile | empty profile still synthesizes | unit |
| Ctrl+E export | Export pack | key | **LIVE BACKEND** | export markdown from profile | FS | — | unit export |
| Ctrl+N new thread | Reset chat keep profile | key | **LIVE BACKEND** | chat history path | FS | — | partial |
| Model pick `-m` | Choose weights | CLI | **LIVE BACKEND** | `local_models.discover` complete filter | disk | incomplete HF stub skipped | discover logic |

### B. Nex TUI (`nex tui` → `nex/tui.py`)

| UI Element | Purpose | Trigger | Classification | Evidence | Backend | Failure | Committee note |
|------------|---------|---------|----------------|----------|---------|---------|----------------|
| Chat input + stream | Local chat | Enter | **LIVE BACKEND** | Engine generate + session persist | MLX + sessions | load fail shown | Real inference |
| Model list / MTP switch | Select model/MTP | UI | **LIVE BACKEND** | registry + Engine reload | models.py | MTP draft missing | Real |
| Tool log | Show tool calls | parse_tool_call | **LIVE BACKEND** | `execute_tool` real | tools/sandbox | exception logged | Real tools |
| Approvals log “PENDING REVIEW” | Human-in-loop | tool path | **SYNTH / HYBRID** | `fake_fx` + `fake_dec` constructed without `policy.evaluate` | none | swallowed except | **Looks like Sentinel; is not** |
| a / b / o bindings | Approve/block/override | keys | **PURE DEMO (UI-only)** | `_handle_pending` only pops list + log write; comment “In full: would record…” | none | no-op if empty | Does not gate tools |
| Stats “Sentinel+policy active” | Oversight reminder | after gen | **HYBRID** | static string append; enforcer not driving chat | marketing text | — | Overclaims if read literally |

### C. CLI surfaces (non-TUI)

| Surface | Classification | Evidence |
|---------|----------------|----------|
| `sage init/people/sit/commit/direction/export` | **LIVE** | FS profile + tests |
| `we constitution/start/check/receipt` | **LIVE** | cell JSON + beneficence + tests |
| `chat/ask/agent` | **LIVE** | Engine + agent loop |
| `models *` | **LIVE** | registry + hub download |
| `serve` health/v1 | **LIVE** | FastAPI routes in `server.py` |
| `mcp` | **LIVE** | mcp.py tools |
| `supervise` + propellant + WattOS | **LIVE** | superintend real PTY/enforcer; tests on ledger/report |
| `trace` / `trace-gallery` | **LIVE** | scans sessions/logs; empty if no data |
| `self doctor/status` | **LIVE** | env checks |
| Screenshot sections in README/index | **PURE DEMO / PLACEHOLDER** | labeled placeholders in PROGRESS |
| Showpiece scripts | **LIVE DEMO** | real policy BLOCK on `.env` (this session re-verified) |
| Example plugin calculator | **LIVE** (side-load) | loads on CLI import |

---

## 5. Backend Service & API Inventory

### HTTP (`nex serve`)

| Method | Path | Handler | Auth | Data | Status |
|--------|------|---------|------|------|--------|
| GET | `/health` | health | none | static | LIVE |
| GET | `/v1/models` | list profiles | none | registry | LIVE |
| POST | `/v1/chat/completions` | generate ± stream | none | Engine | LIVE |

No auth layer — local trust model only.

### Domain services (in-process)

| Service | Entry | Notes |
|---------|-------|-------|
| Engine | `engine.Engine` | mlx-lm |
| SentinelPolicy.evaluate | effects list | deterministic |
| ContinuousEnforcer | observer.diff loop | supervise |
| PropellantLedger | burn/deny | supervise |
| GrokEscalator.escalate | HTTP JSON | optional key |
| evaluate_joint_beneficence | pure | hive/sage sit |
| export_gallery | FS scan | redaction flag |

### Jobs / queues

None. Interactive processes only.

### Integrations

| Integration | Required | Classification |
|-------------|----------|----------------|
| mlx-lm / Apple Silicon | for local gen | LIVE when weights present |
| Hugging Face hub | downloads | LIVE |
| xAI Grok API | escalate | LIVE when key; else graceful “unavailable” dict |
| External claude/codex binaries | supervise | LIVE if installed |

---

## 6. Data & State: Where Truth Lives

| Store | Path / form | Synth? |
|-------|-------------|--------|
| Sage profile + direction + chat | `sessions/sage/<id>/` JSON/md/jsonl | Real user data |
| Hive cells | `sessions/hive/hive-*.json` | Real |
| Chat sessions (Nex) | `sessions/` via persistence | Real |
| Logs | `logs/` | Real when written |
| User config / models | `~/.nex/` (config paths) | Real |
| Sandbox workspace | `./sandbox/` | Real agent effects |
| Demo temp dirs | `/tmp` / tempfile in scripts | Ephemeral real FS |

No SQL DB. No seed fixtures in production path (tests construct real temp/profile data).

---

## 7. Synth / Demo / Live Classification Report

| ID | Feature | Class | Controls / flags |
|----|---------|-------|------------------|
| F1 | Sage dialog + direction | LIVE | needs complete local model |
| F2 | Hive + joint beneficence | LIVE | CLI `we *` |
| F3 | Propellant ledger | LIVE | `--max-grok` |
| F4 | WattOS report | LIVE | `--wattos` / default on supervise |
| F5 | Sentinel policy on FS effects | LIVE | protected paths e.g. `.env` |
| F6 | Superintendant PTY | LIVE | child cmd; dry-run scripts exist |
| F7 | Grok escalation | HYBRID | `XAI_API_KEY`, `--grok/--no-grok`; offline returns review fallback |
| F8 | Nex TUI chat/tools | LIVE | tools real |
| F9 | Nex TUI approval queue | **SYNTH** | always-on fake decision on tool parse |
| F10 | Nex TUI a/b/o | **PURE DEMO** | UI log only |
| F11 | OpenAI server | LIVE | `[server]` extra |
| F12 | MCP | LIVE | |
| F13 | Trace gallery | LIVE | empty without sessions |
| F14 | README screenshots | **PURE DEMO** | placeholders |
| F15 | Showpieces | LIVE DEMO | real asserts |
| F16 | Hardware watts | DEAD/ORPHAN claim | explicitly not implemented |
| F17 | Full multi-agent hive runtime | DEAD/ORPHAN (never claimed as done) | docs non-claim |

**Counts (feature-level):** pure_demo=3 · synth=1 · live=11 · hybrid=1 · dead=2  

---

## 8. Drift Report

| Drift | Evidence |
|-------|----------|
| Product rename incomplete | README MLX-SAGE; pyproject “Nex — Multi-model CLI…”; CLI help still Nex-N2 OptiQ |
| ARCHITECTURE_MERGE “gaps” partially outdated | Many Sentinel items now present; doc still reads pre-merge |
| “Sentinel+policy active” in general TUI | String only; chat path not under ContinuousEnforcer |
| Approval queue “made live” language in PROGRESS | Construction live; **policy authority not live** |
| Screenshot readiness language | Placeholders still present |

Duplication: two TUIs (sage vs nex) — intentional dual surface, not abandoned fork.

---

## 9. Risk Register & Mitigations

| Risk | Impact | Likelihood | Evidence | Mitigation | Quick verify |
|------|--------|------------|----------|------------|--------------|
| Synthetic TUI approvals | Trust collapse | High | `tui.py:266-271` | Only enqueue after `policy.evaluate`; wire enforcer | grep `fake_dec` gone |
| a/b/o no-op on tools | Safety theater | High | `_handle_pending` | Block tool exec until approve | try tool without approve |
| No CI | Silent break | High | no `.github` | pytest workflow | PR red on fail |
| No LICENSE | Legal ambiguity | Med | missing file | add MIT | file exists |
| Identity split | Diligence fail | Med | README vs pyproject | align messaging | same story in both |
| Grok fallback misread | False safety | Med | escalator unavailable dict | surface “not escalated” in all UIs | run without key |
| Untested server/MCP | Runtime fail | Med | no tests | TestClient smokes | pytest new |
| Plugin side-load | Surprise tools | Low | import prints | lazy load / flag | `nex --help` quiet |

---

## 10. Demo Script + Committee Q&A Cards

### 10–15 min honest demo

1. `pytest tests/ -q` → 22 pass  
2. `python -m nex.cli sage models` → READY filter  
3. (if model) `sage tui` one real reply  
4. `we constitution` + `we start` ego-fail vs purpose-pass (or unit tests)  
5. `python scripts/wattos_superintendant_demo.py --max-grok 0 --no-grok` → BLOCK on `.env`, WattOS  
6. **Explicitly show** Nex TUI approval is illustrative (open `tui.py` fake_dec) — committee honesty  
7. `nex serve` `/health` if deps installed  

### Q&A cards

| Q | A |
|---|---|
| What is live? | Sage FS+MLX, hive gate, policy/enforcer, propellant, WattOS, serve/mcp/agent |
| What is synth? | Nex TUI pending queue decisions |
| What breaks if removed? | Removing fake_dec improves honesty; chat still works |
| Next to productionize supervise UX | Real policy→queue→gate tool/PTY; CI; LICENSE |
| Watt meters? | Not claimed |

---

## Proof Ledger (selected)

**Claim:** Writing `.env` under observed workspace BLOCKs.  
**Evidence:** Live smoke this session — `FileEffectObserver.diff` + `SentinelPolicy.evaluate` → `PolicyAction.BLOCK Effect touches protected path: .env`.  
**Confidence:** high  
**Unknowns:** none for unit path  

**Claim:** Nex TUI approvals are real Sentinel decisions.  
**Evidence:** Contradicted by `fake_fx`/`fake_dec` at `nex/tui.py:266-268`; no `policy.evaluate` call.  
**Confidence:** high (as SYNTH)  
**Unknowns:** whether any other path enqueues real decisions (grep shows this construction site)

**Claim:** Joint beneficence is real logic.  
**Evidence:** `tests/test_joint_beneficence.py` 6/6; `mission.evaluate_joint_beneficence`.  
**Confidence:** high  

**Claim:** Live Grok API works in this environment.  
**Evidence:** not exercised this session.  
**Confidence:** unknown  
**Confirm:** set `XAI_API_KEY`, run escalate once, check `escalated: true`.

---

```json
{
  "mode": "forensics",
  "components_total": 17,
  "classification": {
    "pure_demo": 3,
    "synth": 1,
    "live": 11,
    "hybrid": 1,
    "dead": 2
  },
  "top_risks": [
    "TUI synthetic PendingApproval (fake_dec)",
    "a/b/o UI-only no enforcer coupling",
    "no CI",
    "no LICENSE",
    "product identity split",
    "Grok fallback can be misread",
    "server/MCP untested",
    "plugin auto-load",
    "screenshot placeholders",
    "MLX/XAI machine-local proof not re-run"
  ],
  "committee_hot_seats": [
    "Is the approvals pane real policy?",
    "Does approve/block stop tools?",
    "Is WattOS measuring watts?",
    "Is Grok always reviewing?",
    "Can we ship supervise as production?"
  ],
  "confidence": "high",
  "artifact": "Forensics_2026-08-07.md"
}
```
