# Assumption Registry — MLX-SAGE (list)

**Date:** 2026-08-07  
**Storage:** `.governance/assumptions.json`  
**Mode:** `governance --mode=assumptions` (list + seed)

| Metric | Count |
|--------|------:|
| **Total** | 15 |
| **Unvalidated** | 5 (⚠️ RISK) |
| **Validated** | 7 |
| **Invalidated** | 3 |
| **Stale (>30d)** | 0 |

---

## High-Risk Unvalidated

| ID | Text | Source | Verify |
|----|------|--------|--------|
| A-0011 | `sessions/` / sage chat may hold PII and must stay gitignored / uncommitted | `.gitignore`, sage paths | Confirm ignore rules + no tracked chat.jsonl |
| A-0005 | Serve/MCP are single-user localhost trust (no auth) | `server.py` | Threat model + bind review |
| *(none other HIGH unvalidated)* | | | |

> Note: A-0014 was high-risk but **invalidated** (tests are not release proxy). A-0004 high-risk **invalidated** (TUI approvals not real policy).

## Medium-Risk Unvalidated

| ID | Text | Verify |
|----|------|--------|
| A-0002 | Apple Silicon + mlx-lm required for generation | Fail path on unsupported host |
| A-0013 | OpenAI server tool_calls passthrough production-complete | E2E client with tools |
| A-0015 | Models fluid/pluggable without code release | `models add` + download unknown READY |

## High-Risk Invalidated (must not re-assume)

| ID | False assumption | Contradicting evidence |
|----|------------------|------------------------|
| **A-0004** | TUI approval queue = real SentinelPolicy | `fake_dec` at `nex/tui.py:266-268`; forensics SYNTH |
| **A-0010** | Package identity is still Nex-only multi-model | README/destination = Sage-first product |
| **A-0014** | 22 unit tests = release readiness | server/mcp/agent/PTY/TUI under-tested |

## Validated (keep)

| ID | Text | Evidence |
|----|------|----------|
| A-0001 | Complete local weights required | dialog + local_models complete filter |
| A-0003 | No key → Grok unavailable fallback | grok_escalator.py |
| A-0006 | Joint beneficence constitution real | pytest 6 tests |
| A-0007 | WattOS honesty (n/a not 0 watts) | test_wattos |
| A-0008 | Policy BLOCK on `.env` | live smoke 2026-08-07 |
| A-0009 | Propellant max=0 denies | test_propellant |
| A-0012 | Hive is record+gate not multi-agent runtime | code + PROGRESS non-claim |

---

## Lifecycle notes

- New entries defaulted carefully: only validated when code/tests/smoke prove them this session.
- Invalidated entries stay in registry so future agents do not re-assert them.
- Review cadence: re-run `stale` after 30 days from `last_reviewed_at`.

```json
{
  "mode": "assumptions",
  "subcommand": "list",
  "total": 15,
  "unvalidated": 5,
  "validated": 7,
  "invalidated": 3,
  "stale": 0,
  "storage": ".governance/assumptions.json"
}
```
