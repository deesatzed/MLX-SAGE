# MLX-SAGE

**A personal sage partner on your Mac** — local AI for purpose, people, and direction.  
One command. Guided setup. Private by default.

```bash
pip install -e ".[tui]"
export PYTHONPATH=.
nex          # or: nex start · nex main
```

**Landing page:** [docs/index.html](docs/index.html) (open in a browser)

---

## What is it for?

MLX-SAGE is for people who want AI as a **partner in a meaningful life**, not only as a homework machine or a code factory.

| You might want it if… | What you get |
|----------------------|--------------|
| You’re tired of chats that forget who you are | A **living profile**: people who matter, commitments, direction on disk |
| You care about privacy for personal topics | **Local MLX** models on Apple Silicon when available |
| Work title is fading (or never was the point) | A north star built from **your** people and acts — not corporate OKRs |
| You still build software alone | Optional **Rails**: supervise coding agents with real policy + end reports |
| You refuse “AI girlfriend / god / servant” | Explicit **partner** stance — honest role, joint beneficence |

**Not for:** generic cloud chat only, romantic companion sims, “AI will live your life for you.”

---

## Why it’s unique

Most AI products optimize **answers**. MLX-SAGE optimizes **mattering + continuity**.

| Typical AI app | MLX-SAGE |
|----------------|----------|
| Session evaporates | Profile + direction **persist** under `sessions/sage/` |
| You adapt to the product | **One app** guides model → who matters → one commit → talk |
| Cloud-first by default | **Local-first** partner voice; cloud Grok only for optional agent rails |
| “Do my work” | “Who needs me? What did I promise? What’s my north star?” |
| Safety theater | Real policy gates on Rails (e.g. protected paths); no fake approval UI |
| Meaning as marketing | **Joint beneficence**: you + honest AI role + shared/third-party good |

**Two modes, clear split**

| Mode | Command | Role |
|------|---------|------|
| **Partner** | `nex` | Life direction, people, talk — **the product** |
| **Rails** | `nex supervise`, `nex agent` | Coding agents + optional XAI Grok — **not** sage voice |

---

## Why you would want it

1. **Continuity after the job (or beside it)** — Identity isn’t only “what I shipped.” The app keeps *who you care about* and *what you said you’d do*.
2. **Privacy for the real stuff** — Family, purpose, doubt: better on your machine than in a random SaaS log.
3. **Low ceremony** — `nex` opens one Partner app. It walks empty states. No command cookbook to memorize.
4. **Adult agent hygiene (optional)** — When you use coding agents, Superintendant can enforce policy, cap remote Grok burns, and print a real WattOS-style end report.
5. **You own the stack** — Python, MIT, local files, no platform team required.

---

## How it works (happy path)

```text
nex
  → finds a READY local model (or tells you once how to get one)
  → if needed: “Who matters?” (one name)
  → if needed: “One small thing this week?”
  → talk  |  sidebar shows living direction
```

| In the app | What happens |
|------------|----------------|
| Type a name (first run) | Saved as someone who matters |
| Type a weekly act | Saved as a commitment |
| Normal sentences | Local sage dialogue |
| `person Jordan friend` | Add another person |
| `commit Walk tomorrow` | Add a commitment |
| Ctrl+Q | Leave (optional one-line reflection) |
| F5 | Rescan for a local model |

Data lives in `sessions/sage/<profile>/` (gitignored).

---

## Visual tour

See the **[landing page](docs/index.html)** for full UI mockups of:

1. First-run: who matters  
2. Partner chat + living direction sidebar  
3. Optional Rails / WattOS end report  

*(Mockups are accurate product illustrations of the real TUI layout.)*

---

## Models (Partner voice)

Local weights only for Partner chat. Fluid — you pick the model.

```bash
nex sage models                 # READY complete folders only
nex models recommend "chat" --max-memory 16
nex models download <alias-or-repo>
```

Place full mlx-lm dirs under e.g. `~/.mtplx/models/` (`config.json` + real weights).

---

## Optional Rails (builders)

```bash
nex supervise --help
# XAI_API_KEY in .env for propellant-capped Grok on hard reviews
```

Design notes: `docs/plans/2026-08-04-superintendant-wattos-design.md`.

---

## Project layout

```text
nex/
  sage/          # Partner app, dialog, profile, local models
  hive/          # co-goal cells + joint beneficence
  sentinel/      # policy, PTY, enforcer (Rails)
  superintend.py · wattos.py · propellant.py
  engine.py · cli.py · server.py · mcp.py
docs/
  index.html     # landing page
  plans/ · sessions/
tests/
```

Package: **`nex-cli`** · console: **`nex`** · license: **MIT**

---

## Development

```bash
pip install -e ".[tui,dev,server]"
export PYTHONPATH=.
python -m pytest tests/ -q
```

Python ≥3.11 · Apple Silicon recommended for MLX · CI: `.github/workflows/ci.yml`

---

## Mission background

- `docs/sessions/2026-08-04-destination-anti-disposability-brainstorm.md`
- `docs/sessions/2026-08-04-personal-sage-partner-options.md`
- `docs/sessions/2026-08-04-research-what-helps-human-meaning.md`

---

## Name

**MLX-SAGE** — sage partner on MLX.  
Python package remains `nex` for continuity; product focus is partnership.
