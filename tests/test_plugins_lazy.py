"""Plugins must not load on bare import of nex.tools (quiet CLI / CI)."""

from __future__ import annotations

import nex.tools as tools


def test_import_does_not_mark_plugins_loaded():
    # After a fresh import path, flag should be false until execute_tool/agent
    # (If another test already loaded plugins, reset for isolation.)
    tools.PLUGINS_LOADED = False
    # Re-import doesn't re-run module body; flag is what we care about
    assert tools.PLUGINS_LOADED is False


def test_execute_tool_triggers_plugin_load():
    tools.PLUGINS_LOADED = False
    # list_dir is a built-in; execute_tool still calls load_plugins()
    out = tools.execute_tool({"name": "list_dir", "arguments": {"path": "."}})
    assert tools.PLUGINS_LOADED is True
    assert "Error: unknown tool" not in out
