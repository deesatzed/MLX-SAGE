# MLX-SAGE

**Personal sage partner on Apple Silicon** — conversational TUI, living direction, human–AI partnership.

MLX-SAGE helps you find and live **purpose and meaning with AI**, not under it: partnership, healthy “hive” roles, joint beneficence, and a direction shaped by *your* people and commitments.

```bash
pip install -e ".[tui]"
export PYTHONPATH=.

# What models are already on this machine?
python -m nex.cli sage models

# Talk with your sage partner (local MLX)
python -m nex.cli sage tui
```

---

## What it is

| Surface | Purpose |
|---------|---------|
| **`nex sage tui`** | Seamless dialogue with a local MLX model + your memory |
| **Living direction** | `direction.md` built from your people, sits, commits, reflections |
| **Hive cell (`nex we`)** | Co-goal + roles + joint beneficence + receipt |
| **Superintendant** | Optional rails: supervise agents, propellant-capped Grok, WattOS report |
| **Local multi-model Nex** | Chat, agent, serve, models registry for mlx-lm / OptiQ |

**Stance**

- AI progression continues; the failure mode is **purposeless leftover life**, not “machines exist.”
- Partner, not servant / god / romantic companion.
- Meaning and contentment track **contribution and mattering** more than ego status.
- Joint beneficence: advance **you**, the **partner role’s integrity**, and **shared / third-party good**.

---

## Quick start — Sage Partner

```bash
cd MLX-SAGE   # or this repo root
python -m venv .venv && source .venv/bin/activate
pip install -e ".[tui]"

export PYTHONPATH=.
python -m nex.cli sage models
python -m nex.cli sage tui
```

**In the TUI**

| Key | Action |
|-----|--------|
| Type + Enter | Talk |
| Ctrl+D | Show / refresh direction |
| Ctrl+E | Export shareable pack |
| Ctrl+N | New chat thread (keeps profile) |
| Ctrl+Q | Quit |

Optional structured helpers:

```bash
python -m nex.cli sage init
python -m nex.cli sage people add --name Sam --relation sibling \
  --they-need-me "monthly call" --i-need "family continuity"
python -m nex.cli sage direction
python -m nex.cli sage export
```

Profile & direction live under `sessions/sage/<profile>/` (gitignored runtime data).

---

## Models (fluid — you pick)

Models change weekly. Sage treats them as **pluggable local weights**.

### See what’s ready on disk

```bash
python -m nex.cli sage models
```

Only **complete** folders (config + real safetensors) show as READY.

### Run with a specific model

```bash
python -m nex.cli sage tui -m /path/to/mlx-model-folder
```

### Download a new MLX model

Catalog of known OptiQ / mlx-lm repos:

```bash
python -m nex.cli models list
python -m nex.cli models recommend "chat reasoning" --max-memory 16
python -m nex.cli models download qwen3.5-4b
# or full Hugging Face id:
python -m nex.cli models download mlx-community/Qwen3.5-4B-OptiQ-4bit
```

Add a brand-new repo not in the catalog:

```bash
python -m nex.cli models add org/Some-New-MLX-4bit
python -m nex.cli models download org/Some-New-MLX-4bit
```

Then point TUI at the printed path, or re-run `sage models` after the download finishes.

### Manual install

Place a full mlx-lm model directory under e.g. `~/.mtplx/models/Your-Model-4bit/`  
(must include `config.json` and weight files). It will appear as READY if complete.

**Note:** Incomplete HF cache stubs (tiny folders without weights) will not load. Larger models need free unified memory on Apple Silicon.

---

## Superintendant (agent rails)

Wrap daily coding agents under policy + optional Grok budget + WattOS end report:

```bash
python -m nex.cli supervise --help
python -m nex.cli supervise --install   # shell alias hints for grok-claude / grok-codex
```

See `docs/plans/2026-08-04-superintendant-wattos-design.md`.

---

## Project layout

```text
nex/
  sage/          # partner, dialog, TUI, local model discovery
  hive/          # co-goal cells + joint beneficence
  mission.py     # constitution + joint beneficence evaluator
  superintend.py # supervised agent sessions
  wattos.py      # efficiency / oversight report
  propellant.py  # Grok burn ledger
  engine.py      # mlx-lm runtime
  cli.py         # nex entrypoint
docs/
  plans/         # Superintendant design + implementation plan
  sessions/      # mission / sage design notes
tests/           # unit tests (beneficence, hive, sage)
scripts/         # demos
```

Package name in Python: **`nex-cli`** (`pip install -e .`). Console entry: `nex`.

---

## Development

```bash
pip install -e ".[tui,dev]"
# optional: OpenAI server smoke tests need the server extra
pip install -e ".[tui,dev,server]"
export PYTHONPATH=.
python -m pytest tests/ -q
```

Requires: Python 3.11+, Apple Silicon recommended for MLX, `mlx-lm`, Textual (TUI extra).

CI runs unit tests on push/PR (see `.github/workflows/ci.yml`).

---

## Screenshots & recordings

**None published yet.** Do not treat landing-page “suggested shots” as existing media.
When you capture real asciinema/screenshots, link them here and in `docs/index.html`.

---

## Mission docs

- `docs/sessions/2026-08-04-destination-anti-disposability-brainstorm.md` — destination / partnership / hive  
- `docs/sessions/2026-08-04-personal-sage-partner-options.md` — Protocol Sage choice  
- `docs/sessions/2026-08-04-research-what-helps-human-meaning.md` — meaning research notes  
- `docs/sessions/2026-08-05-sage-tui-and-local-models.md` — TUI + local model probe  

---

## License

MIT — see [`LICENSE`](LICENSE).

---

## Name

**MLX-SAGE** — Sage partner on MLX.  
Code package remains `nex` for continuity; product focus is the sage partnership surface.
