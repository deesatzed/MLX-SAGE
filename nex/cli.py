"""Typer CLI for the Nex standalone app.

Enhanced with:
- Default conversation persistence (sessions/ + auto-resume)
- JSONL logging
- Agent mode with safe tools (list_dir, read/write/run_python/shell)
- MCP server launcher (`nex mcp`)
- Better UX and loading feedback
"""

from __future__ import annotations

from typing import Optional

import typer
from rich.prompt import Prompt

from .envload import ensure_env_loaded

ensure_env_loaded()  # XAI_API_KEY etc. from project .env (never committed)

from . import DEFAULT_MODEL
from .agent import run_agent
from .engine import Engine
from .models import (
    KNOWN_MODELS,
    get_default_model,
    get_profile,
    list_profiles,
    suggest_similar,
)
from .config import (
    add_user_model,
    get_config_path,
    get_user_models,
    load_config,
    set_default_model as cfg_set_default,
    set_model_override,
    get_all_overrides,
)

import shutil
import subprocess
import sys
from .persistence import (
    SessionRecord,
    get_latest_session,
    list_sessions,
    load_session,
    log_turn,
    new_session_id,
    save_session,
)
from .render import (
    ThinkAwareStreamer,
    console,
    print_assistant_header,
    print_error,
    print_info,
    print_user_prompt,
    print_welcome,
)
from .session import ChatSession

app = typer.Typer(
    name="nex",
    help=(
        "MLX-SAGE — Sage-first on Apple Silicon.\n\n"
        "[Partner] `nex home` / `nex sage` · `nex sage tui` · `nex sage coach`\n"
        "[Rails]   `nex supervise` · `nex agent` · optional Grok (XAI) — not your sage voice.\n"
        "Also: chat, models, serve, MCP (local multi-model substrate)."
    ),
    add_completion=False,
    rich_markup_mode="rich",
)


def _resolve_model(model: Optional[str]) -> str:
    """Resolve user-provided model string (alias, partial, repo, or None) to a real repo id."""
    if model is None or model.strip() == "":
        return get_default_model()
    profile = get_profile(model)
    return profile.repo_id


def _get_engine(
    model: Optional[str] = None,
    enable_mtp: bool = False,
    draft_model: Optional[str] = None,
    num_draft_tokens: int = 3,
) -> Engine:
    resolved = _resolve_model(model)
    profile = get_profile(resolved)

    # Resolve draft for MTP
    final_draft = draft_model
    if enable_mtp and not final_draft:
        if profile and profile.supports_mtp and profile.mtp_repo_id:
            final_draft = profile.mtp_repo_id
        elif profile and profile.mtp_repo_id:
            final_draft = profile.mtp_repo_id

    eng = Engine(
        model_id=resolved,
        draft_model_id=final_draft,
        num_draft_tokens=num_draft_tokens,
    )
    return eng


# ------------------------------------------------------------------
# Main / default
# ------------------------------------------------------------------

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    model: str = typer.Option(
        None,
        "--model",
        "-m",
        help="HF repo, alias (qwen9b, gemma12b, nemotron, nex, ...), or local path. See `nex models list`.",
    ),
    max_tokens: int = typer.Option(1024, "--max-tokens", "-n"),
    temperature: float = typer.Option(0.7, "--temperature", "-t"),
    top_p: float = typer.Option(0.95, "--top-p"),
    system: Optional[str] = typer.Option(None, "--system", "-s"),
    no_stream: bool = typer.Option(False, "--no-stream"),
    session: Optional[str] = typer.Option(None, "--session", help="Named session to resume or create"),
    resume: bool = typer.Option(False, "--resume", help="Resume the most recent session"),
    no_persist: bool = typer.Option(False, "--no-persist", help="Do not save/load session history"),
    enable_mtp: bool = typer.Option(False, "--enable-mtp", "--mtp", help="Enable MTP / speculative decoding (Multi-Token Prediction) for ~1.3-1.5x faster generation when supported."),
    draft_model: Optional[str] = typer.Option(None, "--draft-model", help="Explicit MTP draft model repo id (e.g. the -MTP variant)."),
    num_draft_tokens: int = typer.Option(3, "--num-draft-tokens", help="Number of draft tokens for MTP speculative decoding."),
):
    """Default action is interactive chat (with smart session persistence)."""
    if ctx.invoked_subcommand is None:
        chat(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            system=system,
            no_stream=no_stream,
            session=session,
            resume=resume,
            no_persist=no_persist,
            enable_mtp=enable_mtp,
            draft_model=draft_model,
            num_draft_tokens=num_draft_tokens,
        )


# ------------------------------------------------------------------
# chat
# ------------------------------------------------------------------

