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


TOOL_HANDLERS: dict[str, Callable] = {
    "run_command": execute_command,
    "read_file": read_file,
    "list_directory": list_directory,
}


async def execute_tool(name: str, arguments: dict) -> dict:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"success": False, "output": f"Unknown tool: {name}"}
    result = await asyncio.to_thread(handler, **arguments)
    return result
