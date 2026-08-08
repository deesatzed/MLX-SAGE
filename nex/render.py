"""Rich-based terminal rendering with support for reasoning / <think> tags."""

from __future__ import annotations

import re
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from .theme import get_color

console = Console()

THINK_START = re.compile(r"<think>", re.IGNORECASE)
THINK_END = re.compile(r"</think>", re.IGNORECASE)


class ThinkAwareStreamer:
    """
    Handles incremental printing while detecting <think> ... </think> regions.

    - Inside think blocks: dim italic
    - Outside: normal
    - On completion can optionally render a nice final panel.
    """

    def __init__(self, show_thinking: bool = True):
        self.show_thinking = show_thinking
        self.in_think = False
        self.buffer = ""
        self._live: Optional[Live] = None
        self._display_text = Text()

    def start(self, title: str = "Nex"):
        """Optional: start a Live display for the whole response (more advanced)."""
        self._display_text = Text()
        self._live = Live(self._display_text, console=console, refresh_per_sec=20)
        self._live.start()

    def stop(self):
        if self._live:
            self._live.stop()
            self._live = None

    def feed(self, chunk: str) -> None:
        """Feed a new token chunk and render appropriately."""
        if not chunk:
            return

        self.buffer += chunk

        # Process complete think regions in the buffer
        while True:
            if not self.in_think:
                # Look for explicit start of think
                m_start = THINK_START.search(self.buffer)
                m_end = THINK_END.search(self.buffer)

                if m_start and (not m_end or m_start.start() < m_end.start()):
                    # Normal case: <think> ... appears first
                    pre = self.buffer[: m_start.start()]
                    if pre:
                        self._emit(pre, style="default")
                    self.buffer = self.buffer[m_start.end() :]
                    self.in_think = True
                    if self.show_thinking:
                        self._emit("[thinking] ", style="dim italic")
                    continue

                if m_end:
                    # We saw </think> without a preceding <think> in this stream.
                    # Treat everything before it as reasoning/scratchpad.
                    pre_think = self.buffer[: m_end.start()]
                    if self.show_thinking and pre_think.strip():
                        self._emit(pre_think, style="dim italic")
                    self.buffer = self.buffer[m_end.end() :]
                    if self.show_thinking:
                        self._emit("\n", style="dim italic")
                    # Now the rest is normal final answer
                    if self.buffer:
                        self._emit(self.buffer, style="default")
                        self.buffer = ""
                    break

                # No think tags yet — treat as normal output
                self._emit(self.buffer, style="default")
                self.buffer = ""
                break
            else:
                # We are inside a think block — look for end
                m = THINK_END.search(self.buffer)
                if not m:
                    # Still thinking — emit what we have in dim
                    if self.show_thinking:
                        self._emit(self.buffer, style="dim italic")
                    self.buffer = ""
                    break
                # Emit the think content
                think_content = self.buffer[: m.start()]
                if self.show_thinking and think_content.strip():
                    self._emit(think_content, style="dim italic")
                self.buffer = self.buffer[m.end() :]
                self.in_think = False
                if self.show_thinking:
                    self._emit(" [/thinking]\n", style="dim italic")

    def _emit(self, text: str, style: str = "default"):
        if not text:
            return
        if self._live:
            if style == "dim italic":
                self._display_text.append(text, style="dim italic")
            else:
                self._display_text.append(text)
            self._live.update(self._display_text)
        else:
            # Fallback to direct console (works great for streaming)
            if style == "dim italic":
                console.print(text, end="", style="dim italic", highlight=False)
            else:
                console.print(text, end="", highlight=False)
            console.file.flush()

    def flush(self):
        """Flush any remaining buffer (in case tags were unbalanced)."""
        if self.buffer:
            style = "dim italic" if self.in_think and self.show_thinking else "default"
            self._emit(self.buffer, style=style)
            self.buffer = ""
        if self._live:
            self.stop()

    def final_panel(self, full_text: str, stats: Optional["GenerationStats"] = None):
        """After generation, optionally show a clean summary panel."""
        # We already streamed the content; this is for post-generation info
        if stats:
            info = (
                f"[dim]prompt: {stats.prompt_tokens} tok · "
                f"gen: {stats.generation_tokens} tok · "
                f"{stats.generation_tps:.1f} t/s · "
                f"peak mem: {stats.peak_memory_gb:.1f} GB[/dim]"
            )
            console.print(Panel(info, title="stats", border_style="dim"))


def print_welcome(model_name: str = "Nex / OptiQ model"):
    accent = get_color("primary")
    console.print(
        Panel.fit(
            f"[bold {accent}]MLX-SAGE · Rails chat[/bold {accent}] — [dim]{model_name}[/dim]\n"
            "Local multi-model substrate (mlx-lm). "
            "[bold]Partner mode:[/bold] [cyan]nex sage tui[/cyan] / [cyan]nex home[/cyan]\n"
            "Grok (XAI) is for supervise/agent escalation — not sage voice.\n\n"
            "Type [bold]/help[/bold] for commands. [bold]Ctrl-C[/bold] or [bold]/quit[/bold] to exit.\n"
            "Discover models: [bold]nex models list[/bold] · status: [bold]nex home[/bold]",
            border_style=accent,
        )
    )


def print_assistant_header():
    console.print("\n[bold cyan]Nex[/bold cyan]: ", end="")


def print_user_prompt():
    return console.input("[bold green]You[/bold green]: ")


def print_error(msg: str):
    console.print(f"[red]Error:[/red] {msg}")


def print_info(msg: str):
    console.print(f"[dim]{msg}[/dim]")