@app.command()
def chat(
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    max_tokens: int = typer.Option(1024, "--max-tokens", "-n"),
    temperature: float = typer.Option(0.7, "--temperature", "-t"),
    top_p: float = typer.Option(0.95, "--top-p"),
    system: Optional[str] = typer.Option(None, "--system", "-s"),
    no_stream: bool = typer.Option(False, "--no-stream"),
    session: Optional[str] = typer.Option(None, "--session", help="Named session id"),
    resume: bool = typer.Option(False, "--resume", help="Auto-resume latest session"),
    no_persist: bool = typer.Option(False, "--no-persist"),
    enable_mtp: bool = typer.Option(False, "--enable-mtp", "--mtp"),
    draft_model: Optional[str] = typer.Option(None, "--draft-model"),
    num_draft_tokens: int = typer.Option(3, "--num-draft-tokens"),
):
    """Interactive multi-turn chat (persisted by default)."""
    engine = _get_engine(model, enable_mtp, draft_model, num_draft_tokens)

    # Resolve session
    rec: Optional[SessionRecord] = None
    sid = session

    if resume and not sid:
        rec = get_latest_session()
        if rec:
            sid = rec.session_id
            print_info(f"Resuming latest session: {sid}")

    if sid:
        rec = load_session(sid) or SessionRecord(session_id=sid, model=model)

    if rec is None:
        sid = new_session_id("chat")
        rec = SessionRecord(session_id=sid, model=model)

    # Apply incoming system if provided
    if system:
        rec.system_prompt = system

    # Create runtime ChatSession
    chat_session = ChatSession(
        engine=engine,
        system_prompt=rec.system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
    )
    # Seed history if we loaded one
    if rec.messages:
        chat_session.messages = list(rec.messages)

    resolved_model = _resolve_model(model)
    profile = get_profile(resolved_model)
    mtp_note = " + MTP" if (enable_mtp or draft_model) else ""
    print_welcome(f"{profile.name}{mtp_note} ({resolved_model})")
    console.print(f"[dim]Session:[/dim] [bold]{sid}[/bold]  [dim](persisted: {not no_persist})[/dim]")
    if enable_mtp or draft_model:
        console.print("[dim]MTP / speculative decoding enabled[/dim]")
    if rec.system_prompt:
        print_info(f"System: {rec.system_prompt[:90]}{'...' if len(rec.system_prompt) > 90 else ''}")

    streamer = ThinkAwareStreamer(show_thinking=True)

    try:
        while True:
            try:
                user_input = print_user_prompt()
            except (EOFError, KeyboardInterrupt):
                if not no_persist:
                    rec.messages = chat_session.messages
                    save_session(rec)
                console.print("\n[dim]Goodbye. Session saved.[/dim]")
                break

            if not user_input or not user_input.strip():
                continue

            cmd = user_input.strip()
            if cmd.startswith("/"):
                handled = _handle_command(cmd, chat_session, engine, rec, no_persist)
                if handled == "quit":
                    break
                continue

            # Normal turn
            chat_session.add_user(cmd)

            # Log user
            log_turn(session_id=sid, model=model, role="user", content=cmd)

            print_assistant_header()

            if no_stream:
                response = chat_session.generate_once()
                streamer = ThinkAwareStreamer(show_thinking=True)
                streamer.feed(response)
                streamer.flush()
                console.print()
                if chat_session.last_stats:
                    print_info(f"stats: {chat_session.last_stats.generation_tokens} tok @ {chat_session.last_stats.generation_tps:.1f} t/s")
            else:
                parts = []
                for chunk, stats in chat_session.generate_stream():
                    if chunk:
                        parts.append(chunk)
                        streamer.feed(chunk)
                streamer.flush()
                console.print()
                assistant_text = "".join(parts)
                chat_session.add_assistant(assistant_text)

                log_turn(
                    session_id=sid,
                    model=model,
                    role="assistant",
                    content=assistant_text,
                    stats=chat_session.last_stats.__dict__ if chat_session.last_stats else None,
                )

                if chat_session.last_stats:
                    print_info(
                        f"{chat_session.last_stats.generation_tokens} tokens @ "
                        f"{chat_session.last_stats.generation_tps:.1f} t/s | peak {chat_session.last_stats.peak_memory_gb:.1f} GB"
                    )

            # Persist after every turn unless disabled
            if not no_persist:
                rec.messages = chat_session.messages
                rec.system_prompt = chat_session.system_prompt
                rec.params.update({
                    "temperature": chat_session.temperature,
                    "top_p": chat_session.top_p,
                    "max_tokens": chat_session.max_tokens,
                })
                save_session(rec)

    except KeyboardInterrupt:
        if not no_persist:
            rec.messages = chat_session.messages
            save_session(rec)
        console.print("\n[dim]Interrupted. Session saved.[/dim]")


def _handle_command(
    cmd: str,
    session: ChatSession,
    engine: Engine,
    rec: SessionRecord,
    no_persist: bool,
) -> Optional[str]:
    parts = cmd.split(maxsplit=1)
    verb = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if verb in ("/quit", "/exit", "/q"):
        if not no_persist:
            rec.messages = session.messages
            save_session(rec)
        return "quit"

    if verb == "/help":
        console.print(
            "\n[bold]Chat commands[/bold]\n"
            "  /help                 This help\n"
            "  /clear                Clear current conversation (in-memory)\n"
            "  /system <text>        Set system prompt for this session\n"
            "  /temp <float>         Change temperature\n"
            "  /maxtokens <int>      Change max new tokens\n"
            "  /stats                Last generation stats\n"
            "  /save [file]          Export current history to JSON\n"
            "  /load <file>          Import history from JSON (in-memory)\n"
            "  /sessions             List recent persisted sessions\n"
            "  /resume [id]          Switch to another session (or latest)\n"
            "  /quit                 Exit (session is auto-saved)\n"
        )
        return None

    if verb == "/clear":
        session.reset()
        print_info("In-memory history cleared (persisted copy unchanged until next turn).")
        return None

    if verb == "/system":
        if arg:
            session.set_system(arg)
            rec.system_prompt = session.system_prompt
            print_info("System prompt updated for this session.")
        else:
            print_info(f"Current system: {session.system_prompt or '(none)'}")
        return None

    if verb == "/temp":
        try:
            session.temperature = float(arg)
            print_info(f"Temperature = {session.temperature}")
        except ValueError:
            print_error("Usage: /temp 0.3")
        return None

    if verb == "/maxtokens":
        try:
            session.max_tokens = int(arg)
            print_info(f"max_tokens = {session.max_tokens}")
        except ValueError:
            print_error("Usage: /maxtokens 2048")
        return None

    if verb == "/stats":
        if session.last_stats:
            s = session.last_stats
            print_info(f"prompt={s.prompt_tokens} gen={s.generation_tokens} tps={s.generation_tps} mem={s.peak_memory_gb}GB")
        else:
            print_info("No stats yet.")
        return None

    if verb == "/save":
        import json
        from pathlib import Path

        fname = arg.strip() or f"{rec.session_id}.json"
        data = {
            "session_id": rec.session_id,
            "system": session.system_prompt,
            "messages": session.messages,
            "params": rec.params,
        }
        Path(fname).write_text(json.dumps(data, indent=2))
        print_info(f"Exported to {fname}")
        return None

    if verb == "/load":
        import json
        from pathlib import Path

        fname = arg.strip()
        if not fname:
            print_error("Usage: /load path/to/file.json")
            return None
        try:
            data = json.loads(Path(fname).read_text())
            session.messages = data.get("messages", [])
            session.system_prompt = data.get("system")
            print_info(f"Loaded {len(session.messages)} messages into current session (not yet persisted).")
        except Exception as e:
            print_error(str(e))
        return None

    if verb == "/sessions":
        recs = list_sessions(12)
        if not recs:
            print_info("No persisted sessions yet.")
        else:
            for r in recs:
                print_info(f"  {r.session_id}  ({len(r.messages)} msgs)  updated {r.updated_at[:16]}")
        return None

    if verb == "/resume":
        target = arg.strip() or None
        if target:
            loaded = load_session(target)
            if loaded:
                session.messages = loaded.messages
                session.system_prompt = loaded.system_prompt
                rec.session_id = loaded.session_id
                rec.messages = loaded.messages
                rec.system_prompt = loaded.system_prompt
                print_info(f"Switched to session {target}")
            else:
                print_error(f"Session not found: {target}")
        else:
            latest = get_latest_session()
            if latest:
                session.messages = latest.messages
                session.system_prompt = latest.system_prompt
                rec.session_id = latest.session_id
                print_info(f"Resumed latest: {latest.session_id}")
            else:
                print_info("No previous session.")
        return None

    print_error(f"Unknown command '{verb}'. Type /help.")
    return None


