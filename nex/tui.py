"""
Production-grade Textual TUI for Nex (local multi-model substrate under MLX-SAGE).

Features:
- Real multi-turn using ChatSession + persistence
- Markdown rendering + basic thinking awareness
- Live model switching from registry (with MTP variants)
- MTP toggle that reloads engine
- Live stats
- Real SentinelPolicy gating of tool calls (approve / block / override)

Run with:
    nex tui
    ./run.sh tui
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    ListView,
    ListItem,
    Log,
    Markdown,
    Static,
    Switch,
)

from .engine import Engine
from .models import get_default_model, get_profile, list_profiles
from .persistence import (
    SessionRecord,
    load_session,
    new_session_id,
    save_session,
)
from .session import ChatSession as CoreChatSession
from .tools import parse_tool_call, execute_tool
from .sentinel.policy import PolicyDecision, PolicyAction, FileEffect, SentinelPolicy
from .tui_policy import (
    ToolGateResult,
    apply_override_and_reevaluate,
    decide_tool_gate,
)


@dataclass
class PendingApproval:
    """Human-in-the-loop item: real policy decision + gated tool call."""

    prompt_line: str
    file_effects: list[FileEffect]
    policy_decision: PolicyDecision
    tool_call: Dict[str, Any]
    grok_verdict: str | None = None
    command_effects: list = field(default_factory=list)


class NexTUI(App):
    """Local multi-model TUI with real Sentinel tool gating."""

    CSS = """
    Screen { background: $surface; }
    #sidebar { width: 30; background: $panel; border-right: thick $primary; }
    #chat_log { height: 1fr; border: round $accent; padding: 1; overflow-y: auto; }
    #input { dock: bottom; margin: 1 0; }
    #stats { height: auto; background: $boost; border: round $secondary; padding: 0 1; }
    .title { padding: 0 1; text-style: bold; }
    .active { background: $accent; color: $text; }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+m", "focus_models", "Models"),
        Binding("ctrl+t", "toggle_mtp", "Toggle MTP"),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("ctrl+n", "new_session", "New Session"),
        Binding("a", "approve_pending", "Approve"),
        Binding("b", "block_pending", "Block"),
        Binding("o", "override_pending", "Override"),
    ]

    current_model: reactive[str] = reactive(get_default_model())
    mtp_enabled: reactive[bool] = reactive(False)
    stats_text: reactive[str] = reactive("Ready")
    approvals: reactive[list] = reactive([])

    def __init__(self):
        super().__init__()
        self.engine: Engine | None = None
        self.chat_session: CoreChatSession | None = None
        self.record: SessionRecord | None = None
        self.sid = new_session_id("tui")
        self.policy = SentinelPolicy()
        self._policy_decisions = 0
        self._policy_blocks = 0
        self._policy_reviews = 0
        self._tools_executed = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal():
            with Vertical(id="sidebar"):
                yield Label("Models", classes="title")
                yield ListView(id="model_list")
                yield Label("MTP", classes="title")
                yield Switch(value=self.mtp_enabled, id="mtp_switch")

            with Vertical():
                yield Markdown(id="chat_log")
                yield Static("Tool Output (policy-gated)", classes="title")
                yield Log(id="tool_log", highlight=True, wrap=True, max_lines=8)
                yield Static(
                    "Sentinel queue — real policy only (a=approve, b=block, o=override)",
                    classes="title",
                )
                yield Log(id="approvals_log", highlight=True, wrap=True, max_lines=6)
                yield Input(
                    placeholder="Message… | tools need a/b/o when policy says review",
                    id="input",
                )
                yield Static(self.stats_text, id="stats")

        yield Footer()

    def on_mount(self) -> None:
        self.title = "MLX-SAGE • Nex local runner"
        self.sub_title = "Sage-first stack · local MLX + Sentinel tool gates"
        self._load_models()
        self._init_session()
        self._load_engine()
        self.query_one("#input", Input).focus()
        self._refresh_view()

    # --- Models & Engine ---

    def _load_models(self) -> None:
        lv = self.query_one("#model_list", ListView)
        lv.clear()
        for p in list_profiles():
            item = ListItem(Label(f"{p.name}"), name=p.repo_id)
            if p.repo_id == self.current_model:
                item.add_class("active")
            lv.append(item)

    def _load_engine(self) -> None:
        draft = None
        if self.mtp_enabled:
            prof = get_profile(self.current_model)
            if prof.supports_mtp and prof.mtp_repo_id:
                draft = prof.mtp_repo_id

        self.engine = Engine(
            model_id=self.current_model,
            draft_model_id=draft,
            num_draft_tokens=3,
        )
        self.engine.load()

        prof = get_profile(self.current_model)
        mtp = " + MTP" if self.mtp_enabled else ""
        self.stats_text = f"{prof.name}{mtp} | policy decisions={self._policy_decisions}"
        self.query_one("#stats", Static).update(self.stats_text)

        if self.chat_session:
            self.chat_session.engine = self.engine

    def watch_mtp_enabled(self, value: bool) -> None:
        self._load_engine()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "mtp_switch":
            self.mtp_enabled = event.value

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "model_list" and event.item and event.item.name:
            new_model = str(event.item.name)
            if new_model != self.current_model:
                self.current_model = new_model
                self._load_models()
                self._load_engine()
                self.query_one("#chat_log", Markdown).update(
                    (self.query_one("#chat_log", Markdown).renderable or "")
                    + f"\n\n[dim]→ Switched to {get_profile(new_model).name}[/dim]"
                )

    # --- Session Management ---

    def _init_session(self) -> None:
        self.record = load_session(self.sid) or SessionRecord(session_id=self.sid)
        self.chat_session = CoreChatSession(engine=self.engine or Engine(self.current_model))
        if self.record.messages:
            self.chat_session.messages = list(self.record.messages)
            if self.record.system_prompt:
                self.chat_session.system_prompt = self.record.system_prompt

    def _refresh_view(self) -> None:
        log = self.query_one("#chat_log", Markdown)
        content_lines = []
        for msg in (self.chat_session.messages if self.chat_session else []):
            role = "**You:**" if msg["role"] == "user" else "**Nex:**"
            text = msg["content"].strip()
            if "<think>" in text and "</think>" in text:
                before, rest = text.split("<think>", 1)
                think_content, after = rest.split("</think>", 1)
                text = f"{before}\n\n> **Thinking:**\n> {think_content.strip()}\n\n{after}"
            content_lines.append(f"{role} {text}")
        log.update("\n\n".join(content_lines) or "*Start typing below...*")

    def _persist(self) -> None:
        if self.record and self.chat_session:
            self.record.messages = self.chat_session.messages
            save_session(self.record)

    def _update_policy_stats(self, extra: str = "") -> None:
        base = self.stats_text.split(" | policy")[0]
        self.stats_text = (
            f"{base} | policy decisions={self._policy_decisions} "
            f"blocks={self._policy_blocks} reviews={self._policy_reviews} "
            f"tools_ok={self._tools_executed}{extra}"
        )
        try:
            self.query_one("#stats", Static).update(self.stats_text)
        except Exception:
            pass

    # --- Chat ---

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or not self.engine or not self.chat_session:
            return

        event.input.value = ""

        self.chat_session.add_user(text)
        self._refresh_view()
        self._persist()

        self.run_worker(self._generate(text), exclusive=True)

    async def _generate(self, user_text: str) -> None:
        log = self.query_one("#chat_log", Markdown)

        try:
            prompt = self.chat_session.build_prompt()
            full_response: list[str] = []

            for chunk, stats in self.engine.stream_generate(
                prompt,
                max_tokens=self.chat_session.max_tokens,
                temperature=self.chat_session.temperature,
                top_p=self.chat_session.top_p,
            ):
                if chunk:
                    full_response.append(chunk)
                if stats:
                    self.stats_text = (
                        f"{stats.generation_tokens} tok @ {stats.generation_tps:.1f} t/s  "
                        f"peak {stats.peak_memory_gb:.1f} GB"
                    )
                    if self.mtp_enabled:
                        self.stats_text += " [MTP]"
                    self._update_policy_stats()

            assistant_text = "".join(full_response).strip()
            self.chat_session.add_assistant(assistant_text)
            self._refresh_view()
            self._persist()

            tool_call = parse_tool_call(assistant_text)
            if tool_call:
                self._handle_tool_call(tool_call)

        except Exception as e:
            log.update(f"**Error during generation:** {e}")

    def _handle_tool_call(self, tool_call: Dict[str, Any]) -> None:
        """Real policy gate: auto-execute ALLOW, queue REVIEW/CONFIRM, refuse BLOCK."""
        tool_log = self.query_one("#tool_log", Log)
        tool_log.write_line(
            f"[yellow]Tool call:[/yellow] {tool_call.get('name')} {tool_call.get('arguments')}"
        )

        gate = decide_tool_gate(self.policy, tool_call)
        self._policy_decisions += 1
        if gate.policy_decision.action == PolicyAction.BLOCK:
            self._policy_blocks += 1
        elif gate.policy_decision.action in (PolicyAction.REVIEW, PolicyAction.CONFIRM):
            self._policy_reviews += 1
        self._update_policy_stats()

        action = gate.policy_decision.action.value
        reason = gate.policy_decision.reason
        tool_log.write_line(f"[cyan]Policy {action}:[/cyan] {reason}")

        if gate.disposition == "auto_execute":
            self._execute_gated_tool(tool_call, via="policy ALLOW")
            return

        if gate.disposition == "hard_block":
            try:
                alog = self.query_one("#approvals_log", Log)
                alog.write_line(f"[red]BLOCKED[/red] {gate.prompt_line[:60]} — {reason[:80]}")
            except Exception:
                pass
            tool_log.write_line("[red]Tool not executed (policy BLOCK).[/red]")
            return

        # queue — do not execute until a / o
        pa = PendingApproval(
            prompt_line=gate.prompt_line,
            file_effects=list(gate.file_effects),
            policy_decision=gate.policy_decision,
            tool_call=tool_call,
            grok_verdict=None,
            command_effects=list(gate.command_effects),
        )
        self.queue_approval(pa)
        tool_log.write_line(
            "[yellow]Queued — press a=approve, b=block, o=override (not executed yet).[/yellow]"
        )

    def _execute_gated_tool(self, tool_call: Dict[str, Any], *, via: str) -> None:
        tool_log = self.query_one("#tool_log", Log)
        try:
            obs = execute_tool(tool_call)
            self._tools_executed += 1
            self._update_policy_stats()
            tool_log.write_line(f"[green]Observation ({via}):[/green] {obs[:200]}...")
        except Exception as e:
            tool_log.write_line(f"[red]Tool error:[/red] {e}")

    # --- Actions ---

    def action_toggle_mtp(self) -> None:
        sw = self.query_one("#mtp_switch", Switch)
        sw.value = not sw.value
        self.mtp_enabled = sw.value

    def action_focus_models(self) -> None:
        self.query_one("#model_list", ListView).focus()

    def action_clear(self) -> None:
        if self.chat_session:
            self.chat_session.reset()
        self.query_one("#chat_log", Markdown).update("*Conversation cleared*")
        self._persist()

    def action_new_session(self) -> None:
        self.sid = new_session_id("tui")
        self.record = SessionRecord(session_id=self.sid)
        self.chat_session = CoreChatSession(engine=self.engine or Engine(self.current_model))
        self.query_one("#chat_log", Markdown).update("*New session started*")
        self._persist()

    def queue_approval(self, pa: PendingApproval) -> None:
        self.approvals = list(self.approvals) + [pa]
        try:
            alog = self.query_one("#approvals_log", Log)
            act = pa.policy_decision.action.value
            alog.write_line(
                f"[yellow]PENDING {act}[/yellow] {pa.prompt_line[:50]} — {pa.policy_decision.reason[:40]}"
            )
        except Exception:
            pass

    def _handle_pending(self, approve: bool, override: bool = False) -> None:
        if not self.approvals:
            return
        remaining = list(self.approvals)
        pa: PendingApproval = remaining.pop(0)
        self.approvals = remaining

        tool_log = self.query_one("#tool_log", Log)
        alog = self.query_one("#approvals_log", Log)

        if override:
            # Re-evaluate after recording session overrides. Hard blocks (e.g. .env) still win.
            new_dec = apply_override_and_reevaluate(
                self.policy, pa.tool_call, pa.file_effects
            )
            self._policy_decisions += 1
            alog.write_line(
                f"[magenta]OVERRIDE re-eval → {new_dec.action.value}[/magenta] {new_dec.reason[:60]}"
            )
            if new_dec.action == PolicyAction.BLOCK:
                self._policy_blocks += 1
                tool_log.write_line(
                    "[red]Override refused: hard policy BLOCK still applies (e.g. protected path).[/red]"
                )
                self._update_policy_stats()
                return
            if new_dec.action == PolicyAction.ALLOW:
                self._execute_gated_tool(pa.tool_call, via="user OVERRIDE→ALLOW")
                self._update_policy_stats()
                return
            # Still review after override attempt — do not execute
            tool_log.write_line(
                f"[yellow]Override did not yield ALLOW ({new_dec.action.value}); tool not run.[/yellow]"
            )
            self._update_policy_stats()
            return

        if approve:
            # User accepts the queued action despite REVIEW/CONFIRM
            alog.write_line(f"[green]APPROVED[/green] {pa.prompt_line[:40]}")
            self._execute_gated_tool(pa.tool_call, via="user APPROVE")
            try:
                clog = self.query_one("#chat_log", Markdown)
                clog.update(
                    (clog.renderable or "")
                    + f"\n\n[dim]→ Sentinel APPROVED: {pa.policy_decision.reason[:60]}[/dim]"
                )
            except Exception:
                pass
            return

        # block
        self._policy_blocks += 1
        alog.write_line(f"[red]BLOCKED by user[/red] {pa.prompt_line[:40]}")
        tool_log.write_line("[red]Tool not executed (user block).[/red]")
        try:
            clog = self.query_one("#chat_log", Markdown)
            clog.update(
                (clog.renderable or "")
                + f"\n\n[dim]→ Sentinel BLOCKED: {pa.policy_decision.reason[:60]}[/dim]"
            )
        except Exception:
            pass
        self._update_policy_stats()

    def action_approve_pending(self) -> None:
        self._handle_pending(approve=True)

    def action_block_pending(self) -> None:
        self._handle_pending(approve=False)

    def action_override_pending(self) -> None:
        self._handle_pending(approve=True, override=True)


def run_tui() -> None:
    NexTUI().run()
