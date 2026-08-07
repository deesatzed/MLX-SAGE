"""Personal Sage Partner TUI — conversational, profile-aware.

Run:  nex sage tui

Stage 3 polish: clearer status, Markdown transcript, busy guard, honest empty-model state.
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
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+d", "show_direction", "Direction"),
        Binding("ctrl+e", "export_pack", "Export"),
        Binding("ctrl+n", "new_chat", "New chat"),
        Binding("ctrl+r", "refresh_status", "Refresh"),
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
        self._transcript: list[tuple[str, str]] = []  # (role, text)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("Loading…", id="status")
        with VerticalScroll(id="scroll"):
            yield Markdown("*Starting…*", id="log")
        yield Input(placeholder="Talk with your sage partner… (Enter to send)", id="input")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "MLX-SAGE · Sage Partner"
        self.sub_title = "purpose · partnership · living direction"
        status = self.query_one("#status", Static)
        local = pick_default_local()
        if self.model_path:
            model = self.model_path
        elif local:
            model = local.path
            status.update(
                f"Model: {local.label} ({local.size_gb} GB) · profile: {self.profile_id}"
            )
        else:
            status.update("No complete local model found — install weights, then restart")
            self._set_log(
                "### No complete MLX chat model on disk\n\n"
                + "```\n"
                + list_models_report()
                + "\n```\n\n"
                + "Place a full mlx-lm model under `~/.mtplx/models` (config + weights) "
                + "or pass `-m /path/to/model`.\n\n"
                + "Only **complete** folders show as READY in `nex sage models`."
            )
            return
        try:
            self.dialog = SageDialog(self.profile, model_path=model)
            status.update(f"Loading model… {Path(model).name}")
            self.dialog.ensure_engine()
            d = self.profile.build_direction()
            north = d.get("north_star") or "No direction yet — talk freely; direction will form."
            status.update(f"Ready · {Path(model).name} · profile `{self.profile_id}`")
            self._set_log(
                "### Sage partner ready\n\n"
                f"**Your direction so far**\n\n{north}\n\n"
                "Talk naturally.\n\n"
                "| Key | Action |\n|-----|--------|\n"
                "| Ctrl+D | Show / refresh direction |\n"
                "| Ctrl+E | Export shareable pack |\n"
                "| Ctrl+N | New chat (keeps profile) |\n"
                "| Ctrl+R | Refresh status line |\n"
                "| Ctrl+Q | Quit |\n"
            )
        except Exception as e:
            status.update("Model load failed")
            self._set_log(
                f"### Could not load model\n\n```\n{e}\n```\n\n"
                f"```\n{list_models_report()}\n```"
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
        self._set_log("\n\n".join(parts) if parts else "*Empty thread — say hello.*")
        try:
            self.query_one("#scroll", VerticalScroll).scroll_end(animate=False)
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = (event.value or "").strip()
        event.input.value = ""
        if not text or self._busy:
            return
        if not self.dialog:
            self._transcript.append(("sys", "No model loaded."))
            self._render_transcript()
            return
        self._busy = True
        self.query_one("#status", Static).update("Thinking…")
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
        status.update(f"Ready · direction: {north}…")

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
        self._render_transcript()

    def action_refresh_status(self) -> None:
        if self._busy:
            self.query_one("#status", Static).update("Thinking…")
            return
        d = self.profile.build_direction()
        north = (d.get("north_star") or "no direction yet")[:100]
        model = Path(self.dialog.model_id).name if self.dialog else "no-model"
        self.query_one("#status", Static).update(
            f"Ready · {model} · `{self.profile_id}` · {north}"
        )


def run_sage_tui(profile_id: str = "default", model_path: Optional[str] = None) -> None:
    app = SageTUI(profile_id=profile_id, model_path=model_path)
    app.run()