# ------------------------------------------------------------------
# ask (one-shot, still useful)
# ------------------------------------------------------------------

@app.command()
def ask(
    prompt: str = typer.Argument(..., help="Prompt to send"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    max_tokens: int = typer.Option(1024, "--max-tokens", "-n"),
    temperature: float = typer.Option(0.7, "--temperature", "-t"),
    top_p: float = typer.Option(0.95, "--top-p"),
    system: Optional[str] = typer.Option(None, "--system", "-s"),
    no_stream: bool = typer.Option(False, "--no-stream"),
    show_thinking: bool = typer.Option(True, "--show-thinking/--hide-thinking"),
    enable_mtp: bool = typer.Option(False, "--enable-mtp", "--mtp"),
    draft_model: Optional[str] = typer.Option(None, "--draft-model"),
    num_draft_tokens: int = typer.Option(3, "--num-draft-tokens"),
):
    """One-shot non-interactive generation."""
    engine = _get_engine(model, enable_mtp, draft_model, num_draft_tokens)
    chat_session = ChatSession(engine=engine, system_prompt=system, max_tokens=max_tokens,
                               temperature=temperature, top_p=top_p)
    chat_session.add_user(prompt)

    streamer = ThinkAwareStreamer(show_thinking=show_thinking)
    print_assistant_header()

    if no_stream:
        text = chat_session.generate_once()
        streamer.feed(text)
        streamer.flush()
        console.print()
    else:
        parts = []
        for chunk, stats in chat_session.generate_stream():
            if chunk:
                parts.append(chunk)
                streamer.feed(chunk)
        streamer.flush()
        console.print()
        full = "".join(parts)
        chat_session.add_assistant(full)

    if chat_session.last_stats:
        print_info(f"{chat_session.last_stats.generation_tokens} tok @ {chat_session.last_stats.generation_tps:.1f} t/s")


# ------------------------------------------------------------------
# agent — autonomous tool-using loop
# ------------------------------------------------------------------

@app.command()
def agent(
    goal: str = typer.Argument(..., help="High-level goal for the autonomous agent (e.g. 'build and test a small CLI tool in the sandbox')"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    max_steps: int = typer.Option(10, "--max-steps", help="Safety cap on tool-using steps"),
    temperature: float = typer.Option(0.4, "--temperature", "-t"),
    session: Optional[str] = typer.Option(None, "--session"),
    enable_mtp: bool = typer.Option(False, "--enable-mtp", "--mtp"),
    draft_model: Optional[str] = typer.Option(None, "--draft-model"),
    num_draft_tokens: int = typer.Option(3, "--num-draft-tokens"),
):
    """Run an autonomous agent that can use safe tools (read/write files, run Python, limited shell) inside ./sandbox/."""
    engine = _get_engine(model, enable_mtp, draft_model, num_draft_tokens)
    run_agent(
        goal=goal,
        engine=engine,
        max_steps=max_steps,
        temperature=temperature,
        session_id=session,
        persist=True,
    )


# ------------------------------------------------------------------
# mcp — launch the MCP server for other AIs
# ------------------------------------------------------------------

@app.command()
def mcp(
    host: str = typer.Option("stdio", help="Transport (currently only stdio supported)"),
):
    """Start the MCP server so Claude / Cursor / other MCP clients can call this model."""
    from .mcp import run_server

    console.print("[bold cyan]Starting Nex MCP server (stdio)...[/bold cyan]")
    console.print("[dim]Other AIs can now discover tools: nex_ask, nex_chat_turn, nex_run_agent, etc.[/dim]")
    run_server()


@app.command()
def tui(
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    enable_mtp: bool = typer.Option(False, "--enable-mtp", "--mtp"),
):
    """Launch the modern Textual TUI (aesthetically SOTA terminal UI)."""
    from .tui import run_tui

    # For a full version we would pass model/mtp into the TUI app.
    # The TUI currently starts with the default / last used model and has live switching.
    console.print("[bold cyan]Launching Nex Textual TUI...[/bold cyan]")
    console.print("[dim]Ctrl+Q to quit • Ctrl+M to focus model list • Ctrl+T to toggle MTP[/dim]")
    run_tui()


@app.command()
def serve(
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on"),
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind to"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    enable_mtp: bool = typer.Option(False, "--enable-mtp", "--mtp"),
    draft_model: Optional[str] = typer.Option(None, "--draft-model"),
    num_draft_tokens: int = typer.Option(3, "--num-draft-tokens"),
):
    """Start an OpenAI-compatible HTTP server (FastAPI + Uvicorn).

    This lets any tool that speaks the OpenAI API (Cursor, Continue.dev, Aider, custom agents, etc.)
    use your local high-quality OptiQ models with full MTP support.
    """
    import uvicorn

    # Pre-load the engine so the first request is fast and shows the nice loading UX
    if model or enable_mtp:
        from .cli import _get_engine  # reuse our smart engine factory

        _get_engine(model, enable_mtp, draft_model, num_draft_tokens)

    console.print(f"[bold cyan]Starting Nex OpenAI-compatible server on http://{host}:{port}[/bold cyan]")
    console.print("[dim]Endpoints: /v1/chat/completions, /v1/models, /health[/dim]")
    console.print("[dim]Use --model qwen9b --enable-mtp etc. (same flags as other commands)[/dim]")

    uvicorn.run(
        "nex.server:app",
        host=host,
        port=port,
        reload=False,
    )


# ------------------------------------------------------------------
# Utility commands
# ------------------------------------------------------------------

@app.command()
def sessions(limit: int = typer.Option(15, "--limit")):
    """List recent persisted sessions."""
    recs = list_sessions(limit=limit)
    if not recs:
        print_info("No sessions found in ./sessions/")
        return
    for r in recs:
        print_info(f"{r.session_id} | msgs={len(r.messages)} | {r.updated_at[:19]}")


@app.command()
def resume(session_id: Optional[str] = typer.Argument(None)):
    """Resume a specific session (or the latest) in chat mode."""
    chat(resume=True, session=session_id)


# =============================================================================
# models — the heart of the multi-model expansion
# =============================================================================

models_app = typer.Typer(
    name="models",
    help="Manage and discover MLX + OptiQ models (Qwen, Gemma, Nemotron, Nex, etc.)",
    add_completion=False,
)
app.add_typer(models_app, name="models")


@models_app.command("list")
def models_list(
    family: Optional[str] = typer.Option(None, "--family", "-f", help="Filter by family (qwen, gemma, nemotron, nex, minicpm, other)"),
    size: Optional[str] = typer.Option(None, "--size", "-s", help="Filter by size_class (tiny, small, medium, large)"),
    strength: Optional[str] = typer.Option(None, "--strength", help="Must have this strength (coding, tool_use, reasoning, speed)"),
):
    """List known high-quality OptiQ and similar MLX models."""
    profiles = list_profiles(family=family, size_class=size, min_strength=strength)

    # Merge user-added models
    user_repos = get_user_models()
    for repo in user_repos:
        p = get_profile(repo)
        if p.repo_id not in [pp.repo_id for pp in profiles]:
            profiles.append(p)

    if not profiles:
        print_error("No models matched the filters.")
        return

    console.print(f"\n[bold]Known OptiQ / MLX Models[/bold] ({len(profiles)} shown)\n")

    for p in profiles:
        strengths = ", ".join(p.strengths) if p.strengths else "-"
        alias_str = f"  aliases: {', '.join(p.aliases)}" if p.aliases else ""
        console.print(
            f"[bold cyan]{p.name}[/bold cyan]  ({p.family} · {p.size_class} · {p.params})\n"
            f"  repo: [dim]{p.repo_id}[/dim]\n"
            f"  strengths: {strengths}\n"
            f"  default temp: {p.recommended_temperature}   max_tokens: {p.recommended_max_tokens}{alias_str}\n"
        )
        if p.notes:
            console.print(f"  [dim]{p.notes}[/dim]\n")


@models_app.command("info")
def models_info(model: str = typer.Argument(..., help="Model key, alias, or partial name (e.g. qwen9b, gemma, nemotron)")):
    """Show detailed profile for one model + suggestions."""
    profile = get_profile(model)
    console.print(f"\n[bold cyan]{profile.name}[/bold cyan]")
    console.print(f"Repository: [link=https://huggingface.co/{profile.repo_id}]{profile.repo_id}[/link]")
    console.print(f"Family: {profile.family}   Size: {profile.size_class}   Params: {profile.params}")
    console.print(f"Strengths: {', '.join(profile.strengths) or 'general'}")
    console.print(f"Recommended: temperature={profile.recommended_temperature}, max_tokens={profile.recommended_max_tokens}")
    if profile.notes:
        console.print(f"\n{profile.notes}")

    suggestions = suggest_similar(profile.repo_id)
    if suggestions:
        console.print("\n[bold]Similar / recommended alternatives:[/bold]")
        for s in suggestions:
            console.print(f"  • {s.name}  ({s.repo_id})")


@models_app.command("set-default")
def models_set_default(model: str = typer.Argument(..., help="Model to use as default (key or alias)")):
    """Persistently set default model (saved in config)."""
    profile = get_profile(model)
    cfg_set_default(model)
    console.print(f"[green]Default model set to[/green] [bold cyan]{profile.name}[/bold cyan] ({profile.repo_id})")


@models_app.command("add")
def models_add(repo: str = typer.Argument(..., help="Full HF repo id of an additional MLX/OptiQ model to remember")):
    """Add a custom or new OptiQ-style model to your personal list (persisted in config)."""
    add_user_model(repo)
    profile = get_profile(repo)
    console.print(f"[green]Added[/green] [bold]{profile.name}[/bold] ({repo}) to user models.")
    console.print("It will now appear in suggestions and can be used with --model or aliases.")


@models_app.command("download")
def models_download(model: str = typer.Argument(..., help="Model alias or repo to download")):
    """Download a model (uses huggingface_hub with resume support)."""
    from .models import download_model
    path = download_model(model)
    console.print(f"[green]Ready to use:[/green] {path}")


@models_app.command("recommend")
def models_recommend(
    query: str = typer.Argument("coding tool use", help="What are you looking for? (e.g. 'fast coding')"),
    max_memory: Optional[float] = typer.Option(None, "--max-memory", help="Maximum unified memory in GB"),
):
    """Recommend models based on your needs."""
    from .models import recommend_models
    recs = recommend_models(query, max_memory_gb=max_memory)
    if not recs:
        print_error("No good matches. Try a broader query.")
        return
    console.print(f"\n[bold]Recommendations for '{query}'[/bold]\n")
    for p in recs:
        mem = f"{p.approx_memory_gb}GB" if hasattr(p, "approx_memory_gb") and p.approx_memory_gb else "?"
        console.print(f"  [cyan]{p.name}[/cyan]  ({p.repo_id})  memory≈{mem}")
        console.print(f"    strengths: {', '.join(p.strengths)}")


@models_app.command("set-override")
def models_set_override(
    model: str = typer.Argument(..., help="Model alias or repo"),
    key: str = typer.Argument(..., help="Override key (temperature, max_tokens, enable_mtp, etc.)"),
    value: str = typer.Argument(..., help="Value (will be parsed as float/bool if possible)"),
):
    """Persist a per-model override."""
    # Parse value
    parsed = value
    if value.lower() in ("true", "false"):
        parsed = value.lower() == "true"
    else:
        try:
            parsed = float(value) if "." in value else int(value)
        except ValueError:
            pass
    set_model_override(model, key, parsed)
    console.print(f"[green]Set override[/green] {key}={parsed} for {get_profile(model).name}")


@app.command()
def search(query: str = typer.Argument(..., help="Semantic search over your chat history")):
    """Search past conversations (requires `pip install -e '.[rag]'`)."""
    from .history_rag import search_history
    results = search_history(query)
    if not results:
        print_info("No results or RAG extra not installed.")
        return
    for r in results:
        console.print(f"[dim]{r.get('session_id')} / {r.get('role')}[/dim]")
        console.print(r.get("content", "")[:400])
        console.print("---")


@app.command("trace")
def trace_replay(
    trace_file: str = typer.Argument(..., help="Path to .jsonl trace"),
    format: str = typer.Option("text", "--format", help="text or json"),
):
    """Unified trace viewer (Nex + gemOptq-style traces, shows Grok escalations)."""
    from .sentinel.trace_viewer import replay_trace
    events = replay_trace(trace_file, format=format)
    if format == "json":
        import json as _json
        console.print_json(_json.dumps(events, indent=2))


@app.command("trace-gallery")
def trace_gallery(
    sessions: str = typer.Option("sessions", "--sessions"),
    logs: str = typer.Option("logs", "--logs"),
    out: str | None = typer.Option(None, "--out", "-o", help="Write to file (e.g. gallery.md)"),
    redact: bool = typer.Option(True, "--redact/--no-redact"),
):
    """Public redacted trace gallery (shareable audit artifact for teams, compliance, demos).
    Scans real sessions/logs for grok/policy/efficiency evidence. Directly addresses
    'auditability for real work' and 'shareable proof without leaking IP' needs.
    """
    from .sentinel.trace_viewer import export_gallery
    export_gallery(sessions_dir=sessions, logs_dir=logs, out=out, redact=redact)


@app.command()
def supervise(  # [Rails] Superintendant — not Partner sage voice
    agent: str = typer.Argument(None, help="Agent to supervise: claude, codex, or custom command (optional with --install)"),
    workspace: str = typer.Option(".", "--workspace", "-w", help="Workspace dir (use temp for safety)"),
    grok_in_loop: bool = typer.Option(False, "--grok-in-loop", help="Deprecated synonym for --grok; enable Grok escalation"),
    use_grok: bool = typer.Option(True, "--grok/--no-grok", help="Allow Grok escalation on REVIEW when API key present"),
    max_grok: int = typer.Option(3, "--max-grok", help="Propellant: max Grok escalations this session"),
    on_empty: str = typer.Option(
        "human_or_block",
        "--on-empty",
        help="When propellant empty on REVIEW: human_or_block | block | allow_local_only",
    ),
    wattos: bool = typer.Option(True, "--wattos/--no-wattos", help="Print WattOS end report"),
    install: bool = typer.Option(False, "--install", help="One-command setup: install aliases/hooks so your daily claude/codex always use Grok-in-the-Loop (needs-based permanent adoption)"),
):
    """
    [Rails] Superintendant: supervise real external AI coding agents under Sentinel policy,
    propellant-capped Grok escalation, and WattOS end report.
    Grok is for hard agent decisions — not your Partner sage voice (`nex sage tui`).

    Examples:
      nex supervise claude .
      nex supervise codex --workspace /tmp/safe-test --grok --max-grok 3
      nex supervise --install
    """
    import tempfile

    if install:
        from pathlib import Path
        home = Path.home()
        grok_dir = home / ".grok"
        grok_dir.mkdir(parents=True, exist_ok=True)
        hooks_src = Path(__file__).resolve().parents[1] / ".grok" / "hooks"
        if hooks_src.exists():
            (grok_dir / "hooks").mkdir(exist_ok=True)
            for h in hooks_src.glob("*"):
                (grok_dir / "hooks" / h.name).write_text(h.read_text())
        alias_block = """
# Grok-in-the-Loop supervision (added by `nex supervise --install`)
# Use your daily drivers under full policy + Grok + traces. No workflow change.
alias claude='grok-claude'
alias codex='grok-codex'
# For Cursor/Aider/etc point OPENAI_BASE_URL or use `nex serve` + policy layer
"""
        print("\n=== One-command setup for permanent supervision ===")
        print("Add this to your ~/.zshrc or ~/.bashrc (or run the lines):")
        print(alias_block)
        print(f"Hooks copied to {grok_dir}/hooks (pre-effect etc. for .claude/.codex flows).")
        print("Then: source ~/.zshrc ; claude .   # now supervised by default")
        print("To revert: remove the alias lines.")
        print("This directly fulfills the top unmet need: keep the powerful agents you already use, just make them safe/auditable/Grok-augmented.")
        return

    if agent is None:
        console.print("[red]Provide an agent (claude, codex, or a command) or use --install[/red]")
        raise typer.Exit(1)

    if agent not in ("claude", "codex"):
        console.print(f"[yellow]Custom agent supervision: {agent}. Using PTY + policy + Grok.[/yellow]")

    effective_grok = bool(use_grok or grok_in_loop)

    if workspace == ".":
        workspace = tempfile.mkdtemp(prefix="grok-supervise-")
        console.print(f"[dim]Using disposable workspace: {workspace}[/dim]")

    cmd_map = {
        "claude": f"claude {workspace}",
        "codex": f"codex {workspace}",
    }
    cmd = cmd_map.get(agent, agent)

    from .superintend import run_supervised_session

    code = run_supervised_session(
        cmd=cmd,
        workspace=workspace,
        agent_label=str(agent),
        max_grok=max_grok,
        use_grok=effective_grok,
        on_empty=on_empty,
        wattos=wattos,
        trust_agent=agent if agent in ("claude", "codex") else None,
    )
    if code != 0:
        raise typer.Exit(code)


# ------------------------------------------------------------------
# home — partnership status (UX Rec 1)
# ------------------------------------------------------------------


@app.command("home")
def home_cmd(
    profile: str = typer.Option("default", "--profile", "-p"),
):
    """[Partner] Partnership home — north star, people, commits, model & Grok status."""
    from .sage.home import build_home_snapshot, render_coach_text, render_home_text

    snap = build_home_snapshot(profile)
    console.print(render_home_text(snap))
    if snap.needs_coach:
        console.print("\n[yellow]Tip:[/yellow] run [bold]nex sage coach[/bold] for first-run steps.\n")


# ------------------------------------------------------------------
# sage — Protocol Sage Partner (personal partnership protocol)
# ------------------------------------------------------------------

sage_app = typer.Typer(
    name="sage",
    help=(
        "[Partner] Protocol Sage — purpose partnership (local MLX), not a companion sim. "
        "Default: partnership home. Rails/Grok live under supervise/agent."
    ),
    add_completion=False,
    invoke_without_command=True,
)
app.add_typer(sage_app, name="sage")


@sage_app.callback(invoke_without_command=True)
def sage_root(
    ctx: typer.Context,
    profile: str = typer.Option("default", "--profile", "-p"),
):
    """Partnership home when no subcommand is given (UX Rec 1)."""
    if ctx.invoked_subcommand is not None:
        return
    from .sage.home import build_home_snapshot, render_home_text

    snap = build_home_snapshot(profile)
    console.print(render_home_text(snap))
    if snap.needs_coach:
        console.print("\n[yellow]Tip:[/yellow] run [bold]nex sage coach[/bold] for first-run steps.\n")


@sage_app.command("coach")
def sage_coach(
    profile: str = typer.Option("default", "--profile", "-p"),
):
    """[Partner] First-run coach — local model + thin profile only (no Rails tour)."""
    from .sage.home import build_home_snapshot, render_coach_text

    snap = build_home_snapshot(profile)
    console.print(render_coach_text(snap))


@sage_app.command("tui")
def sage_tui(
    profile: str = typer.Option("default", "--profile", "-p"),
    model: str = typer.Option(
        "",
        "--model",
        "-m",
        help="Local model path (default: first complete MLX model found)",
    ),
    skip_coach: bool = typer.Option(
        False,
        "--skip-coach",
        help="Do not print first-run coach when model missing",
    ),
):
    """[Partner] Conversational Sage TUI — local model + your memory."""
    from .sage.tui import run_sage_tui
    from .sage.dialog import list_models_report
    from .sage.local_models import pick_default_local
    from .sage.home import build_home_snapshot, render_coach_text

    if not model:
        m = pick_default_local()
        if not m:
            console.print("[red]No complete local MLX chat model found.[/red]")
            if not skip_coach:
                snap = build_home_snapshot(profile)
                console.print(render_coach_text(snap))
            else:
                console.print(list_models_report())
            raise typer.Exit(1)
        console.print(f"[dim]Using local model: {m.label} ({m.size_gb} GB) · Partner mode[/dim]")
        model = m.path
    run_sage_tui(profile_id=profile, model_path=model or None)


@sage_app.command("models")
def sage_models():
    """List local MLX models discovered on this machine."""
    from .sage.dialog import list_models_report

    console.print(list_models_report())


@sage_app.command("init")
def sage_init(
    profile: str = typer.Option("default", "--profile", "-p"),
    values: str = typer.Option(
        "contribution and mattering over status display",
        "--values",
    ),
    orientation: str = typer.Option(
        "beyond isolated ego — purpose with partners in a small hive",
        "--orientation",
        "-o",
    ),
):
    """Create or show a standing sage partner profile."""
    from .sage.partner import load_or_create_profile, REFUSALS
    from rich.panel import Panel

    prof = load_or_create_profile(profile, values_note=values, orientation=orientation)
    # refresh values if re-init
    prof.values_note = values
    prof.orientation = orientation
    path = prof.save()
    console.print(Panel(prof.sage_role, title=f"Sage partner [{prof.profile_id}]", border_style="cyan"))
    console.print(f"[dim]values:[/dim] {prof.values_note}")
    console.print(f"[dim]orientation:[/dim] {prof.orientation}")
    console.print("[dim]refusals:[/dim]")
    for r in REFUSALS:
        console.print(f"  • {r}")
    console.print(f"[dim]profile:[/dim] {path}")


@sage_app.command("people")
def sage_people(
    action: str = typer.Argument("list", help="list | add"),
    name: str = typer.Option("", "--name"),
    relation: str = typer.Option("", "--relation"),
    need_me: str = typer.Option("", "--they-need-me", help="they may need me for"),
    i_need: str = typer.Option("", "--i-need", help="I need them for"),
    profile: str = typer.Option("default", "--profile", "-p"),
):
    """Mattering map — real humans; updates your direction."""
    from .sage.partner import PersonStub, load_or_create_profile
    from rich.panel import Panel
    from rich.table import Table

    prof = load_or_create_profile(profile)
    if action == "add":
        if not name or not relation:
            console.print("[red]--name and --relation required for add[/red]")
            raise typer.Exit(2)
        dpath = prof.add_person(
            PersonStub(
                name=name,
                relation=relation,
                they_may_need_me_for=need_me,
                i_need_them_for=i_need,
            )
        )
        d = prof.build_direction()
        console.print(f"[green]Person on map[/green] {name} ({relation})")
        console.print(Panel(d.get("north_star", ""), title="Your direction (updated)", border_style="cyan"))
        console.print(f"[dim]direction → {dpath}[/dim]")
        return
    table = Table(title=f"People (mattering) — {prof.profile_id}")
    table.add_column("Name")
    table.add_column("Relation")
    table.add_column("They may need me")
    table.add_column("I need them")
    for person in prof.people:
        table.add_row(
            person.name,
            person.relation,
            person.they_may_need_me_for,
            person.i_need_them_for,
        )
    console.print(table)
    if not prof.people:
        console.print("[dim]Add: nex sage people add --name … --relation … --they-need-me … --i-need …[/dim]")


@sage_app.command("sit")
def sage_sit(
    situation: str = typer.Argument(..., help="What you are holding right now"),
    co_goal: str = typer.Option(..., "--co-goal", "-g", help="Shared co-goal for this turn"),
    human: str = typer.Option("advanced", "--human"),
    ai: str = typer.Option("neutral", "--ai"),
    shared: str = typer.Option("advanced", "--shared"),
    mode: str = typer.Option("default", "--mode"),
    notes: str = typer.Option("", "--notes"),
    reflection: str = typer.Option("", "--reflect", "-r", help="Your answer — shapes direction"),
    profile: str = typer.Option("default", "--profile", "-p"),
    require_pass: bool = typer.Option(True, "--require-pass/--allow-fail"),
):
    """Partnership turn → joint beneficence → prompts → living direction."""
    from .sage.partner import load_or_create_profile
    from rich.panel import Panel

    prof = load_or_create_profile(profile)
    entry = prof.sit(
        situation,
        co_goal=co_goal,
        human_effect=human,
        ai_effect=ai,
        shared_effect=shared,
        mode=mode,
        notes=notes,
        reflection=reflection,
    )
    style = "green" if entry["ok"] else "red"
    console.print(Panel(entry["beneficence"]["summary"], border_style=style, title="Joint beneficence"))
    console.print("[bold]Partnership prompts:[/bold]")
    for i, q in enumerate(entry["counsel_prompts"], 1):
        console.print(f"  {i}. {q}")
    direction = entry.get("direction") or {}
    if direction.get("north_star"):
        console.print(Panel(direction["north_star"], title="Your direction", border_style="cyan"))
        acts = direction.get("next_acts") or direction.get("suggested_moves") or []
        if acts:
            console.print("[bold]Next acts[/bold]")
            for a in acts[:5]:
                console.print(f"  • {a}")
    console.print(f"[dim]sit={entry['sit_id']} · {entry.get('direction_path')}[/dim]")
    if require_pass and not entry["ok"]:
        raise typer.Exit(2)


@sage_app.command("reflect")
def sage_reflect(
    text: str = typer.Argument(..., help="What you take from the last sit / life"),
    profile: str = typer.Option("default", "--profile", "-p"),
):
    """Add your words to the living direction."""
    from .sage.partner import load_or_create_profile
    from rich.panel import Panel

    prof = load_or_create_profile(profile)
    sits = [s for s in prof.sit_log if s.get("sit_id")]
    sit_id = sits[-1]["sit_id"] if sits else ""
    dpath = prof.add_reflection(text, sit_id=sit_id)
    d = prof.build_direction()
    console.print(Panel(d.get("north_star", ""), title="Your direction", border_style="cyan"))
    console.print(f"[dim]direction → {dpath}[/dim]")


@sage_app.command("commit")
def sage_commit(
    text: str = typer.Argument(..., help="Concrete act you own"),
    toward: str = typer.Option(..., "--toward", "-t", help="Real person name or shared_good"),
    due: str = typer.Option("", "--due"),
    profile: str = typer.Option("default", "--profile", "-p"),
):
    """Record a commitment; refresh direction."""
    from .sage.partner import Commitment, load_or_create_profile
    from rich.panel import Panel

    prof = load_or_create_profile(profile)
    dpath = prof.add_commitment(Commitment(text=text, toward_person=toward, due=due))
    d = prof.build_direction()
    console.print(f"[green]Commitment[/green] toward {toward}: {text}")
    console.print(Panel(d.get("north_star", ""), title="Your direction", border_style="cyan"))
    console.print(f"[dim]direction → {dpath}[/dim]")


@sage_app.command("done")
def sage_done(
    match: str = typer.Argument(..., help="Substring of commitment text, person, or id"),
    profile: str = typer.Option("default", "--profile", "-p"),
):
    """Mark a commitment complete; refresh direction."""
    from .sage.partner import load_or_create_profile
    from rich.panel import Panel

    prof = load_or_create_profile(profile)
    c = prof.complete_commitment(match=match)
    if not c:
        console.print(f"[red]No open commitment matching[/red] {match!r}")
        raise typer.Exit(2)
    d = prof.build_direction()
    console.print(f"[green]Done[/green] {c.text} → {c.toward_person}")
    console.print(Panel(d.get("north_star", ""), title="Your direction", border_style="cyan"))


@sage_app.command("receipt")
def sage_receipt(
    profile: str = typer.Option("default", "--profile", "-p"),
    last: int = typer.Option(3, "--last", help="How many sits to show"),
):
    """Show profile, recent sits, open commitments, and current north star."""
    from .sage.partner import load_or_create_profile
    import json
    from rich.panel import Panel

    prof = load_or_create_profile(profile)
    open_c = [c for c in prof.commitments if not c.done]
    recent = [s for s in prof.sit_log if s.get("sit_id")][-last:]
    d = prof.build_direction()
    console.print(Panel(prof.sage_role, title=f"Sage partner [{prof.profile_id}]", border_style="cyan"))
    console.print(Panel(d.get("north_star", ""), title="North star", border_style="green"))
    console.print(f"people: {len(prof.people)} | open commitments: {len(open_c)} | sits: {len([s for s in prof.sit_log if s.get('sit_id')])}")
    console.print(f"values: {prof.values_note}")
    if recent:
        console.print("[bold]Recent sits[/bold]")
        for s in recent:
            flag = "ok" if s.get("ok") else "redirect"
            console.print(f"  [{flag}] {s.get('co_goal')}")
    if open_c:
        console.print("[bold]Open commitments[/bold]")
        for c in open_c:
            console.print(f"  • [{c.toward_person}] {c.text}" + (f" (due {c.due})" if c.due else ""))


@sage_app.command("direction")
def sage_direction(
    profile: str = typer.Option("default", "--profile", "-p"),
    show: bool = typer.Option(True, "--show/--no-show", help="Print markdown to terminal"),
):
    """Build and show personalized direction from your people, sits, and commits."""
    from .sage.partner import load_or_create_profile, render_direction_markdown
    from rich.markdown import Markdown

    prof = load_or_create_profile(profile)
    path = prof.write_direction()
    md = render_direction_markdown(prof.build_direction())
    if show:
        try:
            console.print(Markdown(md))
        except Exception:
            console.print(md)
    console.print(f"[green]Direction[/green] → {path}")


@sage_app.command("export")
def sage_export(
    profile: str = typer.Option("default", "--profile", "-p"),
    show: bool = typer.Option(True, "--show/--no-show"),
):
    """Export a shareable pack (direction + people + commits + recent sits)."""
    from .sage.partner import load_or_create_profile
    from rich.markdown import Markdown

    prof = load_or_create_profile(profile)
    path = prof.export_pack()
    if show:
        try:
            console.print(Markdown(path.read_text(encoding="utf-8")))
        except Exception:
            console.print(path.read_text(encoding="utf-8"))
    console.print(f"[green]Export pack[/green] → {path.parent}")


# ------------------------------------------------------------------
# we — hive cell partnership (mission: purpose with AI)
# ------------------------------------------------------------------

we_app = typer.Typer(
    name="we",
    help="Hive cell: human–AI partnership session with co-goal, roles, joint beneficence, receipt",
    add_completion=False,
)
app.add_typer(we_app, name="we")


@we_app.command("constitution")
def we_constitution():
    """Print the mission constitution (partnership, hive, selfless, joint beneficence)."""
    from .mission import print_constitution
    print_constitution(console)


@we_app.command("start")
def we_start(
    co_goal: str = typer.Argument(..., help="Shared co-goal for this hive cell"),
    orientation: str = typer.Option(
        "beyond isolated ego — contribution to shared good",
        "--orientation",
        "-o",
        help="Self-transcendent orientation note",
    ),
    human: str = typer.Option("advanced", "--human", help="Beneficence: advanced|neutral|harmed"),
    ai: str = typer.Option("neutral", "--ai", help="Beneficence for AI partner role"),
    shared: str = typer.Option("advanced", "--shared", help="Beneficence for shared/third good"),
    mode: str = typer.Option("default", "--mode", help="default|strict joint beneficence"),
    notes: str = typer.Option("", "--notes", help="Why these effects"),
    require_pass: bool = typer.Option(
        True,
        "--require-pass/--allow-fail",
        help="Exit non-zero if joint beneficence fails",
    ),
):
    """Start a hive cell: roles + joint beneficence gate + save receipt."""
    from .hive.cell import create_cell
    from .mission import print_constitution
    from rich.panel import Panel
    from rich.table import Table

    print_constitution(console)
    cell = create_cell(co_goal, orientation=orientation)
    result = cell.set_beneficence(
        human=human,
        ai_partner=ai,
        shared_or_third=shared,
        mode=mode,
        notes=notes or None,
    )
    cell.log_contribution("human", "declared co-goal and orientation", co_goal)
    cell.log_contribution("ai", "role reserved: assist within limits", cell.roles[1].responsibility)
    path = cell.save()

    table = Table(title=f"Hive cell {cell.cell_id}", show_header=True)
    table.add_column("Party")
    table.add_column("Name")
    table.add_column("Needed for")
    for r in cell.roles:
        table.add_row(r.party, r.name, r.needed_for)
    console.print(table)
    style = "green" if result.ok else "red"
    console.print(Panel(result.summary + "\n" + "\n".join(result.reasons), border_style=style, title="Joint beneficence"))
    console.print(f"[dim]Receipt:[/dim] {path}")
    console.print(f"[dim]Co-goal:[/dim] {cell.co_goal}")
    if require_pass and not result.ok:
        raise typer.Exit(2)


@we_app.command("check")
def we_check(
    human: str = typer.Option(..., "--human"),
    ai: str = typer.Option(..., "--ai"),
    shared: str = typer.Option(..., "--shared"),
    mode: str = typer.Option("default", "--mode"),
    notes: str = typer.Option("", "--notes"),
):
    """Evaluate joint beneficence without creating a cell."""
    from .mission import evaluate_joint_beneficence
    from rich.panel import Panel

    r = evaluate_joint_beneficence(
        human=human,
        ai_partner=ai,
        shared_or_third=shared,
        mode=mode,
        notes=notes or None,
    )
    style = "green" if r.ok else "red"
    console.print(Panel(r.summary + "\n" + "\n".join(r.reasons), border_style=style, title="Joint beneficence"))
    if not r.ok:
        raise typer.Exit(2)


@we_app.command("receipt")
def we_receipt(
    cell_id: str = typer.Argument(..., help="Cell id (hive-… )"),
):
    """Print a saved hive cell receipt."""
    from .hive.cell import load_cell
    import json
    cell = load_cell(cell_id)
    console.print_json(json.dumps(cell.receipt(), indent=2))


# ------------------------------------------------------------------
# self — self management, updates, doctor (uv + classic support)
# ------------------------------------------------------------------

self_app = typer.Typer(
    name="self",
    help="Manage the Nex installation, dependencies, and updates (uv-aware)",
    add_completion=False,
)
app.add_typer(self_app, name="self")


def _run_update_command(cmd: list[str], use_uv: bool = False) -> bool:
    """Run an update command, preferring uv when available."""
    try:
        if use_uv and shutil.which("uv"):
            full_cmd = ["uv"] + cmd
        else:
            full_cmd = cmd
        console.print(f"[dim]Running:[/dim] {' '.join(full_cmd)}")
        subprocess.check_call(full_cmd)
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Update command failed: {e}")
        return False
    except FileNotFoundError:
        print_error("Required tool not found (uv or pip).")
        return False


@self_app.command("update")
def self_update(
    deps_only: bool = typer.Option(False, "--deps-only", help="Only update dependencies, not the app itself."),
    force_pip: bool = typer.Option(False, "--force-pip", help="Force classic pip even if uv is available."),
):
    """Update Nex and its dependencies (fast with uv if present)."""
    use_uv = not force_pip and bool(shutil.which("uv"))

    console.print("[bold]Updating Nex + core dependencies...[/bold]")

    if use_uv:
        success = _run_update_command(["pip", "install", "-U", "-e", ".[tui]"], use_uv=True)
    else:
        # Classic path
        success = _run_update_command([sys.executable, "-m", "pip", "install", "-U", "-e", ".[tui]"])

    if success:
        console.print("[green]Update complete![/green]")
        console.print("Run [bold]nex --help[/bold] or [bold]nex self status[/bold] to verify.")
    else:
        console.print("[yellow]Update may have partially succeeded. Check above for errors.[/yellow]")


@self_app.command("update-deps")
def self_update_deps(force_pip: bool = typer.Option(False, "--force-pip")):
    """Update only the Python dependencies (mlx-lm, textual, typer, mcp, etc.)."""
    use_uv = not force_pip and bool(shutil.which("uv"))
    console.print("[bold]Updating dependencies only...[/bold]")

    if use_uv:
        _run_update_command(["pip", "install", "-U", "mlx-lm", "rich", "typer", "mcp", "textual"], use_uv=True)
    else:
        _run_update_command([sys.executable, "-m", "pip", "install", "-U", "mlx-lm", "rich", "typer", "mcp", "textual"])

    console.print("[green]Dependencies updated.[/green]")


@self_app.command("status")
def self_status():
    """Show current installation status, Python, uv/pip, and key package versions."""
    console.print("[bold]Nex Self Status[/bold]\n")

    console.print(f"Python: [cyan]{sys.version.split()[0]}[/cyan] ({sys.executable})")
    uv_path = shutil.which("uv")
    console.print(f"uv: {'[green]available[/green] ' + uv_path if uv_path else '[yellow]not found[/yellow] (install from https://astral.sh/uv)'}")

    try:
        import importlib.metadata as im
        for pkg in ["nex-cli", "mlx-lm", "textual", "typer", "mcp", "rich"]:
            try:
                ver = im.version(pkg.replace("-", "_"))
                console.print(f"  {pkg}: {ver}")
            except im.PackageNotFoundError:
                console.print(f"  {pkg}: [dim]not installed[/dim]")
    except Exception as e:
        print_error(f"Could not read package versions: {e}")

    try:
        cfg = load_config()
        console.print(f"\nConfig file: {get_config_path()}")
        if cfg.get("default_model"):
            console.print(f"Default model (from config): {cfg['default_model']}")
        user_models = get_user_models()
        if user_models:
            console.print(f"User-added models: {len(user_models)}")
    except Exception:
        pass


@self_app.command("doctor")
def self_doctor():
    """Run basic health checks (model loading, tools, MCP readiness, etc.)."""
    console.print("[bold]Running Nex doctor...[/bold]\n")
    issues = []

    # Check uv
    if not shutil.which("uv"):
        issues.append("uv not installed (recommended for speed). See https://astral.sh/uv")

    # Try importing core pieces
    try:
        from .models import list_profiles
        models = list_profiles()
        console.print(f"[green]✓[/green] Registry loaded ({len(models)} known models)")
    except Exception as e:
        issues.append(f"Model registry failed: {e}")

    try:
        from .engine import Engine
        e = Engine()
        console.print("[green]✓[/green] Engine class OK")
    except Exception as e:
        issues.append(f"Engine import: {e}")

    try:
        from .mcp import mcp
        console.print(f"[green]✓[/green] MCP server ready (tools: {len(getattr(mcp, '_tool_manager', type('x',(),{'_tools':{}})())._tools)})")
    except Exception as e:
        issues.append(f"MCP: {e}")

    if issues:
        console.print("\n[yellow]Issues found:[/yellow]")
        for i in issues:
            console.print(f"  - {i}")
    else:
        console.print("\n[green]All checks passed! System looks healthy.[/green]")


if __name__ == "__main__":
    app()
