# Design: Superintendant + WattOS (v1)

**Date:** 2026-08-04  
**Track:** H (human product strategy only — no SI claims)  
**Status:** Frozen after brainstorm §1–§3 approval  
**Approach:** A — Thin wrapper first  
**Codebase:** `OptiqMTPMLX` (Nex / Grokkasclate)

---

## 1. One-liner

Wrap the agents you already use; deterministic Sentinel gates effects; Grok only when policy escalates and propellant remains; every session ends with a real efficiency + safety report (WattOS).

---

## 2. Goal

A Mac developer runs their normal agent (`claude` / `codex` or supervised child) under Superintendant and gets:

1. Real effect gating (block / review / allow) on FS and command effects  
2. Selective Grok only when policy escalates and propellant remains  
3. A WattOS report with real counters  

### Non-goals (v1)

- Multi-Mac fleet  
- Full wiki/RAG product  
- Osaurus UI completion  
- Replacing Claude/Codex  
- Mock or simulated policy/Grok numbers  
- “Production ready” claim  
- True hardware watt meters (brand = efficiency proof; v1 metrics are propellant + counters + wall time + local tok when available)

---

## 3. Success criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| S1 | Supervise path runs against a real command or dry harness with real observer | Scripted demo exit 0 |
| S2 | At least one block or review fires on a known-risky effect | Visible in report |
| S3 | Grok path calls real API (key present) or records skip with reason (no key) — never fake verdicts | Log + report |
| S4 | WattOS panel shows numbers from actual counters, not placeholders | Code path from oversight/ledger |
| S5 | Propellant: configurable max Grok escalations; further escalations denied per policy | Config + test |
| S6 | `--install` (or documented aliases) still works for daily-driver wrap | Real run |

---

## 4. Architecture

### 4.1 Shape

```
Human shell / aliases (nex supervise --install)
        │
        ▼
SUPERINTENDANT (nex supervise | grok-claude | grok-codex)
  PTY runner → Effect observer → SentinelPolicy.evaluate
        │
        ├─ ALLOW
        ├─ BLOCK  → count + deny
        └─ REVIEW → human and/or Grok
                        │
              PropellantLedger.can_burn?
                yes → burn → GrokEscalator (real API)
                no  → propellant_denied → human_or_block (default)
        │
        ▼
WattOS counters → SessionOversight / WattOSReport → end panel (always in finally)
```

Optional parallel path: `nex agent` / chat may emit the same report shape if low-risk; not required for S1–S6.

### 4.2 Components

| Component | Status | Role |
|-----------|--------|------|
| PtyAgentRunner | exists | Child agent under PTY |
| FileEffectObserver / ContinuousEnforcer | exists | Real FS signals |
| SentinelPolicy | exists | Deterministic ALLOW/BLOCK/REVIEW |
| GrokEscalator | exists | Real xAI or no-key skip |
| SessionOversight | exists | Base counters |
| PropellantLedger | **add** | Cap Grok burns |
| WattOSReport | **add** | Canonical end panel |
| supervise + grok-* wiring | **extend** | Ledger + always report |

No new daemon. No new package. Stay in `nex/` + `scripts/`.

### 4.3 Effect flow

1. Child attempts effect.  
2. Observer builds FileEffect / CommandEffect.  
3. Policy evaluates → counters update.  
4. REVIEW + grok mode: ledger gate before API.  
5. Never invent Grok verdict without API success.  
6. `finally`: WattOSReport.render.

---

## 5. Propellant rules (v1)

| Rule | Spec |
|------|------|
| Unit | 1 burn = 1 Grok escalation call |
| Default cap | `max_grok_escalations = 3` per session |
| When counted | On successful request **start** (network not sent → no burn) |
| Refund | Only if client never sent (no key / short-circuit) |
| Local MLX | Does not consume propellant |
| Display | `used/max` + remaining on panel |
| Exhaustion | `on_propellant_empty`: `human_or_block` (default) \| `block` \| `allow_local_only` |

Optional later: `$` estimate via `GROK_USD_PER_CALL` env — labeled estimate only.

---

## 6. WattOS report fields (v1)

