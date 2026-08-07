"""Safe built-in tools for the agentic / tool-use loop + flexible tool call parser.

The parser supports several common formats small reasoning models emit:
- XML style: call tool tool_name with arg1 is value1 ...
- JSON in code fences or bare: {"name": "...", "arguments": {...}}
- ReAct style: Action: tool_name\nAction Input: json or text

Execution is restricted to a ./sandbox/ directory for file operations.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from rich.console import Console

console = Console()

# Sandbox root (relative to project)
SANDBOX = Path(__file__).resolve().parents[1] / "sandbox"
SANDBOX.mkdir(parents=True, exist_ok=True)

ToolFunc = Callable[[Dict[str, Any]], str]


# ---------------- Tool Implementations (safe) ----------------

def _resolve_sandbox_path(user_path: str) -> Path:
    """Resolve user-supplied path safely inside the sandbox. Prevents escaping."""
    p = (SANDBOX / user_path).resolve()
    if not str(p).startswith(str(SANDBOX.resolve())):
        raise ValueError("Path escapes sandbox")
    return p


def tool_list_dir(args: Dict[str, Any]) -> str:
    path = args.get("path", ".")
    target = _resolve_sandbox_path(path)
    if not target.exists():
        return f"Directory does not exist: {path}"
    if not target.is_dir():
        return f"Not a directory: {path}"
    entries = []
    for entry in sorted(target.iterdir()):
        if entry.is_dir():
            entries.append(f"[dir]  {entry.name}/")
        else:
            size = entry.stat().st_size
            entries.append(f"[file] {entry.name} ({size} bytes)")
    return "\n".join(entries) or "(empty directory)"


def tool_read_file(args: Dict[str, Any]) -> str:
    path = args.get("path", "")
    if not path:
        return "Error: path is required"
    target = _resolve_sandbox_path(path)
    if not target.exists():
        return f"File not found: {path}"
    if not target.is_file():
        return f"Not a file: {path}"
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        # Limit output size for the model
        if len(content) > 12000:
            content = content[:12000] + "\n... [truncated]"
        return content
    except Exception as e:
        return f"Error reading file: {e}"


def tool_write_file(args: Dict[str, Any]) -> str:
    path = args.get("path", "")
    content = args.get("content", "")
    if not path:
        return "Error: path is required"
    target = _resolve_sandbox_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def tool_run_python(args: Dict[str, Any]) -> str:
    """Execute Python code in a restricted way inside the sandbox (subprocess)."""
    code = args.get("code", "")
    if not code.strip():
        return "Error: code is required"

    # Write to a temp file inside sandbox
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", dir=SANDBOX, delete=False) as tf:
        tf.write(code)
        temp_path = Path(tf.name)

    try:
        # Run with timeout and capture
        result = subprocess.run(
            ["python3", str(temp_path)],
            cwd=SANDBOX,
            capture_output=True,
            text=True,
            timeout=25,
            env={"PYTHONPATH": str(SANDBOX), "PYTHONUNBUFFERED": "1"},
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        combined = ""
        if out:
            combined += f"STDOUT:\n{out}\n"
        if err:
            combined += f"STDERR:\n{err}\n"
        if result.returncode != 0:
            combined += f"\n[exit code: {result.returncode}]"
        return combined.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Python execution timed out after 25 seconds"
    except Exception as e:
        return f"Error during execution: {e}"
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


def tool_shell(args: Dict[str, Any]) -> str:
    """Very restricted shell for common safe commands inside sandbox."""
    cmd = (args.get("command") or "").strip()
    if not cmd:
        return "Error: command is required"

    # Whitelist of allowed base commands (very conservative)
    allowed = {"ls", "cat", "head", "tail", "wc", "pwd", "echo", "find", "grep", "file"}
    first = cmd.split()[0]
    if first not in allowed:
        return f"Error: command '{first}' not allowed in restricted shell. Allowed: {sorted(allowed)}"

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=SANDBOX,
            capture_output=True,
            text=True,
            timeout=15,
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        if result.returncode != 0:
            return f"[exit {result.returncode}]\nSTDOUT: {out}\nSTDERR: {err}".strip()
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: shell command timed out"
    except Exception as e:
        return f"Error: {e}"


# Registry
TOOLS: Dict[str, ToolFunc] = {
    "list_dir": tool_list_dir,
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "run_python": tool_run_python,
    "shell": tool_shell,
}


def get_tool_descriptions() -> str:
    """Return a compact description block suitable for system prompt."""
    return textwrap.dedent("""
    You have access to the following tools. Use them via function calls in the EXACT format below.

    Available tools:
    - list_dir(path): List files and directories inside the sandbox. Use "." for current.
    - read_file(path): Read a file inside the sandbox.
    - write_file(path, content): Create or overwrite a file inside the sandbox.
    - run_python(code): Run Python code (stdout/stderr captured, 25s timeout). Use for computation and testing.
    - shell(command): Restricted shell (only ls, cat, head, tail, wc, pwd, echo, grep, find, file allowed). Runs inside sandbox.

    === STRICT TOOL CALL FORMAT (copy this style exactly) ===
    call tool list_dir with path is .

    call tool read_file with path is example.py

    call tool write_file with path is notes.txt
    content is This is the file content.
    Multi-line is fine.

    call tool run_python with code is print(2 + 2)

    call tool shell with command is ls -la

    Rules:
    - Start with the literal text "call tool" (lowercase).
    - Then the tool name.
    - Then one or more lines of "argument_name is the value" (no quotes around the value unless the value itself needs them).
    - Do not invent argument names like "arg_name1" or include the word "value" as a placeholder.
    - When the task is finished, just give the final answer in plain text without a tool call.
    """).strip()


# ---------------- Flexible Tool Call Parser ----------------

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*<name>(.*?)</name>\s*(.*?)</tool_call>|<invoke\s+name=\"?(.*?)\"?>(.*?)</invoke>|call tool\s+([a-zA-Z0-9_]+)\s+with\s+(.*?)(?=\n<|call tool|$)",
    re.DOTALL | re.IGNORECASE,
)
JSON_TOOL_RE = re.compile(r"```json\s*(\{.*?\})\s*```|(\{\s*\"name\"\s*:.*?\})", re.DOTALL)
REACT_RE = re.compile(r"Action:\s*([a-zA-Z0-9_]+)\s*Action\s*Input:\s*(\{.*?\}|[^\n]+)", re.DOTALL | re.IGNORECASE)


def _parse_xml_style(text: str) -> Optional[Dict[str, Any]]:
    """Parse our recommended XML format and be tolerant of model mistakes."""
    # Primary "call tool name with ..." format (our recommended one)
    m = re.search(r"call tool\s+([a-zA-Z0-9_.-]+)\s+with\s+(.*)", text, re.DOTALL | re.IGNORECASE)
    if m:
        name = m.group(1).strip()
        args_block = m.group(2).strip()

        args: Dict[str, Any] = {}
        # Very tolerant parser for "key is value" lines
        for arg_m in re.finditer(r"(\w+)\s+is\s+(.*?)(?=\n\s*\w+\s+is\s+|\Z)", args_block, re.DOTALL):
            k = arg_m.group(1).strip().lower()
            v = arg_m.group(2).strip()
            # Clean common model mistakes ("value foo", extra quotes, etc.)
            v = re.sub(r'^value\s+["\']?', '', v, flags=re.IGNORECASE).strip()
            v = v.strip().strip('"').strip("'")
            # If the key the model used was literally "arg_name1", map common patterns
            if k in ("arg_name1", "arg1"):
                # Try to guess from context or previous key name in the block
                # Fallback: use a common first arg for the tool
                if name in ("list_dir", "read_file", "write_file"):
                    k = "path"
                elif name in ("run_python",):
                    k = "code"
                elif name in ("shell",):
                    k = "command"
            if k == "value" and name in ("shell", "run_python"):
                k = "command" if name == "shell" else "code"
            args[k] = v

        # Final sanity normalization
        if "path" not in args and "directory" in args:
            args["path"] = args.pop("directory")
        if name in TOOLS:
            return {"name": name, "arguments": args}

    # <tool_call><name>...</name> variant
    m2 = re.search(r"<tool_call>\s*<name>([^<]+)</name>(.*?)</tool_call>", text, re.DOTALL | re.IGNORECASE)
    if m2:
        name = m2.group(1).strip()
        inner = m2.group(2)
        args = {}
        for am in re.finditer(r"<(\w+)>(.*?)</\1>", inner, re.DOTALL):
            args[am.group(1)] = am.group(2).strip()
        if name in TOOLS:
            return {"name": name, "arguments": args}
    return None


def _parse_json_style(text: str) -> Optional[Dict[str, Any]]:
    for match in JSON_TOOL_RE.finditer(text):
        blob = match.group(1) or match.group(2)
        try:
            data = json.loads(blob)
            if isinstance(data, dict):
                if "name" in data and "arguments" in data:
                    return {"name": data["name"], "arguments": data["arguments"]}
                if "function" in data:  # OpenAI style sometimes
                    fn = data["function"]
                    return {"name": fn.get("name"), "arguments": json.loads(fn.get("arguments", "{}"))}
                if "tool" in data:
                    return {"name": data["tool"], "arguments": data.get("args", {})}
        except Exception:
            continue
    return None


def _parse_react_style(text: str) -> Optional[Dict[str, Any]]:
    m = REACT_RE.search(text)
    if m:
        name = m.group(1).strip()
        raw_input = m.group(2).strip()
        args: Dict[str, Any] = {}
        try:
            args = json.loads(raw_input)
        except Exception:
            args = {"input": raw_input}
        if name in TOOLS:
            return {"name": name, "arguments": args}
    return None


def parse_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """Try multiple formats. Returns {'name': str, 'arguments': dict} or None."""
    # Strip any think blocks first
    clean = THINK_RE.sub("", text)

    for parser in (_parse_xml_style, _parse_json_style, _parse_react_style):
        res = parser(clean)
        if res and res.get("name") in TOOLS:
            return res
    return None


def execute_tool(call: Dict[str, Any]) -> str:
    """Execute a parsed tool call safely and return observation string."""
    load_plugins()
    name = call.get("name")
    args = call.get("arguments", {}) or {}
    if name not in TOOLS:
        return f"Error: unknown tool '{name}'"
    try:
        func = TOOLS[name]
        observation = func(args)
        return str(observation)
    except Exception as e:
        return f"Tool execution error in {name}: {e}"


def format_observation(tool_name: str, observation: str) -> str:
    """Format the observation back to the model."""
    # Keep it clear and not too long
    obs = observation[:8000]
    return f"\nObservation from {tool_name}:\n{obs}\n"


def inject_tool_instructions(system_prompt: Optional[str]) -> str:
    base = system_prompt or "You are a helpful, autonomous coding and task execution agent."
    tools_desc = get_tool_descriptions()
    return f"{base}\n\n{tools_desc}\n\nAlways use the exact tool call format when you decide to use a tool."


# ---------------- Simple Plugin System ----------------

PLUGINS_LOADED = False
CUSTOM_TOOLS: Dict[str, ToolFunc] = {}


def load_plugins() -> None:
    """Load user plugins from ~/.nex/plugins/ or ./plugins/."""
    global PLUGINS_LOADED, CUSTOM_TOOLS
    if PLUGINS_LOADED:
        return

    import importlib.util
    from pathlib import Path

    plugin_dirs = [
        Path.home() / ".nex" / "plugins",
        Path("plugins"),
    ]

    for pdir in plugin_dirs:
        if not pdir.exists():
            continue
        for pyfile in pdir.glob("*.py"):
            try:
                spec = importlib.util.spec_from_file_location(pyfile.stem, pyfile)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if hasattr(mod, "register_tools"):
                        mod.register_tools(TOOLS)  # or a separate registry
                        print(f"[plugins] Loaded {pyfile}")
            except Exception as e:
                print(f"[plugins] Failed to load {pyfile}: {e}")

    PLUGINS_LOADED = True


# Plugins load on demand via execute_tool / agent run_agent — not at import
# (keeps `nex --help` and unit imports quiet; D-012 Stage 3 polish).
