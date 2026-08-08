"""WattOS — safety & efficiency end-of-session report.

Brand note: "WattOS" means efficiency proof. v1 metrics are counters,
propellant, wall time, and local tok/tps when measured — not hardware
watt meters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .propellant import PropellantLedger


@dataclass
class WattOSReport:
    mode: str
    agent: str
    wall_time_s: float
    policy_decisions: int
    blocks: int
    reviews: int
    grok_escalations: int
    propellant: "PropellantLedger"
    local_generation_tokens: Optional[int]
    avg_generation_tps: Optional[float]
    note: str
    grok_status: str
    local_stats_reason: Optional[str] = None

    def local_tokens_display(self) -> str:
        if self.local_generation_tokens is not None:
            return str(self.local_generation_tokens)
        reason = self.local_stats_reason or "child agent, not local MLX"
        return f"n/a ({reason})"

    def local_tps_display(self) -> str:
        if self.avg_generation_tps is not None:
            return f"{self.avg_generation_tps:.1f}"
        reason = self.local_stats_reason or "child agent, not local MLX"
        return f"n/a ({reason})"

    def propellant_display(self) -> str:
        p = self.propellant
        return f"{p.used}/{p.max_burns} (remaining {p.remaining}, denied {p.denied})"


def render_wattos_text(report: WattOSReport) -> str:
    """Plain-text WattOS panel for tests and non-Rich paths."""
    lines = [
        "WattOS — Safety & Efficiency [Rails]",
        "role: Rails (supervise / agent / Grok) — not Partner sage voice",
        f"mode: {report.mode}",
        f"agent: {report.agent}",
        f"wall time (s): {report.wall_time_s:.1f}",
        f"policy decisions: {report.policy_decisions}",
        f"blocks: {report.blocks}",
        f"reviews: {report.reviews}",
        f"grok escalations: {report.grok_escalations}",
        f"propellant: {report.propellant_display()}",
        f"local gen tokens: {report.local_tokens_display()}",
        f"avg t/s (local): {report.local_tps_display()}",
        f"grok status: {report.grok_status}",
        f"note: {report.note}",
        "footnote: v1 metrics are counters/propellant/wall; not hardware watt meters",
        "footnote: Grok is for hard agent decisions, not sage partnership chat",
    ]
    return "\n".join(lines)


def print_wattos_report(report: WattOSReport, console=None) -> None:
    """Print WattOS panel via Rich when available; else plain text."""
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
    except ImportError:
        print(render_wattos_text(report))
        return

    c = console or Console()
    table = Table(
        title=f"WattOS — Safety & Efficiency [Rails] ({report.mode})",
        show_header=False,
        box=None,
    )
    table.add_row("role", "Rails (supervise / agent / Grok) — not Partner sage")
    table.add_row("agent", str(report.agent))
    table.add_row("wall time (s)", f"{report.wall_time_s:.1f}")
    table.add_row("policy decisions", str(report.policy_decisions))
    table.add_row("blocks", str(report.blocks))
    table.add_row("reviews", str(report.reviews))
    table.add_row("grok escalations", str(report.grok_escalations))
    table.add_row("propellant", report.propellant_display())
    table.add_row("local gen tokens", report.local_tokens_display())
    table.add_row("avg t/s (local)", report.local_tps_display())
    table.add_row("grok status", report.grok_status)
    table.add_row("note", report.note)
    c.print(
        Panel(
            table,
            border_style="cyan",
            title="WattOS [Rails]: local-first proof + selective Grok + real policy",
        )
    )
    c.print(
        "[dim]v1 metrics: counters, propellant, wall time"
        " (and local tok/tps when MLX ran). Not hardware watt meters. "
        "Grok ≠ sage partner voice — use [cyan]nex sage tui[/cyan] for Partner mode.[/dim]\n"
    )
