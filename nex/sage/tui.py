"""Personal Sage Partner TUI — conversational, profile-aware.

UX: open ritual (receipt), slash capture (/commit /person …), quit reflect,
Partner vs Rails labels.

Run:  nex sage tui
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header, Input, Static, Markdown

from .dialog import SageDialog, list_models_report
from .home import (
    LABEL_PARTNER,
    build_home_snapshot,
    parse_and_apply_capture,
    render_open_ritual_markdown,
)
from .local_models import pick_default_local
from .partner import load_or_create_profile


class SageTUI(App):
    """Seamless dialogue with local model + living personal context."""

    CSS = """
    Screen { background: $surface; }
    #status { height: auto; padding: 0 1; color: $text-muted; background: $panel; }
    #log {
        height: 1fr;
        border: round $accent;
        padding: 1 1;
        overflow-y: auto;
        background: $surface;
    }
    #input { dock: bottom; margin: 1 0; }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit_ritual", "Quit"),
        Binding("ctrl+d", "show_direction", "Direction"),
        Binding("ctrl+e", "export_pack", "Export"),
        Binding("ctrl+n", "new_chat", "New chat"),
        Binding("ctrl+r", "refresh_status", "Refresh"),
        Binding("ctrl+h", "show_home", "Home"),
    ]

    def __init__(
        self,
        profile_id: str = "default",
        model_path: Optional[str] = None,
    ):
        super().__init__()
        self.profile_id = profile_id
        self.model_path = model_path
        self.profile = load_or_create_profile(profile_id)
        self.dialog: Optional[SageDialog] = None
        self._busy = False
        self._transcript: list[tuple[str, str]] = []
        self._quit_armed = False
        self._awaiting_quit_reflect = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("Loading…", id="status")
        with VerticalScroll(id="scroll"):
            yield Markdown("*Starting…*", id="log")
        yield Input(
            placeholder="Talk… or /commit /person /reflect /direction /help · Ctrl+Q quit",
            id="input",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"MLX-SAGE · {LABEL_PARTNER}"
        self.sub_title = "purpose · partnership · living direction · not Rails/Grok chat"
        status = self.query_one("#status", Static)
        local = pick_default_local()
        if self.model_path:
            model = self.model_path
        elif local:
            model = local.path
            status.update(
                f"[Partner] Model: {local.label} ({local.size_gb} GB) · profile: {self.profile_id}"
            )
        else:
            status.update("[Partner] No complete local model — install weights, then restart")
            self._set_log(
                "### No complete MLX chat model on disk\n\n"
                + "```\n"
                + list_models_report()
                + "\n```\n\n"
                + "Run **`nex sage coach`** for first-run steps, or place a full mlx-lm model "
                + "under `~/.mtplx/models` / pass `-m /path`.\n\n"
                + f"*{LABEL_PARTNER} needs local weights. Grok is Rails-only.*"
            )
            return
        try:
            self.dialog = SageDialog(self.profile, model_path=model)
            status.update(f"[Partner] Loading model… {Path(model).name}")
            self.dialog.ensure_engine()
            status.update(
                f"[Partner] Ready · {Path(model).name} · profile `{self.profile_id}`"
            )
            # Rec 4 — open ritual: receipt-style welcome
            snap = build_home_snapshot(self.profile_id)
            self._set_log(render_open_ritual_markdown(snap))
        except Exception as e:
            status.update("[Partner] Model load failed")
            self._set_log(
                f"### Could not load model\n\n```\n{e}\n```\n\n"
                f"```\n{list_models_report()}\n```\n\n"
                "Try `nex sage coach`."
            )
            self.dialog = None
        self.query_one("#input", Input).focus()

    def _set_log(self, md: str) -> None:
        self.query_one("#log", Markdown).update(md)

    def _render_transcript(self) -> None:
        parts: list[str] = []
        for role, text in self._transcript:
            if role == "user":
                parts.append(f"**You:** {text}")
            elif role == "sage":
                parts.append(f"**Sage:** {text}")
            else:
                parts.append(f"*{text}*")
        body = "\n\n".join(parts) if parts else "*Empty thread — say hello or `/help`.*"
        self._set_log(body)
        try:
            self.query_one("#scroll", VerticalScroll).scroll_end(animate=False)
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = (event.value or "").strip()
        event.input.value = ""
        if self._busy:
            return

        # Rec 4 — quit reflect path
        if self._awaiting_quit_reflect:
            if text:
                self.profile.add_reflection(text)
                self._transcript.append(("sys", f"Saved reflection for direction: {text[:200]}"))
                self._render_transcript()
            self.exit()
            return

        if not text:
            return

        # Rec 3 — slash capture (does not require model)
        cap = parse_and_apply_capture(text, self.profile)
        if cap is not None:
            self._quit_armed = False
            self._transcript.append(("user", text))
            flag = "ok" if cap.ok else "note"
            self._transcript.append(("sys", f"[{flag}] {cap.message}"))
            self._render_transcript()
            if cap.updated_direction:
                self.action_refresh_status()
            return

        if not self.dialog:
            self._transcript.append(("sys", "No model loaded. Run `nex sage coach`."))
            self._render_transcript()
            return

        self._quit_armed = False
        self._busy = True
        self.query_one("#status", Static).update("[Partner] Thinking…")
        self._transcript.append(("user", text))
        self._transcript.append(("sage", "…"))
        self._render_transcript()
        threading.Thread(target=self._generate, args=(text,), daemon=True).start()

    def _generate(self, text: str) -> None:
        try:
            assert self.dialog is not None
            parts: list[str] = []
            for chunk in self.dialog.stream_reply(text, max_tokens=512, temperature=0.7):
                parts.append(chunk)
                full = "".join(parts)
                self.call_from_thread(self._set_sage_streaming, full)
            reply = "".join(parts).strip()
            self.call_from_thread(self._finish_sage, reply)
        except Exception as e:
            self.call_from_thread(self._on_error, str(e))

    def _on_error(self, msg: str) -> None:
        if self._transcript and self._transcript[-1][0] == "sage":
            self._transcript[-1] = ("sys", f"Error: {msg}")
        else:
            self._transcript.append(("sys", f"Error: {msg}"))
        self._busy = False
        self._render_transcript()
        self.action_refresh_status()

    def _set_sage_streaming(self, text: str) -> None:
        if self._transcript and self._transcript[-1][0] == "sage":
            self._transcript[-1] = ("sage", text)
        else:
            self._transcript.append(("sage", text))
        self._render_transcript()

    def _finish_sage(self, text: str) -> None:
        self._set_sage_streaming(text or "(empty reply)")
        self._busy = False
        d = self.profile.build_direction()
        status = self.query_one("#status", Static)
        north = (d.get("north_star") or "")[:120]
        status.update(f"[Partner] Ready · direction: {north}…")

    def action_show_direction(self) -> None:
        path = self.profile.write_direction()
        d = self.profile.build_direction()
        body = d.get("north_star", "") or "(empty)"
        self._transcript.append(("sys", f"Direction saved → {path}\n\n{body}"))
        self._render_transcript()

    def action_export_pack(self) -> None:
        path = self.profile.export_pack()
        self._transcript.append(("sys", f"Export pack → {path.parent}"))
        self._render_transcript()

    def action_new_chat(self) -> None:
        from .dialog import chat_history_path

        p = chat_history_path(self.profile)
        if p.exists():
            p.unlink()
        self._transcript = [
            ("sys", "New chat thread. Profile (people, direction, commits) kept."),
        ]
        # Re-show open ritual for continuity
        snap = build_home_snapshot(self.profile_id)
        self._set_log(
            render_open_ritual_markdown(snap)
            + "\n\n*New chat thread — profile kept.*"
        )
        self._transcript = []

    def action_show_home(self) -> None:
        snap = build_home_snapshot(self.profile_id)
        self._transcript.append(("sys", render_open_ritual_markdown(snap)))
        self._render_transcript()
        self.action_refresh_status()

    def action_refresh_status(self) -> None:
        if self._busy:
            self.query_one("#status", Static).update("[Partner] Thinking…")
            return
        if self._awaiting_quit_reflect:
            self.query_one("#status", Static).update(
                "[Partner] Quit: one-line reflection + Enter, or empty Enter to leave"
            )
            return
        d = self.profile.build_direction()
        north = (d.get("north_star") or "no direction yet")[:100]
        model = Path(self.dialog.model_id).name if self.dialog else "no-model"
        self.query_one("#status", Static).update(
            f"[Partner] Ready · {model} · `{self.profile_id}` · {north}"
        )

    def action_quit_ritual(self) -> None:
        """Rec 4: first Ctrl+Q arms quit; offer optional reflection."""
        if self._awaiting_quit_reflect:
            self.exit()
            return
        if self._quit_armed and not self._awaiting_quit_reflect:
            # second path: already armed via message — go to reflect prompt
            pass
        self._quit_armed = True
        self._awaiting_quit_reflect = True
        self._busy = False
        self._transcript.append(
            (
                "sys",
                "Before quit (Partner): type **one sentence** for living direction and press Enter, "
                "or press Enter empty / Ctrl+Q again to leave without saving.\n"
                "*(Rails/Grok are separate — this only updates your sage profile.)*",
            )
        )
        self._render_transcript()
        self.action_refresh_status()
        self.query_one("#input", Input).focus()


def run_sage_tui(profile_id: str = "default", model_path: Optional[str] = None) -> None:
    """Back-compat entry — delegates to the single Partner app."""
    from .app import run_partner_app

    run_partner_app(profile_id=profile_id, model_path=model_path)
