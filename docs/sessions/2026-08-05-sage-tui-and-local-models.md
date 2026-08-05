# Sage TUI + local model probe (2026-08-05)

## Interface
- **TUI** via Textual: `python -m nex.cli sage tui`
- Conversational, profile-aware system prompt (partnership / purpose / mattering)
- Ctrl+D direction · Ctrl+E export · Ctrl+N new chat thread · Ctrl+Q quit

## Local models found on this machine

| Status | Model | Size | Path |
|--------|-------|------|------|
| **READY** | Llama-3.2-3B-Instruct-4bit (mlx) | 1.7 GB | `~/.mtplx/models/mlx-community--Llama-3.2-3B-Instruct-4bit` |
| incomplete | Qwen3.6-27B-MLX-4bit-MTP | ~0 | HF hub stub only |
| incomplete | Qwen3.6-35B-A3B-MLX-MTP-4bit | ~0 | HF hub stub only |
| incomplete | SynLogic-Mix-3-32B OptiQ | ~0 | HF hub stub only |
| empty dirs | Mistral-7B, TinyLlama under mlx-manager | 0 | no weights |
| not chat | all-MiniLM-L6-v2 | 0.17 GB | embeddings |

## Probe result
- Loaded Llama-3.2-3B with mlx_lm successfully.
- Real sage turn generated coherent partner reply referencing emptiness + Sam context.

## Note on “top tier”
3B is what is fully present locally. For frontier-class dialogue quality, download a larger mlx chat quant (or use a remote API later — user selects model). TUI accepts `-m /path/to/model`.
