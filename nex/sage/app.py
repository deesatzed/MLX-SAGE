"""Single Partner app — the only thing most people should run.

    nex
    nex start
    nex main

Automates: profile create, model pick, first person, first commit, then chat.
No command cookbooks. One input box does everything for the current step.
"""

from __future__ import annotations

import threading
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Input, Markdown, Static

from .dialog import SageDialog, list_models_report
from .home import parse_and_apply_capture
from .local_models import pick_default_local
from .partner import Commitment, PersonStub, load_or_create_profile


class Phase(str, Enum):
    BOOT = "boot"
    NEED_MODEL = "need_model"
    ASK_PERSON = "ask_person"
    ASK_COMMIT = "ask_commit"
    CHAT = "chat"
    QUIT_REFLECT = "quit_reflect"


class PartnerApp(App):
    """One app. Start → guided if needed → talk. Everything else is optional chrome."""

    TITLE = "MLX-SAGE"
    CSS = """
    Screen { background: $surface; }
    #sidebar {
        width: 34;
        background: $panel;
        border-right: thick $primary;
        padding: 1;
    }
    #side_md { height: 1fr; }
    #main { width: 1fr; }
    #banner {
        height: auto;
        padding: 0 1;
        background: $boost;
        color: $text;
    }
    #log {
        height: 1fr;
        border: round $accent;
        padding: 1;
        overflow-y: auto;
    }
    #input { dock: bottom; margin: 1 0; }
    """

    BINDINGS = [
        Binding("ctrl+q", "request_quit", "Leave"),
        Binding("ctrl+d", "show_direction", "Direction"),
        Binding("f5", "rescan", "Rescan model"),
    ]

    def __init__(self, profile_id: str = "default", model_path: Optional[str] = None):
        super().__init__()
        self.profile_id = profile_id
        self.model_path = model_path
        self.profile = load_or_create_profile(profile_id)
        self.profile.save()  # ensure exists
        self.dialog: Optional[SageDialog] = None
        self.phase = Phase.BOOT
        self._busy = False
        self._transcript: List[Tuple[str, str]] = []
        self._pending_person_name = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Static("Your direction", classes="title")
                yield Markdown("*…*", id="side_md")
            with Vertical(id="main"):
                yield Static("", id="banner")
                with VerticalScroll():
                    yield Markdown("", id="log")
                yield Input(placeholder="…", id="input")
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = "Partner · local · private"
        self._refresh_sidebar()
        self._advance_from_state()
        self.query_one("#input", Input).focus()
        # If waiting on model, rescan periodically
        self.set_interval(4.0, self._maybe_rescan_model)

    # ------------------------------------------------------------------ state
    def _model_ready_path(self) -> Optional[str]:
        if self.model_path:
            return self.model_path
        m = pick_default_local()
        if m and m.complete:
            return m.path
        return None

    def _profile_needs_person(self) -> bool:
        return len(self.profile.people) == 0

    def _profile_needs_commit(self) -> bool:
        open_c = [c for c in self.profile.commitments if not c.done]
        return len(open_c) == 0 and len(self.profile.reflections) == 0

    def _advance_from_state(self) -> None:
        path = self._model_ready_path()
        if not path:
            self.phase = Phase.NEED_MODEL
            self._show_need_model()
            return
        self.model_path = path
        if self._profile_needs_person():
            self.phase = Phase.ASK_PERSON
            self._show_ask_person()
            return
        if self._profile_needs_commit():
            self.phase = Phase.ASK_COMMIT
            self._show_ask_commit()
            return
        self._enter_chat()

    def _set_banner(self, text: str) -> None:
        self.query_one("#banner", Static).update(text)

    def _set_log(self, md: str) -> None:
        self.query_one("#log", Markdown).update(md)

    def _set_placeholder(self, text: str) -> None:
        self.query_one("#input", Input).placeholder = text

    def _refresh_sidebar(self) -> None:
        d = self.profile.build_direction()
        north = d.get("north_star") or "Your direction will appear here."
        people = self.profile.people
        commits = [c for c in self.profile.commitments if not c.done]
        lines = [
            f"**{north}**",
            "",
            f"People: **{len(people)}**",
        ]
        for p in people[:8]:
            lines.append(f"- {p.name} ({p.relation})")
        lines.append("")
        lines.append(f"Open commits: **{len(commits)}**")
        for c in commits[:6]:
            lines.append(f"- {c.text} → {c.toward_person}")
        model = Path(self.model_path).name if self.model_path else "no model yet"
        lines.append("")
        lines.append(f"*Model: {model}*")
        self.query_one("#side_md", Markdown).update("\n".join(lines))

    # ------------------------------------------------------------------ phases UI
    def _show_need_model(self) -> None:
        self._set_banner("Step 1 of 3 — need a local AI model on this Mac")
        self._set_log(
            "### Almost there\n\n"
            "Sage runs **on your computer** (private). No complete model was found yet.\n\n"
            "**Easiest path**\n\n"
            "1. In any terminal: `nex models recommend \"chat\" --max-memory 16`\n"
            "2. Then: `nex models download <name it suggests>`\n"
            "3. Come back here and press **Enter** (or F5) — we rescan automatically.\n\n"
            "Or put a full mlx-lm folder under `~/.mtplx/models/`.\n\n"
            "*You only do this once.*"
        )
        self._set_placeholder("Press Enter to rescan for a model…")

    def _show_ask_person(self) -> None:
        self._set_banner("Step 2 of 3 — who matters? (one name is enough)")
        self._set_log(
            "### Who is one person that matters to you?\n\n"
            "Type their **first name** and press Enter.\n\n"
            "Examples: `Sam` · `Alex` · `Mom`\n\n"
            "You can add more later by typing:  `person Jordan friend`\n\n"
            "Or type **skip** to continue without this."
        )
        self._set_placeholder("Type a name, or skip…")

    def _show_ask_commit(self) -> None:
        who = self.profile.people[0].name if self.profile.people else "someone"
        self._set_banner("Step 3 of 3 — one small thing this week")
        self._set_log(
            f"### What's one small thing you'll do this week?\n\n"
            f"For example: `Call {who}` or `Walk 20 minutes`\n\n"
            "Type it and press Enter — or **skip**."
        )
        self._set_placeholder("One small commitment, or skip…")

    def _enter_chat(self) -> None:
        self.phase = Phase.CHAT
        path = self._model_ready_path()
        if not path:
            self._advance_from_state()
            return
        self.model_path = path
        self._set_banner("Talk with your sage partner · private · local")
        try:
            if self.dialog is None or self.dialog.model_id != path:
                self.dialog = SageDialog(self.profile, model_path=path)
                self._set_log("### Loading model…\n\nOne moment.")
                self.dialog.ensure_engine()
        except Exception as e:
            self.dialog = None
            self._set_log(
                f"### Could not load model\n\n```\n{e}\n```\n\n"
                "Press F5 after fixing the model."
            )
            self.phase = Phase.NEED_MODEL
            return

        d = self.profile.build_direction()
        north = d.get("north_star") or "Talk freely — your direction will form."
        self._transcript = []
        self._set_log(
            f"### Ready\n\n**{north}**\n\n"
            "Just talk. I'll listen as a partner — not a servant, not a guru.\n\n"
            "*Tips:* type naturally. "
            "To save a person: `person Name relation`. "
            "To save a promise: `commit do X`. "
            "Ctrl+Q to leave."
        )
        self._set_placeholder("Talk…")
        self._refresh_sidebar()

    def _maybe_rescan_model(self) -> None:
        if self.phase != Phase.NEED_MODEL:
            return
        if self._model_ready_path():
            self._advance_from_state()

    def action_rescan(self) -> None:
        self._advance_from_state()

    # ------------------------------------------------------------------ input
    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = (event.value or "").strip()
        event.input.value = ""
        if self._busy:
            return

        if self.phase == Phase.QUIT_REFLECT:
            if text:
                self.profile.add_reflection(text)
            self.exit()
            return

        if self.phase == Phase.NEED_MODEL:
            # Enter = rescan
            self._advance_from_state()
            if self.phase == Phase.NEED_MODEL:
                self._set_log(
                    "### Still no READY model\n\n"
                    "```\n"
                    + list_models_report()
                    + "\n```\n\n"
                    + "Download one, then press **Enter** or **F5**."
                )
            return

        if self.phase == Phase.ASK_PERSON:
            self._handle_person_step(text)
            return

        if self.phase == Phase.ASK_COMMIT:
            self._handle_commit_step(text)
            return

        if self.phase == Phase.CHAT:
            self._handle_chat(text)

    def _handle_person_step(self, text: str) -> None:
        low = text.lower()
        if not text or low in ("skip", "s", "no", "n"):
            self._advance_after_person_skip()
            return
        # "Name" or "Name relation"
        parts = text.split(None, 1)
        name = parts[0]
        relation = parts[1] if len(parts) > 1 else "person"
        self.profile.add_person(
            PersonStub(name=name, relation=relation, they_may_need_me_for="", i_need_them_for="")
        )
        self._refresh_sidebar()
        self._pending_person_name = name
        self.phase = Phase.ASK_COMMIT
        self._show_ask_commit()

    def _advance_after_person_skip(self) -> None:
        if self._profile_needs_commit():
            self.phase = Phase.ASK_COMMIT
            self._show_ask_commit()
        else:
            self._enter_chat()

    def _handle_commit_step(self, text: str) -> None:
        low = text.lower()
        if text and low not in ("skip", "s", "no", "n"):
            toward = self._pending_person_name or (
                self.profile.people[0].name if self.profile.people else "self"
            )
            self.profile.add_commitment(Commitment(text=text, toward_person=toward))
            self._refresh_sidebar()
        self._enter_chat()

    def _handle_chat(self, text: str) -> None:
        if not text:
            return

        # Friendly natural commands (no slash required)
        low = text.lower()
        if low.startswith("person "):
            rest = text[7:].strip()
            bits = rest.split(None, 1)
            if len(bits) == 1:
                text = f"/person {bits[0]}"
            else:
                text = f"/person {bits[0]} | {bits[1]}"
        elif low.startswith("commit "):
            text = f"/commit {text[7:].strip()}"
        elif low in ("direction", "show direction"):
            text = "/direction"
        elif low in ("help", "?"):
            text = "/help"

        # Slash capture
        cap = parse_and_apply_capture(text, self.profile)
        if cap is not None:
            self._append("you", text if text.startswith("/") else text)
            self._append("sys", cap.message)
            self._render_chat()
            self._refresh_sidebar()
            return

        if not self.dialog:
            self._append("sys", "Model not loaded. Press F5.")
            self._render_chat()
            return

        self._busy = True
        self._set_banner("Thinking…")
        self._append("you", text)
        self._append("sage", "…")
        self._render_chat()
        threading.Thread(target=self._generate, args=(text,), daemon=True).start()

    def _generate(self, text: str) -> None:
        try:
            assert self.dialog is not None
            parts: list[str] = []
            for chunk in self.dialog.stream_reply(text, max_tokens=512, temperature=0.7):
                parts.append(chunk)
                self.call_from_thread(self._stream_sage, "".join(parts))
            self.call_from_thread(self._finish_sage, "".join(parts).strip())
        except Exception as e:
            self.call_from_thread(self._fail_sage, str(e))

    def _append(self, role: str, text: str) -> None:
        self._transcript.append((role, text))

    def _stream_sage(self, text: str) -> None:
        if self._transcript and self._transcript[-1][0] == "sage":
            self._transcript[-1] = ("sage", text)
        else:
            self._transcript.append(("sage", text))
        self._render_chat()

    def _finish_sage(self, text: str) -> None:
        self._stream_sage(text or "(empty)")
        self._busy = False
        self._set_banner("Talk with your sage partner · private · local")
        self._refresh_sidebar()

    def _fail_sage(self, err: str) -> None:
        if self._transcript and self._transcript[-1][0] == "sage":
            self._transcript[-1] = ("sys", f"Error: {err}")
        self._busy = False
        self._set_banner("Something went wrong — try again")
        self._render_chat()

    def _render_chat(self) -> None:
        parts = []
        for role, text in self._transcript:
            if role == "you":
                parts.append(f"**You:** {text}")
            elif role == "sage":
                parts.append(f"**Sage:** {text}")
            else:
                parts.append(f"*{text}*")
        self._set_log("\n\n".join(parts) if parts else "*Say hello.*")

    def action_show_direction(self) -> None:
        path = self.profile.write_direction()
        d = self.profile.build_direction()
        self._append("sys", f"Direction\n\n{d.get('north_star', '')}\n\n(saved)")
        if self.phase == Phase.CHAT:
            self._render_chat()
        else:
            self._set_log(f"### Direction\n\n{d.get('north_star', '')}\n\nSaved → `{path}`")
        self._refresh_sidebar()

    def action_request_quit(self) -> None:
        if self.phase == Phase.QUIT_REFLECT:
            self.exit()
            return
        if self.phase != Phase.CHAT:
            self.exit()
            return
        self.phase = Phase.QUIT_REFLECT
        self._set_banner("One sentence for your direction? (or Enter empty to leave)")
        self._append(
            "sys",
            "Before you go: type **one sentence** about what matters, or press Enter to leave.",
        )
        self._render_chat()
        self._set_placeholder("One sentence, or empty to quit…")


def run_partner_app(profile_id: str = "default", model_path: Optional[str] = None) -> None:
    PartnerApp(profile_id=profile_id, model_path=model_path).run()
