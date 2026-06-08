import asyncio
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Callable

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a shell command on the server operating system. "
                "Use this to check system info, list files, run scripts, install packages, "
                "check disk space, check running processes, get network info, etc. "
                "The output (stdout+stderr) is returned. Commands timeout after 30 seconds."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute. Use full paths when possible.",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the contents of a file. Returns the file content as text. "
                "Limited to files under 50KB."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file to read.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories in a given path. Returns names and types.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the directory to list.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "opencode_run",
            "description": (
                "Use opencode (an AI coding assistant) to help write, edit, or analyze code. "
                "Give it a natural language description of the coding task. "
                "It can read files, write code, refactor, fix bugs, add features, etc. "
                "Specify the directory where the codebase lives. "
                "Use this for any code-related tasks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Natural language description of the coding task.",
                    },
                    "directory": {
                        "type": "string",
                        "description": "Absolute path to the codebase directory. Defaults to ~/. Use '.' for current directory.",
                    },
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "end_conversation",
            "description": (
                "End the current conversation session. Call this when the user explicitly "
                "asks to end the conversation, says goodbye, or wants to stop. "
                "After calling this, the conversation will be terminated."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_speaker_name",
            "description": (
                "Set the display name for the current speaker. Call this when a user "
                "introduces themselves by name (e.g. 'My name is Zhang San', '我叫李四'). "
                "Extract only the person's name, not titles or honorifics."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The person's name to display in the conversation UI.",
                    }
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_assistant_name",
            "description": (
                "Rename the voice assistant. Call this when the user explicitly asks "
                "to change the assistant's name (e.g. '从现在起你叫小明', 'Your name is now Alex'). "
                "After calling this, always acknowledge the name change in your response."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The new name for the assistant.",
                    }
                },
                "required": ["name"],
            },
        },
    },
]

DANGEROUS_COMMANDS = {
    "rm", "mkfs", "dd", "shutdown", "reboot", "halt", "poweroff",
    "chmod 777", "fdisk", "parted", "mkfs.", "wipefs",
    ":(){ :|:& };:", "> /dev/sda",
}

CMD_TIMEOUT = 30
MAX_FILE_SIZE = 50 * 1024
MAX_DIR_ENTRIES = 200


def execute_command(command: str) -> dict:
    command = command.strip()
    if not command:
        return {"success": False, "output": "Empty command."}

    cmd_lower = command.lower()
    for dangerous in DANGEROUS_COMMANDS:
        if dangerous in cmd_lower:
            return {
                "success": False,
                "output": f"Blocked: command contains dangerous pattern '{dangerous}'. This operation is not allowed.",
            }

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=CMD_TIMEOUT, cwd=os.path.expanduser("~"),
            env={**os.environ, "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin")},
        )
        output = result.stdout
        if result.stderr:
            output += "\n[stderr]\n" + result.stderr
        output = output.strip() or "(no output)"
        if len(output) > 4000:
            output = output[:4000] + "\n... (truncated)"
        return {"success": result.returncode == 0, "output": output}
    except subprocess.TimeoutExpired:
        return {"success": False, "output": f"Command timed out after {CMD_TIMEOUT}s."}
    except Exception as e:
        return {"success": False, "output": str(e)}


def read_file(path: str) -> dict:
    try:
        real = os.path.realpath(path)
        stat = os.stat(real)
        if stat.st_size > MAX_FILE_SIZE:
            return {"success": False, "output": f"File too large ({stat.st_size} bytes, max {MAX_FILE_SIZE})."}
        with open(real, "r", errors="replace") as f:
            content = f.read(MAX_FILE_SIZE + 1)
        return {"success": True, "output": content, "size": stat.st_size}
    except FileNotFoundError:
        return {"success": False, "output": f"File not found: {path}"}
    except PermissionError:
        return {"success": False, "output": f"Permission denied: {path}"}
    except Exception as e:
        return {"success": False, "output": str(e)}


def list_directory(path: str) -> dict:
    try:
        entries = []
        with os.scandir(path) as it:
            for entry in it:
                if len(entries) >= MAX_DIR_ENTRIES:
                    entries.append("... (truncated)")
                    break
                kind = "[DIR]" if entry.is_dir() else "[FILE]"
                try:
                    size = os.path.getsize(entry.path) if entry.is_file() else 0
                except OSError:
                    size = 0
                entries.append(f"{kind} {entry.name} ({_fmt_size(size)})")
        return {"success": True, "output": "\n".join(entries) or "(empty directory)"}
    except FileNotFoundError:
        return {"success": False, "output": f"Directory not found: {path}"}
    except PermissionError:
        return {"success": False, "output": f"Permission denied: {path}"}
    except Exception as e:
        return {"success": False, "output": str(e)}


def _fmt_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f}{unit}"
        size /= 1024
    return f"{size:.0f}TB"


OPECNCODE_PATH = "/home/suren/.opencode/bin/opencode"
OPENCODE_TIMEOUT = 120


def execute_opencode(message: str, directory: str = None) -> dict:
    if not directory:
        directory = os.path.expanduser("~")
    elif directory == ".":
        directory = os.getcwd()
    directory = os.path.expanduser(directory)

    if not os.path.exists(directory):
        return {"success": False, "output": f"Directory not found: {directory}"}

    binary = OPECNCODE_PATH
    if not os.path.exists(binary):
        binary = "opencode"

    try:
        result = subprocess.run(
            [binary, "run", message, "--dir", directory,
             "--dangerously-skip-permissions", "--format", "json"],
            capture_output=True, text=True, timeout=OPENCODE_TIMEOUT,
            env={**os.environ},
        )
        output = result.stdout.strip()
        if result.stderr:
            output += "\n" + result.stderr.strip()
        if not output:
            output = "(no output)"
        if len(output) > 6000:
            output = output[:6000] + "\n... (truncated)"
        return {"success": result.returncode == 0, "output": output}
    except subprocess.TimeoutExpired:
        return {"success": False, "output": f"Opencode task timed out after {OPENCODE_TIMEOUT}s."}
    except FileNotFoundError:
        return {"success": False, "output": "Opencode binary not found. Is it installed at ~/.opencode/bin/opencode?"}
    except Exception as e:
        return {"success": False, "output": str(e)}


def terminate_conversation() -> dict:
    return {"success": True, "output": "Conversation ended.", "end_conversation": True}


def set_speaker_name(name: str) -> dict:
    return {"success": True, "output": f"Speaker name set to: {name}", "speaker_rename": name.strip()}


def rename_assistant(name: str) -> dict:
    return {"success": True, "output": f"Assistant renamed to: {name}", "assistant_rename": name.strip()}


TOOL_HANDLERS: dict[str, Callable] = {
    "run_command": execute_command,
    "read_file": read_file,
    "list_directory": list_directory,
    "opencode_run": execute_opencode,
    "end_conversation": terminate_conversation,
    "set_speaker_name": set_speaker_name,
    "set_assistant_name": rename_assistant,
}


async def execute_tool(name: str, arguments: dict) -> dict:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"success": False, "output": f"Unknown tool: {name}"}
    result = await asyncio.to_thread(handler, **arguments)
    return result