| Field | Source | If unavailable |
|-------|--------|----------------|
| wall_time_s | timer | always |
| policy_decisions | counter | 0 |
| blocks / reviews | counters | 0 |
| grok_escalations | counter | 0 |
| propellant_used / propellant_max | ledger | always |
| propellant_denied | ledger | 0 |
| local_generation_tokens | GenerationStats if local engine ran | **n/a** with reason (not fake 0) |
| avg_generation_tps | same | **n/a** |
| note | factual template | fixed |

**Honesty:** Pure Claude wrap → `local_generation_tokens: n/a (child agent, not local MLX)`.

**Brand note:** “WattOS” means efficiency proof. v1 does not claim hardware joules without a measured source.

---

## 7. CLI / config

```text
nex supervise -- <cmd>
  --max-grok N
  --grok / --no-grok
  --on-empty human_or_block|block|allow_local_only
  --wattos / --no-wattos   # default on

grok-claude / grok-codex
  same flags where applicable
```

Env: `XAI_API_KEY` (existing). Optional `GROK_USD_PER_CALL`.

---

## 8. Errors and edges

| Case | Behavior |
|------|----------|
| No API key | Grok skipped with reason; policy still runs |
| Grok HTTP error | If request sent, burn counts; fallback human if TTY else BLOCK |
| Propellant empty | on_empty policy; propellant_denied++ |
| Child non-zero exit | Report still prints; exit code preserved |
| Ctrl-C | finally report; partial counters OK |
| No TTY | REVIEW without Grok → BLOCK |
| --max-grok 0 | All burns denied (demo for propellant_denied) |

**Forbidden:** mock Grok, placeholder stats, silent policy failure.

---

## 9. File-level change list

| Path | Action |
|------|--------|
| `nex/propellant.py` | New — PropellantLedger |
| `nex/wattos.py` | New — WattOSReport + render |
| `nex/engine.py` | Align SessionOversight docs with WattOS |
| `nex/cli.py` | supervise flags, ledger, finally WattOS |
| `nex/agent.py` | Optional same report |
| `nex/grok_escalator.py` | Clear no-key / error outcomes |
| `scripts/grok_claude.py` | Flags + WattOS end |
| `scripts/grok_codex.py` | Symmetry |
| `scripts/wattos_superintendant_demo.py` (or extend showpiece) | Real S1–S6 demo |
| `PROGRESS.md`, `DECISIONS.md` | Decision + evidence |
| `README.md` | Honest Superintendant + WattOS section |

**Out of v1:** optQlab, mlx-rag, omlxurus (cross-link only).

---

## 10. Verification plan

| ID | Check | Pass rule |
|----|--------|-----------|
| V1 | Ledger unit | burn to max; next denied |
| V2 | WattOS n/a path | n/a reason present; not fake 0 tok |
| V3 | supervise --help | flags visible |
| V4 | Demo script | exit 0; panel printed |
| V5 | Policy fire | decisions > 0 on real temp FS touch |
| V6 | --max-grok 0 | propellant_denied ≥ 1 |
| V7 | No key | skip reason; no crash |
| V8 | With key (optional) | escalations ≥ 1 or truthful API failure |
| V9 | --install | hooks / alias text |

Any check &lt; 100% → action plan in PROGRESS; no “done” claim.

---

## 11. Implementation order

1. PropellantLedger + self-check  
2. WattOSReport render (n/a honesty)  
3. Wire cli.supervise  
4. Wire grok-claude / grok-codex  
5. Demo script V4–V6  
6. Docs + PROGRESS evidence  
7. Optional agent path  

Validate each step before the next. No mocks.

---

## 12. Risks

| Risk | Mitigation |
|------|------------|
| WattOS overclaims watts | README lists v1 metrics explicitly |
| Claude not installed | Demo uses controlled child under PTY |
| Grok flaky | V8 optional; V6–V7 required |
| Scope creep | Freeze Lab/RAG/fleet until demo green |

---

## 13. Approval record

| Section | Decision |
|---------|----------|
| Role / stage context | H-track product after portfolio inventory + brainstorm |
| §1 Goal / success | Approved |
| Approach A (thin wrapper) | Approved |
| §2 Architecture / propellant / WattOS fields | Approved |
| §3 Errors / files / verification | Approved |
| Design doc written | 2026-08-04 |

---

## 14. Next step after this doc

- **Implementation plan** (task breakdown with verification gates), then code — or  
- **Implement directly** following §11 order  

Do not claim complete until V1–V7 (and V9 if install touched) pass with evidence in PROGRESS.md.
