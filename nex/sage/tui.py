"""Personal Sage Partner TUI — conversational, profile-aware.

Run:  nex sage tui
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Footer, Header, Input, Static, Markdown

from .dialog import SageDialog, list_models_report
from .local_models import pick_default_local
from .partner import load_or_create_profile


class SageTUI(App):
    """Seamless dialogue with local model + living personal context."""

    CSS = """
    Screen { background: $surface; }
    #status { height: auto; padding: 0 1; color: $text-muted; }
    #log { height: 1fr; border: round $accent; padding: 1; overflow-y: auto; }
    #input { dock: bottom; margin: 1 0; }
    .user { color: $success; }
    .sage { color: $text; }
    .sys { color: $warning; text-style: italic; }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+d", "show_direction", "Direction"),
        Binding("ctrl+e", "export_pack", "Export"),
        Binding("ctrl+n", "new_chat", "New chat"),
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

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("Loading…", id="status")
        yield VerticalScroll(Static("…", id="log"))
        yield Input(placeholder="Talk with your sage partner…", id="input")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Sage Partner"
        self.sub_title = "purpose · partnership · direction"
        log = self.query_one("#log", Static)
        status = self.query_one("#status", Static)
        local = pick_default_local()
        if self.model_path:
            model = self.model_path
        elif local:
            model = local.path
            status.update(f"Model: {local.label} ({local.size_gb} GB) · profile: {self.profile_id}")
        else:
            status.update("No complete local model found")
            log.update(
                "[sys]No complete MLX chat model on disk.\n\n"
                + list_models_report()
                + "\n\nPlace a full mlx-lm model under ~/.mtplx/models and retry."
            )
            return
        try:
            self.dialog = SageDialog(self.profile, model_path=model)
            status.update(f"Loading model… {Path(model).name}")
            self.dialog.ensure_engine()
            d = self.profile.build_direction()
            north = d.get("north_star") or "No direction yet — talk freely; direction will form."
            status.update(f"Ready · {Path(model).name} · {self.profile_id}")
            log.update(
                f"[sys]Sage partner ready.\n\n"
                f"Your direction so far:\n{north}\n\n"
                f"Talk naturally. Ctrl+D direction · Ctrl+E export · Ctrl+Q quit."
            )
        except Exception as e:
            status.update("Model load failed")
            log.update(f"[sys]Could not load model:\n{e}\n\n{list_models_report()}")
            self.dialog = None
        self.query_one("#input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = (event.value or "").strip()
        event.input.value = ""
        if not text or self._busy:
            return
        if not self.dialog:
            self._append_sys("No model loaded.")
            return
        self._busy = True
        self._append_user(text)
        self._append_sage_start()
        threading.Thread(target=self._generate, args=(text,), daemon=True).start()

    def _generate(self, text: str) -> None:
        try:
            assert self.dialog is not None
            parts = []
            for chunk in self.dialog.stream_reply(text, max_tokens=512, temperature=0.7):
                parts.append(chunk)
                full = "".join(parts)
                self.call_from_thread(self._set_sage_streaming, full)
            reply = "".join(parts).strip()
            self.call_from_thread(self._finish_sage, reply)
        except Exception as e:
            self.call_from_thread(self._append_sys, f"Error: {e}")
            self.call_from_thread(self._set_busy_false)

    def _set_busy_false(self) -> None:
        self._busy = False

    def _append_user(self, text: str) -> None:
        log = self.query_one("#log", Static)
        prev = str(log.renderable) if log.renderable else ""
        log.update(prev + f"\n\n[you] {text}\n")
        self.query_one("#log").scroll_end(animate=False)

    def _append_sage_start(self) -> None:
        log = self.query_one("#log", Static)
        prev = str(log.renderable) if log.renderable else ""
        log.update(prev + "\n[sage] …")
        self.query_one("#log").scroll_end(animate=False)

    def _set_sage_streaming(self, text: str) -> None:
        log = self.query_one("#log", Static)
        prev = str(log.renderable) if log.renderable else ""
        # replace last sage stream block
        if "\n[sage] " in prev:
            head = prev.rsplit("\n[sage] ", 1)[0]
            log.update(head + f"\n[sage] {text}")
        else:
            log.update(prev + f"\n[sage] {text}")
        self.query_one("#log").scroll_end(animate=False)

    def _finish_sage(self, text: str) -> None:
        self._set_sage_streaming(text)
        self._busy = False
        d = self.profile.build_direction()
        status = self.query_one("#status", Static)
        north = (d.get("north_star") or "")[:120]
        status.update(f"Ready · direction: {north}…")

    def _append_sys(self, text: str) -> None:
        log = self.query_one("#log", Static)
        prev = str(log.renderable) if log.renderable else ""
        log.update(prev + f"\n\n[{text}]")

    def action_show_direction(self) -> None:
        path = self.profile.write_direction()
        d = self.profile.build_direction()
        self._append_sys(f"Direction\n{d.get('north_star', '')}\n→ {path}")

    def action_export_pack(self) -> None:
        path = self.profile.export_pack()
        self._append_sys(f"Export pack → {path.parent}")

    def action_new_chat(self) -> None:
        # clear chat history file but keep profile
        from .dialog import chat_history_path

        p = chat_history_path(self.profile)
        if p.exists():
            p.unlink()
        self.query_one("#log", Static).update(
            "[sys]New chat thread. Profile (people, direction, commits) kept."
        )


def run_sage_tui(profile_id: str = "default", model_path: Optional[str] = None) -> None:
    app = SageTUI(profile_id=profile_id, model_path=model_path)
    app.run()
